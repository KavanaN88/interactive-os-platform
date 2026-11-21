from fastapi import APIRouter

from app.api.v1.common import engine_errors, trace_payload
from app.engines.catalogs import disk_catalog
from app.engines.disk import engine
from app.schemas.modules import DiskCompare, DiskSimulate

router = APIRouter(prefix="/disk", tags=["disk-scheduling"])


@router.get("/algorithms")
def algorithms():
    return disk_catalog()


@router.post("/simulate")
def simulate(req: DiskSimulate):
    with engine_errors():
        return trace_payload(engine.simulate(req.requests, req.head, req.max_cylinder, req.direction, req.algorithm, req.count_jump))


@router.post("/compare")
def compare(req: DiskCompare):
    with engine_errors():
        return engine.compare(req.requests, req.head, req.max_cylinder, req.direction, req.algorithms, req.count_jump)
