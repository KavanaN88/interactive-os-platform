"""Performance Analyzer: runs several algorithms on ONE identical workload, then derives recommendations from the
real numbers. Nothing here is hard-coded: every figure in the output comes from an engine run."""
from __future__ import annotations

import json

from app.engines.cpu import ALGORITHM_LABELS as CPU_L, Process, compare as cpu_compare
from app.engines.cpu.models import ALGORITHMS as CPU_ALGOS
from app.engines.disk import engine as disk
from app.engines.errors import ValidationError
from app.engines.fs import engine as fs
from app.engines.memory import engine as mem
from app.engines.paging import engine as paging
from app.engines.vm import engine as vm

CATALOG = {
    "cpu": {"label": "CPU Scheduling", "algorithms": {a: CPU_L[a] for a in CPU_ALGOS}, "defaults": ["fcfs", "sjf", "srtf", "rr"],
            "metrics": [["avg_waiting_time", "Avg wait", True], ["avg_turnaround_time", "Avg turnaround", True], ["avg_response_time", "Avg response", True],
                        ["cpu_utilization", "CPU %", False], ["throughput", "Throughput", False], ["context_switches", "Ctx switches", True]]},
    "paging": {"label": "Page Replacement", "algorithms": paging.LABELS, "defaults": ["fifo", "lru", "optimal"],
               "metrics": [["faults", "Faults", True], ["hits", "Hits", False], ["hit_ratio", "Hit %", False], ["fault_ratio", "Fault %", True]]},
    "disk": {"label": "Disk Scheduling", "algorithms": disk.LABELS, "defaults": ["fcfs", "sstf", "scan", "look"],
             "metrics": [["total_head_movement", "Total movement", True], ["avg_seek_distance", "Avg seek", True]]},
    "memory": {"label": "Memory Allocation", "algorithms": mem.LABELS, "defaults": ["first_fit", "best_fit", "worst_fit"],
               "metrics": [["failed_allocations", "Failed", True], ["utilization_pct", "Utilization %", False], ["internal_fragmentation", "Internal frag", True],
                           ["largest_hole", "Largest hole", False], ["external_fragmentation_pct", "External frag %", True]]},
    "fs": {"label": "File Allocation", "algorithms": fs.LABELS, "defaults": ["contiguous", "linked", "indexed"],
           "metrics": [["failed_operations", "Failed ops", True], ["utilization_pct", "Utilization %", False], ["index_blocks", "Index blocks", True],
                       ["external_fragmentation_pct", "External frag %", True], ["avg_fragments_per_file", "Fragments/file", True]]},
    "vm": {"label": "Virtual Memory (replacement policy)", "algorithms": {"fifo": "FIFO", "lru": "LRU"}, "defaults": ["fifo", "lru"],
           "metrics": [["page_faults", "Page faults", True], ["tlb_hit_ratio", "TLB hit %", False], ["effective_access_time_ns", "EAT (ns)", True]]},
}


def catalog():
    return [{"module": k, "label": v["label"], "algorithms": [{"id": a, "label": l} for a, l in v["algorithms"].items()],
             "defaults": v["defaults"], "metrics": v["metrics"]} for k, v in CATALOG.items()]


def _need(w, *keys):
    miss = [k for k in keys if k not in w]
    if miss:
        raise ValidationError(f"Workload is missing: {', '.join(miss)}")


def _run(module, w, algos):
    if module not in CATALOG:
        raise ValidationError(f"Unknown module '{module}'. Supported: {', '.join(CATALOG)}")
    if not isinstance(w, dict) or not isinstance(algos, list):
        raise ValidationError("workload must be an object and algorithms a list")
    bad = [a for a in algos if a not in CATALOG[module]["algorithms"]]
    if bad:
        raise ValidationError(f"Unknown algorithm(s) for {module}: {', '.join(map(str, bad))}")
    if module == "cpu":
        _need(w, "processes")
        procs = [Process(**{k: p[k] for k in ("pid", "arrival", "burst", "priority", "queue") if k in p}) for p in w["processes"]]
        cfg = [{"algorithm": a, "quantum": w.get("quantum") if a == "rr" else None, "levels": w.get("levels") if a in ("mlq", "mlfq") else None} for a in algos]
        r = cpu_compare(procs, cfg)
        return {"runs": [{"label": x["label"], "algorithm": c["algorithm"], "metrics": x["metrics"]} for x, c in zip(r["runs"], cfg)],
                "best_by_metric": r["best_by_metric"], "explanation": r["explanation"]}
    if module == "paging":
        _need(w, "refs", "frames")
        return paging.compare(w["refs"], w["frames"], algos)
    if module == "disk":
        _need(w, "requests", "head", "max_cylinder")
        return disk.compare(w["requests"], w["head"], w["max_cylinder"], w.get("direction", "up"), algos, w.get("count_jump", True))
    if module == "memory":
        _need(w, "blocks", "ops")
        return mem.compare(w["blocks"], w["ops"], w.get("mode", "variable"), algos)
    if module == "fs":
        _need(w, "total_blocks", "ops")
        return fs.compare(w["total_blocks"], w["ops"], w.get("block_size_kb", 1), algos)
    _need(w, "page_size", "virtual_size", "physical_size", "addresses")
    return vm.compare(w["page_size"], w["virtual_size"], w["physical_size"], w["addresses"], w.get("tlb_size", 4), w.get("tlb_policy", "lru"), algos, w.get("costs"))


def _by(runs, key):
    return {r["label"]: r["metrics"][key] for r in runs}


def recommend(module, w, result):
    runs, out = result["runs"], []
    if module == "cpu":
        wt, rt, cs = _by(runs, "avg_waiting_time"), _by(runs, "avg_response_time"), _by(runs, "context_switches")
        bw, br = min(wt, key=wt.get), min(rt, key=rt.get)
        out.append(f"For this workload, {bw} gives the lowest average waiting time ({wt[bw]}).")
        if br != bw:
            out.append(f"{br} gives the best response time ({rt[br]}) but its average waiting time is {wt[br]} and it makes {cs[br]} context switches (vs {cs[bw]} for {bw}).")
        if len(set(cs.values())) > 1:
            few = min(cs, key=cs.get)
            out.append(f"{few} switches context least ({cs[few]}), so it has the lowest scheduling overhead here.")
        b = [p["burst"] for p in w["processes"]]
        out.append(f"Workload: {len(b)} processes, burst times {min(b)}–{max(b)}, {len({p['arrival'] for p in w['processes']})} distinct arrival time(s).")
    elif module == "paging":
        f = _by(runs, "faults")
        impl = {k: v for k, v in f.items() if k != "Optimal"}
        if impl:
            best = min(impl, key=impl.get)
            out.append(f"Among implementable algorithms, {best} had the fewest faults ({impl[best]}).")
            if "Optimal" in f:
                out.append(f"Optimal (a lower bound that needs future knowledge) had {f['Optimal']} faults, so {best} was {impl[best] - f['Optimal']} fault(s) away from the theoretical best.")
        out.append(f"With {w['frames']} frame(s) the fault counts are {', '.join(f'{k}={v}' for k, v in f.items())}.")
    elif module == "disk":
        t = _by(runs, "total_head_movement")
        best = min(t, key=t.get)
        out.append(f"{best} moved the head least ({t[best]} cylinders) on this queue.")
        if "FCFS" in t and best != "FCFS" and t["FCFS"]:
            out.append(f"That is {round(100 * (t['FCFS'] - t[best]) / t['FCFS'], 1)}% less movement than FCFS ({t['FCFS']}).")
        if best == "SSTF":
            out.append("SSTF minimises movement here but can starve far-away requests; SCAN/LOOK trade a little movement for fairness.")
    elif module == "memory":
        fails, util = _by(runs, "failed_allocations"), _by(runs, "utilization_pct")
        ok = [k for k, v in fails.items() if v == min(fails.values())]
        if len(set(fails.values())) > 1:
            out.append(f"{', '.join(ok)} placed the most processes ({len(w['ops'])} operations, {min(fails.values())} failure(s)); the others failed on {max(fails.values())}.")
        else:
            bu = max(util, key=util.get)
            out.append(f"All strategies placed the same processes; {bu} ended with the highest utilization ({util[bu]}%).")
        ext = {r["label"]: r["metrics"]["external_failures"] for r in runs if r["metrics"].get("external_failures")}
        if ext:
            out.append("Some failures were caused by external fragmentation (enough total free memory, but not in one hole): " + ", ".join(f"{k} ({v})" for k, v in ext.items()) + ". Compaction would help.")
    elif module == "fs":
        fails, idx = _by(runs, "failed_operations"), _by(runs, "index_blocks")
        out.append("Failed operations: " + ", ".join(f"{k}={v}" for k, v in fails.items()) + ".")
        if any(idx.values()):
            out.append(f"Indexed allocation spent {max(idx.values())} block(s) on index blocks, which is the price of fast direct access.")
        ef = _by(runs, "external_fragmentation_pct")
        out.append("External fragmentation at the end: " + ", ".join(f"{k}={v}%" for k, v in ef.items()) + ". Only contiguous allocation needs one unbroken run of blocks.")
    else:
        pf, eat = _by(runs, "page_faults"), _by(runs, "effective_access_time_ns")
        b = min(eat, key=eat.get)
        out.append(f"{b} has the lowest effective access time ({eat[b]} ns); page faults: " + ", ".join(f"{k}={v}" for k, v in pf.items()) + ".")
        if len(set(eat.values())) > 1 and max(eat.values()) > 1e6:
            out.append(f"One page fault costs about {w.get('costs', {}).get('fault_ns', 8_000_000):,} ns, which is why the number of faults dominates access time.")
    out.append("These recommendations apply to THIS workload; change the input and the best choice may change.")
    return [x for x in out if x]


def compare(module, workload, algorithms):
    if len(algorithms) < 2:
        raise ValidationError("Select at least two algorithms to compare")
    r = _run(module, workload, algorithms)
    return {"module": module, "label": CATALOG[module]["label"], **r, "recommendations": recommend(module, workload, r)}


def report(module, workload, algorithms):
    r = compare(module, workload, algorithms)
    cols = CATALOG[module]["metrics"]
    md = [f"# OS LAB Performance Report: {r['label']}", "", "## Workload (identical for every algorithm)", "```json", json.dumps(workload, indent=2), "```", "",
          "## Results", "", "| Algorithm | " + " | ".join(c[1] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for run in r["runs"]:
        md.append(f"| {run['label']} | " + " | ".join(str(run['metrics'][c[0]]) for c in cols) + " |")
    md += ["", "## Best per metric", ""] + [f"- **{dict((c[0], c[1]) for c in cols)[k]}**: {', '.join(v)}" for k, v in r["best_by_metric"].items()]
    md += ["", "## Why the results differ", ""] + [f"- {e}" for e in r["explanation"]] + ["", "## Recommendations", ""] + [f"- {x}" for x in r["recommendations"]]
    return {"filename": f"oslab-{module}-report.md", "markdown": "\n".join(md) + "\n"}
