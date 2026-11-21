from fastapi import APIRouter

from app.api.v1.common import engine_errors, trace_payload
from app.engines.catalogs import paging_catalog
from app.engines.paging import engine
from app.schemas.modules import PagingBelady, PagingCompare, PagingSimulate

router = APIRouter(prefix="/page-replacement", tags=["page-replacement"])


@router.get("/algorithms")
def algorithms():
    return paging_catalog()


@router.post("/simulate")
def simulate(req: PagingSimulate):
    with engine_errors():
        return trace_payload(engine.simulate(req.refs, req.frames, req.algorithm))


@router.post("/compare")
def compare(req: PagingCompare):
    with engine_errors():
        return engine.compare(req.refs, req.frames, req.algorithms)


@router.post("/belady")
def belady(req: PagingBelady):
    with engine_errors():
        return engine.belady(req.refs, req.algorithm, req.max_frames)
