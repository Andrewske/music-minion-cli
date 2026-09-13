"""Migration coverage for the canonical SoundCloud decision ledger."""

import sqlite3
from zoneinfo import ZoneInfo

import pytest

from music_minion.core.database import migrate_database

LOS_ANGELES = ZoneInfo("America/Los_Angeles")


@pytest.fixture(autouse=True)
def pinned_timezone(monkeypatch):
    """Month labels must not depend on the machine running the tests."""
    monkeypatch.setattr(
        "music_minion.core.database.configured_feed_timezone", lambda: LOS_ANGELES
    )


def _v60_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE discovery_artists (
            id INTEGER PRIMARY KEY,
            is_following INTEGER,
            ranking INTEGER
        );
        CREATE TABLE sc_feed_sync_state (id INTEGER PRIMARY KEY);
        CREATE TABLE discovery_tracks (
            id INTEGER PRIMARY KEY,
            soundcloud_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'unseen',
            first_seen TIMESTAMP,
            created_at TIMESTAMP
        );
        CREATE TABLE discovery_track_reposters (
            discovery_track_id INTEGER,
            discovery_artist_id INTEGER,
            reposted_at TIMESTAMP,
            seen_at TIMESTAMP
        );
        CREATE TABLE sc_artist_uploads (
            id INTEGER PRIMARY KEY,
            discovery_artist_id INTEGER,
            soundcloud_id TEXT UNIQUE NOT NULL,
            uploaded_at TEXT,
            status TEXT DEFAULT 'visible',
            rated_at TIMESTAMP,
            first_seen TIMESTAMP,
            sc_like_done INTEGER DEFAULT 0,
            sc_playlist_done INTEGER DEFAULT 0
        );
        """
    )
    return conn


def _seed_legacy_decisions(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO discovery_tracks
            (id, soundcloud_id, status, first_seen, created_at)
        VALUES (1, 'both', 'dismissed', '2026-01-01', '2026-01-01'),
               (2, 'repost-only', 'liked', '2026-03-01', '2026-03-01');
        INSERT INTO sc_artist_uploads
            (id, soundcloud_id, status, rated_at, first_seen,
             sc_like_done, sc_playlist_done)
        VALUES (1, 'both', 'liked', '2026-02-01 12:00:00', '2026-01-15', 1, 0),
               (2, 'hidden-only', 'hidden', '2026-04-01', '2026-04-01', 0, 0);
        """
    )


def test_migration_preserves_history_and_selects_one_current_label() -> None:
    conn = _v60_connection()
    _seed_legacy_decisions(conn)

    migrate_database(conn, 60)

    history = conn.execute(
        """SELECT decision, surface, is_current FROM sc_track_decisions
        WHERE soundcloud_id = 'both' ORDER BY decided_at, id"""
    ).fetchall()
    assert [tuple(row) for row in history] == [
        ("nope", "repost_builder_migration", 0),
        ("keep", "upload_feed_migration", 1),
    ]
    assert [
        tuple(row)
        for row in conn.execute(
            "SELECT soundcloud_id, decision FROM sc_current_training_decisions ORDER BY soundcloud_id"
        ).fetchall()
    ] == [("both", "keep"), ("repost-only", "keep")]
    assert (
        conn.execute(
            "SELECT workflow_state FROM discovery_tracks WHERE soundcloud_id = 'both'"
        ).fetchone()[0]
        == "processed"
    )
    jobs = conn.execute(
        """SELECT action_type, target_key, status FROM sc_feed_action_jobs
        WHERE soundcloud_id = 'both' ORDER BY action_type"""
    ).fetchall()
    assert [tuple(row) for row in jobs] == [
        ("like", "", "complete"),
        ("monthly_playlist", "Feb 26", "pending"),
    ]
    assert (
        conn.execute(
            "SELECT decision FROM sc_track_decisions WHERE soundcloud_id = 'hidden-only'"
        ).fetchone()[0]
        == "hide"
    )


def test_monthly_target_uses_local_calendar_not_utc() -> None:
    """A like at 8pm Jan 31 in Los Angeles is Feb 1 in UTC; the month is January."""
    conn = _v60_connection()
    conn.execute(
        """INSERT INTO sc_artist_uploads
        (soundcloud_id, status, rated_at, first_seen, sc_like_done, sc_playlist_done)
        VALUES ('late-night', 'liked', '2026-02-01 04:00:00', '2026-01-01', 1, 0)"""
    )

    migrate_database(conn, 60)

    target = conn.execute(
        """SELECT target_key FROM sc_feed_action_jobs
        WHERE soundcloud_id = 'late-night' AND action_type = 'monthly_playlist'"""
    ).fetchone()[0]
    assert target == "Jan 26"


def test_migration_is_idempotent_on_rerun() -> None:
    conn = _v60_connection()
    _seed_legacy_decisions(conn)

    migrate_database(conn, 60)
    migrate_database(conn, 61)

    counts = conn.execute(
        """SELECT COUNT(*), SUM(is_current) FROM sc_track_decisions
        WHERE soundcloud_id = 'both'"""
    ).fetchone()
    assert tuple(counts) == (2, 1)
    assert conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[0] == 2


def test_failed_migration_can_be_rolled_back_without_partial_schema() -> None:
    conn = _v60_connection()
    conn.execute(
        """INSERT INTO sc_artist_uploads
        (soundcloud_id, status, rated_at, first_seen)
        VALUES ('bad', 'liked', '2026-01-01', '2026-01-01')"""
    )
    # Deliberately incompatible pre-existing table forces the legacy copy to
    # fail after ALTER TABLE statements have run.
    conn.execute(
        """CREATE TABLE sc_track_decisions (
            id INTEGER PRIMARY KEY,
            soundcloud_id TEXT,
            decision TEXT CHECK (decision = 'impossible'),
            decided_at TIMESTAMP,
            surface TEXT,
            model_version TEXT,
            feature_snapshot TEXT,
            is_current INTEGER
        )"""
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        migrate_database(conn, 60)
    conn.rollback()

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(discovery_tracks)")
    }
    assert "workflow_state" not in columns
    assert conn.execute("SELECT COUNT(*) FROM sc_track_decisions").fetchone()[0] == 0
