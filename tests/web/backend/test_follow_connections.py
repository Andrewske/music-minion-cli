"""Follow suggestions from connections: co-credits and favorites' followings."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud import api as sc_api
from web.backend import follow_connections as fc
from web.backend.routers.follow_connections import router

NOW = datetime(2026, 11, 11, 3, 0, 0)


def _exec(sql: str, params: tuple = ()) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def add_artist(
    name: str,
    tier: str = "",
    sc_id: str | None = None,
    slug: str | None = None,
    following: int = 1,
) -> int:
    return _exec(
        """INSERT INTO discovery_artists
            (slug, display_name, display_name_normalized, ranking, tier,
             is_following, soundcloud_user_id)
           VALUES (?, ?, ?, 1, ?, ?, ?)""",
        (slug or name.lower(), name, name.lower(), tier, following, sc_id),
    )


def add_track(artist: str, title: str, remix_artist: str | None = None) -> None:
    _exec(
        "INSERT INTO tracks (title, artist, artist_normalized, remix_artist)"
        " VALUES (?, ?, ?, ?)",
        (title, artist, artist.lower(), remix_artist),
    )


def resolve(name_key: str, sc_id: str, display: str) -> None:
    _exec(
        """INSERT INTO sc_name_resolutions
           (name_key, soundcloud_user_id, permalink, display_name, confidence, source)
           VALUES (?, ?, ?, ?, 'high', 'test')""",
        (name_key, sc_id, name_key, display),
    )


def dismiss(key: str) -> None:
    _exec(
        "INSERT INTO follow_suggestion_dismissals (soundcloud_user_id) VALUES (?)",
        (key,),
    )


def follows(
    follower: str, followee: str, followers: int = 1000, at: str = "2026-11-10 00:00:00"
) -> None:
    _exec(
        """INSERT INTO sc_artist_followings
           (follower_id, followee_id, followee_permalink, followee_username,
            followee_followers, fetched_at) VALUES (?, ?, ?, ?, ?, ?)""",
        (follower, followee, f"p{followee}", f"User {followee}", followers, at),
    )


def co_credit() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        return fc.compute_co_credit(conn)


def by_name(results: list[dict]) -> dict[str, dict]:
    return {c["display_name"]: c for c in results}


# ---------------------------------------------------------------------------
# Name keys
# ---------------------------------------------------------------------------


def test_name_key_drops_decoration() -> None:
    assert fc.name_key("▶︎ Dirt Monkey ◀︎") == "dirtmonkey"
    assert fc.name_key("Wooli 🐘") == "wooli"
    assert fc.name_key("Eliminate*") == "eliminate"


def test_slug_keys_strip_suffix_and_prefix() -> None:
    assert "wooli" in fc.slug_keys("woolimusic")
    assert "snake" in fc.slug_keys("djsnake")
    assert "djsnake" in fc.slug_keys("djsnake")


# ---------------------------------------------------------------------------
# Co-credit weighting
# ---------------------------------------------------------------------------


def test_score_links_tier_times_relation() -> None:
    artists = {1: {"tier": "S"}, 2: {"tier": "A"}, 3: {"tier": "B"}}
    assert fc.score_links(
        {1: "collab", 2: "remix", 3: "feat"}, artists
    ) == pytest.approx(3 * 1.0 + 2 * 0.8 + 1 * 0.6)


def test_strongest_relation_per_artist_wins() -> None:
    top = [{"id": 1, "names": {"alpha"}, "tier": "S", "display_name": "Alpha"}]
    tracks = [
        {"artist": "Beta", "title": "Song (Alpha Remix)", "remix_artist": None},
        {"artist": "Alpha & Beta", "title": "Other", "remix_artist": None},
    ]
    partners = fc.collect_co_credits(tracks, top)
    assert partners["beta"]["links"] == {1: "collab"}


def test_relations_map_to_contract() -> None:
    top = [{"id": 1, "names": {"alpha"}, "tier": "S", "display_name": "Alpha"}]
    tracks = [
        {"artist": "Alpha", "title": "Song (feat. Gamma)", "remix_artist": None},
        {"artist": "Delta", "title": "Song (Alpha Remix)", "remix_artist": None},
    ]
    partners = fc.collect_co_credits(tracks, top)
    assert partners["gamma"]["links"] == {1: "feat"}
    assert partners["delta"]["links"] == {1: "remix"}


def test_co_credit_scores_and_thresholds() -> None:
    add_artist("Alpha", "S")
    add_artist("Bravo", "A")
    add_artist("Charlie", "B")
    add_artist("Cee", "C")
    add_track("Alpha & Partner", "One")
    add_track("Bravo & Partner", "Two")
    add_track("Bravo & Solo A", "Three")
    add_track("Charlie & Solo B", "Four")
    add_track("Cee & Solo C", "Five")

    results = by_name(co_credit())

    assert results["Partner"]["score"] == pytest.approx(5.0)
    assert [v["display_name"] for v in results["Partner"]["via"]] == ["Alpha", "Bravo"]
    assert results["Solo A"]["score"] == pytest.approx(2.0)  # one A collab passes
    assert "Solo B" not in results  # one B collab scores 1
    assert "Solo C" not in results  # C-tier links don't count


def test_co_credit_exclusions() -> None:
    add_artist("Alpha", "S")
    add_artist("Wooli 🐘", "", slug="woolimusic")  # followed, untiered
    add_artist("Gone", "", sc_id="900")
    add_track("Alpha & Wooli", "a")
    add_track("Alpha & Gone Alias", "b")
    add_track("Alpha & Dismissed Name", "c")
    add_track("Alpha & Dismissed Id", "d")
    add_track("Alpha & Keeper", "e")
    resolve("gonealias", "900", "Gone")
    resolve("dismissedid", "901", "Dismissed Id")
    dismiss("name:dismissedname")
    dismiss("901")

    results = co_credit()

    assert [c["display_name"] for c in results] == ["Keeper"]
    assert results[0]["key"] == "name:keeper"
    assert results[0]["soundcloud_user_id"] is None


def test_known_id_beats_name_match() -> None:
    add_artist("Alpha", "S")
    add_artist("Snatch Records", "", sc_id="10", slug="snatch")  # the label
    add_track("Alpha & Snatch", "a")
    resolve("snatch", "11", "Snatch")  # the artist account, not followed

    assert [c["key"] for c in co_credit()] == ["11"]


def test_co_credit_uses_resolution_and_activity() -> None:
    add_artist("Alpha", "S")
    add_track("Alpha & keeper", "a")
    resolve("keeper", "777", "KEEPER")
    _exec(
        "INSERT INTO sc_account_activity (soundcloud_user_id, avatar_url, followers)"
        " VALUES ('777', 'https://img/k.jpg', 4200)"
    )

    [conn_] = co_credit()

    assert conn_["key"] == "777"
    assert conn_["display_name"] == "KEEPER"
    assert conn_["avatar_url"] == "https://img/k.jpg"
    assert conn_["followers"] == 4200
    assert conn_["via"][0]["relation"] == "collab"


# ---------------------------------------------------------------------------
# Favorites follow
# ---------------------------------------------------------------------------


def _fav(sc_id: str, tier: str) -> dict[str, Any]:
    return {"id": int(sc_id), "display_name": f"Fav {sc_id}", "tier": tier}


def test_favorites_follow_needs_three_and_damps_popularity() -> None:
    favorites = {
        s: _fav(s, t) for s, t in [("1", "S"), ("2", "A"), ("3", "A"), ("4", "S")]
    }
    rows = [
        *(
            {"follower_id": f, "followee_id": "big", "followee_followers": 1_000_000}
            for f in "1234"
        ),
        *(
            {"follower_id": f, "followee_id": "small", "followee_followers": 990}
            for f in "123"
        ),
        *({"follower_id": f, "followee_id": "two"} for f in "12"),
    ]
    results = fc.build_favorites_follow(rows, favorites, set(), {})

    assert [c["key"] for c in results] == ["small", "big"]
    assert results[0]["score"] == pytest.approx(
        3.5 / 3, abs=1e-3
    )  # (1.5+1+1)/log10(1000)
    assert results[1]["score"] == pytest.approx(5.0 / 6, abs=1e-3)
    assert {v["relation"] for v in results[0]["via"]} == {"follows"}


def test_favorites_follow_exclusions() -> None:
    favorites = {s: _fav(s, "A") for s in "123"}
    rows = [
        {"follower_id": f, "followee_id": x}
        for f in "123"
        for x in ("me", "known", "new")
    ]
    results = fc.build_favorites_follow(rows, favorites, {"me", "known"}, {})
    assert [c["key"] for c in results] == ["new"]


def test_compute_favorites_follow_from_db() -> None:
    for sc_id, tier in [("1", "S"), ("2", "A"), ("3", "A"), ("4", "B")]:
        add_artist(f"Fav {sc_id}", tier, sc_id=sc_id)
    add_artist("Followed", "", sc_id="50")
    for f in "123":
        follows(f, "50")
        follows(f, "60")
        follows(f, "70")
        follows(f, "self")
    for f in "14":  # the B artist doesn't count toward the 3
        follows(f, "80")
    follows("2", "80")
    dismiss("70")

    with get_db_connection() as conn:
        results = fc.compute_favorites_follow(conn, self_user_id="self")

    assert [c["key"] for c in results] == ["60"]
    assert results[0]["display_name"] == "User 60"


# ---------------------------------------------------------------------------
# SoundCloud followings API
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data: Any) -> None:
        self._data = data

    def json(self) -> Any:
        return self._data


def _state() -> ProviderState:
    return ProviderState(config=ProviderConfig(name="soundcloud"), authenticated=True)


def test_get_user_followings_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []
    pages = {
        f"{sc_api.API_BASE_URL}/users/soundcloud:users:42/followings": {
            "collection": [{"id": 1}, {"id": 2}],
            "next_href": "https://next/2",
        },
        "https://next/2": {"collection": [{"id": 3}], "next_href": None},
    }

    def fake(state, method, url, **kwargs):
        calls.append((url, kwargs.get("params")))
        return state, _Resp(pages[url])

    monkeypatch.setattr(sc_api, "_request_with_backoff", fake)
    _s, users, error = sc_api.get_user_followings(_state(), "42")

    assert error is None
    assert [u["id"] for u in users] == [1, 2, 3]
    assert calls[0][1] == {"limit": 200, "linked_partitioning": "true"}
    assert calls[1][1] == {}


def test_get_user_followings_max_pages_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def endless(state, method, url, **kwargs):
        return state, _Resp({"collection": [{"id": 1}], "next_href": "https://more"})

    monkeypatch.setattr(sc_api, "_request_with_backoff", endless)
    _s, users, error = sc_api.get_user_followings(_state(), "42", max_pages=3)
    assert len(users) == 3 and error is None

    def boom(state, method, url, **kwargs):
        raise sc_api.requests.HTTPError("503")

    monkeypatch.setattr(sc_api, "_request_with_backoff", boom)
    _s, users, error = sc_api.get_user_followings(_state(), "42")
    assert users == [] and "503" in error


# ---------------------------------------------------------------------------
# Refresh job
# ---------------------------------------------------------------------------


def test_stale_favorites_orders_never_first_and_caps() -> None:
    fresh = (NOW - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    old = (NOW - timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    older = (NOW - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    fetched = {"fresh": fresh, "old": old, "older": older}
    assert fc.stale_favorites(["fresh", "old", "older", "never"], fetched, NOW) == [
        "never",
        "older",
        "old",
    ]
    many = [str(i) for i in range(50)]
    assert len(fc.stale_favorites(many, {}, NOW)) == fc.FOLLOWINGS_ARTISTS_PER_RUN


def test_refresh_due_once_per_night() -> None:
    assert fc.refresh_due(None, NOW)
    assert not fc.refresh_due(
        (NOW - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"), NOW
    )
    assert fc.refresh_due(
        (NOW - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"), NOW
    )


def _fake_followings(
    monkeypatch: pytest.MonkeyPatch, fail_on: str | None = None
) -> list[str]:
    fetched: list[str] = []

    def fake(state, user_id, max_pages):
        fetched.append(user_id)
        if user_id == fail_on:
            return state, [], "boom"
        users = [{"id": 500, "permalink": "x", "username": "X", "followers_count": 12}]
        return state, users, None

    monkeypatch.setattr(fc, "get_user_followings", fake)
    return fetched


def _followings_rows() -> list[tuple]:
    with get_db_connection() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                "SELECT follower_id, followee_id, followee_followers, fetched_at"
                " FROM sc_artist_followings ORDER BY follower_id, followee_id"
            )
        ]


def test_refresh_replaces_stale_rows_and_skips_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_artist("S1", "S", sc_id="1")
    add_artist("A2", "A", sc_id="2")
    add_artist("B3", "B", sc_id="3")  # B tier is not a favorite
    stale = (NOW - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    follows("1", "old-followee", at=stale)
    fetched = _fake_followings(monkeypatch)

    _state_out, refreshed = fc.refresh_favorite_followings(_state(), NOW)

    assert refreshed == 2 and sorted(fetched) == ["1", "2"]
    now_s = NOW.strftime("%Y-%m-%d %H:%M:%S")
    assert _followings_rows() == [("1", "500", 12, now_s), ("2", "500", 12, now_s)]

    # Same night: nothing runs again.
    fetched.clear()
    fc.refresh_favorite_followings(_state(), NOW + timedelta(hours=1))
    assert fetched == []


def test_refresh_caps_artists_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    for i in range(35):
        add_artist(f"A{i}", "A", sc_id=str(100 + i))
    fetched = _fake_followings(monkeypatch)

    fc.refresh_favorite_followings(_state(), NOW)

    assert len(fetched) == fc.FOLLOWINGS_ARTISTS_PER_RUN


def test_refresh_stops_on_first_error(monkeypatch: pytest.MonkeyPatch) -> None:
    add_artist("S1", "S", sc_id="1")
    add_artist("S2", "S", sc_id="2")
    stale = (NOW - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    follows("1", "keep-me", at=stale)
    fetched = _fake_followings(
        monkeypatch, fail_on="2"
    )  # "2" was never fetched -> first

    _s, refreshed = fc.refresh_favorite_followings(_state(), NOW)

    assert refreshed == 0 and fetched == ["2"]
    assert [r[1] for r in _followings_rows()] == ["keep-me"]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_connections_route(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    add_artist("Alpha", "S", sc_id="1")
    add_artist("Bravo", "A", sc_id="2")
    add_artist("Charlie", "A", sc_id="3")
    add_track("Alpha & Partner", "One")
    for f in "123":
        follows(f, "60")
        follows(f, "61")
    monkeypatch.setenv("SC_SELF_USER_ID", "61")

    body = client.get("/api/follow-suggestions/connections").json()

    assert [c["display_name"] for c in body["co_credit"]] == ["Partner"]
    assert body["co_credit"][0]["via"] == [
        {
            "discovery_artist_id": 1,
            "display_name": "Alpha",
            "tier": "S",
            "relation": "collab",
        }
    ]
    assert [c["key"] for c in body["favorites_follow"]] == ["60"]
