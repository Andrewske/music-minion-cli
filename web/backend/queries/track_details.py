"""Per-track details shown in track banners (organizer + comparison decks).

One definition of the SoundCloud link, the "date" column, and top reposters so
both pages describe a track the same way.
"""

from typing import Any

from ..sc_likes import sc_liked_sql

# Direct permalink when known; tracks.source_url may hold a synthetic
# soundcloud.com/tracks/<id> form SC won't resolve, so unknowns go through
# the lazy-resolving redirect endpoint (which repairs source_url on click).
SC_URL_SQL = """COALESCE(
    CASE WHEN t.source_url IS NOT NULL
          AND t.source_url NOT LIKE 'https://soundcloud.com/tracks/%'
         THEN t.source_url END,
    (SELECT sau.permalink_url FROM sc_artist_uploads sau
     WHERE sau.soundcloud_id = t.soundcloud_id),
    CASE WHEN t.soundcloud_id IS NOT NULL THEN
        '/api/tracks/' || t.id || '/soundcloud'
    END
)"""

# Date shown per track: release, then SC like, then first seen by MM.
# file_mtime comes after created_at because any tag write bumps it.
# Needs `l` (sc_likes) and `pt` (playlist_tracks) joined.
TRACK_DATE_SQL = (
    "COALESCE(t.released_at, l.liked_at, t.created_at,"
    " datetime(t.file_mtime, 'unixepoch'), pt.added_at)"
)

MAX_REPOSTER_RANKING = 200


def clean_sc_url(url: str | None) -> str | None:
    """Strip utm tracking junk; widget URLs need their query string, so only
    strip when tracking params are present."""
    if url and "utm_" in url:
        return url.split("?", 1)[0]
    return url


def fetch_reposters(conn: Any, track_ids: list[int]) -> dict[int, list[dict]]:
    """Top-ranked SoundCloud reposters per track id, best ranking first."""
    if not track_ids:
        return {}
    placeholders = ",".join("?" * len(track_ids))
    rows = conn.execute(
        f"""SELECT t.id as track_id, da.slug, da.display_name, da.avatar_url
        FROM tracks t
        JOIN discovery_tracks dt ON dt.soundcloud_id = t.soundcloud_id
        JOIN discovery_track_reposters dtr ON dtr.discovery_track_id = dt.id
        JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
        WHERE t.id IN ({placeholders}) AND da.ranking <= ?
        ORDER BY da.ranking ASC""",
        [*track_ids, MAX_REPOSTER_RANKING],
    ).fetchall()
    reposters: dict[int, list[dict]] = {}
    for row in rows:
        reposters.setdefault(row["track_id"], []).append(
            {
                "slug": row["slug"],
                "name": row["display_name"] or row["slug"],
                "avatar_url": row["avatar_url"],
            }
        )
    return reposters


def fetch_banner_details(
    conn: Any, playlist_id: int, track_ids: list[int]
) -> dict[int, dict]:
    """Key, date, SC like/link and reposters for tracks in a playlist."""
    if not track_ids:
        return {}
    placeholders = ",".join("?" * len(track_ids))
    rows = conn.execute(
        f"""SELECT t.id, t.key_signature,
               {TRACK_DATE_SQL} as added_at,
               {sc_liked_sql("t.soundcloud_id")} as sc_liked,
               {SC_URL_SQL} as soundcloud_url
        FROM tracks t
        LEFT JOIN playlist_tracks pt ON pt.track_id = t.id AND pt.playlist_id = ?
        LEFT JOIN sc_likes l ON l.soundcloud_id = t.soundcloud_id
        WHERE t.id IN ({placeholders})""",
        [playlist_id, *track_ids],
    ).fetchall()
    reposters = fetch_reposters(conn, track_ids)
    return {
        row["id"]: {
            "key_signature": row["key_signature"],
            "added_at": row["added_at"],
            "sc_liked": bool(row["sc_liked"]),
            "soundcloud_url": clean_sc_url(row["soundcloud_url"]),
            "reposters": reposters.get(row["id"], []),
        }
        for row in rows
    }
