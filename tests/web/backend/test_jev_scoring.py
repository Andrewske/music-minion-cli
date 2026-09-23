"""Jev keep-probability scoring: client, state builder, sync scorer, feed reads."""

from __future__ import annotations

import json
import sqlite3

import pytest

from music_minion.core.database import (
    _migrate_v62_decision_ledger,
    _migrate_v64_track_predictions,
)
from web.backend import jev_client, jev_scorer
from web.backend.jev_client import JevConfig, JevPrediction
from web.backend.queries import feed as feed_queries

MINIMAL_SCHEMA_SQL = """
CREATE TABLE discovery_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_user_id TEXT,
    slug TEXT,
    display_name TEXT,
    display_name_normalized TEXT,
    avatar_url TEXT,
    ranking INTEGER,
    is_following INTEGER DEFAULT 1,
    upload_keep_rate REAL,
    upload_rated_count REAL DEFAULT 0,
    repost_keep_rate REAL,
    repost_rated_count REAL DEFAULT 0
);
CREATE TABLE discovery_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_id TEXT UNIQUE,
    local_track_id INTEGER,
    title TEXT,
    artist_name TEXT,
    artwork_url TEXT,
    permalink_url TEXT,
    duration_ms INTEGER,
    genre TEXT,
    access TEXT,
    uploaded_at TEXT,
    released_at TEXT,
    first_seen TEXT,
    created_at TEXT,
    playlist_batch INTEGER,
    uploader_soundcloud_id TEXT,
    workflow_state TEXT,
    status TEXT DEFAULT 'unseen'
);
CREATE TABLE discovery_track_reposters (
    discovery_track_id INTEGER,
    discovery_artist_id INTEGER,
    reposted_at TEXT,
    seen_at TEXT,
    repost_time_precision TEXT DEFAULT 'approximate',
    PRIMARY KEY (discovery_track_id, discovery_artist_id)
);
CREATE TABLE sc_artist_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_artist_id INTEGER,
    soundcloud_id TEXT UNIQUE,
    local_track_id INTEGER,
    title TEXT,
    artwork_url TEXT,
    permalink_url TEXT,
    duration_ms INTEGER,
    genre TEXT,
    access TEXT,
    uploader_soundcloud_id TEXT,
    uploaded_at TEXT,
    released_at TEXT,
    first_seen TEXT,
    rated_at TEXT,
    status TEXT DEFAULT 'visible'
);
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    soundcloud_id TEXT,
    artist_normalized TEXT,
    local_path TEXT
);
CREATE TABLE ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER, rating_type TEXT, source TEXT
);
CREATE TABLE playlist_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, track_id INTEGER
);
CREATE TABLE sc_feed_action_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soundcloud_id TEXT, action_type TEXT, status TEXT,
    last_error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr("music_minion.core.database.get_database_path", lambda: path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(MINIMAL_SCHEMA_SQL)
    _migrate_v62_decision_ledger(conn)
    _migrate_v64_track_predictions(conn)
    conn.commit()
    conn.close()
    yield path


def _conn(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _seed_repost_track(conn, sc_id="t1", rank=5, keep_rate=0.4) -> None:
    conn.execute(
        """INSERT INTO discovery_artists
        (id, soundcloud_user_id, slug, display_name, ranking, is_following,
         repost_keep_rate, repost_rated_count)
        VALUES (1, 'u1', 'rep', 'Reposter One', ?, 1, ?, 12)""",
        (rank, keep_rate),
    )
    conn.execute(
        """INSERT INTO discovery_tracks
        (id, soundcloud_id, title, artist_name, duration_ms, genre, access,
         first_seen, released_at)
        VALUES (1, ?, 'Bass Anthem', 'Some Artist', 200000, 'dubstep',
                'playable', '2026-09-20 00:00:00', '2026-09-18T00:00:00Z')""",
        (sc_id,),
    )
    conn.execute(
        """INSERT INTO discovery_track_reposters
        (discovery_track_id, discovery_artist_id, reposted_at)
        VALUES (1, 1, '2026-09-20 01:00:00')"""
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def test_config_resolution(monkeypatch) -> None:
    monkeypatch.setenv("JEV_API_KEY", "sk-test")
    monkeypatch.setenv("JEV_BASE_URL", "https://gw.example.com/")
    monkeypatch.delenv("JEV_MODEL_ID", raising=False)
    config = jev_client.get_jev_config()
    assert config == JevConfig(
        "https://gw.example.com", "sk-test", jev_client.DEFAULT_MODEL_ID
    )


def test_config_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.setattr(jev_client, "_load_env_files", lambda: None)
    assert jev_client.get_jev_config() is None


def test_noul_request_and_response_parse() -> None:
    config = JevConfig("https://openrouter.ai/api", "k", "jev-latest")
    request = jev_client._build_noul_request(config, '{"x":1}', "Q?")
    assert request["model"] == "jev-latest"
    assert request["questions"] == {"keep": {"type": "noul", "instructions": "Q?"}}
    # Shape captured from a live OpenRouter /v1/systemone response (2026-09-23).
    parsed = jev_client._parse_noul_response(
        {
            "model": "typesafe/jev-1.13-20260917",
            "answers": {"keep": {"type": "noul", "noul": 0.73, "confidence": 0.9}},
        },
        "fallback",
    )
    assert parsed == JevPrediction(0.73, 0.9, "typesafe/jev-1.13-20260917", parsed.raw)


def test_response_without_answers_raises() -> None:
    with pytest.raises(ValueError):
        jev_client._parse_noul_response({"model": "m"}, "m")


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------


def test_taste_profile_version_is_content_hash() -> None:
    loaded = jev_scorer.load_taste_profile()
    assert loaded is not None
    text, version = loaded
    assert "taste profile" in text.lower()
    assert len(version) == 12
    assert version == jev_scorer.load_taste_profile()[1]


def test_build_state_includes_profile_and_semantics(db_path) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn)
    row = conn.execute(
        jev_scorer._CANDIDATES_SQL,
        {"model_id": "m", "profile_version": "v", "limit": 10},
    ).fetchone()
    from datetime import datetime, timezone

    state = jev_scorer.build_state(
        jev_scorer._track_state_dict(conn, row, datetime.now(timezone.utc)),
        "PROFILE TEXT",
    )
    payload = json.loads(state)
    assert payload["taste_profile"] == "PROFILE TEXT"
    track = payload["track"]
    assert track["title"] == "Bass Anthem"
    assert track["genre"] == "dubstep"
    assert track["reposters"][0]["name"] == "Reposter One"
    assert track["reposters"][0]["keep_rate"] == 0.4
    assert track["top200_reposter_count"] == 1
    assert track["event_type"] == "repost"
    conn.close()


# ---------------------------------------------------------------------------
# Sync-time scoring
# ---------------------------------------------------------------------------


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(
        jev_client,
        "get_jev_config",
        lambda: JevConfig("https://x", "k", "typesafe/jev-latest"),
    )


def test_score_new_tracks_inserts_and_skips_scored(
    db_path, configured, monkeypatch
) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn)
    conn.close()
    monkeypatch.setattr(
        jev_client,
        "ask_noul",
        lambda config, state, question, timeout_s=10.0: JevPrediction(
            0.66, 0.8, config.model_id, {}
        ),
    )
    assert jev_scorer.score_new_tracks(sleep_s=0) == 1
    assert jev_scorer.score_new_tracks(sleep_s=0) == 0  # already scored
    conn = _conn(db_path)
    rows = conn.execute("SELECT * FROM sc_track_predictions").fetchall()
    assert len(rows) == 1
    assert rows[0]["probability"] == 0.66
    assert rows[0]["model_id"] == "typesafe/jev-latest"
    assert json.loads(rows[0]["state_sent"])["track"]["title"] == "Bass Anthem"
    conn.close()


def test_score_new_tracks_survives_one_failure(
    db_path, configured, monkeypatch
) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn, sc_id="t1")
    conn.execute(
        """INSERT INTO discovery_tracks
        (id, soundcloud_id, title, access, first_seen)
        VALUES (2, 't2', 'Other', 'playable', '2026-09-21 00:00:00')"""
    )
    conn.execute(
        """INSERT INTO discovery_track_reposters
        (discovery_track_id, discovery_artist_id) VALUES (2, 1)"""
    )
    conn.commit()
    conn.close()
    calls = {"n": 0}

    def flaky(config, state, question, timeout_s=10.0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return JevPrediction(0.5, None, config.model_id, {})

    monkeypatch.setattr(jev_client, "ask_noul", flaky)
    assert jev_scorer.score_new_tracks(sleep_s=0) == 1


def test_score_new_tracks_without_config_is_noop(db_path, monkeypatch) -> None:
    monkeypatch.setattr(jev_client, "get_jev_config", lambda: None)
    assert jev_scorer.score_new_tracks(sleep_s=0) == 0


# ---------------------------------------------------------------------------
# Feed read path
# ---------------------------------------------------------------------------


def _predict(db_path, sc_id, probability, created_at) -> None:
    conn = _conn(db_path)
    conn.execute(
        """INSERT INTO sc_track_predictions
        (soundcloud_id, model_id, taste_profile_version, probability,
         state_sent, created_at)
        VALUES (?, 'm1', 'v1', ?, '{}', ?)""",
        (sc_id, probability, created_at),
    )
    conn.commit()
    conn.close()


def test_feed_page_exposes_latest_prediction(db_path) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn)
    conn.close()
    _predict(db_path, "t1", 0.2, "2026-09-20 00:00:00")
    _predict(db_path, "t1", 0.8, "2026-09-21 00:00:00")
    items = feed_queries.get_feed_page()
    assert items[0]["keep_probability"] == 0.8
    assert items[0]["prediction_model_version"] == "m1"


def test_feed_page_score_sort_and_min_score(db_path) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn, sc_id="t1")
    for i, sc_id in enumerate(("t2", "t3"), start=2):
        conn.execute(
            """INSERT INTO discovery_tracks
            (id, soundcloud_id, title, access, first_seen)
            VALUES (?, ?, ?, 'playable', ?)""",
            (i, sc_id, f"Track {sc_id}", f"2026-09-2{i} 00:00:00"),
        )
        conn.execute(
            """INSERT INTO discovery_track_reposters
            (discovery_track_id, discovery_artist_id) VALUES (?, 1)""",
            (i,),
        )
    conn.commit()
    conn.close()
    _predict(db_path, "t1", 0.9, "2026-09-21 00:00:00")
    _predict(db_path, "t2", 0.3, "2026-09-21 00:00:00")
    # t3 stays unscored: it must sort last and vanish under min_score.

    by_score = feed_queries.get_feed_page(sort="score")
    assert [item["soundcloud_id"] for item in by_score] == ["t1", "t2", "t3"]

    filtered = feed_queries.get_feed_page(min_score=0.5)
    assert [item["soundcloud_id"] for item in filtered] == ["t1"]

    # Keyset pagination under score sort is stable across pages.
    page_one = feed_queries.get_feed_page(sort="score", limit=1)
    page_two = feed_queries.get_feed_page(
        sort="score",
        limit=2,
        cursor_score=page_one[0]["keep_probability"],
        cursor_soundcloud_id=page_one[0]["soundcloud_id"],
    )
    assert [item["soundcloud_id"] for item in page_two] == ["t2", "t3"]


def test_record_decision_adopts_latest_prediction(db_path) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn)
    conn.close()
    _predict(db_path, "t1", 0.7, "2026-09-21 00:00:00")
    result = feed_queries.record_decision("t1", "keep", "test")
    assert result is not None
    assert result["model_version"] == "m1"
    assert result["feature_snapshot"] == "{}"


def test_record_decision_explicit_snapshot_wins(db_path) -> None:
    conn = _conn(db_path)
    _seed_repost_track(conn)
    conn.close()
    _predict(db_path, "t1", 0.7, "2026-09-21 00:00:00")
    result = feed_queries.record_decision(
        "t1", "keep", "test", model_version="explicit", feature_snapshot={"a": 1}
    )
    assert result is not None
    assert result["model_version"] == "explicit"
    assert result["feature_snapshot"] == {"a": 1}
