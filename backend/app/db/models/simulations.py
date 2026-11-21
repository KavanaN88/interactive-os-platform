import datetime as dt
import uuid
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RunStatus, TimestampMixin, UUIDMixin


class Simulation(UUIDMixin, TimestampMixin, Base):
    """A named, saved scenario: the input configuration a student wants to keep."""
    __tablename__ = "simulations"
    # Nullable only until authentication exists; will be made NOT NULL in the auth phase.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id"), index=True)
    algorithm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("algorithms.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SimulationRun(UUIDMixin, Base):
    """One execution of a simulation."""
    __tablename__ = "simulation_runs"
    simulation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False, length=20), default=RunStatus.completed)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationResult(UUIDMixin, Base):
    __tablename__ = "simulation_results"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)       # gantt, per-process table, etc.


class SimulationStep(UUIDMixin, Base):
    """Stored only for saved runs (bounded). Live animation state is never persisted."""
    __tablename__ = "simulation_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_index"),)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    time: Mapped[int] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(30))
    explanation: Mapped[str] = mapped_column(Text)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ComparisonSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "comparison_sessions"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)         # identical workload + chosen configs
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)       # metrics per algorithm + explanation
