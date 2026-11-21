"""Run several configurations on IDENTICAL input and explain differences from the real numbers."""
from __future__ import annotations

from .models import ALGORITHM_LABELS, Process, ValidationError
from .simulator import simulate

# metric -> (label, True if lower is better)
METRICS = {
    "avg_waiting_time": ("average waiting time", True),
    "avg_turnaround_time": ("average turnaround time", True),
    "avg_response_time": ("average response time", True),
    "cpu_utilization": ("CPU utilization", False),
    "throughput": ("throughput", False),
    "context_switches": ("context switches", True),
}


def _label(cfg):
    base = ALGORITHM_LABELS.get(cfg["algorithm"], cfg["algorithm"])
    if cfg["algorithm"] == "rr":
        return f"{base} (q={cfg.get('quantum')})"
    return base


def compare(processes: list[Process], configs: list[dict]) -> dict:
    if len(configs) < 2:
        raise ValidationError("Select at least two algorithms to compare")
    runs = []
    for cfg in configs:
        tr = simulate(processes, cfg["algorithm"], cfg.get("quantum"), cfg.get("levels"), max_steps=0)
        runs.append({"label": _label(cfg), "config": cfg, "metrics": tr.result["metrics"],
                     "gantt": tr.result["gantt"]})
    labels = [r["label"] for r in runs]
    if len(set(labels)) != len(labels):
        raise ValidationError("Each compared configuration must be distinct")

    best, notes = {}, []
    for key, (name, lower) in METRICS.items():
        vals = [r["metrics"][key] for r in runs]
        if len(set(vals)) == 1:
            notes.append(f"All algorithms tie on {name} ({vals[0]}) for this workload.")
            if key in ("cpu_utilization", "throughput"):
                notes[-1] += " The same total work and arrival pattern finish at the same time."
            continue
        target = min(vals) if lower else max(vals)
        winners = [r["label"] for r in runs if r["metrics"][key] == target]
        best[key] = winners
        worst = max(vals) if lower else min(vals)
        notes.append(f"Best {name}: {', '.join(winners)} ({target}); worst value was {worst}.")

    bursts = [p.burst for p in processes]
    ctx = {"workload": {"processes": len(processes), "min_burst": min(bursts),
                        "max_burst": max(bursts), "distinct_arrivals": len({p.arrival for p in processes})}}
    by = {c["config"]["algorithm"]: c["metrics"] for c in runs}
    if "fcfs" in by:
        for other in ("sjf", "srtf"):
            if other in by and by[other]["avg_waiting_time"] < by["fcfs"]["avg_waiting_time"]:
                notes.append(f"{ALGORITHM_LABELS[other]} waited less than FCFS here "
                             f"({by[other]['avg_waiting_time']} vs {by['fcfs']['avg_waiting_time']}) because "
                             f"burst times range from {min(bursts)} to {max(bursts)}, so FCFS made short jobs wait behind long ones.")
    notes.append("No algorithm is universally best: the winner depends on the metric and the workload above.")
    return {"runs": runs, "best_by_metric": best, "explanation": notes, **ctx}
