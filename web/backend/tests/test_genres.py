"""Tests for genre API endpoints."""

from fastapi.testclient import TestClient

from web.backend.main import app

client = TestClient(app)


def test_create_genre_normalizes_name() -> None:
    response = client.post("/api/genres", json={"name": "  Deep House "})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "deep house"
    assert body["track_count"] == 0


def test_create_genre_returns_existing_on_duplicate() -> None:
    first = client.post("/api/genres", json={"name": "Garage"}).json()
    second = client.post("/api/genres", json={"name": "GARAGE"}).json()
    assert second["id"] == first["id"]


def test_create_genre_rejects_blank_name() -> None:
    response = client.post("/api/genres", json={"name": "   "})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]
