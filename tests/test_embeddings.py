"""Tests for the SQLite embedding store."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from app.embeddings.sqlite_store import SQLiteEmbeddingStore

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> SQLiteEmbeddingStore:
    """Return a fresh SQLite store backed by a temp directory."""
    return SQLiteEmbeddingStore(storage_path=str(tmp_path))


def _unit_vec(dim: int = 512, index: int = 0) -> list[float]:
    """Return a unit vector with a 1.0 at ``index`` and 0.0 elsewhere."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


# ---------------------------------------------------------------------------
# add / count
# ---------------------------------------------------------------------------


def test_add_increments_count(store: SQLiteEmbeddingStore) -> None:
    assert store.count() == 0
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")
    assert store.count() == 1
    store.add("face-2", _unit_vec(index=1), "photo-2", 100.0, "test/crop2.jpg")
    assert store.count() == 2


def test_add_upsert_does_not_duplicate(store: SQLiteEmbeddingStore) -> None:
    """Re-adding an existing lychee_face_id must not create a duplicate row."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")
    assert store.count() == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_entry(store: SQLiteEmbeddingStore) -> None:
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")
    store.delete("face-1")
    assert store.count() == 0


def test_delete_unknown_id_is_noop(store: SQLiteEmbeddingStore) -> None:
    """Deleting a non-existent ID must not raise."""
    store.delete("nonexistent")
    assert store.count() == 0


# ---------------------------------------------------------------------------
# similarity_search
# ---------------------------------------------------------------------------


def test_similarity_search_returns_identical_face(store: SQLiteEmbeddingStore) -> None:
    """An exact match should have similarity ≈ 1.0."""
    vec = _unit_vec(index=0)
    store.add("face-1", vec, "photo-1", 100.0, "test/crop1.jpg")

    results = store.similarity_search(vec, threshold=0.9, limit=10)
    assert len(results) == 1
    lychee_id, sim = results[0]
    assert lychee_id == "face-1"
    assert sim == pytest.approx(1.0, abs=1e-4)


def test_similarity_search_excludes_below_threshold(store: SQLiteEmbeddingStore) -> None:
    """Results below ``threshold`` must be excluded."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")

    # Query with an orthogonal vector - cosine similarity = 0.0
    query = _unit_vec(index=1)
    results = store.similarity_search(query, threshold=0.5, limit=10)
    assert results == []


def test_similarity_search_respects_limit(store: SQLiteEmbeddingStore) -> None:
    """At most ``limit`` results should be returned."""
    for i in range(20):
        # All vectors point in roughly the same direction → high similarity
        v = [1.0 / math.sqrt(512)] * 512
        store.add(f"face-{i}", v, f"photo-{i}", 100.0, f"test/crop{i}.jpg")

    results = store.similarity_search([1.0 / math.sqrt(512)] * 512, threshold=0.0, limit=5)
    assert len(results) <= 5


def test_similarity_search_ordered_descending(store: SQLiteEmbeddingStore) -> None:
    """Results must be ordered by descending similarity."""
    store.add("face-exact", _unit_vec(index=0), "photo-1", 100.0, "test/crop1.jpg")
    store.add("face-close", [0.9, 0.1] + [0.0] * 510, "photo-2", 100.0, "test/crop2.jpg")

    # Normalise the close vector
    norm = math.sqrt(0.9**2 + 0.1**2)
    close = [0.9 / norm, 0.1 / norm] + [0.0] * 510
    store.add("face-close-n", close, "photo-3", 100.0, "test/crop3.jpg")

    results = store.similarity_search(_unit_vec(index=0), threshold=0.0, limit=10)
    sims = [r[1] for r in results]
    assert sims == sorted(sims, reverse=True)


def test_empty_store_returns_no_results(store: SQLiteEmbeddingStore) -> None:
    results = store.similarity_search(_unit_vec(), threshold=0.0, limit=10)
    assert results == []


# ---------------------------------------------------------------------------
# sync_batch / purge_absent
# ---------------------------------------------------------------------------


def test_sync_batch_0_resets_and_marks(store: SQLiteEmbeddingStore) -> None:
    """batch=0 should reset all rows then mark the supplied IDs as present."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")
    store.add("face-2", _unit_vec(index=1), "photo-2", 100.0, "c2.jpg")
    store.add("face-3", _unit_vec(index=2), "photo-3", 100.0, "c3.jpg")

    marked = store.sync_batch(["face-1", "face-2"], batch=0)

    assert marked == 2
    # purge removes face-3 only
    deleted = store.purge_absent()
    assert deleted == 1
    assert store.count() == 2


def test_sync_batch_0_empty_face_ids_marks_all_absent(store: SQLiteEmbeddingStore) -> None:
    """batch=0 with empty list resets all rows; subsequent purge removes everything."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")
    store.add("face-2", _unit_vec(index=1), "photo-2", 100.0, "c2.jpg")

    marked = store.sync_batch([], batch=0)
    assert marked == 0

    deleted = store.purge_absent()
    assert deleted == 2
    assert store.count() == 0


def test_sync_batch_nonzero_only_marks_given_ids(store: SQLiteEmbeddingStore) -> None:
    """batch>0 must only set is_present=True for the supplied IDs."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")
    store.add("face-2", _unit_vec(index=1), "photo-2", 100.0, "c2.jpg")

    # Start a session: reset all, mark face-1
    store.sync_batch(["face-1"], batch=0)
    # Add face-2 in a later batch
    marked = store.sync_batch(["face-2"], batch=1)
    assert marked == 1

    # Nothing should be purged: both are marked present
    deleted = store.purge_absent()
    assert deleted == 0
    assert store.count() == 2


def test_purge_absent_safe_when_all_present(store: SQLiteEmbeddingStore) -> None:
    """Calling purge before any sync (all rows default to is_present=1) removes nothing."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")

    deleted = store.purge_absent()
    assert deleted == 0
    assert store.count() == 1


def test_sync_batch_idempotent(store: SQLiteEmbeddingStore) -> None:
    """Sending the same batch=1 request twice must not raise or double-count."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")
    store.sync_batch([], batch=0)  # reset all

    store.sync_batch(["face-1"], batch=1)
    marked = store.sync_batch(["face-1"], batch=1)  # repeat
    assert marked == 1  # rowcount reflects rows touched, not newly changed

    deleted = store.purge_absent()
    assert deleted == 0


def test_purge_absent_removes_vec_rows(store: SQLiteEmbeddingStore) -> None:
    """purge_absent must clean up vec_faces as well as face_meta."""
    store.add("face-1", _unit_vec(index=0), "photo-1", 100.0, "c1.jpg")
    store.add("face-2", _unit_vec(index=1), "photo-2", 100.0, "c2.jpg")

    store.sync_batch(["face-1"], batch=0)
    store.purge_absent()

    # After purge, similarity search should only find face-1
    results = store.similarity_search(_unit_vec(index=0), threshold=0.9, limit=10)
    assert len(results) == 1
    assert results[0][0] == "face-1"
