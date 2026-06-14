"""Tests for the /queue API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

_AUTH = {"X-API-Key": "test-api-key"}


# ---------------------------------------------------------------------------
# GET /queue
# ---------------------------------------------------------------------------


def test_queue_size_returns_pending_count(client: TestClient, mock_queue: AsyncMock) -> None:
    mock_queue.size.return_value = 7
    response = client.get("/queue", headers=_AUTH)
    assert response.status_code == 200
    assert response.json() == {"pending": 7}


def test_queue_size_returns_zero_when_empty(client: TestClient, mock_queue: AsyncMock) -> None:
    mock_queue.size.return_value = 0
    response = client.get("/queue", headers=_AUTH)
    assert response.status_code == 200
    assert response.json()["pending"] == 0


def test_queue_size_requires_api_key(client: TestClient) -> None:
    response = client.get("/queue")
    assert response.status_code == 422


def test_queue_size_rejects_wrong_key(client: TestClient) -> None:
    response = client.get("/queue", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /queue
# ---------------------------------------------------------------------------


def test_queue_purge_returns_204(client: TestClient, mock_queue: AsyncMock) -> None:
    response = client.delete("/queue", headers=_AUTH)
    assert response.status_code == 204
    assert response.content == b""


def test_queue_purge_calls_purge_once(client: TestClient, mock_queue: AsyncMock) -> None:
    client.delete("/queue", headers=_AUTH)
    mock_queue.purge.assert_called_once()


def test_queue_purge_requires_api_key(client: TestClient) -> None:
    response = client.delete("/queue")
    assert response.status_code == 422


def test_queue_purge_rejects_wrong_key(client: TestClient) -> None:
    response = client.delete("/queue", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /queue/{photo_id}
# ---------------------------------------------------------------------------


def test_queue_position_pending(client: TestClient, mock_queue: AsyncMock) -> None:
    mock_queue.position.return_value = 3
    response = client.get("/queue/photo-abc", headers=_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["photo_id"] == "photo-abc"
    assert data["position"] == 3


def test_queue_position_currently_processing(client: TestClient, mock_queue: AsyncMock) -> None:
    """position=0 means the job is currently being processed."""
    mock_queue.position.return_value = 0
    response = client.get("/queue/photo-abc", headers=_AUTH)
    assert response.status_code == 200
    assert response.json()["position"] == 0


def test_queue_position_absent_returns_404(client: TestClient, mock_queue: AsyncMock) -> None:
    """Absent photo (done or never submitted) must return 404."""
    mock_queue.position.return_value = None
    response = client.get("/queue/photo-done", headers=_AUTH)
    assert response.status_code == 404


def test_queue_position_requires_api_key(client: TestClient) -> None:
    response = client.get("/queue/photo-abc")
    assert response.status_code == 422


def test_queue_position_rejects_wrong_key(client: TestClient) -> None:
    response = client.get("/queue/photo-abc", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_queue_position_calls_backend_with_photo_id(client: TestClient, mock_queue: AsyncMock) -> None:
    mock_queue.position.return_value = 1
    client.get("/queue/specific-photo-id", headers=_AUTH)
    mock_queue.position.assert_called_once_with("specific-photo-id")
