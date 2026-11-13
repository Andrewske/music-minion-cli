"""Uploader capture on sc_likes: hourly sync, nightly reconcile, backfill."""

from unittest.mock import MagicMock, patch

from music_minion.core.database import get_db_connection, upsert_sc_likes
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud import api, likes_reconcile
from music_minion.domain.library.providers.soundcloud.like_uploaders import (
    LikeUploader,
    fill_like_uploaders,
    local_uploaders,
    missing_uploader_ids,
    permalink_from_url,
    uploader_from_track,
    uploaders_by_track,
)
from music_minion.domain.library.providers.soundcloud.likes_fetch import (
    fetch_all_liked_ids,
)


def _item(track_id: int, user_id: int | None = 70) -> dict:
    user = {"id": user_id, "permalink": f"u{user_id}", "username": f"User {user_id}"}
    return {
        "kind": "track",
        "id": track_id,
        "title": "t",
        "user": user if user_id else None,
    }


def _uploaders() -> dict[str, tuple]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT soundcloud_id, uploader_soundcloud_id, uploader_permalink,
            uploader_username FROM sc_likes"""
        ).fetchall()
    return {r[0]: tuple(r[1:]) for r in rows}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestParsing:
    def test_uploader_from_track(self) -> None:
        assert uploader_from_track(_item(1)) == LikeUploader("70", "u70", "User 70")
        assert uploader_from_track(_item(1, user_id=None)) is None
        assert uploader_from_track("junk") is None

    def test_permalink_from_url(self) -> None:
        url = "https://soundcloud.com/phrva/shabba?utm_medium=api"
        assert permalink_from_url(url) == "phrva"
        assert permalink_from_url("https://example.com/phrva/x") is None
        assert permalink_from_url(None) is None

    def test_uploaders_by_track_skips_missing(self) -> None:
        found = uploaders_by_track([_item(1), _item(2, None), {"user": {"id": 3}}])
        assert found == {"1": LikeUploader("70", "u70", "User 70")}


class TestFill:
    def test_fills_only_missing_and_keeps_first_id(self) -> None:
        upsert_sc_likes(["1", "2"], "sync")
        assert fill_like_uploaders({"1": LikeUploader("70", "a", "A")}) == 1
        assert fill_like_uploaders({"1": LikeUploader("99", "b", "B")}) == 0
        assert fill_like_uploaders({"404": LikeUploader("70", "a", "A")}) == 0
        assert _uploaders() == {"1": ("70", "a", "A"), "2": (None, None, None)}

    def test_names_fill_in_for_bare_id(self) -> None:
        upsert_sc_likes(["1"], "sync")
        fill_like_uploaders({"1": LikeUploader("70", None, None)})
        assert fill_like_uploaders({"1": LikeUploader("70", None, None)}) == 0
        assert fill_like_uploaders({"1": LikeUploader("70", "a", "A")}) == 1
        assert _uploaders()["1"] == ("70", "a", "A")


class TestHourlySync:
    def test_sync_library_records_uploaders(self) -> None:
        state = ProviderState(
            config=ProviderConfig(name="soundcloud"),
            authenticated=True,
            cache={"token_data": {"access_token": "tok"}},
        )
        page = {"collection": [_item(1), _item(2, 71)], "next_href": None}
        with (
            patch.object(
                api,
                "_ensure_valid_token",
                return_value=(state, {"access_token": "tok"}),
            ),
            patch.object(api.requests, "get", return_value=_response(page)),
        ):
            api.sync_library(state, incremental=False)
        assert _uploaders()["1"] == ("70", "u70", "User 70")
        assert _uploaders()["2"] == ("71", "u71", "User 71")


class TestNightlyReconcile:
    def test_full_fetch_carries_uploaders(self) -> None:
        page = {"collection": [_item(1), _item(2, None)], "next_href": None}
        snap = fetch_all_liked_ids("tok", http_get=lambda *a, **k: _response(page))
        assert snap.ids == {"1", "2"}
        assert dict(snap.uploaders) == {"1": LikeUploader("70", "u70", "User 70")}

    def test_apply_fills_new_and_existing_rows(self) -> None:
        upsert_sc_likes(["1"], "sync")  # existing row, no uploader yet
        page = {"collection": [_item(1), _item(2, 71)], "next_href": None}
        fake = lambda *a, **k: _response(page)
        with patch.object(
            likes_reconcile, "fetch_all_liked_ids",
            lambda token: fetch_all_liked_ids(token, http_get=fake),
        ):  # fmt: skip
            likes_reconcile.reconcile_sc_likes("tok", apply=True)
        assert _uploaders() == {
            "1": ("70", "u70", "User 70"),
            "2": ("71", "u71", "User 71"),
        }

    def test_dry_run_writes_nothing(self) -> None:
        upsert_sc_likes(["1"], "sync")
        page = {"collection": [_item(1)], "next_href": None}
        fake = lambda *a, **k: _response(page)
        with patch.object(
            likes_reconcile, "fetch_all_liked_ids",
            lambda token: fetch_all_liked_ids(token, http_get=fake),
        ):  # fmt: skip
            likes_reconcile.reconcile_sc_likes("tok", apply=False)
        assert _uploaders()["1"] == (None, None, None)


class TestBackfillPhase1:
    def _exec(self, sql: str, params: tuple = ()) -> None:
        with get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def test_local_sources(self) -> None:
        upsert_sc_likes(["d1", "u1", "none", "done"], "sync")
        fill_like_uploaders({"done": LikeUploader("5", "five", "Five")})
        self._exec(
            """INSERT INTO discovery_tracks (soundcloud_id, uploader_soundcloud_id,
            permalink_url) VALUES ('d1', '10', 'https://soundcloud.com/ten/song'),
            ('done', '11', NULL)"""
        )
        self._exec(
            """INSERT INTO discovery_artists (soundcloud_user_id, slug, display_name, ranking)
            VALUES ('20', 'known', 'Known Artist', 1)"""
        )
        self._exec(
            """INSERT INTO sc_artist_uploads (discovery_artist_id, soundcloud_id,
            uploaded_at, uploader_soundcloud_id)
            VALUES ((SELECT id FROM discovery_artists), 'u1', '2026-01-01', '20')"""
        )
        found = local_uploaders()
        assert found == {
            "d1": LikeUploader("10", "ten", None),
            "u1": LikeUploader("20", "known", "Known Artist"),
        }
        assert fill_like_uploaders(found) == 2
        assert missing_uploader_ids() == ["none"]
        assert _uploaders()["done"] == ("5", "five", "Five")  # untouched
