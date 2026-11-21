"""Contiguous memory allocation: First/Best/Worst Fit, fixed or variable partitions, free, compaction.
Initial partitions are separate; freeing coalesces adjacent free space (variable mode only).
External fragmentation % = (1 - largest hole / total free) * 100."""
from __future__ import annotations

from app.engines.compare_util import summarize
from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

STRATEGIES = ["first_fit", "best_fit", "worst_fit"]
LABELS = {"first_fit": "First Fit", "best_fit": "Best Fit", "worst_fit": "Worst Fit"}
MODES = ["fixed", "variable"]
MAX_BLOCKS, MAX_OPS, MAX_SIZE = 50, 200, 1_000_000


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate(blocks, ops, strategy, mode):
    if strategy not in STRATEGIES:
        raise ValidationError(f"Unknown strategy '{strategy}'. Supported: {', '.join(STRATEGIES)}")
    if mode not in MODES:
        raise ValidationError("mode must be 'fixed' or 'variable'")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= MAX_BLOCKS:
        raise ValidationError(f"Provide 1..{MAX_BLOCKS} memory blocks")
    if any(not _int(b) or not 1 <= b <= MAX_SIZE for b in blocks):
        raise ValidationError(f"Block sizes must be whole numbers between 1 and {MAX_SIZE}")
    if not isinstance(ops, list) or len(ops) > MAX_OPS:
        raise ValidationError(f"At most {MAX_OPS} operations are allowed")
    for o in ops:
        kind = o.get("op")
        if kind == "alloc":
            if not isinstance(o.get("pid"), str) or not o["pid"].strip():
                raise ValidationError("alloc needs a non-empty pid")
            if not _int(o.get("size")) or not 1 <= o["size"] <= MAX_SIZE:
                raise ValidationError(f"{o.get('pid')}: size must be a whole number between 1 and {MAX_SIZE}")
        elif kind == "free":
            if not isinstance(o.get("pid"), str) or not o["pid"].strip():
                raise ValidationError("free needs a non-empty pid")
        elif kind == "compact":
            if mode != "variable":
                raise ValidationError("Compaction is only available with variable partitions")
        else:
            raise ValidationError(f"Unknown operation '{kind}' (use alloc, free or compact)")


def _stats(segs):
    total = sum(s["size"] for s in segs)
    holes = [s["size"] for s in segs if s["pid"] is None]
    used = sum(s["used"] for s in segs if s["pid"] is not None)
    allocated = sum(s["size"] for s in segs if s["pid"] is not None)
    free = sum(holes)
    largest = max(holes, default=0)
    return {
        "total_memory": total, "allocated_memory": allocated, "used_memory": used, "free_memory": free,
        "largest_hole": largest, "hole_count": len(holes),
        "internal_fragmentation": allocated - used,
        "external_fragmentation_pct": round((1 - largest / free) * 100, 2) if free else 0.0,
        "utilization_pct": round(100 * used / total, 2),
    }


def _snap(segs):
    return [dict(s) for s in segs]


def simulate(blocks, ops, strategy, mode="variable") -> SimulationTrace:
    _validate(blocks, ops, strategy, mode)
    segs, addr = [], 0
    for b in blocks:
        segs.append({"start": addr, "size": b, "pid": None, "used": 0})
        addr += b
    trace = SimulationTrace("memory_management", strategy, {"blocks": blocks, "ops": ops, "mode": mode})
    trace.add(0, "init", "Initial memory", f"{len(blocks)} free partitions, {addr} KB in total", {"segments": _snap(segs), **_stats(segs)})
    failed = external_failures = 0

    for i, op in enumerate(ops, start=1):
        kind = op["op"]
        if kind == "alloc":
            pid, size = op["pid"], op["size"]
            if any(s["pid"] == pid for s in segs):
                trace.add(i, "error", f"Allocate {pid}", f"{pid} already holds memory", {"segments": _snap(segs), **_stats(segs)})
                continue
            holes = [s for s in segs if s["pid"] is None]
            fits = [h for h in holes if h["size"] >= size]
            if strategy == "first_fit":
                examined = []
                chosen = None
                for h in holes:
                    ok = h["size"] >= size
                    examined.append({"start": h["start"], "size": h["size"], "fits": ok})
                    if ok:
                        chosen = h
                        break
                why = f"First Fit takes the first hole that is large enough"
            else:
                examined = [{"start": h["start"], "size": h["size"], "fits": h["size"] >= size} for h in holes]
                chosen = (min(fits, key=lambda h: (h["size"], h["start"])) if strategy == "best_fit"
                          else max(fits, key=lambda h: (h["size"], -h["start"]))) if fits else None
                why = ("Best Fit takes the smallest hole that is large enough" if strategy == "best_fit"
                       else "Worst Fit takes the largest hole")
            if chosen is None:
                failed += 1
                st = _stats(segs)
                if st["free_memory"] >= size:
                    external_failures += 1
                    msg = (f"{pid} ({size} KB) cannot be placed: {st['free_memory']} KB is free in total, but the largest "
                           f"hole is only {st['largest_hole']} KB (external fragmentation)")
                else:
                    msg = f"{pid} ({size} KB) cannot be placed: only {st['free_memory']} KB is free in total"
                trace.add(i, "alloc_failed", f"Allocate {pid}", msg, {"segments": _snap(segs), "examined": examined, **st})
                continue
            idx = segs.index(chosen)
            if mode == "variable" and chosen["size"] > size:
                rest = {"start": chosen["start"] + size, "size": chosen["size"] - size, "pid": None, "used": 0}
                segs[idx] = {"start": chosen["start"], "size": size, "pid": pid, "used": size}
                segs.insert(idx + 1, rest)
                tail = f"; {rest['size']} KB remains free at address {rest['start']}"
            else:
                chosen["pid"], chosen["used"] = pid, size
                tail = f"; {chosen['size'] - size} KB wasted inside the partition (internal fragmentation)" if chosen["size"] > size else ""
            trace.add(i, "alloc", f"Allocate {pid}", f"{why}: {pid} ({size} KB) placed at address {chosen['start']}{tail}",
                      {"segments": _snap(segs), "examined": examined, "chosen_start": chosen["start"], **_stats(segs)})
        elif kind == "free":
            pid = op["pid"]
            seg = next((s for s in segs if s["pid"] == pid), None)
            if seg is None:
                trace.add(i, "error", f"Free {pid}", f"{pid} holds no memory", {"segments": _snap(segs), **_stats(segs)})
                continue
            seg["pid"], seg["used"] = None, 0
            if mode == "variable":
                merged = []
                for s in segs:
                    if merged and merged[-1]["pid"] is None and s["pid"] is None:
                        merged[-1]["size"] += s["size"]
                    else:
                        merged.append(s)
                segs = merged
            trace.add(i, "free", f"Free {pid}", f"{pid} released its memory" + ("; adjacent free space is merged" if mode == "variable" else ""),
                      {"segments": _snap(segs), **_stats(segs)})
        else:  # compact
            moved, cursor, new = [], 0, []
            for s in segs:
                if s["pid"] is not None:
                    if s["start"] != cursor:
                        moved.append({"pid": s["pid"], "from": s["start"], "to": cursor})
                    new.append({**s, "start": cursor})
                    cursor += s["size"]
            total = sum(s["size"] for s in segs)
            if cursor < total:
                new.append({"start": cursor, "size": total - cursor, "pid": None, "used": 0})
            segs = new
            trace.add(i, "compact", "Compaction", f"{len(moved)} process(es) relocated; all free space merged into one hole of {total - cursor} KB",
                      {"segments": _snap(segs), "moved": moved, **_stats(segs)})

    final = _stats(segs)
    trace.result = {"algorithm_label": LABELS[strategy], "segments": _snap(segs),
                    "metrics": {**final, "failed_allocations": failed, "external_failures": external_failures}}
    return trace


def compare(blocks, ops, mode, strategies=None):
    strategies = strategies or STRATEGIES
    if len(strategies) < 2 or len(set(strategies)) != len(strategies):
        raise ValidationError("Select at least two different strategies to compare")
    runs = []
    for s in strategies:
        tr = simulate(blocks, ops, s, mode)
        runs.append({"label": LABELS[s], "algorithm": s, "metrics": tr.result["metrics"], "segments": tr.result["segments"]})
    spec = {"failed_allocations": ("failed allocations", True), "utilization_pct": ("memory utilization %", False),
            "internal_fragmentation": ("internal fragmentation", True), "largest_hole": ("largest remaining hole", False)}
    best, notes = summarize(runs, spec)
    return {"runs": runs, "best_by_metric": best, "explanation": notes}
