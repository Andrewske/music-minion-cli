"""Role-specific artist quality (#60): attribution semantics and persistence."""

from __future__ import annotations

import sqlite3

import pytest

from music_minion.core.database import _migrate_v62_decision_ledger, migrate_database
from web.backend.artist_quality import (
    aggregate_artist_role_stats,
    bayesian_keep_rate,
    legacy_full_credit_stats,
    rate_or_prior,
    recalculate_artist_role_stats,
    role_attributions,
)
from web.backend.keep_decisions import ReposterEvent, TrackDecision

SCHEMA_SQL = """
CREATE TABLE discovery_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_user_id TEXT,
    slug TEXT,
    display_name TEXT,
    display_name_normalized TEXT,
    ranking INTEGER,
    tier TEXT,
    is_following INTEGER DEFAULT 1,
    hit_rate REAL DEFAULT 0,
    upload_keep_rate REAL,
    upload_rated_count REAL NOT NULL DEFAULT 0,
    repost_keep_rate REAL,
    repost_rated_count REAL NOT NULL DEFAULT 0
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
"""


def _decision(
    sc_id: str,
    label: int,
    uploader: int | None = None,
    reposters: tuple[int, ...] = (),
) -> TrackDecision:
    return TrackDecision(
        soundcloud_id=sc_id,
        label=label,
        event_type="both" if uploader and reposters else "repost",
        uploader_id=uploader,
        uploader_ranking=None,
        uploader_is_following=True,
        uploader_source="upload_event" if uploader else "none",
        duration_ms=200_000,
        title="t",
        genre=None,
        released_at=None,
        first_seen=None,
        playlist_batch=None,
        reposters=tuple(
            ReposterEvent(
                artist_id=a,
                ranking=None,
                is_following=True,
                event_at=None,
                seen_at=None,
            )
            for a in reposters
        ),
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    _migrate_v62_decision_ledger(connection)  # real ledger table, index and view
    yield connection
    connection.close()


def test_bayesian_rate_is_prior_when_cold_and_shrinks_small_samples() -> None:
    assert bayesian_keep_rate(0, 0) == pytest.approx(0.22)
    assert 0.22 < bayesian_keep_rate(1, 1) < 0.5
    assert bayesian_keep_rate(100, 100) > 0.9
    with pytest.raises(ValueError):
        bayesian_keep_rate(2, 1)


def test_rate_or_prior_distinguishes_null_from_measured_zero() -> None:
    assert rate_or_prior(None) == pytest.approx(0.22)
    assert rate_or_prior(0.0) == 0.0


def test_one_track_is_one_observation_split_across_reposters() -> None:
    attributions = role_attributions(
        _decision("a", 1, uploader=1, reposters=(2, 3, 4, 5))
    )
    assert attributions[0] == (1, "upload", 1.0)
    repost_weights = [w for _, role, w in attributions if role == "repost"]
    assert sum(repost_weights) == pytest.approx(1.0)
    assert repost_weights == pytest.approx([0.25] * 4)


def test_uploader_and_reposter_roles_are_kept_apart() -> None:
    decisions = [
        _decision("one", 1, uploader=1, reposters=(2, 3)),
        _decision("two", 0, uploader=1, reposters=(2,)),
        _decision("two", 1, uploader=1, reposters=(2,)),  # duplicate id ignored
        _decision("three", 1, uploader=2, reposters=()),
    ]
    stats = {(s.artist_id, s.role): s for s in aggregate_artist_role_stats(decisions)}
    assert stats[(1, "upload")].rated_weight == 2
    assert stats[(1, "upload")].kept_weight == 1
    assert (1, "repost") not in stats
    assert stats[(2, "upload")].rated_weight == 1
    assert stats[(2, "repost")].rated_weight == pytest.approx(1.5)
    assert stats[(2, "repost")].kept_weight == pytest.approx(0.5)
    assert stats[(3, "repost")].rated_weight == pytest.approx(0.5)
    assert stats[(3, "repost")].keep_rate == pytest.approx(bayesian_keep_rate(0.5, 0.5))


def test_legacy_full_credit_replays_every_track_per_actor() -> None:
    decisions = [_decision("one", 1, uploader=1, reposters=(2, 3, 4))]
    legacy = legacy_full_credit_stats(decisions)
    assert {aid: rated for aid, (_, rated, _) in legacy.items()} == {
        1: 1,
        2: 1,
        3: 1,
        4: 1,
    }
    separated = aggregate_artist_role_stats(decisions)
    assert sum(s.rated_weight for s in separated) == pytest.approx(2.0)


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO discovery_artists (id, slug, display_name, display_name_normalized, ranking, tier)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "up", "Up", "up", 3, "S"),
            (2, "re1", "Re1", "re1", 1, None),
            (3, "re2", "Re2", "re2", 400, "B"),
        ],
    )
    conn.executemany(
        "INSERT INTO discovery_tracks (id, soundcloud_id, artist_name, status, playlist_batch)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (10, "keep", "Up", "liked", 1),
            (11, "nope", "Other", "dismissed", 1),
            (12, "pending", "Other", "in_playlist", 2),
            (13, "unseen", "Other", "unseen", None),
        ],
    )
    conn.executemany(
        "INSERT INTO discovery_track_reposters (discovery_track_id, discovery_artist_id) VALUES (?, ?)",
        [(10, 2), (10, 3), (11, 2), (12, 2), (13, 3)],
    )
    # Legacy labels become ledger rows exactly as the v62 backfill does.
    _migrate_v62_decision_ledger(conn)


def test_recalculate_persists_rates_with_counts_and_keeps_rank_and_tier(conn) -> None:
    _seed(conn)
    assert recalculate_artist_role_stats(conn) == 3
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM discovery_artists")}
    # Uploader matched by name: one keep as uploader, never a reposter.
    assert rows[1]["upload_rated_count"] == 1
    assert rows[1]["upload_keep_rate"] == pytest.approx(bayesian_keep_rate(1, 1))
    assert rows[1]["repost_rated_count"] == 0
    assert rows[1]["repost_keep_rate"] is None
    # Reposter 2 shares "keep" with 3 and owns "nope"; undecided tracks ignored.
    assert rows[2]["repost_rated_count"] == pytest.approx(1.5)
    assert rows[2]["repost_keep_rate"] == pytest.approx(bayesian_keep_rate(0.5, 1.5))
    assert rows[3]["repost_rated_count"] == pytest.approx(0.5)
    # Editorial signals untouched.
    assert [(r["ranking"], r["tier"]) for r in rows.values()] == [
        (3, "S"),
        (1, None),
        (400, "B"),
    ]


def test_v63_migration_adds_role_columns_idempotently() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE discovery_artists (
            id INTEGER PRIMARY KEY, ranking INTEGER, is_following INTEGER
        );
        CREATE TABLE discovery_tracks (
            id INTEGER PRIMARY KEY, soundcloud_id TEXT,
            status TEXT DEFAULT 'unseen', first_seen TEXT, created_at TEXT
        );
        CREATE TABLE discovery_track_reposters (
            discovery_track_id INTEGER, discovery_artist_id INTEGER,
            reposted_at TEXT, seen_at TEXT
        );
        CREATE TABLE sc_artist_uploads (
            id INTEGER PRIMARY KEY, discovery_artist_id INTEGER,
            soundcloud_id TEXT, uploaded_at TEXT, status TEXT DEFAULT 'visible',
            rated_at TEXT, first_seen TEXT,
            sc_like_done INTEGER DEFAULT 0, sc_playlist_done INTEGER DEFAULT 0
        );
        CREATE TABLE sc_feed_sync_state (id INTEGER PRIMARY KEY);
        """
    )
    migrate_database(conn, 60)
    migrate_database(conn, 62)
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(discovery_artists)")
    }
    assert {
        "upload_keep_rate",
        "upload_rated_count",
        "repost_keep_rate",
        "repost_rated_count",
    } <= columns
