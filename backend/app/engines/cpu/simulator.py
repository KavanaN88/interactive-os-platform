"""Tick-based CPU scheduling simulator. One tick = one time unit of CPU.
The same loop drives all eight algorithms; only the policy differs, so the
Gantt chart, metrics and trace are produced identically for every algorithm."""
from __future__ import annotations

from dataclasses import dataclass

from app.engines.trace import SimulationTrace
from .models import ALGORITHMS, ALGORITHM_LABELS, Process, validate
from .policies import MultiLevelPolicy, QueuePolicy, SelectPolicy


@dataclass
class _RT:
    idx: int
    arrival: int
    burst: int
    priority: int
    remaining: int
    queue: int = 0
    first_start: int | None = None
    completion: int | None = None


def _build_policy(algorithm, rt, quantum, levels):
    rem = lambda p: rt[p].remaining
    if algorithm == "fcfs":
        return QueuePolicy(rt, None)
    if algorithm == "rr":
        return QueuePolicy(rt, quantum)
    if algorithm == "sjf":
        return SelectPolicy(rt, lambda p: rt[p].burst, "burst time", False)
    if algorithm == "srtf":
        return SelectPolicy(rt, rem, "remaining time", True)
    if algorithm == "priority_np":
        return SelectPolicy(rt, lambda p: rt[p].priority, "priority (lower number = higher)", False)
    if algorithm == "priority_p":
        return SelectPolicy(rt, lambda p: rt[p].priority, "priority (lower number = higher)", True)
    return MultiLevelPolicy(rt, levels, feedback=(algorithm == "mlfq"))


def _r(x):
    return round(x, 4)


MAX_STEPS = 5000      # steps recorded per run; metrics/Gantt are always computed from the FULL run


def simulate(processes: list[Process], algorithm: str, quantum: int | None = None,
             levels: list[int | None] | None = None, max_steps: int = MAX_STEPS) -> SimulationTrace:
    quantum, levels = validate(processes, algorithm, quantum, levels)
    rt = {p.pid: _RT(i, p.arrival, p.burst, p.priority, p.burst, p.queue) for i, p in enumerate(processes)}
    order = [p.pid for p in processes]
    policy = _build_policy(algorithm, rt, quantum, levels)

    trace = SimulationTrace(
        module="cpu_scheduling", algorithm=algorithm,
        input={"processes": [vars(p) for p in processes], "quantum": quantum, "levels": levels},
    )
    completed: list[str] = []
    segments: list[dict] = []          # Gantt: merged contiguous runs, pid None = idle
    context_switches = 0
    t, running, slice_used, last_pid, idle_open = 0, None, 0, None, False

    def snap(run):
        return {"running": run, "ready": policy.ready(), "completed": list(completed)}

    total_steps = 0

    def emit(now, event, action, why, run):
        """Record a step only while under the limit, so a huge run never builds a huge trace."""
        nonlocal total_steps
        total_steps += 1
        if total_steps <= max_steps:
            trace.add(now, event, action, why, snap(run))

    def admit_arrivals(now):
        for pid in order:
            if rt[pid].arrival == now:
                policy.admit(pid)
                emit(now, "arrive", f"{pid} arrives",
                          f"{pid} (burst {rt[pid].burst}) enters the ready queue", running)

    admit_arrivals(0)
    while len(completed) < len(order):
        pid, why = policy.select(running, slice_used)
        if pid is None:
            if not idle_open:
                emit(t, "idle", "CPU idle", "No process is ready; the CPU waits for the next arrival", None)
                idle_open = True
            _extend(segments, None, t)
            t += 1
            admit_arrivals(t)
            continue
        idle_open = False
        if pid != running:
            if running is not None:
                emit(t, "preempt", f"{running} preempted", why, None)
            if rt[pid].first_start is None:
                rt[pid].first_start = t
            if last_pid is not None and last_pid != pid:
                context_switches += 1
            running, slice_used = pid, 0
            emit(t, "dispatch", f"{pid} dispatched", why, pid)
        _extend(segments, pid, t)
        rt[pid].remaining -= 1
        slice_used += 1
        last_pid = pid
        t += 1
        admit_arrivals(t)               # arrivals at t join before a preempted process re-queues
        finished = rt[pid].remaining == 0
        if finished:
            rt[pid].completion = t
            completed.append(pid)
            emit(t, "complete", f"{pid} completes",
                      f"{pid} has no remaining burst; turnaround = {t - rt[pid].arrival}", None)
        running, note, kind = policy.tick_done(running, finished, slice_used)
        if note:
            emit(t, kind, f"{pid} {'demoted' if kind == 'demote' else 'time slice ended'}", note, None)

    makespan = t
    trace.total_steps = total_steps
    per, busy = [], sum(r.burst for r in rt.values())
    for pid in order:
        r = rt[pid]
        tat = r.completion - r.arrival
        per.append({"pid": pid, "arrival": r.arrival, "burst": r.burst, "priority": r.priority,
                    "start": r.first_start, "completion": r.completion, "turnaround": tat,
                    "waiting": tat - r.burst, "response": r.first_start - r.arrival})
    n = len(per)
    trace.result = {
        "algorithm_label": ALGORITHM_LABELS[algorithm],
        "gantt": segments,
        "idle_periods": [s for s in segments if s["pid"] is None],
        "processes": per,
        "metrics": {
            "avg_waiting_time": _r(sum(x["waiting"] for x in per) / n),
            "avg_turnaround_time": _r(sum(x["turnaround"] for x in per) / n),
            "avg_response_time": _r(sum(x["response"] for x in per) / n),
            "cpu_utilization": _r(100 * busy / makespan),
            "throughput": _r(n / makespan),
            "context_switches": context_switches,
            "makespan": makespan,
        },
    }
    return trace


def _extend(segments, pid, t):
    if segments and segments[-1]["pid"] == pid and segments[-1]["end"] == t:
        segments[-1]["end"] = t + 1
    else:
        segments.append({"pid": pid, "start": t, "end": t + 1})
