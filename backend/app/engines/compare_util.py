"""Shared helper: pick the best algorithm per metric from REAL results and describe ties honestly."""


def summarize(runs: list[dict], spec: dict[str, tuple[str, bool]]):
    """spec: metric key -> (human name, lower_is_better)."""
    best, notes = {}, []
    for key, (name, lower) in spec.items():
        vals = [r["metrics"][key] for r in runs]
        if len(set(vals)) == 1:
            notes.append(f"All algorithms tie on {name} ({vals[0]}) for this workload.")
            continue
        target = min(vals) if lower else max(vals)
        best[key] = [r["label"] for r in runs if r["metrics"][key] == target]
        worst = max(vals) if lower else min(vals)
        notes.append(f"Best {name}: {', '.join(best[key])} ({target}); worst value was {worst}.")
    notes.append("No algorithm is universally best: the winner depends on the metric and the workload.")
    return best, notes
