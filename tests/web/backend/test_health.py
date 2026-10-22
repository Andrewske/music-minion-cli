"""Tests for the /health endpoint the deploy script gates on."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from web.backend import main


def test_health_ok_when_db_answers() -> None:
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_503_when_db_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_connection():
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(
        "music_minion.core.database.get_db_connection", broken_connection
    )

    response = TestClient(main.app).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
