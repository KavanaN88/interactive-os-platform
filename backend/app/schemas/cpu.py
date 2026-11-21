from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessIn(BaseModel):
    pid: str = Field(min_length=1, max_length=32)
    arrival: int = Field(ge=0, le=50_000)
    burst: int = Field(ge=1, le=50_000)
    priority: int = Field(default=0, ge=-1000, le=1000)
    queue: int = Field(default=0, ge=0, le=7)


class SimulateRequest(BaseModel):
    algorithm: str
    processes: list[ProcessIn] = Field(min_length=1, max_length=100)
    quantum: int | None = Field(default=None, ge=1, le=10_000)
    levels: list[int | None] | None = Field(default=None, max_length=8)


class AlgorithmConfig(BaseModel):
    algorithm: str
    quantum: int | None = Field(default=None, ge=1, le=10_000)
    levels: list[int | None] | None = Field(default=None, max_length=8)


class CompareRequest(BaseModel):
    processes: list[ProcessIn] = Field(min_length=1, max_length=100)
    configs: list[AlgorithmConfig] = Field(min_length=2, max_length=8)
