import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import host, devices, imports, files, settings as settings_router, ws
from .services.queue import import_worker


logging.basicConfig(level=settings.log_level)
log = logging.getLogger("sdoffload")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("DB ready at %s", settings.db_path)
    worker_task = await import_worker.start()
    try:
        yield
    finally:
        await import_worker.stop(worker_task)


app = FastAPI(title="SD Media Offload", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(host.router, prefix="/api/host", tags=["host"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
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
