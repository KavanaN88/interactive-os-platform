from fastapi import APIRouter

from app.api.v1.common import engine_errors, trace_payload
from app.engines.catalogs import memory_catalog
from app.engines.memory import engine
from app.schemas.modules import MemoryCompare, MemorySimulate

router = APIRouter(prefix="/memory", tags=["memory-management"])


@router.get("/strategies")
def strategies():
    return memory_catalog()


@router.post("/simulate")
def simulate(req: MemorySimulate):
    with engine_errors():
        return trace_payload(engine.simulate(req.blocks, [o.model_dump(exclude_none=True) for o in req.ops], req.strategy, req.mode))


@router.post("/compare")
def compare(req: MemoryCompare):
    with engine_errors():
        return engine.compare(req.blocks, [o.model_dump(exclude_none=True) for o in req.ops], req.mode, req.strategies)
