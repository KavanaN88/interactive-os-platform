from contextlib import contextmanager

from fastapi import HTTPException

from app.auth.service import AuthError
from app.engines.errors import ValidationError

MAX_STEPS_RETURNED = 5000


@contextmanager
def engine_errors():
    """Turn engine validation problems into HTTP 422 with a readable message."""
    try:
        yield
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


def trace_payload(trace):
    data = trace.to_dict()
    total = data.get("total_steps") or len(data["steps"])
    data["steps"] = data["steps"][:MAX_STEPS_RETURNED]
    data["total_steps"], data["truncated"] = total, total > len(data["steps"])
    return data


@contextmanager
def api_errors():
    """ValidationError -> 422, AuthError -> 401 (used by the account and admin routes)."""
    try:
        yield
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
