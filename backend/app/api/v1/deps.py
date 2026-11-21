"""Authentication dependencies. Authorization is enforced HERE, on the server, for every protected route."""
from fastapi import Depends, Header, HTTPException

from app.auth import service
from app.auth.service import AuthError


def _bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def optional_user(authorization: str | None = Header(default=None)):
    """The signed-in user, or None for guests (an invalid token is treated as a guest)."""
    token = _bearer(authorization)
    if not token:
        return None
    try:
        return service.user_from_access(token)
    except AuthError:
        return None


def require_user(authorization: str | None = Header(default=None)):
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return service.user_from_access(token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})


def require_admin(user: dict = Depends(require_user)):
    if user["role"] != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def client_ip(request) -> str:
    return request.client.host if getattr(request, "client", None) else "unknown"
