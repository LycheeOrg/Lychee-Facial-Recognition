"""Async queue consumer worker."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import AppSettings
    from app.queue.base import JobQueue

logger = logging.getLogger(__name__)


async def run_worker(queue: JobQueue, state: Any, settings: AppSettings) -> None:
    """Continuously dequeue and process jobs until cancelled.

    Intended to run as a long-lived asyncio task started during application
    lifespan.  One worker task per ``VISION_FACE_THREAD_POOL_SIZE`` is started
    so that CPU-bound inference threads are kept fully utilised.
    """
    while True:
        try:
            job = await queue.dequeue()
            if job is None:
                await asyncio.sleep(0.5)
                continue

            logger.info("Worker picked up job id=%d type=%s photo_id=%r", job.id, job.job_type, job.photo_id)
            try:
                if job.job_type == "detect":
                    await _handle_detect(job, state, settings)
                elif job.job_type == "cluster":
                    await _handle_cluster(state, settings)
                else:
                    logger.warning("Unknown job type %r — discarding", job.job_type)
            finally:
                await queue.complete(job.id)

            if job.job_type == "detect":
                await _maybe_dispatch_clustering(queue, settings)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Worker loop error — continuing")


async def _handle_detect(job: Any, state: Any, settings: AppSettings) -> None:
    from app.api.routes import _run_detection_job

    payload = json.loads(job.payload)
    await _run_detection_job(
        photo_id=job.photo_id,
        image_path=Path(payload["photo_path"]),
        detector=state.detector,
        store=state.store,
        executor=state.executor,
        settings=settings,
    )


async def _handle_cluster(state: Any, settings: AppSettings) -> None:
    from app.api.routes import _run_clustering_job

    await _run_clustering_job(
        store=state.store,
        executor=state.executor,
        settings=settings,
    )


async def _maybe_dispatch_clustering(queue: JobQueue, settings: AppSettings) -> None:
    """Atomically enqueue a clustering job when the queue is idle and auto-dispatch is enabled."""
    if not settings.auto_dispatch_dbscan:
        return

    enqueued = await queue.enqueue_if_idle(job_type="cluster", photo_id="", payload=json.dumps({}))
    if enqueued:
        logger.info("Queue idle after detect job — auto-dispatched DBSCAN clustering")
