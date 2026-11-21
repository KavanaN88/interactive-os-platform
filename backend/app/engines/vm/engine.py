"""Virtual memory: address translation, TLB, demand paging with page replacement, working set and a thrashing model."""
from __future__ import annotations

from collections import OrderedDict

from app.engines.compare_util import summarize
from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

POLICIES = ["fifo", "lru"]
DEFAULT_COSTS = {"tlb_ns": 10, "mem_ns": 100, "fault_ns": 8_000_000}


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate(ps, vs, pm, addrs, tlb_size, tlb_policy, repl):
    if not _int(ps) or not 1 <= ps <= 65536:
        raise ValidationError("Page size must be 1..65536 bytes")
    if not _int(vs) or not ps <= vs <= 2 ** 26 or -(-vs // ps) > 4096:
        raise ValidationError("Virtual memory must be at least one page and at most 4096 pages")
    if not _int(pm) or pm < ps or pm // ps > 256:
        raise ValidationError("Physical memory must hold between 1 and 256 frames")
    if not _int(tlb_size) or not 0 <= tlb_size <= 16:
        raise ValidationError("TLB size must be 0..16 entries")
    if tlb_policy not in POLICIES or repl not in POLICIES:
        raise ValidationError("TLB and page replacement policies must be 'fifo' or 'lru'")
    if not isinstance(addrs, list) or not 1 <= len(addrs) <= 200 or any(not _int(a) for a in addrs):
        raise ValidationError("Provide 1..200 whole-number virtual addresses")


def translate(page_size, virtual_size, physical_size, addresses, tlb_size=4, tlb_policy="lru", replacement="lru", costs=None) -> SimulationTrace:
    _validate(page_size, virtual_size, physical_size, addresses, tlb_size, tlb_policy, replacement)
    c = {**DEFAULT_COSTS, **(costs or {})}
    ps, F = page_size, physical_size // page_size
    pages = -(-virtual_size // ps)
    frames: list[int | None] = [None] * F
    pt: dict[int, dict] = {}
    tlb: list[list[int]] = []
    trace = SimulationTrace("virtual_memory", replacement, {"page_size": ps, "virtual_size": virtual_size, "physical_size": physical_size,
                                                          "addresses": addresses, "tlb_size": tlb_size, "tlb_policy": tlb_policy, "replacement": replacement,
                                                          "pages": pages, "frames": F})
    hits = misses = faults = invalid = 0
    cost = 0
    snap = lambda extra: {"page_table": {str(k): dict(v) for k, v in sorted(pt.items())}, "tlb": [list(e) for e in tlb], "frames": list(frames), **extra}
    trace.add(0, "init", "Start", f"{pages} virtual pages, {F} physical frames of {ps} bytes. Nothing is in memory yet (demand paging).", snap({}))
    for t, a in enumerate(addresses, start=1):
        if a < 0 or a >= virtual_size:
            invalid += 1
            trace.add(t, "invalid", f"Access {a}", f"Address {a} is outside the virtual address space 0..{virtual_size - 1}: the MMU raises a fault and the OS would terminate the process (segmentation fault).",
                      snap({"address": a, "actions": ["Address out of range"]}))
            continue
        page, off = divmod(a, ps)
        acts = [f"Split {a}: page = {a} // {ps} = {page}, offset = {a} % {ps} = {off}"]
        entry = next((e for e in tlb if e[0] == page), None) if tlb_size else None
        if entry:
            event, frame = "tlb_hit", entry[1]
            hits += 1
            acts.append(f"TLB lookup: HIT, page {page} → frame {frame} (no page-table access needed)")
            if tlb_policy == "lru":
                tlb.remove(entry)
                tlb.append(entry)
            cost += c["tlb_ns"] + c["mem_ns"]
        else:
            misses += 1
            acts.append("TLB lookup: MISS" if tlb_size else "No TLB: consult the page table")
            cost += (c["tlb_ns"] if tlb_size else 0) + c["mem_ns"]
            ent = pt.get(page)
            if ent and ent["valid"]:
                event, frame = "tlb_miss", ent["frame"]
                acts.append(f"Page table: page {page} is valid → frame {frame}")
                cost += c["mem_ns"]
            else:
                event = "page_fault"
                faults += 1
                acts.append(f"Page table: page {page} is not valid (valid bit = 0) → PAGE FAULT, trap to the OS")
                if None in frames:
                    frame = frames.index(None)
                    acts.append(f"OS finds free frame {frame}")
                else:
                    resident = [p for p, e in pt.items() if e["valid"]]
                    victim = min(resident, key=lambda p: pt[p]["loaded_at"] if replacement == "fifo" else pt[p]["last_used"])
                    frame = pt[victim]["frame"]
                    pt[victim].update(valid=False, frame=None)
                    gone = [e for e in tlb if e[0] == victim]
                    for e in gone:
                        tlb.remove(e)
                    acts.append(f"No free frame: {replacement.upper()} evicts page {victim} from frame {frame}" + (" and its stale TLB entry is invalidated" if gone else ""))
                acts.append(f"OS reads page {page} from disk into frame {frame}, sets valid bit = 1 and restarts the instruction")
                frames[frame] = page
                pt[page] = {"frame": frame, "valid": True, "loaded_at": t, "last_used": t}
                cost += c["fault_ns"] + c["mem_ns"]
            if tlb_size:
                if len(tlb) >= tlb_size:
                    gone = tlb.pop(0)
                    acts.append(f"TLB full: entry for page {gone[0]} is replaced ({tlb_policy.upper()})")
                tlb.append([page, frame])
                acts.append(f"TLB updated with page {page} → frame {frame}")
        pt.setdefault(page, {"frame": frame, "valid": True, "loaded_at": t, "last_used": t})["last_used"] = t
        phys = frame * ps + off
        acts.append(f"Physical address = {frame} × {ps} + {off} = {phys}")
        trace.add(t, event, f"Access {a}", f"{a} → page {page}, offset {off}: {event.replace('_', ' ')} → frame {frame} → physical {phys}",
                  snap({"address": a, "page": page, "offset": off, "frame": frame, "physical": phys, "actions": acts}))
    valid_n = len(addresses) - invalid
    trace.result = {"algorithm_label": replacement.upper(), "metrics": {
        "accesses": len(addresses), "invalid_accesses": invalid, "tlb_hits": hits, "tlb_misses": misses,
        "tlb_hit_ratio": round(100 * hits / valid_n, 2) if valid_n else 0.0, "page_faults": faults,
        "fault_rate": round(100 * faults / valid_n, 2) if valid_n else 0.0,
        "effective_access_time_ns": round(cost / valid_n, 2) if valid_n else 0.0}, "costs": c}
    return trace


def compare(page_size, virtual_size, physical_size, addresses, tlb_size=4, tlb_policy="lru", policies=None, costs=None):
    policies = policies or POLICIES
    if len(policies) < 2 or len(set(policies)) != len(policies):
        raise ValidationError("Select at least two different policies to compare")
    runs = []
    for p in policies:
        tr = translate(page_size, virtual_size, physical_size, addresses, tlb_size, tlb_policy, p, costs)
        runs.append({"label": p.upper(), "algorithm": p, "metrics": tr.result["metrics"]})
    best, notes = summarize(runs, {"page_faults": ("page faults", True), "tlb_hit_ratio": ("TLB hit ratio %", False),
                                   "effective_access_time_ns": ("effective access time (ns)", True)})
    return {"runs": runs, "best_by_metric": best, "explanation": notes}


def working_set(refs, delta):
    if not isinstance(refs, list) or not 1 <= len(refs) <= 500 or any(not _int(p) or not 0 <= p <= 9999 for p in refs):
        raise ValidationError("Reference string must contain 1..500 pages (0-9999)")
    if not _int(delta) or not 1 <= delta <= 100:
        raise ValidationError("Window size (delta) must be 1..100")
    rows = []
    for t in range(len(refs)):
        ws = sorted(set(refs[max(0, t - delta + 1): t + 1]))
        rows.append({"t": t + 1, "page": refs[t], "working_set": ws, "size": len(ws)})
    sizes = [r["size"] for r in rows]
    return {"delta": delta, "rows": rows, "peak": max(sizes), "average": round(sum(sizes) / len(sizes), 2),
            "explanation": f"With a window of the last {delta} references the process needed at most {max(sizes)} frames at once "
                           f"(average {round(sum(sizes) / len(sizes), 2)}). Give it fewer than {max(sizes)} frames and it will fault heavily at its peak."}


def _lcg_refs(w, n, seed=12345):
    x, out = seed, []
    for _ in range(n):
        x = (1103515245 * x + 12345) % 2 ** 31
        out.append((x >> 8) % w)          # references stay inside the working set
    return out


def _lru_faults(refs, f):
    if f <= 0:
        return len(refs)
    cache, faults = OrderedDict(), 0
    for p in refs:
        if p in cache:
            cache.move_to_end(p)
        else:
            faults += 1
            if len(cache) >= f:
                cache.popitem(last=False)
            cache[p] = True
    return faults


def thrashing(total_frames, working_set_size, refs_per_process=400, max_processes=12, fault_cost=50):
    """Simplified bottleneck model. n identical processes each get total_frames // n frames and reference a working set of
    w pages (LRU). A fault costs `fault_cost` memory-access times on a single paging disk. CPU utilisation is limited by
    (a) the CPU itself (1), (b) how many processes can overlap their waits (n * c, c = CPU share of one process) and
    (c) the paging disk, which serves one fault at a time (refs / (faults * fault_cost))."""
    for name, v, lo, hi in [("Total frames", total_frames, 1, 256), ("Working set size", working_set_size, 1, 32),
                            ("References per process", refs_per_process, 50, 2000), ("Max processes", max_processes, 1, 32), ("Fault cost", fault_cost, 1, 10000)]:
        if not _int(v) or not lo <= v <= hi:
            raise ValidationError(f"{name} must be a whole number between {lo} and {hi}")
    refs = _lcg_refs(working_set_size, refs_per_process)
    rows, cache = [], {}
    for n in range(1, max_processes + 1):
        f = total_frames // n
        if f not in cache:
            cache[f] = _lru_faults(refs, f)
        faults = cache[f]
        c = refs_per_process / (refs_per_process + faults * fault_cost)
        disk_cap = refs_per_process / (faults * fault_cost) if faults else float("inf")
        rows.append({"processes": n, "frames_per_process": f, "faults_per_process": faults, "fault_rate": round(100 * faults / refs_per_process, 2),
                     "cpu_utilization": round(100 * min(1.0, n * c, disk_cap), 2)})
    top = max(r["cpu_utilization"] for r in rows)
    at_peak = [r["processes"] for r in rows if r["cpu_utilization"] == top]
    peak = rows[at_peak[0] - 1]
    start = next((r["processes"] for r in rows if r["frames_per_process"] < working_set_size), None)
    if start and start <= max_processes:
        rng = f"{at_peak[0]}" if at_peak[0] == at_peak[-1] else f"{at_peak[0]}-{at_peak[-1]}"
        msg = (f"CPU utilisation peaks at {top}% with {rng} process(es). From {start} processes each one gets only "
               f"{total_frames // start} frame(s), fewer than its working set ({working_set_size}), so faults explode ({rows[start - 1]['fault_rate']}% of references) "
               f"and utilisation falls to {rows[-1]['cpu_utilization']}% at {max_processes}: that collapse is thrashing. Adding processes made things worse.")
    else:
        msg = f"Every process always had at least its working set of {working_set_size} frames, so there is no thrashing in this range (peak {peak['cpu_utilization']}%)."
    return {"rows": rows, "peak_processes": peak["processes"], "thrashing_starts_at": start if start and start <= max_processes else None, "explanation": msg}
