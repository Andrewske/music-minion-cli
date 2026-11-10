"""Multiple organizer sessions per playlist: park / activate / list / rename,
read-time reconciliation, and pull-on-link.

Runs against the per-test migrated SQLite DB provided by the root conftest.
"""

import sqlite3
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from web.backend.queries import buckets as bq
from web.backend.routers import buckets as buckets_router


@pytest.fixture(autouse=True)
def _no_sc_push(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the SoundCloud push worker out of tests."""
    for name in (
        "enqueue_sc_push_add",
        "enqueue_sc_push_remove",
        "enqueue_sc_push_bulk_sync",
    ):
        monkeypatch.setattr(bq, name, lambda *a, **k: None)


def _make_playlist(name: str, track_ids: list[int]) -> int:
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO playlists (name, type) VALUES (?, 'manual')", (name,)
        )
        playlist_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            [(playlist_id, tid, pos) for pos, tid in enumerate(track_ids)],
        )
        conn.commit()
    assert playlist_id is not None
    return playlist_id


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


def _remove_from_playlist(playlist_id: int, track_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        conn.commit()


def _add_to_playlist(playlist_id: int, track_id: int, position: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            (playlist_id, track_id, position),
        )
        conn.commit()


def _status(session_id: str) -> str:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT status FROM bucket_sessions WHERE id = ?", (session_id,)
        ).fetchone()["status"]


def _bucket_emojis(track_id: int) -> set[str]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT emoji_id FROM track_emojis WHERE track_id = ?", (track_id,)
        ).fetchall()
    return {r["emoji_id"] for r in rows}


@pytest.fixture
def tracks() -> list[int]:
    return _make_tracks(6)


@pytest.fixture
def playlist(tracks: list[int]) -> int:
    return _make_playlist("Reposts", tracks)


# === Schema ===


def test_v71_columns_and_index_exist() -> None:
    with get_db_connection() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bucket_sessions)")}
        idx = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='bucket_sessions'"
            )
        }
    assert {"name", "last_opened_at"} <= cols
    assert "idx_bucket_sessions_playlist_status" in idx


# === Session lifecycle ===


def test_get_or_create_resumes_and_sets_last_opened(
    playlist: int, tracks: list[int]
) -> None:
    first = bq.get_or_create_session(playlist)
    again = bq.get_or_create_session(playlist)

    assert again["id"] == first["id"]
    assert first["status"] == "active"
    assert first["name"] is None
    assert first["created_at"]
    assert first["unassigned_track_ids"] == tracks
    [summary] = bq.list_sessions(playlist)
    assert summary["last_opened_at"] is not None


def test_new_session_parks_old_and_starts_empty(
    playlist: int, tracks: list[int]
) -> None:
    old = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(old["id"], "Keep", "🔥", 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])

    new = bq.create_new_session(playlist, "  Dubstep split  ")

    assert new["id"] != old["id"]
    assert new["status"] == "active"
    assert new["name"] == "Dubstep split"
    assert new["buckets"] == []
    assert new["unassigned_track_ids"] == tracks
    assert _status(old["id"]) == "parked"
    # Parking leaves emojis and assignments alone
    assert "🔥" in _bucket_emojis(tracks[0])
    parked = bq.get_session_with_data(old["id"])
    assert parked is not None
    assert parked["buckets"][0]["track_ids"] == [tracks[0]]
    # get-or-create now resumes the new one
    assert bq.get_or_create_session(playlist)["id"] == new["id"]


def test_activate_swaps_active_session(playlist: int, tracks: list[int]) -> None:
    old = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(old["id"], "Keep", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[1])
    new = bq.create_new_session(playlist, None)

    reopened = bq.activate_session(old["id"])

    assert reopened is not None
    assert reopened["id"] == old["id"]
    assert reopened["status"] == "active"
    assert reopened["buckets"][0]["track_ids"] == [tracks[1]]
    assert tracks[1] not in reopened["unassigned_track_ids"]
    assert _status(new["id"]) == "parked"
    with get_db_connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM bucket_sessions WHERE playlist_id = ? AND status = 'active'",
            (playlist,),
        ).fetchone()[0]
    assert active == 1


def test_activate_already_active_is_noop(playlist: int) -> None:
    session = bq.get_or_create_session(playlist)
    result = bq.activate_session(session["id"])
    assert result is not None and result["status"] == "active"


def test_partial_unique_index_still_enforced(playlist: int) -> None:
    bq.get_or_create_session(playlist)
    with get_db_connection() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO bucket_sessions (id, playlist_id, status) VALUES ('x', ?, 'active')",
            (playlist,),
        )


def test_activate_applied_session(playlist: int) -> None:
    done = bq.get_or_create_session(playlist)
    assert bq.finalize_session(done["id"])
    fresh = bq.get_or_create_session(playlist)

    reopened = bq.activate_session(done["id"])

    assert reopened is not None and reopened["status"] == "active"
    assert _status(fresh["id"]) == "parked"


def test_discarded_cannot_be_activated(playlist: int) -> None:
    gone = bq.get_or_create_session(playlist)
    assert bq.discard_session(gone["id"])
    assert bq.activate_session(gone["id"]) is None
    assert bq.activate_session("missing") is None
    assert _status(gone["id"]) == "discarded"


def test_list_excludes_discarded_and_orders_by_last_opened(
    playlist: int, tracks: list[int]
) -> None:
    a = bq.create_new_session(playlist, "A")
    bucket = bq.create_bucket(a["id"], "Keep", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])
    bq.assign_track_to_bucket(bucket["id"], tracks[1])
    b = bq.create_new_session(playlist, "B")
    c = bq.create_new_session(playlist, "C")
    assert bq.discard_session(c["id"])
    bq.activate_session(a["id"])

    sessions = bq.list_sessions(playlist)

    assert [s["id"] for s in sessions] == [a["id"], b["id"]]
    assert sessions[0]["status"] == "active"
    assert sessions[1]["status"] == "parked"
    assert sessions[0]["bucket_count"] == 1
    assert sessions[0]["assigned_count"] == 2
    assert sessions[1]["bucket_count"] == 0
    assert set(sessions[0]) == {
        "id",
        "playlist_id",
        "name",
        "status",
        "created_at",
        "last_opened_at",
        "bucket_count",
        "assigned_count",
    }


def test_rename_session(playlist: int) -> None:
    session = bq.get_or_create_session(playlist)
    assert bq.rename_session(session["id"], "Vibes")
    assert bq.get_session_with_data(session["id"])["name"] == "Vibes"
    assert bq.rename_session(session["id"], "   ")
    assert bq.get_session_with_data(session["id"])["name"] is None
    assert bq.rename_session("missing", "x") is False


# === Read-time reconciliation ===


def test_track_leaving_playlist_is_hidden_then_returns(
    playlist: int, tracks: list[int]
) -> None:
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "Keep", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[2])

    _remove_from_playlist(playlist, tracks[2])
    resumed = bq.get_or_create_session(playlist)  # used to hard-delete here
    assert resumed["buckets"][0]["track_ids"] == []
    assert tracks[2] not in resumed["unassigned_track_ids"]
    assert bq.list_sessions(playlist)[0]["assigned_count"] == 0

    _add_to_playlist(playlist, tracks[2], 99)
    back = bq.get_or_create_session(playlist)
    assert back["buckets"][0]["track_ids"] == [tracks[2]]
    assert tracks[2] not in back["unassigned_track_ids"]
    assert bq.list_sessions(playlist)[0]["assigned_count"] == 1


def test_apply_ignores_hidden_tracks(playlist: int, tracks: list[int]) -> None:
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "Keep", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])
    bq.assign_track_to_bucket(bucket["id"], tracks[5])
    _remove_from_playlist(playlist, tracks[0])

    assert bq.apply_session(session["id"])

    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT track_id, position FROM playlist_tracks WHERE playlist_id = ? "
            "ORDER BY position",
            (playlist,),
        ).fetchall()
    assert [r["track_id"] for r in rows] == [tracks[5], *tracks[1:5]]
    assert [r["position"] for r in rows] == list(range(5))  # no gaps


# === Pull-on-link ===


def test_pullable_ids_and_pull_linked(playlist: int, tracks: list[int]) -> None:
    target = _make_playlist("Bangers", [tracks[4], tracks[1], tracks[3]])
    session = bq.get_or_create_session(playlist)
    other = bq.create_bucket(session["id"], "Other", None, 0)
    bq.assign_track_to_bucket(other["id"], tracks[3])
    bucket = bq.create_bucket(session["id"], "Bangers", "💥", 1)

    assert bq.get_pullable_track_ids(bucket["id"]) == []  # unlinked
    assert bq.link_bucket_to_playlist(bucket["id"], target)
    # Session-playlist order, skipping tracks[3] (already in "Other")
    assert bq.get_pullable_track_ids(bucket["id"]) == [tracks[1], tracks[4]]

    assert bq.pull_linked_tracks(bucket["id"]) == 2
    data = bq.get_session_with_data(session["id"])
    assert data is not None
    assert data["buckets"][1]["track_ids"] == [tracks[1], tracks[4]]
    assert "💥" in _bucket_emojis(tracks[1])
    assert bq.get_pullable_track_ids(bucket["id"]) == []
    assert bq.pull_linked_tracks(bucket["id"]) == 0
    assert bq.pull_linked_tracks("missing") is None


def test_new_session_pulls_from_playlist_linked_by_parked_session(
    playlist: int, tracks: list[int]
) -> None:
    target = _make_playlist("Keepers", [])
    old = bq.get_or_create_session(playlist)
    old_bucket = bq.create_bucket(old["id"], "Keepers", None, 0)
    bq.link_bucket_to_playlist(old_bucket["id"], target)
    bq.assign_track_to_bucket(old_bucket["id"], tracks[0])
    bq.assign_track_to_bucket(old_bucket["id"], tracks[2])

    new = bq.create_new_session(playlist, None)
    sorting = bq.create_bucket(new["id"], "Sorting", None, 0)
    bq.assign_track_to_bucket(sorting["id"], tracks[2])
    keepers = bq.create_bucket(new["id"], "Keepers again", None, 1)
    bq.link_bucket_to_playlist(keepers["id"], target)

    assert bq.get_pullable_track_ids(keepers["id"]) == [tracks[0]]
    assert bq.pull_linked_tracks(keepers["id"]) == 1
    assert _status(old["id"]) == "parked"
    parked = bq.get_session_with_data(old["id"])
    assert parked is not None
    assert parked["buckets"][0]["track_ids"] == [tracks[0], tracks[2]]


# === Router ===


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(buckets_router, "update_organizer_queue", AsyncMock())
    app = FastAPI()
    app.include_router(buckets_router.router)
    with TestClient(app) as c:
        yield c


def test_router_session_routes(
    client: TestClient, playlist: int, tracks: list[int]
) -> None:
    first = client.post("/api/buckets/sessions", json={"playlist_id": playlist})
    assert first.status_code == 200
    assert first.json()["name"] is None and first.json()["created_at"]

    new = client.post(
        "/api/buckets/sessions/new", json={"playlist_id": playlist, "name": "Split"}
    )
    assert new.status_code == 200, new.text
    body = new.json()
    assert body["name"] == "Split" and body["status"] == "active"
    assert body["unassigned_track_ids"] == tracks

    listed = client.get("/api/buckets/sessions", params={"playlist_id": playlist})
    assert listed.status_code == 200
    assert [s["id"] for s in listed.json()] == [body["id"], first.json()["id"]]

    act = client.post(f"/api/buckets/sessions/{first.json()['id']}/activate")
    assert act.status_code == 200 and act.json()["status"] == "active"

    ren = client.patch(f"/api/buckets/sessions/{body['id']}", json={"name": "X"})
    assert ren.status_code == 200 and ren.json() == {"renamed": True}
    assert (
        client.patch("/api/buckets/sessions/nope", json={"name": "X"}).status_code
        == 404
    )

    assert client.delete(f"/api/buckets/sessions/{body['id']}").status_code == 200
    assert (
        client.post(f"/api/buckets/sessions/{body['id']}/activate").status_code == 404
    )
    assert client.post("/api/buckets/sessions/nope/activate").status_code == 404
    # GET by id still works and is not shadowed by the literal routes
    got = client.get(f"/api/buckets/sessions/{first.json()['id']}")
    assert got.status_code == 200 and got.json()["status"] == "active"


def test_router_link_and_pull(
    client: TestClient, playlist: int, tracks: list[int]
) -> None:
    target = _make_playlist("Linked", [tracks[2], tracks[0]])
    session = client.post(
        "/api/buckets/sessions", json={"playlist_id": playlist}
    ).json()
    bucket = client.post(
        f"/api/buckets/sessions/{session['id']}/buckets", json={"name": "B"}
    ).json()

    linked = client.post(
        f"/api/buckets/{bucket['id']}/link", json={"playlist_id": target}
    )
    assert linked.status_code == 200
    assert linked.json() == {
        "linked": True,
        "pullable_track_ids": [tracks[0], tracks[2]],
    }

    pulled = client.post(f"/api/buckets/{bucket['id']}/pull-linked")
    assert pulled.status_code == 200 and pulled.json() == {"assigned": 2}
    buckets_router.update_organizer_queue.assert_awaited_with(session["id"])
    assert client.post("/api/buckets/nope/pull-linked").status_code == 404

    unlinked = client.post(
        f"/api/buckets/{bucket['id']}/link", json={"playlist_id": None}
    )
    assert unlinked.json() == {"linked": False, "pullable_track_ids": []}


def test_parking_does_not_run_discovery_feedback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, playlist: int
) -> None:
    feedback = AsyncMock()
    monkeypatch.setattr(buckets_router, "_update_discovery_feedback", feedback)
    old = client.post("/api/buckets/sessions", json={"playlist_id": playlist}).json()

    client.post("/api/buckets/sessions/new", json={"playlist_id": playlist})
    client.post(f"/api/buckets/sessions/{old['id']}/activate")

    feedback.assert_not_called()


# === Review fixes: shared linked-playlist membership, hidden rows, races ===


def _in_playlist(playlist_id: int, track_id: int) -> bool:
    with get_db_connection() as conn:
        return (
            conn.execute(
                "SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            ).fetchone()
            is not None
        )


def test_unassign_keeps_linked_membership_held_by_parked_session(
    playlist: int, tracks: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    removals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        bq, "enqueue_sc_push_remove", lambda p, t: removals.append((p, t))
    )
    target = _make_playlist("Shared", [])
    old = bq.get_or_create_session(playlist)
    old_bucket = bq.create_bucket(old["id"], "A", None, 0)
    bq.link_bucket_to_playlist(old_bucket["id"], target)
    bq.assign_track_to_bucket(old_bucket["id"], tracks[0])

    new = bq.create_new_session(playlist, None)
    new_bucket = bq.create_bucket(new["id"], "B", None, 0)
    bq.link_bucket_to_playlist(new_bucket["id"], target)
    assert bq.pull_linked_tracks(new_bucket["id"]) == 1

    assert bq.unassign_track(new_bucket["id"], tracks[0])

    assert _in_playlist(target, tracks[0])
    assert removals == []


def test_unassign_single_session_still_removes_from_linked(
    playlist: int, tracks: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    removals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        bq, "enqueue_sc_push_remove", lambda p, t: removals.append((p, t))
    )
    target = _make_playlist("Solo", [])
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "A", None, 0)
    bq.link_bucket_to_playlist(bucket["id"], target)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])
    assert _in_playlist(target, tracks[0])

    assert bq.unassign_track(bucket["id"], tracks[0])

    assert not _in_playlist(target, tracks[0])
    assert removals == [(target, tracks[0])]


def test_discarded_session_does_not_hold_linked_membership(
    playlist: int, tracks: list[int]
) -> None:
    target = _make_playlist("Gone", [])
    old = bq.get_or_create_session(playlist)
    old_bucket = bq.create_bucket(old["id"], "A", None, 0)
    bq.link_bucket_to_playlist(old_bucket["id"], target)
    bq.assign_track_to_bucket(old_bucket["id"], tracks[0])
    assert bq.discard_session(old["id"])

    new = bq.get_or_create_session(playlist)
    new_bucket = bq.create_bucket(new["id"], "B", None, 0)
    bq.link_bucket_to_playlist(new_bucket["id"], target)
    bq.pull_linked_tracks(new_bucket["id"])
    bq.unassign_track(new_bucket["id"], tracks[0])

    assert not _in_playlist(target, tracks[0])


def test_link_does_not_push_hidden_tracks(playlist: int, tracks: list[int]) -> None:
    target = _make_playlist("Push", [])
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "A", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])
    bq.assign_track_to_bucket(bucket["id"], tracks[1])
    _remove_from_playlist(playlist, tracks[0])

    assert bq.link_bucket_to_playlist(bucket["id"], target)

    assert not _in_playlist(target, tracks[0])
    assert _in_playlist(target, tracks[1])


def _bucket_positions(bucket_id: str) -> dict[int, int]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT track_id, position FROM bucket_tracks WHERE bucket_id = ?",
            (bucket_id,),
        ).fetchall()
    return {r["track_id"]: r["position"] for r in rows}


def test_shuffle_and_reorder_skip_hidden_rows(playlist: int, tracks: list[int]) -> None:
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "A", None, 0)
    for tid in tracks[:4]:
        bq.assign_track_to_bucket(bucket["id"], tid)
    _remove_from_playlist(playlist, tracks[0])
    visible = tracks[1:4]

    shuffled = bq.shuffle_bucket_tracks(bucket["id"])
    assert sorted(shuffled) == sorted(visible)
    assert _bucket_positions(bucket["id"])[tracks[0]] == 3

    assert bq.reorder_bucket_tracks(bucket["id"], list(reversed(visible)))
    positions = _bucket_positions(bucket["id"])
    assert [positions[t] for t in reversed(visible)] == [0, 1, 2]
    assert positions[tracks[0]] == 3

    _add_to_playlist(playlist, tracks[0], 99)
    data = bq.get_session_with_data(session["id"])
    assert data is not None
    assert data["buckets"][0]["track_ids"] == [*reversed(visible), tracks[0]]


def test_bulk_unassign_counts_visible_only(
    client: TestClient, playlist: int, tracks: list[int]
) -> None:
    session = bq.get_or_create_session(playlist)
    bucket = bq.create_bucket(session["id"], "A", None, 0)
    bq.assign_track_to_bucket(bucket["id"], tracks[0])
    bq.assign_track_to_bucket(bucket["id"], tracks[1])
    _remove_from_playlist(playlist, tracks[0])

    resp = client.delete(
        f"/api/buckets/sessions/{session['id']}/buckets/{bucket['id']}/tracks"
    )

    assert resp.status_code == 200
    assert resp.json()["tracks_unassigned"] == 1
    assert _bucket_positions(bucket["id"]) == {}


def test_activate_rechecks_discard_in_final_update(
    playlist: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A discard landing between the eligibility read and the UPDATE loses."""
    target = bq.get_or_create_session(playlist)
    current = bq.create_new_session(playlist, None)
    real_park = bq._park_active_session

    def park_then_discard(conn: sqlite3.Connection, playlist_id: int) -> None:
        real_park(conn, playlist_id)
        conn.execute(
            "UPDATE bucket_sessions SET status = 'discarded' WHERE id = ?",
            (target["id"],),
        )

    monkeypatch.setattr(bq, "_park_active_session", park_then_discard)

    assert bq.activate_session(target["id"]) is None
    # Whole transition rolled back: the interleaved write and the park
    assert _status(target["id"]) == "parked"
    assert _status(current["id"]) == "active"


def test_activate_waits_for_concurrent_discard(playlist: int) -> None:
    """BEGIN IMMEDIATE: activation blocks behind a writer, then sees the discard."""
    import threading

    from music_minion.core.database import get_database_path

    target = bq.get_or_create_session(playlist)
    bq.create_new_session(playlist, None)

    writer = sqlite3.connect(get_database_path(), timeout=30.0, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    result: list[object] = []
    thread = threading.Thread(
        target=lambda: result.append(bq.activate_session(target["id"]))
    )
    thread.start()
    thread.join(0.3)
    assert thread.is_alive()  # blocked on the write lock, not reading stale state
    writer.execute(
        "UPDATE bucket_sessions SET status = 'discarded' WHERE id = ?", (target["id"],)
    )
    writer.execute("COMMIT")
    writer.close()
    thread.join(10)

    assert result == [None]
    assert _status(target["id"]) == "discarded"
