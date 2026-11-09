"""Stories page: window, dedupe, listened signals, ordering, and the API."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from web.backend.queries import stories
from web.backend.routers.stories import router as stories_router

NOW = datetime(2026, 11, 8, 20, 0, 0, tzinfo=UTC)


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _raw(days: float) -> str:
    """SoundCloud's raw exact repost format."""
    return _ago(days).strftime("%Y/%m/%d %H:%M:%S +0000")


def _seen(days: float) -> str:
    """SQLite CURRENT_TIMESTAMP format."""
    return _ago(days).strftime("%Y-%m-%d %H:%M:%S")


def _iso(days: float) -> str:
    """Upload format: ISO with offset."""
    return _ago(days).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _z(days: float) -> str:
    return _ago(days).strftime("%Y-%m-%dT%H:%M:%SZ")


def _exec(sql: str, params: tuple = ()) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def add_artist(slug: str, following: int = 1, sc_user: str | None = None) -> int:
    return _exec(
        """INSERT INTO discovery_artists
            (slug, display_name, ranking, is_following, soundcloud_user_id, avatar_url)
        VALUES (?, ?, 1, ?, ?, ?)""",
        (slug, slug.upper(), following, sc_user, f"https://img/{slug}.jpg"),
    )


def add_track(
    sc_id: str, uploader: str | None = None, access: str | None = None
) -> int:
    return _exec(
        """INSERT INTO discovery_tracks
            (soundcloud_id, title, artist_name, uploader_soundcloud_id,
             duration_ms, access, permalink_url, artwork_url)
        VALUES (?, ?, 'Raw Name', ?, 200000, ?, ?, ?)""",
        (sc_id, f"Track {sc_id}", uploader, access, f"https://sc/{sc_id}", "art"),
    )


def add_repost(
    track_id: int, artist_id: int, reposted_at: str | None, seen_at: str
) -> None:
    precision = "exact" if reposted_at else "approximate"
    _exec(
        """INSERT INTO discovery_track_reposters
            (discovery_track_id, discovery_artist_id, reposted_at, seen_at,
             repost_time_precision)
        VALUES (?, ?, ?, ?, ?)""",
        (track_id, artist_id, reposted_at, seen_at, precision),
    )


def add_upload(artist_id: int, sc_id: str, uploaded_at: str) -> None:
    _exec(
        """INSERT INTO sc_artist_uploads
            (discovery_artist_id, soundcloud_id, title, uploaded_at, duration_ms)
        VALUES (?, ?, ?, ?, 180000)""",
        (artist_id, sc_id, f"Upload {sc_id}", uploaded_at),
    )


def add_score(sc_id: str, probability: float, created_at: str) -> None:
    _exec(
        """INSERT INTO sc_track_predictions
            (soundcloud_id, model_id, taste_profile_version, probability,
             state_sent, created_at)
        VALUES (?, 'm', 'v', ?, '{}', ?)""",
        (sc_id, probability, created_at),
    )


def add_library_track(sc_id: str, local_path: str | None = None) -> int:
    return _exec(
        "INSERT INTO tracks (title, soundcloud_id, source, local_path) "
        "VALUES (?, ?, 'soundcloud', ?)",
        (f"lib {sc_id}", sc_id, local_path),
    )


def reposted(sc_id: str, artist_id: int, days: float = 1) -> None:
    add_repost(add_track(sc_id), artist_id, _raw(days), _seen(days))


def payload(days: int = 7) -> dict:
    return stories.get_stories(days, now=NOW)


def tracks_of(data: dict, artist_id: int) -> list[dict]:
    artist = next(a for a in data["artists"] if a["discovery_artist_id"] == artist_id)
    return artist["tracks"]


def track(data: dict, artist_id: int, sc_id: str) -> dict:
    return next(t for t in tracks_of(data, artist_id) if t["soundcloud_id"] == sc_id)


# ---------------------------------------------------------------------------
# Window + timestamp normalization
# ---------------------------------------------------------------------------


class TestWindow:
    def test_mixed_formats_filtered_by_normalized_time(self) -> None:
        artist = add_artist("a")
        add_repost(add_track("exact_in"), artist, _raw(2), _seen(2))
        add_repost(add_track("exact_out"), artist, _raw(8), _seen(8))
        add_repost(add_track("approx_in"), artist, None, _seen(3))
        add_repost(add_track("empty_in"), artist, "", _seen(4))
        add_repost(add_track("approx_out"), artist, None, _seen(9))
        # Re-repost: old seen_at, fresh reposted_at -> in window.
        add_repost(add_track("rerepost"), artist, _raw(1), _seen(40))
        add_upload(artist, "up_in", _iso(5))
        add_upload(artist, "up_out", _iso(7.5))

        ids = {t["soundcloud_id"] for t in tracks_of(payload(), artist)}

        assert ids == {"exact_in", "approx_in", "empty_in", "rerepost", "up_in"}

    def test_timestamps_are_iso_utc_z(self) -> None:
        artist = add_artist("a")
        add_repost(add_track("x"), artist, _raw(2), _seen(2))
        add_repost(add_track("y"), artist, None, _seen(3))
        data = payload()
        assert data["generated_at"] == "2026-11-08T20:00:00Z"
        assert track(data, artist, "x")["activity_at"] == _z(2)
        assert track(data, artist, "y")["activity_at"] == _z(3)
        assert data["artists"][0]["latest_activity_at"] == _z(2)

    def test_days_parameter_widens_window(self) -> None:
        artist = add_artist("a")
        reposted("old", artist, days=10)
        assert payload(7)["artists"] == []
        assert payload(14)["artists"][0]["tracks"][0]["soundcloud_id"] == "old"

    @pytest.mark.parametrize("days", [0, 31])
    def test_days_out_of_range_rejected(self, days: int) -> None:
        with pytest.raises(ValueError):
            payload(days)

    def test_unfollowed_and_unplayable_excluded(self) -> None:
        followed = add_artist("a")
        unfollowed = add_artist("b", following=0)
        reposted("ok", followed)
        reposted("theirs", unfollowed)
        add_repost(add_track("snip", access="preview"), followed, _raw(1), _seen(1))
        data = payload()
        assert [a["discovery_artist_id"] for a in data["artists"]] == [followed]
        assert {t["soundcloud_id"] for t in tracks_of(data, followed)} == {"ok"}


# ---------------------------------------------------------------------------
# Listened signals
# ---------------------------------------------------------------------------


class TestListened:
    @pytest.fixture
    def artist(self) -> int:
        artist = add_artist("a")
        reposted("target", artist)
        reposted("fresh", artist)  # keeps the artist listed
        return artist

    def _listened(self, artist: int) -> bool:
        return track(payload(), artist, "target")["listened"]

    def test_unheard_by_default(self, artist: int) -> None:
        assert self._listened(artist) is False

    def test_explicit_listen(self, artist: int) -> None:
        stories.mark_listened("target", "stories")
        assert self._listened(artist) is True

    @pytest.mark.parametrize("decision", ["keep", "not_quite", "nope"])
    def test_current_decision(self, artist: int, decision: str) -> None:
        _exec(
            "INSERT INTO sc_track_decisions (soundcloud_id, decision, surface) "
            "VALUES ('target', ?, 'web_feed')",
            (decision,),
        )
        data = payload()
        assert track(data, artist, "target")["listened"] is True
        assert track(data, artist, "target")["decision"] == decision

    def test_superseded_decision_does_not_count(self, artist: int) -> None:
        _exec(
            "INSERT INTO sc_track_decisions (soundcloud_id, decision, surface,"
            " is_current) VALUES ('target', 'keep', 'web_feed', 0)"
        )
        assert self._listened(artist) is False

    def test_library_local_file(self, artist: int) -> None:
        add_library_track("target", local_path="/music/target.opus")
        assert self._listened(artist) is True

    def test_library_playlist_membership(self, artist: int) -> None:
        track_id = add_library_track("target")
        playlist_id = _exec("INSERT INTO playlists (name, type) VALUES ('p', 'manual')")
        _exec(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position)"
            " VALUES (?, ?, 0)",
            (playlist_id, track_id),
        )
        assert self._listened(artist) is True

    def test_streaming_only_row_is_not_listened(self, artist: int) -> None:
        track_id = add_library_track("target")
        data = payload()
        assert track(data, artist, "target")["listened"] is False
        assert track(data, artist, "target")["local_track_id"] == track_id

    def _play(self, position_ms: int | None) -> None:
        track_id = add_library_track("target")
        _exec(
            "INSERT INTO radio_history (track_id, source_type, position_ms)"
            " VALUES (?, 'soundcloud', ?)",
            (track_id, position_ms),
        )

    def test_radio_history_play(self, artist: int) -> None:
        self._play(5000)
        assert self._listened(artist) is True

    def test_short_play_is_not_listened(self, artist: int) -> None:
        self._play(1200)
        assert self._listened(artist) is False

    def test_open_play_is_not_listened(self, artist: int) -> None:
        self._play(None)
        assert self._listened(artist) is False

    def test_listened_is_global_across_artists(self) -> None:
        first, second = add_artist("a"), add_artist("b")
        track_id = add_track("shared")
        add_repost(track_id, first, _raw(1), _seen(1))
        add_repost(track_id, second, _raw(2), _seen(2))
        reposted("other_a", first)
        reposted("other_b", second)
        stories.mark_listened("shared", "stories")
        data = payload()
        assert track(data, first, "shared")["listened"] is True
        assert track(data, second, "shared")["listened"] is True

    def test_artist_omitted_when_everything_heard(self) -> None:
        heard, active = add_artist("heard"), add_artist("active")
        reposted("h1", heard)
        reposted("h2", heard)
        reposted("a1", active)
        reposted("h1b", active)
        stories.mark_listened("h1", None)
        stories.mark_listened("h2", None)
        stories.mark_listened("h1b", None)
        data = payload()
        assert [a["discovery_artist_id"] for a in data["artists"]] == [active]
        assert data["artists"][0]["unheard_count"] == 1
        assert len(data["artists"][0]["tracks"]) == 2  # heard ones stay visible


# ---------------------------------------------------------------------------
# Flags, dedupe, ordering
# ---------------------------------------------------------------------------


class TestShape:
    def test_flagged_track_excluded_and_rescued_returns(self) -> None:
        artist = add_artist("a")
        reposted("flagged", artist)
        reposted("rescued", artist)
        reposted("plain", artist)
        _exec(
            "INSERT INTO sc_track_flags (soundcloud_id, reason, source)"
            " VALUES ('flagged', 'live_mix', 'user')"
        )
        _exec(
            "INSERT INTO sc_track_flags (soundcloud_id, reason, source, rescued_at)"
            " VALUES ('rescued', 'podcast', 'rule', CURRENT_TIMESTAMP)"
        )
        ids = {t["soundcloud_id"] for t in tracks_of(payload(), artist)}
        assert ids == {"rescued", "plain"}

    def test_own_upload_and_repost_dedupe_to_upload_with_latest_time(self) -> None:
        artist = add_artist("a", sc_user="u-a")
        add_upload(artist, "own", _iso(3))
        add_repost(add_track("own", uploader="u-a"), artist, _raw(1), _seen(1))
        tracks = tracks_of(payload(), artist)
        assert len(tracks) == 1
        assert tracks[0]["kind"] == "upload"
        assert tracks[0]["activity_at"] == _z(1)
        assert tracks[0]["title"] == "Upload own"
        assert tracks[0]["artist_name"] == "A"

    def test_repost_artist_name_uses_uploader_alias(self) -> None:
        reposter = add_artist("r")
        add_artist("orig", following=0, sc_user="u-orig")
        add_repost(add_track("t", uploader="u-orig"), reposter, _raw(1), _seen(1))
        reposted("unknown_uploader", reposter)
        data = payload()
        assert track(data, reposter, "t")["artist_name"] == "ORIG"
        assert track(data, reposter, "unknown_uploader")["artist_name"] == "Raw Name"

    def test_same_track_shows_under_each_artist_once(self) -> None:
        first, second = add_artist("a"), add_artist("b")
        track_id = add_track("t")
        add_repost(track_id, first, _raw(1), _seen(1))
        add_repost(track_id, second, None, _seen(2))
        data = payload()
        assert [t["soundcloud_id"] for t in tracks_of(data, first)] == ["t"]
        assert [t["soundcloud_id"] for t in tracks_of(data, second)] == ["t"]

    def test_tracks_ordered_by_latest_score_then_recency(self) -> None:
        artist = add_artist("a")
        for sc_id, days in [
            ("low", 1),
            ("high", 5),
            ("none_new", 1.5),
            ("none_old", 4),
            ("tie_new", 2),
            ("tie_old", 3),
        ]:
            reposted(sc_id, artist, days)
        add_score("high", 0.2, "2026-11-01 00:00:00")
        add_score("high", 0.9, "2026-11-07 00:00:00")  # latest wins
        add_score("low", 0.1, "2026-11-07 00:00:00")
        add_score("tie_new", 0.5, "2026-11-07 00:00:00")
        add_score("tie_old", 0.5, "2026-11-07 00:00:00")
        tracks = tracks_of(payload(), artist)
        assert [t["soundcloud_id"] for t in tracks] == [
            "high",
            "tie_new",
            "tie_old",
            "low",
            "none_new",
            "none_old",
        ]
        assert tracks[0]["score"] == 0.9
        assert tracks[-1]["score"] is None

    def test_artists_ordered_by_latest_activity(self) -> None:
        older, newer, middle = add_artist("o"), add_artist("n"), add_artist("m")
        reposted("o1", older, 5)
        reposted("n1", newer, 6)
        add_upload(newer, "n2", _iso(0.5))
        reposted("m1", middle, 2)
        data = payload()
        assert [a["discovery_artist_id"] for a in data["artists"]] == [
            newer,
            middle,
            older,
        ]
        assert data["artists"][0]["latest_activity_at"] == _z(0.5)

    def test_artist_payload_shape(self) -> None:
        artist = add_artist("mirr-img")
        reposted("t", artist)
        entry = payload()["artists"][0]
        assert set(entry) == {
            "discovery_artist_id",
            "display_name",
            "slug",
            "avatar_url",
            "latest_activity_at",
            "unheard_count",
            "tracks",
        }
        assert entry["slug"] == "mirr-img"
        assert set(entry["tracks"][0]) == {
            "soundcloud_id",
            "title",
            "artist_name",
            "artwork_url",
            "permalink_url",
            "duration_ms",
            "kind",
            "activity_at",
            "local_track_id",
            "score",
            "decision",
            "listened",
        }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(stories_router)
    return TestClient(app)


def _listen_rows(sc_id: str) -> list[tuple]:
    with get_db_connection() as conn:
        return [
            tuple(row)
            for row in conn.execute(
                "SELECT soundcloud_id, first_listened_at, surface"
                " FROM sc_track_listens WHERE soundcloud_id = ?",
                (sc_id,),
            )
        ]


class TestApi:
    def test_listened_is_idempotent_and_keeps_first_surface(
        self, client: TestClient
    ) -> None:
        add_track("t")
        first = client.post("/api/stories/t/listened", json={"surface": "stories"})
        assert first.status_code == 200
        assert first.json() == {"soundcloud_id": "t", "listened": True}
        before = _listen_rows("t")
        again = client.post("/api/stories/t/listened", json={"surface": "other"})
        assert again.status_code == 200
        assert _listen_rows("t") == before
        assert before[0][2] == "stories"

    def test_listened_without_body_defaults_surface(self, client: TestClient) -> None:
        add_upload(add_artist("a"), "up", _iso(1))
        assert client.post("/api/stories/up/listened").status_code == 200
        assert _listen_rows("up")[0][2] == "stories"

    def test_listened_unknown_track_404(self, client: TestClient) -> None:
        response = client.post("/api/stories/nope/listened")
        assert response.status_code == 404
        assert _listen_rows("nope") == []

    def test_get_stories_validates_days(self, client: TestClient) -> None:
        assert client.get("/api/stories?days=0").status_code == 422
        assert client.get("/api/stories?days=31").status_code == 422

    def test_get_stories_returns_contract(self, client: TestClient) -> None:
        artist = add_artist("a")
        add_upload(artist, "up", datetime.now(UTC).isoformat())
        body = client.get("/api/stories").json()
        assert body["generated_at"].endswith("Z")
        assert body["artists"][0]["tracks"][0]["soundcloud_id"] == "up"
        assert body["artists"][0]["tracks"][0]["kind"] == "upload"
