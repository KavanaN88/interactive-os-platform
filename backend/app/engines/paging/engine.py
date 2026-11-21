"""Page replacement: FIFO, LRU, Optimal, LFU, Clock (second chance).
Conventions: frames are fixed slots (a replaced page takes the victim's slot); LFU counts references while the page
is resident (reset on eviction) and breaks ties by oldest load; Optimal breaks ties (never used again) by oldest load;
Clock sets the reference bit to 1 when a page is loaded or hit, and the hand moves past the slot it just filled."""
from __future__ import annotations

from app.engines.compare_util import summarize
from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

ALGORITHMS = ["fifo", "lru", "optimal", "lfu", "clock"]
LABELS = {"fifo": "FIFO", "lru": "LRU", "optimal": "Optimal", "lfu": "LFU", "clock": "Clock (Second Chance)"}
MAX_REFS, MAX_FRAMES = 500, 16


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate(refs, frames, algorithm):
    if algorithm not in ALGORITHMS:
        raise ValidationError(f"Unknown algorithm '{algorithm}'. Supported: {', '.join(ALGORITHMS)}")
    if not isinstance(refs, list) or not 1 <= len(refs) <= MAX_REFS:
        raise ValidationError(f"Reference string must contain 1..{MAX_REFS} pages")
    if any(not _int(p) or p < 0 or p > 9999 for p in refs):
        raise ValidationError("Pages must be whole numbers between 0 and 9999")
    if not _int(frames) or not 1 <= frames <= MAX_FRAMES:
        raise ValidationError(f"Frames must be a whole number between 1 and {MAX_FRAMES}")


def simulate(refs: list[int], frames: int, algorithm: str) -> SimulationTrace:
    _validate(refs, frames, algorithm)
    mem: list[int | None] = [None] * frames
    loaded: dict[int, int] = {}
    last: dict[int, int] = {}
    freq: dict[int, int] = {}
    bits = [0] * frames
    ptr = 0
    hits = faults = 0
    timeline: list[str] = []
    trace = SimulationTrace("page_replacement", algorithm, {"refs": refs, "frames": frames})

    def next_use(p, t):
        for k in range(t + 1, len(refs)):
            if refs[k] == p:
                return k
        return len(refs) + 1  # never used again

    for t, page in enumerate(refs):
        victim = None
        if page in mem:
            hits += 1
            slot = mem.index(page)
            last[page], bits[slot] = t, 1
            freq[page] += 1
            event, why = "hit", f"Page {page} is already in frame {slot}: page hit"
            timeline.append("H")
        else:
            faults += 1
            timeline.append("F")
            if None in mem:
                slot = mem.index(None)
                event, why = "fault", f"Page {page} is not in memory (page fault); free frame {slot} is used"
                if algorithm == "clock":
                    ptr = (slot + 1) % frames
            else:
                event = "replace"
                if algorithm == "fifo":
                    victim = min(mem, key=lambda p: loaded[p])
                    why_v = f"it entered memory earliest (at step {loaded[victim] + 1})"
                elif algorithm == "lru":
                    victim = min(mem, key=lambda p: last[p])
                    why_v = f"it was used least recently (last used at step {last[victim] + 1})"
                elif algorithm == "lfu":
                    victim = min(mem, key=lambda p: (freq[p], loaded[p]))
                    why_v = f"it has the lowest use count ({freq[victim]}; ties go to the oldest page)"
                elif algorithm == "optimal":
                    victim = max(mem, key=lambda p: (next_use(p, t), -loaded[p]))
                    nu = next_use(victim, t)
                    why_v = ("it is never used again" if nu > len(refs) - 1 else f"its next use is farthest away (step {nu + 1})")
                else:  # clock
                    while bits[ptr] == 1:
                        bits[ptr] = 0
                        ptr = (ptr + 1) % frames
                    victim = mem[ptr]
                    why_v = "the clock hand found its reference bit 0 after giving other pages a second chance"
                slot = mem.index(victim)
                if algorithm == "clock":
                    ptr = (slot + 1) % frames
                why = f"Page {page} is not in memory (page fault); page {victim} is replaced because {why_v}"
                del loaded[victim], last[victim], freq[victim]
            mem[slot] = page
            loaded[page], last[page], freq[page], bits[slot] = t, t, 1, 1
        state = {"page": page, "frames": list(mem), "slot": slot, "victim": victim, "hit": event == "hit",
                 "hits": hits, "faults": faults}
        if algorithm == "clock":
            state.update(ref_bits=list(bits), pointer=ptr)
        trace.add(t, event, f"Reference {page}", why, state)

    n = len(refs)
    trace.result = {
        "algorithm_label": LABELS[algorithm], "refs": refs, "timeline": timeline,
        "metrics": {"hits": hits, "faults": faults, "hit_ratio": round(100 * hits / n, 2),
                    "fault_ratio": round(100 * faults / n, 2), "references": n},
    }
    return trace


def compare(refs, frames, algorithms):
    if len(algorithms) < 2 or len(set(algorithms)) != len(algorithms):
        raise ValidationError("Select at least two different algorithms to compare")
    runs = []
    for a in algorithms:
        tr = simulate(refs, frames, a)
        runs.append({"label": LABELS[a], "algorithm": a, "metrics": tr.result["metrics"], "timeline": tr.result["timeline"]})
    best, notes = summarize(runs, {"faults": ("page faults", True), "hit_ratio": ("hit ratio", False)})
    return {"runs": runs, "best_by_metric": best, "explanation": notes}


def belady(refs, algorithm="fifo", max_frames=7):
    _validate(refs, 1, algorithm)
    if not _int(max_frames) or not 2 <= max_frames <= MAX_FRAMES:
        raise ValidationError(f"max_frames must be between 2 and {MAX_FRAMES}")
    curve = [{"frames": f, "faults": simulate(refs, f, algorithm).result["metrics"]["faults"]} for f in range(1, max_frames + 1)]
    anomalies = [{"from_frames": a["frames"], "to_frames": b["frames"], "faults_from": a["faults"], "faults_to": b["faults"]}
                 for a, b in zip(curve, curve[1:]) if b["faults"] > a["faults"]]
    if anomalies:
        x = anomalies[0]
        msg = (f"Belady's anomaly occurred: with {x['from_frames']} frames {LABELS[algorithm]} had {x['faults_from']} faults, "
               f"but with {x['to_frames']} frames it had {x['faults_to']}. More memory produced MORE faults.")
    else:
        msg = f"No anomaly for this reference string: {LABELS[algorithm]} never faulted more when frames increased."
    return {"algorithm": algorithm, "label": LABELS[algorithm], "curve": curve, "anomalies": anomalies,
            "anomaly": bool(anomalies), "explanation": msg}
