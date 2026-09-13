"""Decision loading: labels, dedup, uploader resolution, decision-time proxies."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from web.backend.keep_decisions import (
    load_sync_run_starts,
    load_track_decisions,
    resolve_decision_time,
    timeline_track_decisions,
)

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


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
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


def _track(conn, sc_id, status, **fields) -> int:
    columns = ["soundcloud_id", "status", *fields]
    values = [sc_id, status, *fields.values()]
    cursor = conn.execute(
        f"INSERT INTO discovery_tracks ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
        values,
    )
    return cursor.lastrowid


def test_only_liked_and_dismissed_are_labels(conn) -> None:
    for sc_id, status in [
        ("keep", "liked"),
        ("nope", "dismissed"),
        ("pending", "in_playlist"),
        ("fresh", "unseen"),
    ]:
        _track(conn, sc_id, status)
    conn.execute(
        "INSERT INTO sc_artist_uploads (discovery_artist_id, soundcloud_id, status, uploaded_at)"
        " VALUES (1, 'hidden-upload', 'hidden', '2026-01-01 00:00:00')"
    )
    decisions = {d.soundcloud_id: d for d in load_track_decisions(conn)}
    assert set(decisions) == {"keep", "nope"}
    assert decisions["keep"].label == 1
    assert decisions["nope"].label == 0


def test_uploader_resolution_prefers_id_then_upload_event_then_name(conn) -> None:
    _track(conn, "by-id", "liked", artist_name="By Name!", uploader_soundcloud_id="u1")
    _track(conn, "by-upload", "liked", artist_name="By Name!")
    conn.execute(
        "INSERT INTO sc_artist_uploads (discovery_artist_id, soundcloud_id, status, uploaded_at)"
        " VALUES (3, 'by-upload', 'visible', '2026-01-01 00:00:00')"
    )
    _track(conn, "by-name", "dismissed", artist_name="by name")
    _track(conn, "unknown", "dismissed", artist_name="Nobody")
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


def test_upload_decision_wins_over_discovery_status_for_same_track(conn) -> None:
    _track(conn, "shared", "dismissed")
    conn.execute(
        "INSERT INTO sc_artist_uploads (discovery_artist_id, soundcloud_id, status, uploaded_at, rated_at)"
        " VALUES (1, 'shared', 'liked', '2026-01-01 00:00:00', '2026-02-01 12:00:00')"
    )
    decisions = load_track_decisions(conn)
    assert len(decisions) == 1
    assert decisions[0].label == 1
    assert decisions[0].decided_at_source == "upload_rated_at"
    assert decisions[0].decided_at == datetime(2026, 2, 1, 12, tzinfo=timezone.utc)


def test_reposters_attach_with_rank_time_and_precision(conn) -> None:
    track_id = _track(conn, "t", "liked")
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


def test_batch_decisions_are_stamped_with_the_next_sync_start(conn) -> None:
    _runs(conn)
    runs = load_sync_run_starts(conn)
    assert len(runs) == 3
    _track(conn, "batch1", "liked", playlist_batch=1)
    _track(conn, "batch2", "dismissed", playlist_batch=2)
    _track(conn, "open", "liked", playlist_batch=3)
    _track(conn, "nobatch", "liked", first_seen="2026-01-06 00:00:00")
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


def test_explicit_decision_time_is_never_overridden(conn) -> None:
    conn.execute(
        "INSERT INTO sc_artist_uploads (discovery_artist_id, soundcloud_id, status, uploaded_at, rated_at)"
        " VALUES (1, 'u', 'dismissed', '2026-01-01 00:00:00', '2026-01-03 00:00:00')"
    )
    decision = load_track_decisions(conn)[0]
    resolved = resolve_decision_time(
        decision,
        [datetime(2026, 1, 5, tzinfo=timezone.utc)],
        datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    assert resolved.decided_at == datetime(2026, 1, 3, tzinfo=timezone.utc)
