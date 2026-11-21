"""Educational text and input requirements per algorithm. Served by the API so the
frontend never hard-codes algorithm facts."""
from .models import ALGORITHMS, ALGORITHM_LABELS

INFO = {
    "fcfs": ("Runs processes strictly in arrival order. Simple and fair in order, but short jobs can wait behind long ones (convoy effect).",
             ["Non-preemptive: a running process keeps the CPU until it finishes.",
              "The ready queue is ordered by arrival time; ties use input order.",
              "If no process has arrived, the CPU idles until the next arrival."]),
    "sjf": ("Picks the ready process with the smallest total burst time and runs it to completion. Minimises average waiting time for non-preemptive scheduling when all jobs are known.",
            ["Non-preemptive.", "Among ready processes, choose the smallest burst time.",
             "Ties: earlier arrival, then input order. Long jobs can starve."]),
    "srtf": ("Preemptive version of SJF: whenever a process arrives, the CPU goes to whichever ready process has the least remaining time.",
             ["Preemptive: re-evaluated every time unit.", "Choose the smallest remaining time.",
              "A tie keeps the running process (no pointless context switch)."]),
    "rr": ("Each process gets the CPU for at most one time quantum, then returns to the back of the ready queue. Good response time, more context switches.",
           ["Preemptive by time quantum q.", "A process arriving at the same moment a quantum ends is queued BEFORE the preempted process.",
            "A very large q behaves like FCFS."]),
    "priority_np": ("Runs the ready process with the highest priority to completion. Lower number means higher priority.",
                    ["Non-preemptive.", "Choose the lowest priority number among ready processes.",
                     "Ties: earlier arrival, then input order. Low-priority jobs can starve."]),
    "priority_p": ("Like priority scheduling, but a newly ready higher-priority process preempts the running one immediately.",
                   ["Preemptive.", "Lower priority number = higher priority.",
                    "Equal priority never preempts the running process."]),
    "mlq": ("Several fixed ready queues, each with its own policy. A process stays in the queue it was assigned to.",
            ["Strict priority between queues: queue 0 always runs first.",
             "A process becoming ready in a higher queue preempts a lower queue; the preempted process returns to the FRONT of its queue.",
             "Each queue has a quantum (round robin) or none (FCFS)."]),
    "mlfq": ("Processes start in the top queue and are demoted when they use a full quantum, so short/interactive jobs finish quickly and CPU-bound jobs sink.",
             ["All processes enter queue 0.", "Using a full quantum demotes a process one level (the last level just round-robins).",
              "Higher queues preempt lower ones. This model has no I/O, so there is no promotion or aging."]),
}


def algorithm_catalog():
    out = []
    for a in ALGORITHMS:
        desc, rules = INFO[a]
        out.append({
            "id": a, "label": ALGORITHM_LABELS[a], "description": desc, "rules": rules,
            "needs_quantum": a == "rr",
            "needs_priority": a in ("priority_np", "priority_p"),
            "needs_queue": a == "mlq",
            "needs_levels": a in ("mlq", "mlfq"),
        })
    return out
