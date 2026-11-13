"""Unfollow suggestions: scoring rules, the DB loaders, keep, and the routes."""

from datetime import UTC, datetime
from typing import Any

import pytest
import requests
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from web.backend import artist_unfollow
from web.backend import unfollow_suggestions as us
from web.backend.follow_suggestions import RECENCY_FLOOR
from web.backend.queries import unfollow_suggestions as queries
from web.backend.routers.unfollow_suggestions import MAX_BATCH, router
from web.backend.unfollow_suggestions import FollowedAccount, GoodItem

NOW = datetime(2026, 11, 12, tzinfo=UTC)
FEED_START = datetime(2026, 4, 15, tzinfo=UTC)
AUTH = ProviderState(config=ProviderConfig(name="soundcloud"), authenticated=True)


def _account(artist_id: int = 1, **overrides: Any) -> FollowedAccount:
    base = FollowedAccount(
        discovery_artist_id=artist_id,
        soundcloud_user_id=str(1000 + artist_id),
        display_name=f"Artist {artist_id}",
        slug=f"artist-{artist_id}",
        avatar_url=None,
        followers=None,
        tier=None,
        followed_at=None,
        polled=True,
        reposts=0,
        uploads=0,
        last_item_at=None,
    )
    return base._replace(**overrides)


def _item(artist_id: int, sc_id: str, kind: str = "repost", **kw: Any) -> GoodItem:
    base = GoodItem(artist_id, sc_id, kind, "2026-10-01 00:00:00", None, None)
    return base._replace(**kw)


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------


class TestFindItems:
    def test_repost_only_one_account_carried_is_a_find(self) -> None:
        finds, good = us.find_items([_item(1, "a"), _item(1, "b"), _item(2, "b")])
        assert [(f.discovery_artist_id, f.soundcloud_id) for f in finds] == [(1, "a")]
        assert good == {1: 2, 2: 1}

    def test_own_upload_counts_even_when_others_repost_it(self) -> None:
        finds, _good = us.find_items([_item(1, "a", "upload"), _item(2, "a")])
        assert [(f.discovery_artist_id, f.kind) for f in finds] == [(1, "upload")]

    def test_upload_plus_own_repost_merges_to_upload(self) -> None:
        items = [
            _item(1, "a", "repost", item_at="2026-09-01 00:00:00"),
            _item(1, "a", "upload", item_at="2026-08-01 00:00:00"),
        ]
        finds, good = us.find_items(items)
        assert len(finds) == 1
        assert finds[0].kind == "upload"
        assert finds[0].item_at == "2026-08-01 00:00:00"
        assert good[1] == 1


class TestEligibility:
    def test_unpolled_skipped(self) -> None:
        assert not us.is_eligible(_account(polled=False), NOW)

    def test_recent_follow_skipped(self) -> None:
        recent = _account(followed_at="2026-11-01 00:00:00")
        assert not us.is_eligible(recent, NOW)

    def test_old_or_unknown_follow_kept(self) -> None:
        assert us.is_eligible(_account(followed_at="2026-09-01 00:00:00"), NOW)
        assert us.is_eligible(_account(), NOW)


class TestLabelName:
    @pytest.mark.parametrize(
        "name",
        ["Slow Roast Records", "JOYTIME COLLECTIVE", "EuropeEDM Promo", "Bass Reposts"],
    )
    def test_matches(self, name: str) -> None:
        assert us.is_label_name(name, "x")

    def test_slug_matches_too(self) -> None:
        assert us.is_label_name("Wobble", "wobble-recordings")

    def test_artist_name_does_not(self) -> None:
        assert not us.is_label_name("Kimati", "kimati")


class TestScore:
    def test_noise_uses_months_since_follow_or_feed_start(self) -> None:
        old = us.score_account(_account(reposts=210), [], 0, FEED_START, NOW)
        assert old["noise_per_month"] == pytest.approx(210 / (211 / 30.44), abs=0.1)
        new = _account(reposts=60, followed_at="2026-09-13 00:00:00")
        assert (
            us.score_account(new, [], 0, FEED_START, NOW)["noise_per_month"] == 30.4
        )  # 60 days

    def test_value_sums_recency_and_counts_parts(self) -> None:
        finds = [
            _item(1, "a", liked_at="2026-11-12T00:00:00+00:00"),
            _item(1, "b", "upload", item_at="2026-11-01 00:00:00"),
        ]
        row = us.score_account(
            _account(reposts=5, uploads=1), finds, 4, FEED_START, NOW
        )
        assert row["value"] == pytest.approx(1.0 + RECENCY_FLOOR, abs=1e-3)
        assert (row["unique_finds"], row["liked_uploads"], row["good"]) == (1, 1, 4)
        assert row["items"] == 6
        assert row["last_find_at"] == "2026-11-01T00:00:00+00:00"

    def test_last_find_compares_across_formats(self) -> None:
        assert (
            us.latest(["2026/10/30 18:58:01 +0000", "2026-10-02T00:00:00+00:00"])
            == "2026-10-30T18:58:01+00:00"
        )


def _row(**overrides: Any) -> dict[str, Any]:
    base = {
        "items": 100, "unique_finds": 0, "liked_uploads": 0,
        "display_name": "Someone", "slug": "someone",
    }  # fmt: skip
    return {**base, **overrides}


class TestSections:
    def test_section_rules(self) -> None:
        assert us.section_of(_row()) == "redundant"
        assert us.section_of(_row(unique_finds=1)) == "redundant"
        assert us.section_of(_row(unique_finds=2)) == "low_yield"
        assert us.section_of(_row(liked_uploads=1)) == "low_yield"
        assert us.section_of(_row(items=49)) == "low_yield"
        assert us.section_of(_row(items=0)) == "dormant"
        assert us.section_of(_row(items=10, display_name="X Records")) == "labels"
        assert us.section_of(_row(display_name="X Records")) == "redundant"

    def test_build_orders_and_skips_ineligible(self) -> None:
        accounts = [
            _account(1, reposts=100),
            _account(2, reposts=300, tier="A"),  # tiered accounts still listed
            _account(3, reposts=20),
            _account(4, reposts=20),
            _account(5),
            _account(6, polled=False),
        ]
        items = [_item(3, "a", liked_at="2026-11-01T00:00:00+00:00")]
        sections = us.build_sections(accounts, items, FEED_START, NOW)
        ids = {k: [r["discovery_artist_id"] for r in v] for k, v in sections.items()}
        assert ids == {
            "redundant": [2, 1],
            "dormant": [5],
            "labels": [],
            "low_yield": [4, 3],
        }

    def test_low_yield_is_capped(self) -> None:
        accounts = [_account(i, reposts=5) for i in range(1, us.LOW_YIELD_MAX + 5)]
        sections = us.build_sections(accounts, [], FEED_START, NOW)
        assert len(sections["low_yield"]) == us.LOW_YIELD_MAX


# ---------------------------------------------------------------------------
# DB loaders and keep
# ---------------------------------------------------------------------------


def _insert(table: str, **cols: Any) -> int:
    names, marks = ", ".join(cols), ", ".join("?" * len(cols))
    with get_db_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO {table} ({names}) VALUES ({marks})", tuple(cols.values())
        )
        conn.commit()
        return int(cursor.lastrowid or 0)


def add_artist(slug: str, **cols: Any) -> int:
    values = {
        "slug": slug, "display_name": slug.upper(), "ranking": 1,
        "is_following": 1, "uploads_last_checked": "2026-11-01 00:00:00", **cols,
    }  # fmt: skip
    return _insert("discovery_artists", **values)


def add_repost(
    artist_id: int, sc_id: str, seen_at: str = "2026-05-01 00:00:00"
) -> None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM discovery_tracks WHERE soundcloud_id = ?", (sc_id,)
        ).fetchone()
    track_id = row[0] if row else _insert("discovery_tracks", soundcloud_id=sc_id)
    _insert(
        "discovery_track_reposters",
        discovery_track_id=track_id,
        discovery_artist_id=artist_id,
        seen_at=seen_at,
    )


def add_upload(artist_id: int, sc_id: str) -> None:
    _insert(
        "sc_artist_uploads",
        discovery_artist_id=artist_id,
        soundcloud_id=sc_id,
        uploaded_at="2026-10-01T00:00:00+00:00",
    )


def like(sc_id: str) -> None:
    _insert("sc_likes", soundcloud_id=sc_id, source="test", like_order=0)


class TestLoaders:
    def test_finds_and_counts_from_tables(self) -> None:
        solo = add_artist("solo")
        crowd = add_artist("crowd")
        for sc_id in ("a", "b", "c"):
            add_repost(solo, sc_id)
        add_repost(crowd, "b")
        add_upload(crowd, "u")
        for sc_id in ("a", "b", "u"):
            like(sc_id)
        with get_db_connection() as conn:
            accounts = {a.slug: a for a in queries.load_accounts(conn)}
            finds, good = us.find_items(queries.load_good_items(conn))
        assert (accounts["solo"].reposts, accounts["crowd"].uploads) == (3, 1)
        assert {(f.discovery_artist_id, f.soundcloud_id) for f in finds} == {
            (solo, "a"),
            (crowd, "u"),
        }
        assert good == {solo: 2, crowd: 2}

    def test_kept_account_hidden_but_still_carries(self) -> None:
        kept = add_artist("kept", tier="A")
        other = add_artist("other")
        add_repost(kept, "a")
        add_repost(other, "a")
        like("a")
        with get_db_connection() as conn:
            assert queries.keep(conn, kept)
            slugs = {a.slug for a in queries.load_accounts(conn)}
            finds, _good = us.find_items(queries.load_good_items(conn))
        assert slugs == {"other"}
        assert finds == []  # kept still reposted it, so other's repost is not unique

    def test_keep_tiers_untiered_as_c_only(self) -> None:
        untiered = add_artist("untiered", tier=None)
        tiered = add_artist("tiered", tier="S")
        with get_db_connection() as conn:
            queries.keep(conn, untiered)
            queries.keep(conn, tiered)
            queries.keep(conn, tiered)  # idempotent
            tiers = dict(conn.execute("SELECT slug, tier FROM discovery_artists"))
            assert not queries.keep(conn, 9999)
        assert tiers == {"untiered": "C", "tiered": "S"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def sc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Fake SC: records unfollows; `fail` maps an SC id to an exception."""
    fake: dict[str, Any] = {"unfollowed": [], "fail": {}}

    def unfollow(state: ProviderState, user_id: str) -> tuple[ProviderState, bool]:
        if user_id in fake["fail"]:
            raise fake["fail"][user_id]
        fake["unfollowed"].append(user_id)
        return state, True

    monkeypatch.setattr(artist_unfollow, "get_web_provider_state", lambda: AUTH)
    monkeypatch.setattr(artist_unfollow, "unfollow_user", unfollow)
    return fake


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


def _following(slug: str) -> int:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT is_following FROM discovery_artists WHERE slug = ?", (slug,)
        ).fetchone()[0]


class TestRoutes:
    def test_get_returns_sections_and_meter(self, client: TestClient) -> None:
        add_artist("quiet", soundcloud_user_id="1")
        body = client.get("/api/unfollow-suggestions").json()
        assert set(body["sections"]) == set(us.SECTIONS)
        assert [r["slug"] for r in body["sections"]["dormant"]] == ["quiet"]
        assert body["following"] == {"count": 1, "limit": 2000}

    def test_keep_removes_from_list(self, client: TestClient) -> None:
        artist_id = add_artist("quiet")
        assert client.post(f"/api/unfollow-suggestions/{artist_id}/keep").json() == {
            "ok": True
        }
        body = client.get("/api/unfollow-suggestions").json()
        assert body["sections"]["dormant"] == []
        assert client.post("/api/unfollow-suggestions/9999/keep").status_code == 404

    def test_unfollow_one(self, client: TestClient, sc: dict[str, Any]) -> None:
        artist_id = add_artist("gone", soundcloud_user_id="77")
        res = client.post(f"/api/unfollow-suggestions/{artist_id}/unfollow")
        assert res.json()["unfollowed"] is True
        assert sc["unfollowed"] == ["77"]
        assert _following("gone") == 0

    def test_unfollow_sc_down_leaves_local_state(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        artist_id = add_artist("stays", soundcloud_user_id="77")
        sc["fail"]["77"] = _http_error(502)
        res = client.post(f"/api/unfollow-suggestions/{artist_id}/unfollow")
        assert res.status_code == 503
        assert _following("stays") == 1

    def test_batch_skips_missing_and_stops_on_service_error(
        self, client: TestClient, sc: dict[str, Any]
    ) -> None:
        ids = [add_artist(f"a{i}", soundcloud_user_id=str(i)) for i in range(4)]
        sc["fail"]["2"] = requests.ConnectionError()
        res = client.post(
            "/api/unfollow-suggestions/unfollow-batch",
            json={"ids": [ids[0], 9999, ids[1], ids[2], ids[3]]},
        ).json()
        assert [(r["id"], r["ok"]) for r in res["results"]] == [
            (ids[0], True), (9999, False), (ids[1], True), (ids[2], False),
        ]  # fmt: skip
        assert res["results"][1]["status"] == 404
        assert res["stopped"] is True
        assert sc["unfollowed"] == ["0", "1"]
        assert _following("a3") == 1

    def test_batch_size_limit(self, client: TestClient) -> None:
        too_many = {"ids": list(range(1, MAX_BATCH + 2))}
        res = client.post("/api/unfollow-suggestions/unfollow-batch", json=too_many)
        assert res.status_code == 422
        empty = client.post(
            "/api/unfollow-suggestions/unfollow-batch", json={"ids": []}
        )
        assert empty.status_code == 422


def test_unfollow_unknown_artist_is_404() -> None:
    with pytest.raises(HTTPException) as exc:
        artist_unfollow.unfollow_discovery_artist(9999)
    assert exc.value.status_code == 404
