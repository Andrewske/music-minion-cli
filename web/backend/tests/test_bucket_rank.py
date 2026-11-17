"""Organizer "Apply rating": bucket order -> playlist ELO, with stack undo.

Runs against the per-test migrated SQLite DB provided by the root conftest.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from web.backend.queries import bucket_rank as br
from web.backend.queries import buckets as bq
from web.backend.routers import buckets as buckets_router
from web.backend.routers import playlists as playlists_router


@pytest.fixture(autouse=True)
def _no_sc_push(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "enqueue_sc_push_add",
        "enqueue_sc_push_remove",
        "enqueue_sc_push_bulk_sync",
    ):
        monkeypatch.setattr(bq, name, lambda *a, **k: None)


def _make_tracks(n: int) -> list[int]:
    with get_db_connection() as conn:
        ids = [
            conn.execute(
                "INSERT INTO tracks (title, artist) VALUES (?, 'a')", (f"t{i}",)
            ).lastrowid
            for i in range(n)
        ]
        conn.commit()
    return [i for i in ids if i is not None]


def _make_playlist(track_ids: list[int]) -> int:
    with get_db_connection() as conn:
        cur = conn.execute("INSERT INTO playlists (name, type) VALUES ('P', 'manual')")
        conn.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            [(cur.lastrowid, tid, pos) for pos, tid in enumerate(track_ids)],
        )
        conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _make_bucket(playlist_id: int, track_ids: list[int], name: str = "B") -> str:
    session = bq.get_or_create_session(playlist_id)
    bucket = bq.create_bucket(session["id"], name, None, 0)
    for tid in track_ids:
        bq.assign_track_to_bucket(bucket["id"], tid)
    bq.reorder_bucket_tracks(bucket["id"], track_ids)
    return bucket["id"]


def _set_rating(playlist_id: int, track_id: int, rating: float, count: int = 0) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO playlist_elo_ratings
                (track_id, playlist_id, rating, comparison_count, wins)
            VALUES (?, ?, ?, ?, 0)
            """,
            (track_id, playlist_id, rating, count),
        )
        conn.commit()


def _ratings(playlist_id: int) -> dict[int, tuple[float, int]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT track_id, rating, comparison_count FROM playlist_elo_ratings "
            "WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchall()
    return {r["track_id"]: (r["rating"], r["comparison_count"]) for r in rows}


def _history_count() -> int:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM playlist_comparison_history"
        ).fetchone()[0]


@pytest.fixture
def tracks() -> list[int]:
    return _make_tracks(4)


@pytest.fixture
def playlist(tracks: list[int]) -> int:
    return _make_playlist(tracks)


def test_apply_redistributes_and_keeps_counters(
    playlist: int, tracks: list[int]
) -> None:
    a, b, c, _ = tracks
    _set_rating(playlist, a, 1400.0, count=5)
    _set_rating(playlist, b, 1600.0, count=7)
    _set_rating(playlist, c, 1500.0, count=2)
    bucket = _make_bucket(playlist, [a, b, c])

    result = br.apply_bucket_rating(bucket, [a, b, c])

    assert result["method"] == "redistribute"
    assert _ratings(playlist) == {
        a: (1600.0, 5),
        b: (1500.0, 7),
        c: (1400.0, 2),
    }
    assert _history_count() == 0


def test_apply_unrated_bucket_uses_band_and_undo_deletes_created_rows(
    playlist: int, tracks: list[int]
) -> None:
    a, b, c, _ = tracks
    bucket = _make_bucket(playlist, [a, b, c])

    result = br.apply_bucket_rating(bucket, [a, b, c])
    assert result["method"] == "band"
    assert {k: v[0] for k, v in _ratings(playlist).items()} == {
        a: 1600.0,
        b: 1500.0,
        c: 1400.0,
    }

    assert br.undo_bucket_rating(result["application_id"]) == {
        "restored": 3,
        "skipped": 0,
    }
    assert _ratings(playlist) == {}


def test_hidden_tracks_are_skipped(playlist: int, tracks: list[int]) -> None:
    a, b, c, _ = tracks
    bucket = _make_bucket(playlist, [a, b, c])
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist, b),
        )
        conn.commit()

    preview = br.preview_bucket_rating(bucket)
    assert preview["track_ids"] == [a, c]


def test_stale_order_is_conflict_with_no_writes(
    playlist: int, tracks: list[int]
) -> None:
    a, b, c, _ = tracks
    bucket = _make_bucket(playlist, [a, b, c])

    with pytest.raises(br.RankConflictError):
        br.apply_bucket_rating(bucket, [b, a, c])
    assert _ratings(playlist) == {}


def test_undo_skips_tracks_compared_since(playlist: int, tracks: list[int]) -> None:
    a, b, _, _ = tracks
    _set_rating(playlist, a, 1450.0, count=3)
    _set_rating(playlist, b, 1550.0, count=3)
    bucket = _make_bucket(playlist, [a, b])
    app_id = br.apply_bucket_rating(bucket, [a, b])["application_id"]
    _set_rating(playlist, b, 1450.0, count=4)  # a real comparison happened

    assert br.undo_bucket_rating(app_id) == {"restored": 1, "skipped": 1}
    assert _ratings(playlist) == {a: (1450.0, 3), b: (1450.0, 4)}

    with pytest.raises(br.RankConflictError, match="already undone"):
        br.undo_bucket_rating(app_id)


def test_undo_is_a_stack_across_overlapping_buckets(
    playlist: int, tracks: list[int]
) -> None:
    a, b, c, _ = tracks
    first = _make_bucket(playlist, [a, b], "First")
    second = _make_bucket(playlist, [b, c], "Second")
    app_a = br.apply_bucket_rating(first, [a, b])["application_id"]
    app_b = br.apply_bucket_rating(second, [b, c])["application_id"]

    with pytest.raises(br.RankConflictError, match="newer"):
        br.undo_bucket_rating(app_a)

    br.undo_bucket_rating(app_b)
    br.undo_bucket_rating(app_a)
    assert _ratings(playlist) == {}


# === Router ===


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(buckets_router, "update_organizer_queue", AsyncMock())
    app = FastAPI()
    app.include_router(buckets_router.router)
    with TestClient(app) as c:
        yield c


def test_router_preview_apply_undo(
    client: TestClient, playlist: int, tracks: list[int]
) -> None:
    a, b, _, _ = tracks
    bucket = _make_bucket(playlist, [a, b])

    preview = client.get(f"/api/buckets/{bucket}/rating/preview").json()
    assert preview["rows"][0] == {"track_id": a, "before": 1500.0, "after": 1600.0}

    stale = client.post(
        f"/api/buckets/{bucket}/rating/apply", json={"track_ids": [b, a]}
    )
    assert stale.status_code == 409

    applied = client.post(
        f"/api/buckets/{bucket}/rating/apply", json={"track_ids": preview["track_ids"]}
    )
    assert applied.status_code == 200
    app_id = applied.json()["application_id"]

    undo = client.post(f"/api/buckets/rating-applications/{app_id}/undo")
    assert undo.json() == {"restored": 2, "skipped": 0}


def test_router_errors(client: TestClient, playlist: int, tracks: list[int]) -> None:
    assert client.get("/api/buckets/nope/rating/preview").status_code == 404
    single = _make_bucket(playlist, [tracks[0]])
    assert client.get(f"/api/buckets/{single}/rating/preview").status_code == 400
    assert client.post("/api/buckets/rating-applications/nope/undo").status_code == 404


def test_reapplying_same_order_writes_nothing(playlist: int, tracks: list[int]) -> None:
    a, b, _, _ = tracks
    bucket = _make_bucket(playlist, [a, b])
    first = br.apply_bucket_rating(bucket, [a, b])["application_id"]

    again = br.apply_bucket_rating(bucket, [a, b])
    assert again["application_id"] is None

    # The real apply is still the newest, so it stays undoable
    assert br.undo_bucket_rating(first) == {"restored": 2, "skipped": 0}


def test_router_apply_and_undo_drop_tracks_cache(
    client: TestClient, playlist: int, tracks: list[int]
) -> None:
    a, b, _, _ = tracks
    bucket = _make_bucket(playlist, [a, b])
    playlists_router._playlist_tracks_cache[(playlist,)] = (0.0, ([], 0))
    applied = client.post(
        f"/api/buckets/{bucket}/rating/apply", json={"track_ids": [a, b]}
    ).json()
    assert playlists_router._playlist_tracks_cache == {}

    playlists_router._playlist_tracks_cache[(playlist,)] = (0.0, ([], 0))
    client.post(f"/api/buckets/rating-applications/{applied['application_id']}/undo")
    assert playlists_router._playlist_tracks_cache == {}
