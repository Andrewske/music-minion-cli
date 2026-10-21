"""Not for feed (#30): rule matching, flags, rescue, and flag exclusions."""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import _migrate_v68_feed_flags, get_db_connection
from tests.test_feed_uploads import _insert_artist, _insert_upload, test_db  # noqa: F401
from web.backend.feed_filter_rules import (
    first_matching_rule,
    rule_matches,
    rule_precision,
    validate_rule,
)

DURATION_RULE = {"id": 1, "kind": "duration_min", "threshold": 15.0, "enabled": True}


def _regex_rule(pattern: str, rule_id: int = 2) -> dict:
    return {"id": rule_id, "kind": "title_regex", "pattern": pattern, "enabled": True}


def _seed_rules() -> dict[str, dict]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _migrate_v68_feed_flags(conn)
    rows = conn.execute("SELECT * FROM feed_filter_rules").fetchall()
    return {row["seed_key"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Pure rule matching
# ---------------------------------------------------------------------------


class TestRuleMatching:
    def test_duration_rule_catches_only_longer_tracks(self) -> None:
        assert rule_matches({"duration_ms": 15 * 60_000 + 1}, DURATION_RULE)
        assert not rule_matches({"duration_ms": 15 * 60_000}, DURATION_RULE)
        assert not rule_matches({"duration_ms": None}, DURATION_RULE)

    def test_title_regex_is_case_insensitive(self) -> None:
        rule = _regex_rule(r"boiler room")
        assert rule_matches({"title": "DJ X | BOILER ROOM Berlin"}, rule)
        assert not rule_matches({"title": None}, rule)

    def test_tag_match_compares_genre_tags(self) -> None:
        rule = {
            "id": 3,
            "kind": "tag_match",
            "pattern": "Podcast, Radio",
            "enabled": True,
        }
        assert rule_matches({"genre": "Techno / podcast"}, rule)
        assert rule_matches({"genre": None, "tags": ["Radio"]}, rule)
        assert not rule_matches({"genre": "radio edit"}, rule)

    def test_disabled_rule_never_matches(self) -> None:
        assert not rule_matches(
            {"duration_ms": 3_600_000}, {**DURATION_RULE, "enabled": False}
        )

    def test_first_matching_rule_respects_order(self) -> None:
        track = {"title": "Live at Fabric", "duration_ms": 3_600_000}
        rules = [_regex_rule("live at", rule_id=7), DURATION_RULE]
        assert first_matching_rule(track, rules)["id"] == 7
        assert first_matching_rule({"title": "Song", "duration_ms": 1}, rules) is None

    @pytest.mark.parametrize(
        "title",
        [
            "Live at Boiler Room London",
            "A b2b B",
            "Sunrise Set 2026",
            "Essential Mix",
            "My Radio Show 12",
            "Weekly Podcast",
            "Episode recap EP. 45",
            "Show ep12",
        ],
    )
    def test_seed_rules_catch_live_sets_and_shows(self, title: str) -> None:
        rules = list(_seed_rules().values())
        assert first_matching_rule({"title": title, "duration_ms": 1}, rules)

    @pytest.mark.parametrize(
        "title",
        [
            "Track (Original Mix)",
            "Track (Extended Mix)",
            "Track (Radio Mix)",
            "Deep 2",
            "Settle Down",
            "Remix Culture",
        ],
    )
    def test_seed_rules_spare_normal_tracks(self, title: str) -> None:
        rules = list(_seed_rules().values())
        assert first_matching_rule({"title": title, "duration_ms": 1}, rules) is None

    def test_precision_is_one_minus_rescue_share(self) -> None:
        assert rule_precision(0, 0) is None
        assert rule_precision(4, 1) == pytest.approx(0.75)


class TestRuleValidation:
    def test_invalid_regex_has_clear_error(self) -> None:
        with pytest.raises(ValueError, match=r"Invalid regex '\(live': .*position"):
            validate_rule(
                {
                    "name": "x",
                    "kind": "title_regex",
                    "pattern": "(live",
                    "reason": "other",
                }
            )

    def test_duration_needs_positive_threshold(self) -> None:
        with pytest.raises(ValueError, match="between 0"):
            validate_rule(
                {"name": "x", "kind": "duration_min", "threshold": 0, "reason": "other"}
            )

    def test_normalizes_fields(self) -> None:
        rule = validate_rule(
            {
                "name": "  Long  ",
                "kind": "duration_min",
                "threshold": "20",
                "pattern": "ignored",
                "reason": "live_mix",
            }
        )
        assert rule == {
            "name": "Long",
            "kind": "duration_min",
            "reason": "live_mix",
            "enabled": True,
            "pattern": None,
            "threshold": 20.0,
        }

    def test_rejects_unknown_kind_and_reason(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            validate_rule({"name": "x", "kind": "nope", "reason": "other"})
        with pytest.raises(ValueError, match="reason"):
            validate_rule(
                {"name": "x", "kind": "tag_match", "pattern": "a", "reason": "?"}
            )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMigrationV68:
    def test_rerun_is_idempotent_and_never_reseeds(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _migrate_v68_feed_flags(conn)
        seeds = conn.execute("SELECT COUNT(*) FROM feed_filter_rules").fetchone()[0]
        assert seeds == 3
        conn.execute(
            "DELETE FROM feed_filter_rules WHERE seed_key = 'seed_duration_15m'"
        )
        _migrate_v68_feed_flags(conn)
        assert conn.execute("SELECT COUNT(*) FROM feed_filter_rules").fetchone()[0] == 2

    def test_seed_rules_pass_validation(self) -> None:
        for rule in _seed_rules().values():
            validate_rule(rule)

    def test_one_active_flag_per_track(self) -> None:
        conn = sqlite3.connect(":memory:")
        _migrate_v68_feed_flags(conn)
        insert = "INSERT INTO sc_track_flags (soundcloud_id, reason, source) VALUES ('1', 'other', 'user')"
        conn.execute(insert)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert)


# ---------------------------------------------------------------------------
# DB: ingest, feed, rescue, exclusions
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_db):  # noqa: F811
    from web.backend.routers.feed import router as feed_router
    from web.backend.routers.feed_filters import router as filters_router

    app = FastAPI()
    app.include_router(feed_router)
    app.include_router(filters_router)
    return TestClient(app)


def _seed_uploads(titles: dict[str, str]) -> int:
    with get_db_connection() as conn:
        artist_id = _insert_artist(conn)
        for sc_id, title in titles.items():
            _insert_upload(
                conn,
                artist_id,
                sc_id,
                f"2026-07-0{sc_id[-1]}T00:00:00+00:00",
                title=title,
            )
        conn.commit()
    return artist_id


def _feed_ids(client) -> set[str]:
    response = client.get("/api/feed", params={"limit": 100})
    assert response.status_code == 200, response.text
    return {item["soundcloud_id"] for item in response.json()["items"]}


def _rule_id(seed_key: str) -> int:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT id FROM feed_filter_rules WHERE seed_key = ?", (seed_key,)
        ).fetchone()["id"]


class TestIngestAndRescue:
    def test_ingest_flags_matching_tracks_and_hides_them(self, client) -> None:
        from web.backend.queries.discovery import insert_discovery_tracks

        _seed_uploads({"11": "Real Track"})
        insert_discovery_tracks(
            [
                {
                    "soundcloud_id": "21",
                    "title": "Live at Boiler Room",
                    "duration_ms": 1,
                },
                {"soundcloud_id": "22", "title": "Banger", "duration_ms": 200_000},
            ]
        )
        with get_db_connection() as conn:
            flags = conn.execute(
                "SELECT soundcloud_id, source, rule_id FROM sc_track_flags"
            ).fetchall()
            decisions = conn.execute(
                "SELECT COUNT(*) FROM sc_track_decisions"
            ).fetchone()[0]
        assert [(f["soundcloud_id"], f["source"]) for f in flags] == [("21", "rule")]
        assert flags[0]["rule_id"] == _rule_id("seed_title_live_set")
        assert decisions == 0

        listed = client.get("/api/feed-filters/tracks").json()["items"]
        assert [(i["soundcloud_id"], i["rule_name"]) for i in listed] == [
            ("21", "Live set / mix title")
        ]

    def test_feed_hides_flagged_and_rescue_brings_it_back(self, client) -> None:
        from web.backend.queries import feed_filters

        _seed_uploads({"11": "Real Track", "12": "Sunday Podcast 3"})
        assert feed_filters.apply_rules(None) == 1
        assert _feed_ids(client) == {"11"}

        response = client.delete("/api/feed/12/flag")
        assert response.status_code == 200
        assert response.json()["removed"] is False
        assert _feed_ids(client) == {"11", "12"}

        rule = next(
            r
            for r in client.get("/api/feed-filters/rules").json()["rules"]
            if r["seed_key"] == "seed_title_podcast"
        )
        assert (rule["hits"], rule["rescues"], rule["precision"]) == (1, 1, 0.0)

        # A rescued track is never flagged again, by this or any other rule.
        assert feed_filters.apply_rules(None) == 0
        assert _feed_ids(client) == {"11", "12"}

    def test_run_only_scans_the_feed_window(self, test_db, monkeypatch) -> None:  # noqa: F811
        from web.backend.queries import feed_filters

        monkeypatch.setattr("web.backend.queries.feed.FEED_WINDOW_DAYS", 90)
        _seed_uploads({"12": "Sunday Podcast 3"})  # July 2026: outside the window
        assert feed_filters.apply_rules(None) == 0
        # Ingest hooks pass explicit ids and ignore the window.
        assert feed_filters.apply_rules(["12"]) == 1

    def test_rules_skip_decided_tracks(self, test_db) -> None:  # noqa: F811
        from web.backend.queries import feed_filters

        with get_db_connection() as conn:
            artist_id = _insert_artist(conn)
            _insert_upload(
                conn,
                artist_id,
                "31",
                "2026-07-01T00:00:00+00:00",
                status="liked",
                title="Live at X",
            )
            conn.commit()
        assert feed_filters.apply_rules(None) == 0

    def test_deleting_a_rule_releases_its_tracks(self, client) -> None:
        from web.backend.queries import feed_filters

        _seed_uploads({"12": "Sunday Podcast 3"})
        feed_filters.apply_rules(None)
        rule_id = _rule_id("seed_title_podcast")
        assert client.delete(f"/api/feed-filters/rules/{rule_id}").status_code == 200
        assert _feed_ids(client) == {"12"}


class TestUserFlag:
    def test_flag_hides_without_a_decision_and_saves_note(self, client) -> None:
        _seed_uploads({"11": "Real Track", "12": "Some Show"})
        response = client.post(
            "/api/feed/12/flag", json={"reason": "podcast", "note": "weekly show"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["flag"]["source"] == "user"
        assert _feed_ids(client) == {"11"}

        items = client.get(
            "/api/feed-filters/tracks", params={"source": "user"}
        ).json()["items"]
        assert [(i["soundcloud_id"], i["reason"], i["note"]) for i in items] == [
            ("12", "podcast", "weekly show")
        ]
        with get_db_connection() as conn:
            assert (
                conn.execute("SELECT COUNT(*) FROM sc_track_decisions").fetchone()[0]
                == 0
            )

    def test_unflag_deletes_user_flag(self, client) -> None:
        _seed_uploads({"12": "Some Show"})
        client.post("/api/feed/12/flag", json={"reason": "other"})
        response = client.delete("/api/feed/12/flag")
        assert response.json()["removed"] is True
        assert _feed_ids(client) == {"12"}
        assert client.delete("/api/feed/12/flag").status_code == 404

    def test_flag_rejects_unknown_track_and_reason(self, client) -> None:
        _seed_uploads({"12": "Some Show"})
        assert (
            client.post("/api/feed/999/flag", json={"reason": "other"}).status_code
            == 404
        )
        assert (
            client.post("/api/feed/12/flag", json={"reason": "dislike"}).status_code
            == 422
        )


class TestRulesApi:
    def test_create_edit_toggle_delete(self, client) -> None:
        created = client.post(
            "/api/feed-filters/rules",
            json={
                "name": "Long",
                "kind": "duration_min",
                "threshold": 30,
                "reason": "live_mix",
            },
        )
        assert created.status_code == 201, created.text
        rule = created.json()
        assert (rule["hits"], rule["precision"]) == (0, None)

        edited = client.patch(
            f"/api/feed-filters/rules/{rule['id']}",
            json={"threshold": 45, "enabled": False},
        )
        assert (edited.json()["threshold"], edited.json()["enabled"]) == (45.0, False)

        assert client.delete(f"/api/feed-filters/rules/{rule['id']}").status_code == 200
        assert (
            client.patch(
                f"/api/feed-filters/rules/{rule['id']}", json={"enabled": True}
            ).status_code
            == 404
        )

    def test_invalid_regex_is_rejected_with_reason(self, client) -> None:
        response = client.post(
            "/api/feed-filters/rules",
            json={
                "name": "Bad",
                "kind": "title_regex",
                "pattern": "[live",
                "reason": "other",
            },
        )
        assert response.status_code == 422
        assert "Invalid regex" in response.json()["detail"]

    def test_run_endpoint_flags_existing_tracks(self, client) -> None:
        _seed_uploads({"12": "Sunday Podcast 3"})
        assert client.post("/api/feed-filters/run").json() == {"flagged": 1}


class TestFlagExclusions:
    """A flagged track is not a track: no artist stats, no training label."""

    def _seed_flagged_keep(self) -> int:
        with get_db_connection() as conn:
            artist_id = _insert_artist(conn)
            _insert_upload(
                conn, artist_id, "41", "2026-07-01T00:00:00+00:00", status="liked"
            )
            _insert_upload(
                conn, artist_id, "42", "2026-07-02T00:00:00+00:00", status="dismissed"
            )
            conn.execute(
                "INSERT INTO sc_track_flags (soundcloud_id, reason, source) VALUES ('42', 'live_mix', 'user')"
            )
            conn.commit()
        return artist_id

    def test_artist_stats_ignore_flagged_tracks(self, test_db) -> None:  # noqa: F811
        from web.backend.queries.discovery import recalculate_artist_stats

        artist_id = self._seed_flagged_keep()
        recalculate_artist_stats([artist_id])
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT tracks_seen, tracks_liked, tracks_dismissed, hit_rate FROM discovery_artists WHERE id = ?",
                (artist_id,),
            ).fetchone()
        assert tuple(row) == (1, 1, 0, 100.0)

    def test_training_data_ignores_flagged_tracks(self, test_db) -> None:  # noqa: F811
        from web.backend.keep_decisions import load_track_decisions

        self._seed_flagged_keep()
        with get_db_connection() as conn:
            decisions = load_track_decisions(conn)
        assert [d.soundcloud_id for d in decisions] == ["41"]

    def test_rescued_track_counts_again(self, test_db) -> None:  # noqa: F811
        from web.backend.keep_decisions import load_track_decisions

        self._seed_flagged_keep()
        with get_db_connection() as conn:
            conn.execute("UPDATE sc_track_flags SET rescued_at = CURRENT_TIMESTAMP")
            conn.commit()
            decisions = load_track_decisions(conn)
        assert sorted(d.soundcloud_id for d in decisions) == ["41", "42"]

    def test_jev_skips_flagged_tracks(self, test_db) -> None:  # noqa: F811
        from web.backend import jev_scorer
        from web.backend.queries import feed as feed_queries

        with get_db_connection() as conn:
            artist_id = _insert_artist(conn)
            _insert_upload(conn, artist_id, "51", "2026-07-01T00:00:00+00:00")
            _insert_upload(conn, artist_id, "52", "2026-07-02T00:00:00+00:00")
            conn.execute(
                "INSERT INTO sc_track_flags (soundcloud_id, reason, source) VALUES ('52', 'podcast', 'user')"
            )
            conn.commit()
            rows = conn.execute(
                jev_scorer._candidates_sql(),
                {
                    "model_id": "m",
                    "profile_version": "p",
                    **feed_queries.window_params(),
                },
            ).fetchall()
        assert [row["soundcloud_id"] for row in rows] == ["51"]
