"""In-process async job queue. One worker, processes imports sequentially.

For v1 this is enough — copying from one SD reader at a time is the bottleneck anyway.
Multiple workers + per-device queues can be added later without changing the API.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..config import settings
from ..db import session_scope
from . import importer as importer_mod
from .ws_broker import broker


log = logging.getLogger("sdoffload.queue")


class ImportWorker:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._stopped = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> list[asyncio.Task]:
        # On startup, attempt to auto-resume in-flight imports if their source mount is still there.
        from .. import models
        from .importer import remap_source

        to_resume: list[int] = []
        with session_scope() as s:
            stuck = (s.query(models.Import)
                     .filter(models.Import.status.in_(("pending", "scanning", "copying")))
                     .all())
            for imp in stuck:
                src = remap_source(imp.mount_path)
                if src.exists():
                    imp.status = "pending"
                    s.add(models.Event(level="info", source="queue", import_id=imp.id,
                                       device_id=imp.device_id,
                                       message="Auto-resuming after restart"))
                    to_resume.append(imp.id)
                else:
                    imp.status = "failed"
                    imp.error = "Interrupted by restart; source no longer accessible"
                    s.add(models.Event(level="warn", source="queue", import_id=imp.id,
                                       device_id=imp.device_id,
                                       message="Marked failed: source path gone after restart"))

        n = max(1, settings.worker_count)
        loop = asyncio.get_running_loop()
        self._tasks = [asyncio.create_task(self._run(loop), name=f"import-worker-{i}") for i in range(n)]
        log.info("Started %d import worker(s)", n)
        for import_id in to_resume:
            await self.queue.put(import_id)
        if to_resume:
            log.info("Auto-resuming %d import(s) after restart: %s", len(to_resume), to_resume)
        return self._tasks

    async def stop(self, tasks: list[asyncio.Task] | asyncio.Task) -> None:
        self._stopped = True
        if isinstance(tasks, asyncio.Task):
            tasks = [tasks]
        for _ in tasks:
            await self.queue.put(-1)
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
        except asyncio.TimeoutError:
            for t in tasks:
                t.cancel()

    async def enqueue(self, import_id: int) -> None:
        await self.queue.put(import_id)

    async def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        log.info("Import worker %s online", asyncio.current_task().get_name())
        while not self._stopped:
            import_id = await self.queue.get()
            if import_id == -1:
                break
            try:
                await asyncio.to_thread(self._process, import_id, loop)
            except Exception:
                log.exception("Worker error processing import %s", import_id)

    def _process(self, import_id: int, loop: asyncio.AbstractEventLoop) -> None:
        def progress(payload: dict) -> None:
            try:
                asyncio.run_coroutine_threadsafe(broker.publish(payload), loop).result(timeout=2)
            except Exception:
                pass  # broker fan-out is best-effort, never block the import

        with session_scope() as s:
            importer_mod.run_import(s, import_id, on_progress=progress)


import_worker = ImportWorker()
