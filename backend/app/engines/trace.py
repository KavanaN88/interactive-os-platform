"""Shared execution-trace format used by EVERY module's engine.

The backend produces a SimulationTrace; the frontend only renders it and never
recomputes algorithm results. Animation speed is purely a client concern, so it
cannot change the trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Step:
    index: int
    time: int
    event: str          # e.g. arrive, dispatch, preempt, complete, idle
    action: str         # short human label
    explanation: str    # why the algorithm did this
    state: dict[str, Any]  # snapshot rendered by the UI


@dataclass
class SimulationTrace:
    module: str
    algorithm: str
    input: dict[str, Any]
    steps: list[Step] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    total_steps: int | None = None      # real number of steps when the engine recorded only the first N

    def add(self, time: int, event: str, action: str, explanation: str,
            state: dict[str, Any]) -> None:
        self.steps.append(Step(len(self.steps), time, event, action, explanation, state))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def page(self, offset: int = 0, limit: int = 200) -> dict[str, Any]:
        """Bounded slice of steps so large traces are never sent in one payload."""
        if offset < 0 or limit < 1:
            raise ValueError("offset must be >= 0 and limit >= 1")
        limit = min(limit, 1000)
        chunk = self.steps[offset: offset + limit]
        return {
            "module": self.module, "algorithm": self.algorithm,
            "total_steps": len(self.steps), "offset": offset, "limit": limit,
            "steps": [asdict(s) for s in chunk],
        }
