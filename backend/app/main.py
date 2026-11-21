import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import accounts, admin, cpu, deadlock, disk, memory, paging, phase5, system
from app.auth import content, service
from app.core.usage import usage_for
from app.core.ratelimit import SlidingWindowLimiter

@asynccontextmanager
async def lifespan(_app):
    content.install()                                       # admin-managed lessons/questions become visible to learners
    email, pw = os.getenv("OSLAB_ADMIN_EMAIL"), os.getenv("OSLAB_ADMIN_PASSWORD")
    if email and pw:                                        # optional first-run administrator (never hard-coded)
        try:
            if service.ensure_admin(email, os.getenv("OSLAB_ADMIN_USERNAME", "admin"), pw):
                print(f"[oslab] created administrator '{os.getenv('OSLAB_ADMIN_USERNAME', 'admin')}'")
        except Exception as e:                              # bad password policy etc.: warn, keep running
            print(f"[oslab] could not create the administrator from environment variables: {e}")
    yield


app = FastAPI(title="OS LAB API", version="0.2.0", description="Operating System simulation engines", lifespan=lifespan)

origins = [o.strip() for o in os.getenv("OSLAB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "Authorization", "X-OSLab-Client"])

app.include_router(cpu.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
for _r in (paging.router, disk.router, memory.router, deadlock.router, phase5.process, phase5.sync, phase5.filesystem, phase5.vm,
           phase5.analyzer, phase5.terminal, phase5.learn, phase5.quiz):
    app.include_router(_r, prefix="/api/v1")
for _r in (accounts.router, accounts.me_router, admin.router):
    app.include_router(_r, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok"}


# Rate limiting: per client IP, sliding window. Tunable through environment variables.
_limiter = SlidingWindowLimiter(int(os.getenv("OSLAB_RATE_LIMIT", "600")), 60)


@app.middleware("http")
async def rate_limit(request, call_next):
    if request.url.path.startswith("/api/") and not _limiter.allow(request.client.host if request.client else "unknown"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Too many requests. Please slow down and try again in a minute."}, status_code=429)
    return await call_next(request)


# Usage statistics for the admin dashboard: one row per successful simulation request (module + action, user if signed in).
@app.middleware("http")
async def record_usage(request, call_next):
    response = await call_next(request)
    hit = usage_for(request.method, request.url.path, response.status_code)
    if hit:
        try:
            auth = request.headers.get("authorization", "")
            uid = service.user_from_access(auth[7:].strip())["id"] if auth.lower().startswith("bearer ") else None
        except Exception:
            uid = None
        try:
            service.record_usage(hit[0], hit[1], uid)
        except Exception:
            pass
    return response
