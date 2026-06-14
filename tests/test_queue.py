"""Unit tests for the SQLite job queue backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.queue.db_queue import SQLiteJobQueue

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def queue(tmp_path: Path) -> SQLiteJobQueue:
    """Return a fresh SQLite queue backed by a temp directory (max 5 jobs)."""
    return SQLiteJobQueue(str(tmp_path), max_size=5)


# ---------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------


async def test_empty_queue_has_size_zero(queue: SQLiteJobQueue) -> None:
    assert await queue.size() == 0


async def test_size_counts_only_pending_jobs(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    await queue.enqueue("detect", "photo-2", "{}")
    job = await queue.dequeue()  # becomes "processing"
    assert job is not None
    assert await queue.size() == 1  # only photo-2 is still pending


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------


async def test_enqueue_increases_size(queue: SQLiteJobQueue) -> None:
    result = await queue.enqueue("detect", "photo-1", '{"photo_path": "/tmp/a.jpg"}')
    assert result is True
    assert await queue.size() == 1


async def test_enqueue_returns_false_when_full(queue: SQLiteJobQueue) -> None:
    for i in range(5):
        assert await queue.enqueue("detect", f"photo-{i}", "{}") is True
    assert await queue.enqueue("detect", "overflow", "{}") is False
    assert await queue.size() == 5


async def test_enqueue_stores_all_fields(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("cluster", "photo-x", '{"key": "val"}')
    job = await queue.dequeue()
    assert job is not None
    assert job.job_type == "cluster"
    assert job.photo_id == "photo-x"
    assert job.payload == '{"key": "val"}'


# ---------------------------------------------------------------------------
# dequeue
# ---------------------------------------------------------------------------


async def test_dequeue_returns_none_when_empty(queue: SQLiteJobQueue) -> None:
    assert await queue.dequeue() is None


async def test_dequeue_returns_oldest_job_first(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "first", "{}")
    await queue.enqueue("detect", "second", "{}")
    job = await queue.dequeue()
    assert job is not None
    assert job.photo_id == "first"


async def test_dequeue_removes_job_from_pending(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    await queue.dequeue()
    assert await queue.size() == 0  # now "processing", not "pending"


async def test_dequeue_assigns_unique_ids(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "a", "{}")
    await queue.enqueue("detect", "b", "{}")
    j1 = await queue.dequeue()
    j2 = await queue.dequeue()
    assert j1 is not None and j2 is not None
    assert j1.id != j2.id


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------


async def test_complete_removes_job_entirely(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    job = await queue.dequeue()
    assert job is not None
    await queue.complete(job.id)
    assert await queue.position("photo-1") is None


async def test_complete_is_idempotent(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    job = await queue.dequeue()
    assert job is not None
    await queue.complete(job.id)
    await queue.complete(job.id)  # second call must not raise


# ---------------------------------------------------------------------------
# purge
# ---------------------------------------------------------------------------


async def test_purge_removes_all_pending(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    await queue.enqueue("detect", "photo-2", "{}")
    await queue.purge()
    assert await queue.size() == 0


async def test_purge_does_not_affect_processing_jobs(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    job = await queue.dequeue()  # now "processing"
    assert job is not None
    await queue.purge()
    # "processing" job is still present
    assert await queue.position("photo-1") == 0


# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------


async def test_position_returns_none_for_unknown_photo(queue: SQLiteJobQueue) -> None:
    assert await queue.position("not-in-queue") is None


async def test_position_returns_one_for_single_pending(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    assert await queue.position("photo-1") == 1


async def test_position_reflects_fifo_rank(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-a", "{}")
    await queue.enqueue("detect", "photo-b", "{}")
    await queue.enqueue("detect", "photo-c", "{}")
    assert await queue.position("photo-a") == 1
    assert await queue.position("photo-b") == 2
    assert await queue.position("photo-c") == 3


async def test_position_adjusts_after_dequeue(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-a", "{}")
    await queue.enqueue("detect", "photo-b", "{}")
    job = await queue.dequeue()  # photo-a now processing
    assert job is not None
    assert await queue.position("photo-b") == 1


async def test_position_returns_zero_for_processing_job(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    job = await queue.dequeue()
    assert job is not None
    assert await queue.position("photo-1") == 0


async def test_position_returns_none_after_complete(queue: SQLiteJobQueue) -> None:
    await queue.enqueue("detect", "photo-1", "{}")
    job = await queue.dequeue()
    assert job is not None
    await queue.complete(job.id)
    assert await queue.position("photo-1") is None


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------


async def test_new_instance_resets_processing_to_pending(tmp_path: Path) -> None:
    """Jobs stuck in 'processing' after a crash must be retried on restart."""
    q1 = SQLiteJobQueue(str(tmp_path), max_size=10)
    await q1.enqueue("detect", "photo-1", "{}")
    job = await q1.dequeue()
    assert job is not None
    assert await q1.size() == 0  # 0 pending; 1 processing

    # Simulate restart: new instance on same DB
    q2 = SQLiteJobQueue(str(tmp_path), max_size=10)
    assert await q2.size() == 1
    assert await q2.position("photo-1") == 1
