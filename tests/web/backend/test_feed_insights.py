"""Feed Insights aggregation (#31): keep %, lift, min count, normalization."""

import sqlite3

import pytest

from music_minion.core.database import _migrate_v69_feed_insights, get_db_connection
from tests.test_feed_uploads import _insert_artist, _insert_upload, test_db  # noqa: F401
from web.backend import feed_insights
from web.backend.feed_insights import (
    age_bucket,
    aggregate,
    duration_bucket,
    feature_values,
    format_taste_evidence,
    keep_pct,
    matching_tracks,
    normalize_text,
    overall_keep_pct,
    title_keywords,
    top_lift_features,
)
from web.backend.queries import insights as insight_queries
from web.backend.soundcloud_metadata import parse_tag_list, track_metadata


def _track(decision: str, **fields) -> dict:
    return {"decision": decision, "title": "", "genre": None, "tags": [], **fields}


class TestKeepPctAndLift:
    def test_not_quite_counts_as_half_a_keep(self) -> None:
        assert keep_pct(["keep", "not_quite", "nope", "nope"]) == 37.5

    def test_empty_is_none(self) -> None:
        assert keep_pct([]) is None

    def test_lift_is_points_over_overall(self) -> None:
        tracks = [
            _track("keep", genre="Dubstep"),
            _track("keep", genre="Dubstep"),
            _track("nope", genre="House"),
            _track("nope", genre="House"),
        ]
        assert overall_keep_pct(tracks) == 50.0
        rows = {row["value"]: row for row in aggregate(tracks, "genre", min_count=1)}
        assert rows["dubstep"]["keep_pct"] == 100.0
        assert rows["dubstep"]["lift"] == 50.0
        assert rows["house"]["lift"] == -50.0
        assert rows["house"]["nopes"] == 2

    def test_not_quite_in_feature_rows(self) -> None:
        tracks = [_track("not_quite", genre="Riddim"), _track("nope", genre="Riddim")]
        (row,) = aggregate(tracks, "genre", min_count=1)
        assert (row["seen"], row["not_quites"], row["keep_pct"]) == (2, 1, 25.0)
        assert row["lift"] == 0.0

    def test_min_count_hides_rare_values(self) -> None:
        tracks = [_track("keep", genre="Dubstep")] * 8 + [_track("nope", genre="Trap")]
        assert [row["value"] for row in aggregate(tracks, "genre")] == ["dubstep"]
        values = {row["value"] for row in aggregate(tracks, "genre", min_count=1)}
        assert values == {"dubstep", "trap"}

    def test_sorted_by_lift_then_seen(self) -> None:
        tracks = (
            [_track("keep", title="alpha")] * 2
            + [_track("keep", title="beta")] * 3
            + [_track("nope", title="gamma")] * 3
        )
        rows = aggregate(tracks, "keyword", min_count=1)
        assert [row["value"] for row in rows] == ["beta", "alpha", "gamma"]

    def test_a_feature_counts_once_per_track(self) -> None:
        (row,) = aggregate([_track("keep", title="vip vip VIP")], "keyword", 1)
        assert row["seen"] == 1


class TestNormalization:
    @pytest.mark.parametrize(
        "raw", ["A Cappella", "acappella", "Acapella", "a capella", "ACCAPELLA"]
    )
    def test_acapella_variants_merge(self, raw: str) -> None:
        assert normalize_text(raw) == "acapella"

    def test_dnb_variants_merge(self) -> None:
        assert {normalize_text(v) for v in ("Drum & Bass", "D&B", "DnB")} == {"dnb"}

    def test_keywords_and_phrases_respect_punctuation(self) -> None:
        keywords = title_keywords("Artist - Track (Radio Show Edit) — Live at 2024")
        assert {"radio show", "show edit", "live", "track"} <= keywords
        assert "artist track" not in keywords
        assert "edit live" not in keywords
        assert "2024" not in keywords and "at" not in keywords

    def test_genre_missing_is_its_own_value(self) -> None:
        assert feature_values(_track("keep"), "genre") == {feed_insights.NO_GENRE}

    def test_tags_come_from_tag_list_when_not_parsed(self) -> None:
        track = {"decision": "keep", "tag_list": 'dubstep "Bass Music"'}
        assert feature_values(track, "tag") == {"dubstep", "bass music"}

    def test_unknown_dimension_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid insight dimension"):
            feature_values(_track("keep"), "description")


class TestBuckets:
    @pytest.mark.parametrize(
        ("minutes", "label"),
        [(1.5, "under 2 min"), (3, "2-4 min"), (6, "4-7 min"), (10, "7-15 min")],
    )
    def test_duration(self, minutes: float, label: str) -> None:
        assert duration_bucket(int(minutes * 60_000)) == label

    def test_duration_unknown(self) -> None:
        assert duration_bucket(0) is None and duration_bucket(None) is None

    def test_age(self) -> None:
        assert age_bucket(-2) == "under 1 week"
        assert age_bucket(45) == "1-6 months"
        assert age_bucket(800) == "1+ year"
        assert age_bucket(None) is None


class TestDrillDownAndProfile:
    def test_matching_tracks(self) -> None:
        tracks = [_track("keep", title="Big VIP"), _track("nope", title="Big Mix")]
        assert matching_tracks(tracks, "keyword", "vip") == [tracks[0]]

    def test_top_lift_features_split_by_sign(self) -> None:
        tracks = [_track("keep", genre="Dubstep")] * 3 + [_track("nope", genre="House")]
        positives, negatives = top_lift_features(tracks, ["genre"], min_count=1)
        assert [row["value"] for row in positives] == ["dubstep"]
        assert [row["value"] for row in negatives] == ["house"]
        assert positives[0]["dimension"] == "genre"

    def test_evidence_text(self) -> None:
        positive = {"dimension": "genre", "value": "dubstep", "keep_pct": 40.0}
        positive |= {"seen": 30, "lift": 15.5}
        note = {"decision": "not_quite", "title": "Song", "note": "drop too\nweak"}
        text = format_taste_evidence(24.5, [positive], [], [note])
        assert "Overall keep rate: 24.5%" in text
        assert 'genre "dubstep": keep 40% over 30 reviewed (+15.5 pts)' in text
        assert '- not quite on "Song": drop too weak' in text
        assert "predict passes" not in text

    def test_no_evidence_is_empty(self) -> None:
        assert format_taste_evidence(0.0, [], [], []) == ""


class TestTagList:
    def test_parse_quoted_and_machine_tags(self) -> None:
        raw = 'Dubstep "bass music" soundcloud:source=web-record dubstep'
        assert parse_tag_list(raw) == ["dubstep", "bass music"]

    def test_track_metadata_keeps_tag_list(self) -> None:
        assert track_metadata({"id": 1, "tag_list": "a b"})["tag_list"] == "a b"
        assert track_metadata({"id": 1, "tag_list": ""})["tag_list"] is None

    def test_migration_is_idempotent(self) -> None:
        conn = sqlite3.connect(":memory:")
        for table in ("discovery_tracks", "sc_artist_uploads", "sc_track_flags"):
            conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        _migrate_v69_feed_insights(conn)
        _migrate_v69_feed_insights(conn)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sc_track_flags)")}
        assert "confidence" in columns


# ---------------------------------------------------------------------------
# DB loader
# ---------------------------------------------------------------------------


def _decide(conn, sc_id: str, decision: str, decided_at: str = "2026-01-10") -> None:
    conn.execute(
        """INSERT INTO sc_track_decisions (soundcloud_id, decision, decided_at, surface)
        VALUES (?, ?, ?, 'test')""",
        (sc_id, decision, decided_at),
    )


@pytest.fixture
def reviewed_db(test_db):  # noqa: F811
    with get_db_connection() as conn:
        artist = _insert_artist(conn, name="Uploader")
        for sc_id, decision in (
            ("1", "keep"),
            ("2", "not_quite"),
            ("3", "nope"),
            ("4", "hide"),
            ("5", "keep"),
        ):
            _insert_upload(conn, artist, sc_id, "2026-01-01", title=f"Song {sc_id} VIP")
            _decide(conn, sc_id, decision)
        conn.execute("UPDATE sc_artist_uploads SET tag_list = 'riddim' WHERE id = 1")
        conn.execute(
            "INSERT INTO sc_track_flags (soundcloud_id, reason, source) "
            "VALUES ('5', 'live_mix', 'user')"
        )
        conn.execute(
            "INSERT INTO sc_track_notes (soundcloud_id, note) VALUES ('3', 'meh')"
        )
        conn.commit()
    return test_db


class TestReviewedLoader:
    def test_excludes_hide_and_flagged(self, reviewed_db) -> None:
        tracks = insight_queries.load_reviewed_tracks()
        assert sorted(t["soundcloud_id"] for t in tracks) == ["1", "2", "3"]

    def test_track_fields(self, reviewed_db) -> None:
        by_id = {t["soundcloud_id"]: t for t in insight_queries.load_reviewed_tracks()}
        assert by_id["1"]["uploader"] == "Uploader"
        assert by_id["1"]["age_days"] == 9.0
        assert feature_values(by_id["1"], "tag") == {"riddim"}

    def test_insights_payload(self, reviewed_db) -> None:
        payload = insight_queries.get_insights("keyword", min_count=3)
        assert payload["overall"] == {"seen": 3, "keep_pct": 50.0}
        vip = next(row for row in payload["rows"] if row["value"] == "vip")
        assert (vip["seen"], vip["lift"]) == (3, 0.0)

    def test_drill_down(self, reviewed_db) -> None:
        result = insight_queries.get_insight_tracks("tag", "riddim")
        assert result["total"] == 1
        assert result["items"][0]["soundcloud_id"] == "1"

    def test_recent_notes_only_near_misses_and_nopes(self, reviewed_db) -> None:
        notes = insight_queries.load_recent_notes()
        assert [(n["decision"], n["note"]) for n in notes] == [("nope", "meh")]
