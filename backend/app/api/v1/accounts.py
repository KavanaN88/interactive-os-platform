import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.v1.common import api_errors
from app.api.v1.deps import client_ip, require_user
from app.auth import service, tokens
from app.core.ratelimit import SlidingWindowLimiter
from app.schemas.auth import LoginIn, ProgressIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])
COOKIE = "oslab_refresh"
COOKIE_PATH = "/api/v1/auth"
_login_limiter = SlidingWindowLimiter(10, 60)
_register_limiter = SlidingWindowLimiter(10, 3600)


def _set_cookie(response: Response, token: str) -> None:
    # httponly: scripts cannot read it. samesite=strict: not sent on cross-site requests. Set OSLAB_COOKIE_SECURE=1 behind HTTPS.
    response.set_cookie(COOKIE, token, max_age=tokens.REFRESH_TTL, httponly=True, samesite="strict", secure=os.getenv("OSLAB_COOKIE_SECURE") == "1", path=COOKIE_PATH)


def _require_client_header(request: Request) -> None:
    # A custom header cannot be sent by a plain cross-site form, so this blocks cross-site cookie abuse (CSRF).
    if request.headers.get("x-oslab-client") != "web":
        raise HTTPException(status_code=403, detail="Missing client header")


@router.post("/register", status_code=201)
def register(req: RegisterIn, request: Request):
    ip = client_ip(request)
    if not _register_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Too many sign-ups from this address. Try again later.")
    with api_errors():
        return service.register(req.email, req.username, req.password, ip=ip)


@router.post("/login")
def login(req: LoginIn, request: Request, response: Response):
    ip = client_ip(request)
    if not _login_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please wait a minute.")
    with api_errors():
        user, access, refresh = service.login(req.identifier, req.password, ip=ip)
    _set_cookie(response, refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": tokens.ACCESS_TTL, "user": user}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    _require_client_header(request)
    try:
        user, access, new_refresh = service.refresh(request.cookies.get(COOKIE), ip=client_ip(request))
    except service.AuthError as e:
        response.delete_cookie(COOKIE, path=COOKIE_PATH)
        raise HTTPException(status_code=401, detail=str(e))
    _set_cookie(response, new_refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": tokens.ACCESS_TTL, "user": user}


@router.post("/logout")
def logout(request: Request, response: Response):
    _require_client_header(request)
    service.logout(request.cookies.get(COOKIE), ip=client_ip(request))
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    return user


@me_router.get("/progress")
def get_progress(user: dict = Depends(require_user)):
    return {"completed": service.get_progress(user["id"])}


@me_router.put("/progress")
def put_progress(req: ProgressIn, user: dict = Depends(require_user)):
    with api_errors():
        return {"completed": service.set_progress(user["id"], req.topic_id, req.completed)}


@me_router.get("/quiz-history")
def quiz_history(user: dict = Depends(require_user)):
    return service.quiz_history(user["id"])
