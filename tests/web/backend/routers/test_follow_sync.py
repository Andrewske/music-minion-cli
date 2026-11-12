"""Follow endpoint (SC mocked) and untiered review ordering."""

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from web.backend.routers import follow_sync

AUTH = ProviderState(config=ProviderConfig(name="soundcloud"), authenticated=True)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(follow_sync.router)
    return TestClient(app)


@pytest.fixture
def sc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Fake SC: records follow calls; follow result and user lookup are settable."""
    fake: dict[str, Any] = {"followed": [], "ok": True, "user": None, "raise": None}

    def follow(state: ProviderState, user_id: str) -> tuple[ProviderState, bool]:
        if fake["raise"]:
            raise fake["raise"]
        fake["followed"].append(user_id)
        return state, fake["ok"]

    monkeypatch.setattr(follow_sync, "get_web_provider_state", lambda: AUTH)
    monkeypatch.setattr(follow_sync, "follow_user", follow)
    monkeypatch.setattr(follow_sync, "get_user", lambda s, uid: (s, fake["user"]))
    return fake


def add_artist(slug: str, **cols: Any) -> int:
    values = {
        "slug": slug,
        "display_name": slug.upper(),
        "ranking": 1,
        "is_following": 1,
        "tier": "",
        **cols,
    }
    names = ", ".join(values)
    marks = ", ".join("?" * len(values))
    with get_db_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO discovery_artists ({names}) VALUES ({marks})",
            tuple(values.values()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)


def artist(artist_id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        return dict(
            conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (artist_id,)
            ).fetchone()
        )


class TestFollow:
    def test_follows_and_records_tier_c(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        sc["user"] = {"id": 42, "permalink": "wooli", "username": "Wooli"}
        response = client.post("/api/follow-suggestions/42/follow")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        row = artist(body["discovery_artist_id"])
        assert (row["soundcloud_user_id"], row["slug"], row["tier"]) == (
            "42",
            "wooli",
            "C",
        )
        assert row["is_following"] == 1 and row["followed_at"] is not None
        assert sc["followed"] == ["42"]

    def test_lookup_failure_still_records(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        response = client.post("/api/follow-suggestions/42/follow")
        assert response.status_code == 200
        assert (
            artist(response.json()["discovery_artist_id"])["soundcloud_user_id"] == "42"
        )

    def test_refusal_is_502_and_writes_nothing(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        sc["ok"] = False
        response = client.post("/api/follow-suggestions/42/follow")
        assert response.status_code == 502
        assert "refused" in response.json()["detail"]
        with get_db_connection() as conn:
            assert (
                conn.execute("SELECT COUNT(*) FROM discovery_artists").fetchone()[0]
                == 0
            )

    def test_sc_server_error_is_502(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        sc["raise"] = requests.HTTPError(response=MagicMock(status_code=503))
        assert client.post("/api/follow-suggestions/42/follow").status_code == 502

    def test_unreachable_is_503(self, client: TestClient, sc: dict[str, Any]) -> None:
        sc["raise"] = requests.ConnectionError()
        assert client.post("/api/follow-suggestions/42/follow").status_code == 503

    def test_rejects_name_keys(self, client: TestClient, sc: dict[str, Any]) -> None:
        response = client.post("/api/follow-suggestions/name:wooli/follow")
        assert response.status_code == 400
        assert sc["followed"] == []

    def test_unauthenticated_is_401(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(follow_sync, "get_web_provider_state", lambda: None)
        assert client.post("/api/follow-suggestions/42/follow").status_code == 401


class TestUntiered:
    def _get(self, client: TestClient) -> dict[str, list[dict[str, Any]]]:
        response = client.get("/api/follow-suggestions/untiered")
        assert response.status_code == 200
        return response.json()

    def test_recent_order(self, client: TestClient) -> None:
        add_artist("old", follow_order=5)
        add_artist("newest", followed_at="2026-11-10 10:00:00", follow_order=9)
        add_artist("newer", followed_at="2026-11-09 10:00:00")
        add_artist("first_in_response", follow_order=0)
        add_artist("no_signal")
        add_artist("tiered", tier="C", followed_at="2026-11-11 00:00:00")
        add_artist("null_tier", tier=None, follow_order=7)
        add_artist("unfollowed", is_following=0, follow_order=1)
        slugs = [a["slug"] for a in self._get(client)["recent"]]
        assert slugs == ["newest", "newer", "first_in_response", "old", "null_tier"]

    def test_rated_by_weighted_keep_rate(self, client: TestClient) -> None:
        add_artist(
            "few", upload_keep_rate=0.9, upload_rated_count=2, repost_rated_count=0
        )
        add_artist(
            "mixed",
            upload_keep_rate=0.6,
            upload_rated_count=2,
            repost_keep_rate=0.2,
            repost_rated_count=2,
        )
        add_artist(
            "high", upload_keep_rate=0.5, upload_rated_count=3, repost_rated_count=0
        )
        add_artist("tiered", tier="A", upload_keep_rate=0.9, upload_rated_count=9)
        rated = self._get(client)["rated"]
        assert [a["slug"] for a in rated] == ["high", "mixed"]
        assert rated[1]["rated_count"] == 4
        assert rated[1]["keep_rate"] == pytest.approx(0.4)

    def test_row_shape(self, client: TestClient) -> None:
        artist_id = add_artist("x", follow_order=0, avatar_url="a.jpg")
        row = self._get(client)["recent"][0]
        assert row == {
            "discovery_artist_id": artist_id,
            "display_name": "X",
            "slug": "x",
            "avatar_url": "a.jpg",
            "followed_at": None,
            "follow_order": 0,
            "rated_count": 0,
            "keep_rate": None,
        }
