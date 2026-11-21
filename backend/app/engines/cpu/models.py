from __future__ import annotations

from dataclasses import dataclass

ALGORITHMS = ["fcfs", "sjf", "srtf", "rr", "priority_np", "priority_p", "mlq", "mlfq"]
ALGORITHM_LABELS = {
    "fcfs": "First Come First Serve",
    "sjf": "Shortest Job First (non-preemptive)",
    "srtf": "Shortest Remaining Time First",
    "rr": "Round Robin",
    "priority_np": "Priority (non-preemptive)",
    "priority_p": "Priority (preemptive)",
    "mlq": "Multilevel Queue",
    "mlfq": "Multilevel Feedback Queue",
}

MAX_PROCESSES = 100
MAX_TICKS = 50_000          # bound on simulated time: protects the server
MAX_LEVELS = 8
DEFAULT_MLQ_LEVELS = [2, None]       # queue 0: RR q=2, queue 1: FCFS
DEFAULT_MLFQ_LEVELS = [2, 4, 8]


from app.engines.errors import ValidationError  # noqa: E402  (shared across all engines)


@dataclass(frozen=True)
class Process:
    """Times are integer ticks. Lower priority number = higher priority.
    `queue` is only used by Multilevel Queue (0 = highest queue)."""
    pid: str
    arrival: int
    burst: int
    priority: int = 0
    queue: int = 0


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate(processes, algorithm, quantum, levels):
    """Validate input and return normalised (quantum, levels)."""
    if algorithm not in ALGORITHMS:
        raise ValidationError(f"Unknown algorithm '{algorithm}'. Supported: {', '.join(ALGORITHMS)}")
    if not processes:
        raise ValidationError("At least one process is required")
    if len(processes) > MAX_PROCESSES:
        raise ValidationError(f"At most {MAX_PROCESSES} processes are allowed")

    seen = set()
    for p in processes:
        if not isinstance(p.pid, str) or not p.pid.strip():
            raise ValidationError("Every process needs a non-empty string pid")
        if p.pid in seen:
            raise ValidationError(f"Duplicate process id '{p.pid}'")
        seen.add(p.pid)
        for name in ("arrival", "burst", "priority", "queue"):
            if not _is_int(getattr(p, name)):
                raise ValidationError(f"{p.pid}: {name} must be an integer")
        if p.arrival < 0:
            raise ValidationError(f"{p.pid}: arrival time cannot be negative")
        if p.burst < 1:
            raise ValidationError(f"{p.pid}: burst time must be at least 1")
        if p.queue < 0:
            raise ValidationError(f"{p.pid}: queue index cannot be negative")

    if max(p.arrival for p in processes) + sum(p.burst for p in processes) > MAX_TICKS:
        raise ValidationError(f"Workload too large: simulated time would exceed {MAX_TICKS} ticks")

    if algorithm == "rr":
        if not _is_int(quantum) or quantum < 1:
            raise ValidationError("Round Robin requires an integer time quantum >= 1")
    if algorithm in ("mlq", "mlfq"):
        if levels is None:
            levels = list(DEFAULT_MLQ_LEVELS if algorithm == "mlq" else DEFAULT_MLFQ_LEVELS)
        if not isinstance(levels, (list, tuple)) or not 1 <= len(levels) <= MAX_LEVELS:
            raise ValidationError(f"levels must be a list of 1..{MAX_LEVELS} quanta (null = FCFS)")
        for q in levels:
            if q is not None and (not _is_int(q) or q < 1):
                raise ValidationError("Each level quantum must be an integer >= 1 or null (FCFS)")
        levels = list(levels)
        if algorithm == "mlq":
            for p in processes:
                if p.queue >= len(levels):
                    raise ValidationError(f"{p.pid}: queue {p.queue} does not exist ({len(levels)} queues)")
    return quantum, levels
