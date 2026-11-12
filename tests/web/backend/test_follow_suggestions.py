"""Follow suggestions: every scoring rule, the DB loaders, and the routes."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from web.backend import follow_suggestions as fs
from web.backend.follow_suggestions import (
    Account,
    Activity,
    Context,
    EvidenceTrack,
    Resolution,
)
from web.backend.queries import follow_suggestions as queries
from web.backend.routers.follow_suggestions import router

NOW = datetime(2026, 11, 11, tzinfo=UTC)


def _track(
    sc_id: str,
    artist: str,
    title: str = "Song",
    remix_artist: str | None = None,
    liked: bool = True,
    liked_at: str | None = None,
    uploader: tuple[str, str, str] | None = None,
) -> EvidenceTrack:
    uid, permalink, username = uploader or (None, None, None)
    return EvidenceTrack(
        sc_id, title, artist, remix_artist, liked, liked_at, uid, permalink, username
    )


def _ctx(**overrides: object) -> Context:
    base = Context(
        followed=(),
        resolutions={},
        activity={},
        dismissed=frozenset(),
        label_overrides={},
        now=NOW,
    )
    return base._replace(**overrides)


def _activity(**overrides: object) -> Activity:
    base = Activity(
        username=None,
        permalink=None,
        avatar_url=None,
        followers=None,
        last_upload_at="2026-11-01T00:00:00+00:00",
        last_repost_at=None,
        uploads_90d=8,
        reposts_90d=0,
        is_label=False,
    )
    return base._replace(**overrides)


def _by_key(tracks: list[EvidenceTrack], ctx: Context | None = None) -> dict:
    return {s["key"]: s for s in fs.rank_entities(tracks, ctx or _ctx())}


# ---------------------------------------------------------------------------
# Name keys
# ---------------------------------------------------------------------------


class TestNameKeys:
    def test_decoration_and_accents_drop(self) -> None:
        assert fs.name_key("Wooli 🐘") == "wooli"
        assert fs.name_key("▶︎ Dirt Monkey ◀︎") == "dirtmonkey"
        assert fs.name_key("Eliminate*") == "eliminate"
        assert fs.name_key("Mörk") == "mork"
        assert fs.name_key(None) == ""

    def test_slug_affixes_strip(self) -> None:
        assert fs.slug_keys("woolimusic") == {"woolimusic", "wooli"}
        assert fs.slug_keys("dj-snake") == {"djsnake", "snake"}
        assert "eater" in fs.slug_keys("itseater")
        assert fs.slug_keys("djmusic") == {"djmusic"}  # too short once stripped


# ---------------------------------------------------------------------------
# Role weights
# ---------------------------------------------------------------------------


class TestRoleWeights:
    def test_each_role_weight(self) -> None:
        tracks = [
            _track("1", "Orig"),
            _track("2", "Base", "Song (Mixer Remix)"),
            _track("3", "Host", "Song (feat. Guest)"),
        ]
        hits = {(h.ref, h.role): h.weight for h in fs.collect_hits(tracks)}
        assert hits[("name:orig", "original")] == 1.0
        assert hits[("name:mixer", "remixer")] == 0.8
        assert hits[("name:base", "remixed_by_others")] == 0.2
        assert hits[("name:guest", "feat")] == 0.5
        assert hits[("name:host", "original")] == 1.0

    def test_uploader_gets_full_weight(self) -> None:
        hits = fs.collect_hits([_track("1", "X", uploader=("77", "up", "Up"))])
        assert ("77", "uploaded", 1.0) in [(h.ref, h.role, h.weight) for h in hits]

    def test_kept_not_liked_caps_at_half(self) -> None:
        tracks = [
            _track("1", "Keeper", liked=False, uploader=("9", "u", "U")),
            _track("2", "Base", "Song (Mixer Remix)", liked=False),
        ]
        hits = {h.ref: (h.role, h.weight) for h in fs.collect_hits(tracks)}
        assert hits["name:keeper"] == ("kept", 0.5)
        assert hits["9"] == ("kept", 0.5)
        assert hits["name:base"] == ("kept", 0.2)  # remixed-by-others stays low

    def test_liked_beats_kept_for_same_track(self) -> None:
        tracks = [_track("1", "A", liked=False), _track("1", "A", liked=True)]
        assert [h.role for h in fs.collect_hits(tracks)] == ["original"]

    def test_one_credit_per_account_per_track(self) -> None:
        # Uploader and credited primary are the same account: count once, at 1.0
        resolutions = {"artist": Resolution("5", "artist", "Artist", "high", "x")}
        track = _track("1", "Artist", uploader=("5", "artist", "Artist"))
        grouped = fs.best_hits_by_entity(fs.collect_hits([track]), resolutions)
        assert list(grouped) == ["5"]
        assert [h.weight for h in grouped["5"]] == [1.0]

    def test_highest_role_wins_within_a_track(self) -> None:
        # Spotify-style: remixer also listed as primary -> remixer, not 0.2
        track = _track("1", "Base, Mixer", "Song (Mixer Remix)")
        roles = {h.ref: h.role for h in fs.collect_hits([track])}
        assert roles["name:mixer"] == "remixer"
        assert roles["name:base"] == "remixed_by_others"


# ---------------------------------------------------------------------------
# Duo guard
# ---------------------------------------------------------------------------


class TestDuoGuard:
    def test_duo_that_always_co_occurs_stays_whole(self) -> None:
        tracks = [_track(str(i), "Chase & Status") for i in range(5)]
        refs = {h.ref for h in fs.collect_hits(tracks)}
        assert refs == {"name:chasestatus"}

    def test_real_collab_splits(self) -> None:
        tracks = [_track("1", "Wooli & Trivecta")] + [
            _track(str(i), "Wooli") for i in range(2, 8)
        ]
        refs = {h.ref for h in fs.collect_hits(tracks)}
        assert {"name:wooli", "name:trivecta"} <= refs
        assert "name:woolitrivecta" not in refs

    def test_part_alone_at_20_percent_splits(self) -> None:
        # 'a' alone on 1 of 5 tracks (20%) -> not a duo
        tracks = [_track(str(i), "A & B") for i in range(4)] + [_track("9", "A")]
        assert "name:ab" not in {h.ref for h in fs.collect_hits(tracks)}

    def test_duo_as_remixer_stays_whole(self) -> None:
        tracks = [_track("1", "Chase & Status")] + [
            _track("2", "Other", "Song (Chase & Status Remix)")
        ]
        roles = {(h.ref, h.role) for h in fs.collect_hits(tracks)}
        assert ("name:chasestatus", "remixer") in roles


# ---------------------------------------------------------------------------
# Factors
# ---------------------------------------------------------------------------


class TestFactors:
    def test_recency_new_like_is_full(self) -> None:
        assert fs.recency_weight("2026-11-11 00:00:00", NOW) == pytest.approx(1.0)

    def test_recency_one_year_is_half_decay(self) -> None:
        w = fs.recency_weight("2025-11-11 00:00:00", NOW)
        assert w == pytest.approx(0.3 + 0.7 * 0.5, abs=0.01)

    def test_recency_floor(self) -> None:
        assert fs.recency_weight(None, NOW) == 0.3

    def test_like_order_fallback(self) -> None:
        assert fs.recency_weight(None, NOW, 0) == pytest.approx(1.0)
        assert fs.recency_weight(None, NOW, 1000) == pytest.approx(0.65)
        assert fs.recency_weight(None, NOW, 100_000) == pytest.approx(0.3, abs=1e-6)

    def test_like_time_beats_like_order(self) -> None:
        assert fs.recency_weight("2026-11-11 00:00:00", NOW, 5000) == pytest.approx(1.0)
        assert fs.recency_weight("2006-01-01 00:00:00", NOW) == pytest.approx(
            0.3, abs=0.001
        )

    def test_activity_factor(self) -> None:
        assert fs.activity_factor(None, NOW) == 0.6
        assert fs.activity_factor(_activity(uploads_90d=0), NOW) == 0.5
        assert fs.activity_factor(_activity(uploads_90d=4), NOW) == 0.75
        assert fs.activity_factor(_activity(uploads_90d=20), NOW) == 1.0
        dormant = _activity(last_upload_at="2025-01-01T00:00:00+00:00")
        assert fs.activity_factor(dormant, NOW) == 0.1
        never = _activity(last_upload_at=None)
        assert fs.activity_factor(never, NOW) == 0.1

    def test_activity_uses_latest_of_upload_and_repost(self) -> None:
        a = _activity(
            last_upload_at="2024-01-01T00:00:00+00:00",
            last_repost_at="2026-10-01T00:00:00+00:00",
            uploads_90d=0,
            reposts_90d=8,
        )
        assert fs.activity_factor(a, NOW) == 1.0

    def test_size_factor(self) -> None:
        assert fs.size_factor(None) == 1.0
        assert fs.size_factor(500_000) == 1.0
        assert fs.size_factor(10_000_000) == pytest.approx(0.5)
        assert 0.5 < fs.size_factor(2_000_000) < 1.0
        assert fs.size_factor(10**10) == 0.2

    def test_score_is_product(self) -> None:
        tracks = [_track(str(i), "x", uploader=("1", "acct", "Acct")) for i in range(3)]
        ctx = _ctx(activity={"1": _activity(uploads_90d=4, followers=10_000_000)})
        s = _by_key(tracks, ctx)["1"]
        assert s["evidence_score"] == pytest.approx(0.9)
        assert s["score"] == pytest.approx(0.9 * 0.75 * 0.5)


# ---------------------------------------------------------------------------
# Exclusions, merge, labels
# ---------------------------------------------------------------------------


class TestExclusions:
    def test_followed_by_id(self) -> None:
        tracks = [_track("1", "x", uploader=("5", "someone", "Someone"))]
        ctx = _ctx(followed=(Account("5", "Totally Different", "zzz"),))
        assert "5" not in _by_key(tracks, ctx)

    def test_followed_by_decorated_display_name(self) -> None:
        tracks = [_track(str(i), "Wooli") for i in range(3)]
        tracks += [_track(str(i + 10), "Dirt Monkey") for i in range(3)]
        followed = (
            Account("1", "Wooli 🐘", "woolimusic"),
            Account("2", "▶︎ Dirt Monkey ◀︎", "dirtmonkey"),
        )
        assert _by_key(tracks, _ctx(followed=followed)) == {}

    def test_followed_by_stripped_slug(self) -> None:
        tracks = [_track(str(i), "Eliminate") for i in range(3)]
        ctx = _ctx(followed=(Account("3", "ELMNT*", "eliminatemusic"),))
        assert _by_key(tracks, ctx) == {}

    def test_label_followed_does_not_hide_artist(self) -> None:
        tracks = [_track(str(i), "DirtySnatcha") for i in range(3)]
        ctx = _ctx(followed=(Account("4", "DirtySnatcha Records", "dsrecords"),))
        assert "name:dirtysnatcha" in _by_key(tracks, ctx)

    def test_dismissed_account_and_name(self) -> None:
        tracks = [
            _track(str(i), "Named", uploader=("8", "acct", "Acct")) for i in range(3)
        ]
        ctx = _ctx(dismissed=frozenset({"8", "name:named"}))
        assert _by_key(tracks, ctx) == {}

    def test_dismissed_name_hides_account_it_resolves_to(self) -> None:
        tracks = [_track(str(i), "Named") for i in range(3)]
        ctx = _ctx(
            resolutions={"named": Resolution("8", "named", "Named", "high", "x")},
            dismissed=frozenset({"name:named"}),
        )
        assert _by_key(tracks, ctx) == {}

    def test_name_only_needs_two_tracks(self) -> None:
        assert "name:solo" not in _by_key([_track("1", "Solo")])
        assert "name:duo" in _by_key([_track("1", "Duo"), _track("2", "Duo")])

    def test_single_track_account_survives(self) -> None:
        assert "8" in _by_key([_track("1", "x", uploader=("8", "acct", "Acct"))])


class TestMergeAndLabels:
    def test_name_merges_into_resolved_account(self) -> None:
        tracks = [
            _track("1", "Phrva", uploader=("70", "phrva", "Phrva")),
            _track("2", "Other", "Song (PHRVA Remix)"),
        ]
        ctx = _ctx(resolutions=fs.uploader_resolutions(tracks))
        by_key = _by_key(tracks, ctx)
        assert "name:phrva" not in by_key
        assert by_key["70"]["evidence"]["uploaded"] == 1
        assert by_key["70"]["evidence"]["remixer"] == 1
        assert by_key["70"]["display_name"] == "Phrva"

    def test_stripped_slug_resolves_only_without_exact_claim(self) -> None:
        tracks = [
            _track("1", "x", uploader=("1", "gawmmusic", None)),
            _track("2", "x", uploader=("2", "snakemusic", None)),
            _track("3", "x", uploader=("3", "snake", "Snake")),
        ]
        found = fs.uploader_resolutions(tracks)
        assert found["gawm"].soundcloud_user_id == "1"
        assert found["snake"].soundcloud_user_id == "3"  # exact key wins

    def test_label_split_by_name(self) -> None:
        tracks = [_track(str(i), "x", uploader=("9", "mcat", "Monstercat Records"))
                  for i in range(2)]  # fmt: skip
        artists, labels = fs.split_suggestions(fs.rank_entities(tracks, _ctx()), 10, 10)
        assert [s["key"] for s in labels] == ["9"] and artists == []

    def test_label_from_activity_flag_and_override(self) -> None:
        tracks = [_track("1", "x", uploader=("9", "hybridtrap", "Hybrid Trap"))]
        ctx = _ctx(activity={"9": _activity(is_label=True)})
        assert _by_key(tracks, ctx)["9"]["is_label"] is True
        ctx = ctx._replace(label_overrides={"9": False})
        assert _by_key(tracks, ctx)["9"]["is_label"] is False

    def test_label_from_liked_uploads_crediting_others(self) -> None:
        mcat = ("9", "monstercat", "Monstercat")
        tracks = [_track(str(i), f"Artist {i}", uploader=mcat) for i in range(3)]
        own = ("8", "wooli", "Wooli")
        tracks += [_track(f"w{i}", "Wooli x Someone", uploader=own) for i in range(3)]
        by_key = _by_key(tracks)
        assert by_key["9"]["is_label"] is True
        assert by_key["8"]["is_label"] is False

    def test_liked_uploads_without_credits_are_not_a_label(self) -> None:
        eater = ("9", "eater", "Eater")
        tracks = [_track(str(i), "", t, uploader=eater)
                  for i, t in enumerate(("Echoes", "Orbit", "Pulse"))]  # fmt: skip
        assert _by_key(tracks)["9"]["is_label"] is False
        assert fs.credits_others({"eater"}, [("", "A - Song")] * 3) is True

    def test_override_marks_name_entry_as_label(self) -> None:
        tracks = [_track("1", "Promo"), _track("2", "Promo")]
        ctx = _ctx(label_overrides={"name:promo": True})
        assert _by_key(tracks, ctx)["name:promo"]["is_label"] is True

    def test_combine_resolutions_order(self) -> None:
        hit_a = Resolution("1", None, None, "high", "uploader")
        hit_b = Resolution("2", None, None, "high", "discovery_artists")
        miss = Resolution(None, None, None, "none", "search")
        combined = fs.combine_resolutions(
            {"x": hit_a, "z": miss}, {"x": hit_b, "z": hit_b}
        )
        assert combined == {"x": hit_a, "z": hit_b}


class TestSuggestionShape:
    def test_tracks_newest_first_and_last_liked(self) -> None:
        tracks = [
            _track("1", "A", liked_at=None),
            _track("2", "A", liked_at="2026-01-01 00:00:00"),
            _track("3", "A", liked_at="2026-06-01 00:00:00"),
        ]
        s = _by_key(tracks)["name:a"]
        assert [t["soundcloud_id"] for t in s["tracks"]] == ["3", "2", "1"]
        assert s["last_liked_at"] == "2026-06-01 00:00:00"
        assert s["soundcloud_user_id"] is None
        assert set(s["evidence"]) == set(fs.ROLES)

    def test_tracks_capped_at_20(self) -> None:
        tracks = [_track(str(i), "A") for i in range(30)]
        assert len(_by_key(tracks)["name:a"]["tracks"]) == 20


# ---------------------------------------------------------------------------
# DB loaders and routes
# ---------------------------------------------------------------------------


def _exec(sql: str, params: tuple = ()) -> None:
    with get_db_connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def _seed() -> None:
    """Two liked uploads by account 70, a kept track, a followed artist."""
    for sc_id in ("t1", "t2"):
        _exec(
            """INSERT INTO sc_likes (soundcloud_id, source, uploader_soundcloud_id,
            uploader_permalink, uploader_username) VALUES (?, 'sync', '70', 'phrva', 'PHRVA')""",
            (sc_id,),
        )
        _exec(
            """INSERT INTO tracks (title, artist, soundcloud_id, source)
            VALUES ('Song', 'PHRVA', ?, 'soundcloud')""",
            (sc_id,),
        )
    _exec(
        """INSERT INTO discovery_tracks (soundcloud_id, title, artist_name,
        uploader_soundcloud_id) VALUES ('k1', 'Kept', 'Wooli', '1')"""
    )
    _exec(
        """INSERT INTO sc_track_decisions (soundcloud_id, decision, surface)
        VALUES ('k1', 'keep', 'feed')"""
    )
    _exec(
        """INSERT INTO discovery_artists (soundcloud_user_id, slug, display_name,
        ranking, is_following) VALUES ('1', 'woolimusic', 'Wooli 🐘', 1, 1)"""
    )


class TestQueries:
    def test_load_evidence_tracks(self) -> None:
        _seed()
        with get_db_connection() as conn:
            tracks = {t.soundcloud_id: t for t in queries.load_evidence_tracks(conn)}
        assert tracks["t1"].liked and tracks["t1"].uploader_id == "70"
        kept = tracks["k1"]
        assert not kept.liked and kept.uploader_id == "1"
        assert kept.uploader_username == "Wooli 🐘"  # named via discovery_artists

    def test_compute_ranked_excludes_followed(self) -> None:
        _seed()
        with get_db_connection() as conn:
            keys = [s["key"] for s in queries.compute_ranked(conn, NOW)]
        assert keys == ["70"]

    def test_discovery_resolutions(self) -> None:
        _seed()
        with get_db_connection() as conn:
            found = queries.discovery_resolutions(conn)
        assert found["wooli"].soundcloud_user_id == "1"
        assert found["woolimusic"].soundcloud_user_id == "1"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRoutes:
    def test_get_contract(self, client: TestClient) -> None:
        _seed()
        body = client.get("/api/follow-suggestions").json()
        assert set(body) == {"artists", "labels", "generated_at"}
        (s,) = body["artists"]
        assert s["key"] == "70" and s["display_name"] == "PHRVA"
        assert s["evidence"]["uploaded"] == 2 and body["labels"] == []
        for field in (
            "soundcloud_user_id",
            "permalink",
            "avatar_url",
            "followers",
            "is_label",
            "score",
            "last_liked_at",
            "activity",
            "tracks",
        ):
            assert field in s  # fmt: skip

    def test_dismiss_is_permanent(self, client: TestClient) -> None:
        _seed()
        assert client.post("/api/follow-suggestions/70/dismiss").json() == {"ok": True}
        assert client.post("/api/follow-suggestions/70/dismiss").json() == {"ok": True}
        assert client.get("/api/follow-suggestions").json()["artists"] == []

    def test_dismiss_name_key(self, client: TestClient) -> None:
        assert (
            client.post("/api/follow-suggestions/name:eater/dismiss").status_code == 200
        )
        with get_db_connection() as conn:
            assert "name:eater" in queries.load_dismissed(conn)

    def test_label_override_moves_section(self, client: TestClient) -> None:
        _seed()
        r = client.post("/api/follow-suggestions/70/label", json={"is_label": True})
        assert r.json() == {"ok": True}
        body = client.get("/api/follow-suggestions").json()
        assert [s["key"] for s in body["labels"]] == ["70"] and body["artists"] == []
        client.post("/api/follow-suggestions/70/label", json={"is_label": False})
        assert client.get("/api/follow-suggestions").json()["artists"][0]["key"] == "70"

    def test_bad_key_rejected(self, client: TestClient) -> None:
        assert (
            client.post("/api/follow-suggestions/drop;table/dismiss").status_code == 422
        )
        r = client.post("/api/follow-suggestions/70/label", json={})
        assert r.status_code == 422


class TestSemicolonCredits:
    def test_semicolon_credits_split(self) -> None:
        _exec("INSERT INTO sc_likes (soundcloud_id, source) VALUES ('s1', 'sync')")
        _exec(
            """INSERT INTO tracks (title, artist, soundcloud_id, source)
            VALUES ('Song', 'Ganja White Night; Boogie T', 's1', 'soundcloud')"""
        )
        with get_db_connection() as conn:
            (track,) = queries.load_evidence_tracks(conn)
        refs = {h.ref for h in fs.collect_hits([track])}
        assert refs == {"name:ganjawhitenight", "name:boogiet"}

    def test_uploader_permalink_from_track_url(self) -> None:
        _exec("INSERT INTO sc_likes (soundcloud_id, source) VALUES ('u1', 'sync')")
        _exec(
            """INSERT INTO discovery_tracks (soundcloud_id, uploader_soundcloud_id,
            permalink_url) VALUES ('u1', '70', 'https://soundcloud.com/phrva/x')"""
        )
        with get_db_connection() as conn:
            (track,) = queries.load_evidence_tracks(conn)
        assert (track.uploader_id, track.uploader_permalink) == ("70", "phrva")
