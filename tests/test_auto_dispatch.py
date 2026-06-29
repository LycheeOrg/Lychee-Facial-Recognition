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
    m.size.return_value = 0
    m.enqueue.return_value = True
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


async def test_dispatches_cluster_when_queue_empty_and_enabled(queue: AsyncMock, settings_enabled: AppSettings) -> None:
    queue.size.return_value = 0

    await _maybe_dispatch_clustering(queue, settings_enabled)

    queue.enqueue.assert_called_once_with(job_type="cluster", photo_id="", payload="{}")


async def test_does_not_dispatch_when_disabled(queue: AsyncMock, settings_disabled: AppSettings) -> None:
    queue.size.return_value = 0

    await _maybe_dispatch_clustering(queue, settings_disabled)

    queue.enqueue.assert_not_called()
    queue.size.assert_not_called()


async def test_does_not_dispatch_when_queue_has_pending_jobs(queue: AsyncMock, settings_enabled: AppSettings) -> None:
    queue.size.return_value = 3

    await _maybe_dispatch_clustering(queue, settings_enabled)

    queue.enqueue.assert_not_called()


async def test_does_not_dispatch_when_single_job_pending(queue: AsyncMock, settings_enabled: AppSettings) -> None:
    queue.size.return_value = 1

    await _maybe_dispatch_clustering(queue, settings_enabled)

    queue.enqueue.assert_not_called()
