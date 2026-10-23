"""Tests for UTC timestamp serialization of API responses."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from web.backend.timestamps import (
    UtcJSONResponse,
    format_utc,
    normalize_timestamps,
    to_utc_iso,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-23 22:33:07", "2026-10-23T22:33:07Z"),
        ("2026-10-23T22:33:07", "2026-10-23T22:33:07Z"),
        ("2026-10-23T22:33:07.123456", "2026-10-23T22:33:07.123Z"),
        ("2026-10-23T22:33:07+00:00", "2026-10-23T22:33:07Z"),
        ("2026-10-23T22:33:07Z", "2026-10-23T22:33:07Z"),
        ("2026-10-23T15:33:07-07:00", "2026-10-23T22:33:07Z"),
        ("2026/10/23 22:33:07 +0000", "2026-10-23T22:33:07Z"),
    ],
)
def test_to_utc_iso_normalizes_stored_formats(raw: str, expected: str) -> None:
    assert to_utc_iso(raw) == expected


@pytest.mark.parametrize(
    "raw", ["2026-10-23", "2026", "", "not a date", "garbage-garbage-x"]
)
def test_to_utc_iso_leaves_non_timestamps_alone(raw: str) -> None:
    assert to_utc_iso(raw) == raw


def test_to_utc_iso_handles_none_and_datetimes() -> None:
    assert to_utc_iso(None) is None
    assert to_utc_iso(datetime(2026, 10, 23, 22, 33, 7)) == "2026-10-23T22:33:07Z"
    pdt = timezone(timedelta(hours=-7))
    assert (
        format_utc(datetime(2026, 10, 23, 15, 33, 7, tzinfo=pdt))
        == "2026-10-23T22:33:07Z"
    )


def test_normalize_timestamps_only_touches_timestamp_keys() -> None:
    content = {
        "started_at": "2026-10-23 22:33:07",
        "ended_at": None,
        "track_started_at": 1761258787.5,
        "title": "2026-10-23 22:33:07",
        "released_at": "2026-10-23",
        "nested": [{"first_seen": "2026-10-23 22:33:07", "count": 3}],
    }
    assert normalize_timestamps(content) == {
        "started_at": "2026-10-23T22:33:07Z",
        "ended_at": None,
        "track_started_at": 1761258787.5,
        "title": "2026-10-23 22:33:07",
        "released_at": "2026-10-23",
        "nested": [{"first_seen": "2026-10-23T22:33:07Z", "count": 3}],
    }
    # Pure: input untouched
    assert content["started_at"] == "2026-10-23 22:33:07"


class _Entry(BaseModel):
    started_at: str
    seen: datetime


def _client() -> TestClient:
    app = FastAPI(default_response_class=UtcJSONResponse)

    @app.get("/model", response_model=list[_Entry])
    def model_route() -> list[_Entry]:
        return [
            _Entry(started_at="2026-10-23 22:33:07", seen=datetime(2026, 1, 2, 3, 4, 5))
        ]

    @app.get("/dict")
    def dict_route() -> dict[str, object]:
        return {"rows": [{"added_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)}]}

    return TestClient(app)


def test_default_response_class_serializes_response_models() -> None:
    body = _client().get("/model").json()
    assert body == [
        {"started_at": "2026-10-23T22:33:07Z", "seen": "2026-01-02T03:04:05"}
    ]


def test_default_response_class_serializes_plain_dicts() -> None:
    body = _client().get("/dict").json()
    assert body == {"rows": [{"added_at": "2026-01-02T03:04:05Z"}]}


def test_history_endpoint_returns_utc_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from music_minion.domain.library.models import Track
    from music_minion.domain.radio import history as history_domain
    from web.backend.main import app

    entry = history_domain.HistoryEntry(
        id=1,
        track=Track(id=7, local_path=None, title="T", artist="A"),
        source_type="local",
        started_at=datetime(2026, 10, 23, 22, 33, 7),
        ended_at=None,
        duration_ms=0,
    )
    monkeypatch.setattr(history_domain, "get_history_entries", lambda **_: [entry])

    body = TestClient(app).get("/api/history").json()
    assert body[0]["started_at"] == "2026-10-23T22:33:07Z"
    assert body[0]["ended_at"] is None
