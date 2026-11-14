"""Smart playlist staleness triggers (schema v76) and the change-only refresh."""

import sqlite3
from typing import Any

import pytest

from music_minion.core.database import (
    _migrate_v76_smart_playlist_staleness,
    get_database_path,
    get_db_connection,
)
from music_minion.domain.playlists import filters, smart_refresh
from music_minion.domain.playlists.builder import skip_track, unskip_track
from music_minion.domain.playlists.crud import create_playlist, get_playlist_tracks

OLD_TIMESTAMP = "2020-01-01 00:00:00"


def _add_track(title: str, genre: str = "dubstep", path: str | None = None) -> int:
    local_path = path if path is not None else f"/music/{title}.mp3"
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, album, genre, year, bpm, key_signature,"
            " local_path, source) VALUES (?, 'Artist', 'Album', ?, 2024, 140, '1A', ?, 'local')",
            (title, genre, local_path or None),
        )
        conn.commit()
        return cursor.lastrowid


def _version() -> int:
    with get_db_connection() as conn:
        return smart_refresh.library_version(conn)


def _sql(statement: str, params: tuple = ()) -> None:
    with get_db_connection() as conn:
        conn.execute(statement, params)
        conn.commit()


def _rows(playlist_id: int) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, track_id, position, added_at, source FROM playlist_tracks"
            " WHERE playlist_id = ? ORDER BY id",
            (playlist_id,),
        )
        return [dict(r) for r in cursor.fetchall()]


def _member_ids(playlist_id: int) -> set[int]:
    return {r["track_id"] for r in _rows(playlist_id)}


def _materialized_version(playlist_id: int) -> int | None:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT materialized_version FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()[0]


def _smart(name: str, field: str = "genre", value: str = "dubstep") -> int:
    playlist_id = create_playlist(name, playlist_type="smart", library="local")
    operator = "has" if field == "emoji" else "equals"
    filters.add_filter(playlist_id, field, operator, value)
    return playlist_id


def _age_rows(playlist_id: int) -> None:
    _sql(
        "UPDATE playlist_tracks SET added_at = ? WHERE playlist_id = ?",
        (OLD_TIMESTAMP, playlist_id),
    )


# --- triggers ---------------------------------------------------------------

FILTER_COLUMN_CHANGES = [
    ("title", "'New Title'"),
    ("artist", "'Someone Else'"),
    ("album", "'Other Album'"),
    ("genre", "'house'"),
    ("year", "1999"),
    ("bpm", "174"),
    ("key_signature", "'8B'"),
    ("local_path", "'/music/moved.mp3'"),
]


@pytest.mark.parametrize(("column", "value"), FILTER_COLUMN_CHANGES)
def test_filter_column_update_bumps_version(column: str, value: str) -> None:
    track_id = _add_track("a")
    before = _version()

    _sql(f"UPDATE tracks SET {column} = {value} WHERE id = ?", (track_id,))

    assert _version() == before + 1


def test_noop_upsert_does_not_bump_version() -> None:
    track_id = _add_track("a")
    before = _version()

    # batch_upsert_tracks' shape: COALESCE keeps every value as it was
    _sql(
        "UPDATE tracks SET title = COALESCE(NULL, title), genre = COALESCE(NULL, genre),"
        " bpm = COALESCE(NULL, bpm), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (track_id,),
    )
    _sql("UPDATE tracks SET duration = 321 WHERE id = ?", (track_id,))

    assert _version() == before


def test_insert_bumps_only_for_local_files() -> None:
    before = _version()
    _add_track("streamed", path="")
    assert _version() == before

    _add_track("local")
    assert _version() == before + 1


def test_track_without_file_changing_tags_does_not_bump() -> None:
    track_id = _add_track("streamed", path="")
    before = _version()

    _sql("UPDATE tracks SET genre = 'house' WHERE id = ?", (track_id,))

    assert _version() == before


def test_track_delete_bumps_version() -> None:
    track_id = _add_track("a")
    before = _version()

    _sql("DELETE FROM tracks WHERE id = ?", (track_id,))

    assert _version() == before + 1


def test_emoji_changes_bump_only_when_a_filter_uses_the_emoji() -> None:
    track_id = _add_track("a")
    _smart("Fire", field="emoji", value="🔥")
    before = _version()

    _sql(
        "INSERT INTO track_emojis (id, track_id, emoji_id) VALUES ('x1', ?, '🎹')",
        (track_id,),
    )
    assert _version() == before

    _sql(
        "INSERT INTO track_emojis (id, track_id, emoji_id) VALUES ('x2', ?, '🔥')",
        (track_id,),
    )
    assert _version() == before + 1

    _sql("UPDATE track_emojis SET emoji_id = '🔥' WHERE id = 'x1'")
    assert _version() == before + 2

    _sql("DELETE FROM track_emojis WHERE id = 'x2'")
    assert _version() == before + 3


def test_filter_changes_mark_only_that_playlist_stale() -> None:
    _add_track("a")
    first = _smart("First")
    second = _smart("Second")
    assert _materialized_version(first) is not None

    _sql("UPDATE playlist_filters SET value = 'house' WHERE playlist_id = ?", (first,))

    assert _materialized_version(first) is None
    assert _materialized_version(second) is not None


def test_skip_list_changes_mark_playlist_stale() -> None:
    track_id = _add_track("a")
    playlist_id = _smart("Dub")

    _sql(
        "INSERT INTO playlist_builder_skipped (playlist_id, track_id) VALUES (?, ?)",
        (playlist_id, track_id),
    )
    assert _materialized_version(playlist_id) is None

    smart_refresh.refresh_smart_playlist(playlist_id)
    _sql("DELETE FROM playlist_builder_skipped WHERE playlist_id = ?", (playlist_id,))
    assert _materialized_version(playlist_id) is None


# --- diff refresh -----------------------------------------------------------


def test_refresh_adds_new_matches_and_drops_old_ones() -> None:
    keep = _add_track("keep")
    leaves = _add_track("leaves")
    playlist_id = _smart("Dub")
    assert _member_ids(playlist_id) == {keep, leaves}

    arrives = _add_track("arrives")
    _sql("UPDATE tracks SET genre = 'house' WHERE id = ?", (leaves,))
    result = smart_refresh.refresh_smart_playlist(playlist_id)

    assert _member_ids(playlist_id) == {keep, arrives}
    assert (result.inserted, result.deleted, result.track_count) == (1, 1, 2)


def test_refresh_keeps_added_at_for_unchanged_rows() -> None:
    keep = _add_track("keep")
    playlist_id = _smart("Dub")
    _age_rows(playlist_id)

    _add_track("zzz new")
    smart_refresh.refresh_smart_playlist(playlist_id)

    by_track = {r["track_id"]: r for r in _rows(playlist_id)}
    assert by_track[keep]["added_at"] == OLD_TIMESTAMP
    assert len(by_track) == 2


def test_refresh_without_changes_leaves_playlist_tracks_untouched() -> None:
    _add_track("a")
    _add_track("b")
    playlist_id = _smart("Dub")
    _age_rows(playlist_id)
    before = _rows(playlist_id)

    _sql("UPDATE tracks SET genre = 'dubstep', title = title || '' WHERE 1")
    _sql(
        "UPDATE playlist_filters SET value = value WHERE playlist_id = ?",
        (playlist_id,),
    )
    result = smart_refresh.refresh_smart_playlist(playlist_id)

    assert result is not None and not result.changed
    assert _rows(playlist_id) == before


def test_refresh_never_deletes_rows_it_does_not_own() -> None:
    match = _add_track("match")
    foreign = _add_track("foreign", genre="house")
    foreign_match = _add_track("foreign match")
    playlist_id = _smart("Dub")
    _sql(
        "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, foreign_match),
    )
    # Rows written by someone else (bucket link, SC sync, manual SQL): source NULL
    for position, track_id in ((50, foreign), (51, foreign_match)):
        _sql(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            (playlist_id, track_id, position),
        )
    _sql(
        "UPDATE playlist_filters SET value = 'none' WHERE playlist_id = ?",
        (playlist_id,),
    )

    smart_refresh.refresh_smart_playlist(playlist_id)

    rows = {r["track_id"]: r for r in _rows(playlist_id)}
    assert set(rows) == {foreign, foreign_match}
    assert all(r["source"] is None for r in rows.values())
    assert match not in rows


def test_refresh_does_not_duplicate_a_foreign_row_that_matches() -> None:
    playlist_id = _smart("Dub")
    track_id = _add_track("a")
    _sql(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, 0)",
        (playlist_id, track_id),
    )

    smart_refresh.refresh_smart_playlist(playlist_id)

    assert [(r["track_id"], r["source"]) for r in _rows(playlist_id)] == [
        (track_id, None)
    ]


def test_refresh_orders_matches_by_artist_album_title() -> None:
    _add_track("b")
    playlist_id = _smart("Dub")
    _add_track("a")
    smart_refresh.refresh_smart_playlist(playlist_id)

    tracks = get_playlist_tracks(playlist_id)

    assert [t["title"] for t in tracks] == ["a", "b"]
    assert [t["position"] for t in tracks] == [0, 1]


def test_refresh_ignores_manual_playlists() -> None:
    _add_track("a")
    playlist_id = create_playlist("Manual", playlist_type="manual", library="local")

    assert smart_refresh.refresh_smart_playlist(playlist_id) is None
    assert _rows(playlist_id) == []


def test_only_stale_playlists_are_refreshed() -> None:
    _add_track("a")
    fresh = _smart("Fresh")
    stale = _smart("Stale")
    smart_refresh.refresh_stale_smart_playlists()
    fresh_version = _materialized_version(fresh)

    _sql("UPDATE playlist_filters SET value = 'house' WHERE playlist_id = ?", (stale,))
    refreshed = [r.playlist_id for r in smart_refresh.refresh_stale_smart_playlists()]

    assert refreshed == [stale]
    assert _materialized_version(fresh) == fresh_version
    assert smart_refresh.refresh_stale_smart_playlists() == []


def test_raw_sql_from_another_connection_shows_up_on_read() -> None:
    """A script writing with plain sqlite3 (no app code) still reaches the playlist."""
    track_id = _add_track("a", genre="house")
    playlist_id = _smart("Dub")
    assert get_playlist_tracks(playlist_id) == []

    script = sqlite3.connect(get_database_path())
    script.execute("UPDATE tracks SET genre = 'dubstep' WHERE id = ?", (track_id,))
    script.commit()
    script.close()

    assert [t["id"] for t in get_playlist_tracks(playlist_id)] == [track_id]


def test_skip_and_unskip_round_trip() -> None:
    track_id = _add_track("a")
    playlist_id = _smart("Dub")

    skip_track(playlist_id, track_id)
    assert get_playlist_tracks(playlist_id) == []

    unskip_track(playlist_id, track_id)
    assert [t["id"] for t in get_playlist_tracks(playlist_id)] == [track_id]


def test_track_delete_fixes_track_count() -> None:
    track_id = _add_track("a")
    _add_track("b")
    playlist_id = _smart("Dub")

    _sql("DELETE FROM tracks WHERE id = ?", (track_id,))
    smart_refresh.refresh_stale_smart_playlists()

    with get_db_connection() as conn:
        count = conn.execute(
            "SELECT track_count FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()[0]
    assert count == 1


# --- migration ---------------------------------------------------------------


def test_migration_backfill_claims_smart_rows_only_and_is_idempotent() -> None:
    track_id = _add_track("a")
    smart = _smart("Dub")
    manual = create_playlist("Manual", playlist_type="manual", library="local")
    _sql(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, 0)",
        (manual, track_id),
    )
    _sql("UPDATE playlist_tracks SET source = NULL")

    with get_db_connection() as conn:
        _migrate_v76_smart_playlist_staleness(conn)
        conn.commit()

    assert [r["source"] for r in _rows(smart)] == ["smart"]
    assert [r["source"] for r in _rows(manual)] == [None]
