"""Decision loading from the ledger: labels, uploader resolution, decision times."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from music_minion.core.database import _migrate_v62_decision_ledger
from web.backend.keep_decisions import (
    load_sync_run_starts,
    load_track_decisions,
    resolve_decision_time,
    timeline_track_decisions,
)

# Legacy tables only; the ledger itself comes from the real migration helper.
SCHEMA_SQL = """
CREATE TABLE discovery_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_user_id TEXT,
    slug TEXT,
    display_name TEXT,
    display_name_normalized TEXT,
    ranking INTEGER,
    is_following INTEGER DEFAULT 1
);
CREATE TABLE discovery_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_id TEXT UNIQUE,
    title TEXT,
    artist_name TEXT,
    duration_ms INTEGER,
    genre TEXT,
    released_at TEXT,
    first_seen TEXT,
    created_at TEXT,
    playlist_batch INTEGER,
    uploader_soundcloud_id TEXT,
    status TEXT DEFAULT 'unseen'
);
CREATE TABLE discovery_track_reposters (
    discovery_track_id INTEGER,
    discovery_artist_id INTEGER,
    reposted_at TEXT,
    raw_reposted_at TEXT,
    seen_at TEXT,
    repost_time_precision TEXT DEFAULT 'approximate',
    PRIMARY KEY (discovery_track_id, discovery_artist_id)
);
CREATE TABLE sc_artist_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_artist_id INTEGER,
    soundcloud_id TEXT UNIQUE,
    title TEXT,
    duration_ms INTEGER,
    genre TEXT,
    uploaded_at TEXT,
    released_at TEXT,
    first_seen TEXT,
    rated_at TEXT,
    status TEXT DEFAULT 'visible'
);
CREATE TABLE discovery_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    tracks_added INTEGER DEFAULT 0,
    mixes_added INTEGER DEFAULT 0
);
"""

LIVE_AT = "2026-03-15T10:00:00+00:00"


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    _migrate_v62_decision_ledger(connection)  # real table, index and view
    connection.executemany(
        "INSERT INTO discovery_artists (id, soundcloud_user_id, slug, display_name,"
        " display_name_normalized, ranking, is_following) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "u1", "byid", "By Id", "by id", 10, 1),
            (2, "u2", "byname", "By Name!", "by name", 20, 0),
            (3, "u3", "reposter", "Reposter", "reposter", 5, 1),
        ],
    )
    yield connection
    connection.close()


def _track(conn, sc_id, status="in_playlist", **fields) -> int:
    columns = ["soundcloud_id", "status", *fields]
    values = [sc_id, status, *fields.values()]
    cursor = conn.execute(
        f"INSERT INTO discovery_tracks ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
        values,
    )
    return cursor.lastrowid


def _upload(conn, sc_id, artist_id=1, status="visible", **fields) -> None:
    columns = ["discovery_artist_id", "soundcloud_id", "status", "uploaded_at", *fields]
    values = [artist_id, sc_id, status, "2026-01-01 00:00:00", *fields.values()]
    conn.execute(
        f"INSERT INTO sc_artist_uploads ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
        values,
    )


def _decide(conn, sc_id, decision, decided_at=LIVE_AT, surface="repost_builder"):
    """Append a ledger row the way the live surfaces do (one current per track)."""
    conn.execute(
        "UPDATE sc_track_decisions SET is_current = 0 WHERE soundcloud_id = ?",
        (sc_id,),
    )
    conn.execute(
        "INSERT INTO sc_track_decisions (soundcloud_id, decision, decided_at, surface)"
        " VALUES (?, ?, ?, ?)",
        (sc_id, decision, decided_at, surface),
    )


def test_only_current_keep_and_nope_ledger_rows_are_labels(conn) -> None:
    for sc_id in ("keep", "nope", "hidden", "flipped", "pending", "fresh"):
        _track(conn, sc_id)
    _decide(conn, "keep", "keep")
    _decide(conn, "nope", "nope")
    _decide(conn, "hidden", "hide")
    _decide(conn, "flipped", "keep")
    _decide(conn, "flipped", "hide")  # hide supersedes the earlier keep
    _upload(conn, "hidden-upload", status="hidden")
    _decide(conn, "hidden-upload", "hide", surface="upload_feed")
    # Legacy status columns are never consulted.
    conn.execute(
        "UPDATE discovery_tracks SET status = 'liked' WHERE soundcloud_id = 'fresh'"
    )
    decisions = {d.soundcloud_id: d for d in load_track_decisions(conn)}
    assert set(decisions) == {"keep", "nope"}
    assert decisions["keep"].label == 1
    assert decisions["nope"].label == 0


def test_redecision_uses_only_the_current_row(conn) -> None:
    _track(conn, "changed")
    _decide(conn, "changed", "nope", decided_at="2026-03-01T00:00:00+00:00")
    _decide(conn, "changed", "keep", decided_at="2026-03-02T00:00:00+00:00")
    (decision,) = load_track_decisions(conn)
    assert decision.label == 1
    assert decision.decided_at == datetime(2026, 3, 2, tzinfo=timezone.utc)


def test_ledger_rows_without_a_known_track_are_skipped(conn) -> None:
    _decide(conn, "orphan", "keep")
    assert load_track_decisions(conn) == []


def test_uploader_resolution_prefers_id_then_upload_event_then_name(conn) -> None:
    _track(conn, "by-id", artist_name="By Name!", uploader_soundcloud_id="u1")
    _track(conn, "by-upload", artist_name="By Name!")
    _upload(conn, "by-upload", artist_id=3)
    _track(conn, "by-name", artist_name="by name")
    _track(conn, "unknown", artist_name="Nobody")
    for sc_id, decision in [
        ("by-id", "keep"),
        ("by-upload", "keep"),
        ("by-name", "nope"),
        ("unknown", "nope"),
    ]:
        _decide(conn, sc_id, decision)
    decisions = {d.soundcloud_id: d for d in load_track_decisions(conn)}
    assert (decisions["by-id"].uploader_id, decisions["by-id"].uploader_source) == (
        1,
        "soundcloud_id",
    )
    assert (
        decisions["by-upload"].uploader_id,
        decisions["by-upload"].uploader_source,
    ) == (3, "upload_event")
    assert decisions["by-upload"].event_type == "release"
    assert (decisions["by-name"].uploader_id, decisions["by-name"].uploader_source) == (
        2,
        "name_match",
    )
    assert decisions["by-name"].uploader_is_following is False
    assert (decisions["unknown"].uploader_id, decisions["unknown"].uploader_source) == (
        None,
        "none",
    )


def test_upload_only_track_takes_metadata_from_the_upload_row(conn) -> None:
    _upload(
        conn,
        "feed-only",
        artist_id=1,
        status="liked",
        title="Feed Track",
        duration_ms=123_000,
        genre="House",
        first_seen="2026-01-02 00:00:00",
        rated_at=LIVE_AT,
    )
    _decide(conn, "feed-only", "keep", surface="upload_feed")
    (decision,) = load_track_decisions(conn)
    assert (decision.title, decision.duration_ms, decision.genre) == (
        "Feed Track",
        123_000,
        "House",
    )
    assert decision.event_type == "release"
    assert decision.uploader_id == 1
    assert decision.released_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert decision.first_seen == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert decision.playlist_batch is None
    assert decision.decided_at_source == "ledger"


def test_live_surfaces_stamp_the_real_decision_time(conn) -> None:
    _track(conn, "builder", playlist_batch=1)
    _decide(conn, "builder", "keep", decided_at="2026-03-15T10:00:00.123456+00:00")
    (decision,) = load_track_decisions(conn)
    assert decision.decided_at_source == "ledger"
    assert decision.decided_at == datetime(
        2026, 3, 15, 10, 0, 0, 123456, tzinfo=timezone.utc
    )
    # resolve_decision_time never overrides an authoritative stamp.
    resolved = resolve_decision_time(
        decision,
        [datetime(2026, 1, 5, tzinfo=timezone.utc)],
        datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    assert resolved.decided_at == decision.decided_at


def test_migrated_rows_only_trust_a_real_upload_rated_at(conn) -> None:
    """The v62 backfill stamps ingestion time for builder rows; ignore it."""
    _track(
        conn,
        "builder",
        status="liked",
        first_seen="2026-01-06 00:00:00",
        playlist_batch=1,
    )
    _upload(
        conn,
        "rated-upload",
        status="dismissed",
        first_seen="2026-01-01 00:00:00",
        rated_at="2026-01-03 00:00:00",
    )
    _upload(conn, "unrated-upload", status="liked", first_seen="2026-01-04 00:00:00")
    _migrate_v62_decision_ledger(conn)
    surfaces = {
        row["soundcloud_id"]: row["surface"]
        for row in conn.execute("SELECT soundcloud_id, surface FROM sc_track_decisions")
    }
    assert surfaces == {
        "builder": "repost_builder_migration",
        "rated-upload": "upload_feed_migration",
        "unrated-upload": "upload_feed_migration",
    }
    decisions = {d.soundcloud_id: d for d in load_track_decisions(conn)}
    assert decisions["builder"].label == 1
    assert (
        decisions["builder"].decided_at,
        decisions["builder"].decided_at_source,
    ) == (
        None,
        "unknown",
    )
    assert decisions["rated-upload"].decided_at_source == "upload_rated_at"
    assert decisions["rated-upload"].decided_at == datetime(
        2026, 1, 3, tzinfo=timezone.utc
    )
    assert decisions["unrated-upload"].decided_at_source == "unknown"


def test_reposters_attach_with_rank_time_and_precision(conn) -> None:
    track_id = _track(conn, "t")
    _decide(conn, "t", "keep")
    conn.executemany(
        "INSERT INTO discovery_track_reposters (discovery_track_id, discovery_artist_id,"
        " reposted_at, raw_reposted_at, seen_at, repost_time_precision) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                track_id,
                3,
                "2026/03/01 10:00:00 +0000",
                "2026/03/01 10:00:00 +0000",
                "2026-03-02 00:00:00",
                "exact",
            ),
            (
                track_id,
                1,
                None,
                "2026/02/01 10:00:00 +0000",
                "2026-03-02 00:00:00",
                "approximate",
            ),
        ],
    )
    decision = load_track_decisions(conn)[0]
    by_artist = {event.artist_id: event for event in decision.reposters}
    assert by_artist[3].ranking == 5 and by_artist[3].exact_time
    assert by_artist[1].event_at == datetime(2026, 2, 1, 10, tzinfo=timezone.utc)
    assert not by_artist[1].exact_time
    assert decision.event_type == "repost"


def test_uploaded_and_reposted_track_is_both(conn) -> None:
    track_id = _track(conn, "shared")
    _upload(conn, "shared", artist_id=1)
    conn.execute(
        "INSERT INTO discovery_track_reposters (discovery_track_id, discovery_artist_id)"
        " VALUES (?, 3)",
        (track_id,),
    )
    _decide(conn, "shared", "keep", surface="upload_feed")
    (decision,) = load_track_decisions(conn)
    assert decision.event_type == "both"
    assert decision.uploader_source == "upload_event"
    assert [event.artist_id for event in decision.reposters] == [3]


def _runs(conn) -> None:
    conn.executemany(
        "INSERT INTO discovery_sync_log (started_at, tracks_added) VALUES (?, ?)",
        [
            ("2026-01-01T00:00:00+00:00", 0),  # no batch created
            ("2026-01-05T00:00:00+00:00", 50),  # batch 1
            ("2026-01-10T00:00:00+00:00", 50),  # batch 2
            ("2026-01-20T00:00:00+00:00", 50),  # batch 3 (open)
        ],
    )


def test_migrated_batch_decisions_are_stamped_with_the_next_sync_start(conn) -> None:
    _runs(conn)
    runs = load_sync_run_starts(conn)
    assert len(runs) == 3
    _track(conn, "batch1", status="liked", playlist_batch=1, first_seen="2026-01-02")
    _track(
        conn, "batch2", status="dismissed", playlist_batch=2, first_seen="2026-01-06"
    )
    _track(conn, "open", status="liked", playlist_batch=3, first_seen="2026-01-11")
    _track(conn, "nobatch", status="liked", first_seen="2026-01-06 00:00:00")
    _migrate_v62_decision_ledger(conn)
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    decisions = {d.soundcloud_id: d for d in timeline_track_decisions(conn, now=now)}
    assert decisions["batch1"].decided_at == datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert decisions["batch1"].decided_at_source == "next_sync_after_batch"
    assert decisions["batch2"].decided_at == datetime(2026, 1, 20, tzinfo=timezone.utc)
    assert decisions["open"].decided_at == now
    assert decisions["open"].decided_at_source == "open_batch_now"
    assert decisions["nobatch"].decided_at == datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert decisions["nobatch"].decided_at_source == "next_sync_after_first_seen"
    ordered = [d.soundcloud_id for d in timeline_track_decisions(conn, now=now)]
    assert ordered == ["batch1", "nobatch", "batch2", "open"]


def test_timeline_mixes_ledger_stamps_with_migration_proxies(conn) -> None:
    _runs(conn)
    _track(conn, "migrated", status="liked", playlist_batch=1, first_seen="2026-01-02")
    _migrate_v62_decision_ledger(conn)
    _track(conn, "live", playlist_batch=3)
    _decide(conn, "live", "nope", decided_at="2026-01-12T00:00:00+00:00")
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    ordered = [
        (d.soundcloud_id, d.decided_at_source)
        for d in timeline_track_decisions(conn, now=now)
    ]
    assert ordered == [("migrated", "next_sync_after_batch"), ("live", "ledger")]
