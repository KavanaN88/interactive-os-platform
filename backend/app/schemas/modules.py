from __future__ import annotations

from pydantic import BaseModel, Field, StrictInt

Pages = list[StrictInt]


class PagingSimulate(BaseModel):
    refs: Pages = Field(min_length=1, max_length=500)
    frames: StrictInt = Field(ge=1, le=16)
    algorithm: str


class PagingCompare(BaseModel):
    refs: Pages = Field(min_length=1, max_length=500)
    frames: StrictInt = Field(ge=1, le=16)
    algorithms: list[str] = Field(min_length=2, max_length=5)


class PagingBelady(BaseModel):
    refs: Pages = Field(min_length=1, max_length=500)
    algorithm: str = "fifo"
    max_frames: StrictInt = Field(default=7, ge=2, le=16)


class DiskSimulate(BaseModel):
    requests: list[StrictInt] = Field(min_length=1, max_length=500)
    head: StrictInt = Field(ge=0)
    max_cylinder: StrictInt = Field(ge=1, le=100_000)
    direction: str = "up"
    algorithm: str
    count_jump: bool = True


class DiskCompare(BaseModel):
    requests: list[StrictInt] = Field(min_length=1, max_length=500)
    head: StrictInt = Field(ge=0)
    max_cylinder: StrictInt = Field(ge=1, le=100_000)
    direction: str = "up"
    algorithms: list[str] = Field(min_length=2, max_length=6)
    count_jump: bool = True


class MemoryOp(BaseModel):
    op: str
    pid: str | None = Field(default=None, max_length=32)
    size: StrictInt | None = None


class MemorySimulate(BaseModel):
    blocks: list[StrictInt] = Field(min_length=1, max_length=50)
    ops: list[MemoryOp] = Field(max_length=200)
    strategy: str
    mode: str = "variable"


class MemoryCompare(BaseModel):
    blocks: list[StrictInt] = Field(min_length=1, max_length=50)
    ops: list[MemoryOp] = Field(max_length=200)
    mode: str = "variable"
    strategies: list[str] | None = Field(default=None, max_length=3)


Vec = list[StrictInt]
Mat = list[list[StrictInt]]


class DeadlockState(BaseModel):
    available: Vec = Field(max_length=10)
    allocation: Mat = Field(max_length=20)
    maximum: Mat = Field(max_length=20)


class DeadlockRequest(DeadlockState):
    pid: StrictInt
    request: Vec = Field(max_length=10)


class DeadlockDetect(BaseModel):
    available: Vec = Field(max_length=10)
    allocation: Mat = Field(max_length=20)
    request: Mat = Field(max_length=20)


# ---------------- Phase 5 modules ----------------
class ProcIn(BaseModel):
    pid: str = Field(min_length=1, max_length=16)
    arrival: StrictInt = Field(ge=0, le=5000)
    bursts: list[StrictInt] = Field(min_length=1, max_length=9)
    priority: StrictInt = 0
    parent: str | None = Field(default=None, max_length=16)
    memory: StrictInt = Field(default=64, ge=1, le=1_000_000)


class ProcSimulate(BaseModel):
    processes: list[ProcIn] = Field(min_length=1, max_length=20)
    quantum: StrictInt = Field(default=2, ge=1, le=100)


class IpcOp(BaseModel):
    by: str = Field(max_length=16)
    op: str = Field(max_length=10)
    data: str | StrictInt | None = None
    key: str | None = Field(default=None, max_length=16)


class IpcRequest(BaseModel):
    mechanism: str
    ops: list[IpcOp] = Field(min_length=1, max_length=100)
    capacity: StrictInt = Field(default=3, ge=1, le=16)


class ThreadsRequest(BaseModel):
    threads: StrictInt = Field(ge=1, le=8)
    work: StrictInt = Field(ge=1, le=20)


class SyncRun(BaseModel):
    scenario: str = Field(max_length=40)
    params: dict[str, StrictInt | bool | str] = Field(default_factory=dict, max_length=12)


class FsOp(BaseModel):
    op: str = Field(max_length=10)
    path: str = Field(max_length=200)
    size: StrictInt | None = None


class FsSimulate(BaseModel):
    total_blocks: StrictInt = Field(ge=4, le=512)
    method: str
    ops: list[FsOp] = Field(min_length=1, max_length=200)
    block_size_kb: StrictInt = Field(default=1, ge=1, le=64)


class FsCompare(BaseModel):
    total_blocks: StrictInt = Field(ge=4, le=512)
    ops: list[FsOp] = Field(min_length=1, max_length=200)
    block_size_kb: StrictInt = Field(default=1, ge=1, le=64)
    methods: list[str] | None = Field(default=None, max_length=3)


class VmBase(BaseModel):
    page_size: StrictInt = Field(ge=1, le=65536)
    virtual_size: StrictInt = Field(ge=1, le=2 ** 26)
    physical_size: StrictInt = Field(ge=1, le=2 ** 26)
    addresses: list[StrictInt] = Field(min_length=1, max_length=200)
    tlb_size: StrictInt = Field(default=4, ge=0, le=16)
    tlb_policy: str = "lru"


class VmTranslate(VmBase):
    replacement: str = "lru"


class VmCompare(VmBase):
    policies: list[str] | None = Field(default=None, max_length=2)


class WorkingSetRequest(BaseModel):
    refs: list[StrictInt] = Field(min_length=1, max_length=500)
    delta: StrictInt = Field(ge=1, le=100)


class ThrashingRequest(BaseModel):
    total_frames: StrictInt = Field(ge=1, le=256)
    working_set_size: StrictInt = Field(ge=1, le=32)
    refs_per_process: StrictInt = Field(default=400, ge=50, le=2000)
    max_processes: StrictInt = Field(default=12, ge=1, le=32)
    fault_cost: StrictInt = Field(default=50, ge=1, le=10_000)


class AnalyzerRequest(BaseModel):
    module: str = Field(max_length=20)
    workload: dict = Field(default_factory=dict)
    algorithms: list[str] = Field(min_length=2, max_length=8)


class TerminalRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    command: str = Field(max_length=300)


class QuizGrade(BaseModel):
    question_ids: list[str] = Field(min_length=1, max_length=60)
    answers: dict[str, str] = Field(default_factory=dict, max_length=60)
    level: str | None = Field(default=None, max_length=20)
