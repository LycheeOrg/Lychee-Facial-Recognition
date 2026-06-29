"""Tests for auto-dispatch of DBSCAN clustering after detection jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import AppSettings
from app.queue.worker import _maybe_dispatch_clustering

if TYPE_CHECKING:
    from app.queue.base import JobQueue


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def queue() -> JobQueue:
    m = AsyncMock()
    m.enqueue_if_idle.return_value = True
    return m  # type: ignore[return-value]


@pytest.fixture
def settings_enabled() -> AppSettings:
    m = MagicMock(spec=AppSettings)
    m.auto_dispatch_dbscan = True
    return m  # type: ignore[return-value]


@pytest.fixture
def settings_disabled() -> AppSettings:
    m = MagicMock(spec=AppSettings)
    m.auto_dispatch_dbscan = False
    return m  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# _maybe_dispatch_clustering
# ---------------------------------------------------------------------------


async def test_dispatches_cluster_when_queue_idle_and_enabled(
    queue: AsyncMock, settings_enabled: AppSettings
) -> None:
    queue.enqueue_if_idle.return_value = True

    await _maybe_dispatch_clustering(queue, settings_enabled)

    queue.enqueue_if_idle.assert_called_once_with(job_type="cluster", photo_id="", payload="{}")


async def test_does_not_dispatch_when_disabled(queue: AsyncMock, settings_disabled: AppSettings) -> None:
    await _maybe_dispatch_clustering(queue, settings_disabled)

    queue.enqueue_if_idle.assert_not_called()


async def test_does_not_enqueue_when_queue_not_idle(queue: AsyncMock, settings_enabled: AppSettings) -> None:
    queue.enqueue_if_idle.return_value = False

    await _maybe_dispatch_clustering(queue, settings_enabled)

    queue.enqueue_if_idle.assert_called_once()


# ---------------------------------------------------------------------------
# enqueue_if_idle — SQLite integration
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_queue(tmp_path: pytest.TempPathFactory) -> AsyncMock:
    from app.queue.db_queue import SQLiteJobQueue

    return SQLiteJobQueue(str(tmp_path), max_size=10)


async def test_enqueue_if_idle_succeeds_on_empty_queue(sqlite_queue: AsyncMock) -> None:
    result = await sqlite_queue.enqueue_if_idle("cluster", "", "{}")
    assert result is True
    assert await sqlite_queue.size() == 1
    job = await sqlite_queue.dequeue()
    assert job is not None
    assert job.job_type == "cluster"


async def test_enqueue_if_idle_rejected_when_pending_job_exists(sqlite_queue: AsyncMock) -> None:
    await sqlite_queue.enqueue("detect", "photo-1", "{}")

    result = await sqlite_queue.enqueue_if_idle("cluster", "", "{}")
    assert result is False


async def test_enqueue_if_idle_rejected_when_inflight_job_exists(sqlite_queue: AsyncMock) -> None:
    await sqlite_queue.enqueue("detect", "photo-1", "{}")
    await sqlite_queue.dequeue()  # moves to processing

    result = await sqlite_queue.enqueue_if_idle("cluster", "", "{}")
    assert result is False
