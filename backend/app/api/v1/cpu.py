from fastapi import APIRouter, HTTPException

from app.api.v1.common import trace_payload
from app.engines.cpu import Process, ValidationError, compare, simulate
from app.engines.cpu.info import algorithm_catalog
from app.schemas.cpu import CompareRequest, SimulateRequest

router = APIRouter(prefix="/cpu", tags=["cpu-scheduling"])
MAX_STEPS_RETURNED = 5000     # bounded payload; `truncated` tells the client


def _procs(items):
    return [Process(**p.model_dump()) for p in items]


@router.get("/algorithms")
def algorithms():
    return algorithm_catalog()


@router.post("/simulate")
def run_simulation(req: SimulateRequest):
    try:
        trace = simulate(_procs(req.processes), req.algorithm, req.quantum, req.levels)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return trace_payload(trace)


@router.post("/compare")
def run_comparison(req: CompareRequest):
    try:
        return compare(_procs(req.processes), [c.model_dump() for c in req.configs])
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
