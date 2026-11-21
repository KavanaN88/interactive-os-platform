from fastapi import APIRouter

from app.api.v1.common import engine_errors, trace_payload
from app.engines.deadlock import engine
from app.schemas.modules import DeadlockDetect, DeadlockRequest, DeadlockState

router = APIRouter(prefix="/deadlock", tags=["deadlock-management"])


@router.post("/safety")
def safety(req: DeadlockState):
    with engine_errors():
        return trace_payload(engine.safety(req.available, req.allocation, req.maximum))


@router.post("/request")
def request(req: DeadlockRequest):
    with engine_errors():
        return engine.request(req.available, req.allocation, req.maximum, req.pid, req.request)


@router.post("/detect")
def detect(req: DeadlockDetect):
    with engine_errors():
        return trace_payload(engine.detect(req.available, req.allocation, req.request))


@router.post("/recover")
def recover(req: DeadlockDetect):
    with engine_errors():
        return trace_payload(engine.recover(req.available, req.allocation, req.request))


@router.post("/graph")
def graph(req: DeadlockDetect):
    with engine_errors():
        return engine.rag(req.available, req.allocation, req.request)
