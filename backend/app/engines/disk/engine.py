"""Disk scheduling: FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK (seek-based HDD model).
Conventions: cylinders are 0..max_cylinder. SCAN/C-SCAN always travel to the disk boundary in the initial direction;
they continue past it only if requests remain on the other side. A C-SCAN/C-LOOK return jump counts as head movement
unless count_jump is False."""
from __future__ import annotations

from app.engines.compare_util import summarize
from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

ALGORITHMS = ["fcfs", "sstf", "scan", "cscan", "look", "clook"]
LABELS = {"fcfs": "FCFS", "sstf": "SSTF", "scan": "SCAN", "cscan": "C-SCAN", "look": "LOOK", "clook": "C-LOOK"}
MAX_CYL, MAX_REQ = 100_000, 500


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate(requests, head, max_cyl, direction, algorithm):
    if algorithm not in ALGORITHMS:
        raise ValidationError(f"Unknown algorithm '{algorithm}'. Supported: {', '.join(ALGORITHMS)}")
    if not _int(max_cyl) or not 1 <= max_cyl <= MAX_CYL:
        raise ValidationError(f"max_cylinder must be a whole number between 1 and {MAX_CYL}")
    if not _int(head) or not 0 <= head <= max_cyl:
        raise ValidationError(f"Head position must be between 0 and {max_cyl}")
    if direction not in ("up", "down"):
        raise ValidationError("direction must be 'up' or 'down'")
    if not isinstance(requests, list) or not 1 <= len(requests) <= MAX_REQ:
        raise ValidationError(f"Provide 1..{MAX_REQ} requests")
    if any(not _int(r) or not 0 <= r <= max_cyl for r in requests):
        raise ValidationError(f"Every request must be a whole number between 0 and {max_cyl}")


def _path(requests, head, max_cyl, direction, algo):
    """Return [(cylinder, kind, note)] with kind in service | boundary | jump."""
    S = lambda c, n: (c, "service", n)
    if algo == "fcfs":
        return [S(r, "next in arrival order") for r in requests]
    if algo == "sstf":
        pending, pos, out = list(requests), head, []
        while pending:
            best = min(range(len(pending)), key=lambda i: (abs(pending[i] - pos), i))
            c = pending.pop(best)
            out.append(S(c, f"closest pending request ({abs(c - pos)} cylinders away)"))
            pos = c
        return out
    up = direction == "up"
    first = sorted([r for r in requests if (r >= head if up else r <= head)], reverse=not up)
    second = sorted([r for r in requests if (r < head if up else r > head)], reverse=up)
    sweep = "up" if up else "down"
    out = [S(c, f"next request while sweeping {sweep}") for c in first]
    boundary, other_end = (max_cyl, 0) if up else (0, max_cyl)
    if algo in ("scan", "cscan"):
        out.append((boundary, "boundary", f"{LABELS[algo]} travels to the disk end at cylinder {boundary}"))
    if algo == "scan":
        out += [S(c, f"next request while sweeping back {'down' if up else 'up'}") for c in second]
    elif algo == "cscan":
        if second:
            out.append((other_end, "jump", f"return jump to cylinder {other_end}"))
            out += [S(c, f"next request in the second sweep {sweep}") for c in sorted(second, reverse=not up)]
    elif algo == "look":
        out += [S(c, f"next request while sweeping back {'down' if up else 'up'}") for c in second]
    elif algo == "clook":
        if second:
            rest = sorted(second, reverse=not up)
            out.append((rest[0], "jump", f"jump to the farthest pending request, cylinder {rest[0]}"))
            out += [S(c, f"next request in the second sweep {sweep}") for c in rest]
    return out


def simulate(requests, head, max_cylinder, direction, algorithm, count_jump=True) -> SimulationTrace:
    _validate(requests, head, max_cylinder, direction, algorithm)
    path = _path(requests, head, max_cylinder, direction, algorithm)
    trace = SimulationTrace("disk_scheduling", algorithm, {"requests": requests, "head": head, "max_cylinder": max_cylinder,
                                                            "direction": direction, "count_jump": count_jump})
    pos, total, serviced = head, 0, []
    positions = [head]
    trace.add(0, "start", "Start", f"Head starts at cylinder {head}", {"head": head, "serviced": [], "total": 0})
    for i, (cyl, kind, note) in enumerate(path, start=1):
        dist = abs(cyl - pos)
        counted = 0 if (kind == "jump" and not count_jump) else dist
        total += counted
        if kind == "service":
            serviced.append(cyl)
        explanation = f"{note}; head moves {pos} → {cyl}" + (" (jump not counted)" if counted == 0 and dist else f" ({counted} cylinders)")
        trace.add(i, kind, f"Move to {cyl}", explanation,
                  {"head": cyl, "from": pos, "distance": counted, "serviced": list(serviced), "total": total})
        pos = cyl
        positions.append(cyl)
    n = len(requests)
    trace.result = {
        "algorithm_label": LABELS[algorithm], "head_path": positions, "service_order": serviced,
        "metrics": {"total_head_movement": total, "avg_seek_distance": round(total / n, 4), "requests": n},
    }
    return trace


def compare(requests, head, max_cylinder, direction, algorithms, count_jump=True):
    if len(algorithms) < 2 or len(set(algorithms)) != len(algorithms):
        raise ValidationError("Select at least two different algorithms to compare")
    runs = []
    for a in algorithms:
        tr = simulate(requests, head, max_cylinder, direction, a, count_jump)
        runs.append({"label": LABELS[a], "algorithm": a, "metrics": tr.result["metrics"], "head_path": tr.result["head_path"]})
    best, notes = summarize(runs, {"total_head_movement": ("total head movement", True), "avg_seek_distance": ("average seek distance", True)})
    return {"runs": runs, "best_by_metric": best, "explanation": notes}
