import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import auth as auth_router, host, devices, imports, files, settings as settings_router, ws, events, admin
from .services import auth as auth_svc
from .services.backup import start_backup_loop
from .services.queue import import_worker


logging.basicConfig(level=settings.log_level)
log = logging.getLogger("sdoffload")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("DB ready at %s", settings.db_path)
    worker_tasks = await import_worker.start()
    backup_task = await start_backup_loop()
    try:
        yield
    finally:
        await import_worker.stop(worker_tasks)
        if backup_task:
            backup_task.cancel()


app = FastAPI(title="SD Media Offload", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not auth_svc.auth_required():
        return await call_next(request)
    path = request.url.path
    # Public endpoints / static assets
    if path == "/api/health" or path.startswith("/api/auth/"):
        return await call_next(request)
    # Host-agent uses its own X-Host-Token, not user cookie
    if path.startswith("/api/host/"):
        return await call_next(request)
    # SPA assets (login page must load before user is authenticated)
    if not path.startswith("/api/"):
        return await call_next(request)
    token = request.cookies.get(auth_svc.COOKIE_NAME, "")
    if not auth_svc.verify_token(token):
        return JSONResponse({"error": "auth required"}, status_code=401)
    return await call_next(request)


app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(host.router, prefix="/api/host", tags=["host"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(ws.router, prefix="/api/ws", tags=["ws"])


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.1.0"}


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        target = STATIC_DIR / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
