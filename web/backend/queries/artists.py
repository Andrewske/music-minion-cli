"""Artist query functions for discovery_artists table."""

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Artist stats CTE query
# ---------------------------------------------------------------------------

ARTISTS_STATS_SQL = """
WITH library_counts AS (
  SELECT amr.discovery_artist_id, COUNT(*) AS library_count
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  GROUP BY amr.discovery_artist_id
),
feed_stats AS (
  SELECT discovery_artist_id,
         COUNT(*) FILTER (WHERE seen_at > datetime('now', '-7 days')) / 7.0 AS noise_7d,
         COUNT(*) FILTER (WHERE seen_at > datetime('now', '-30 days')) / 30.0 AS noise_30d,
         MAX(seen_at) AS last_activity_at
  FROM discovery_track_reposters GROUP BY discovery_artist_id
),
repost_counts AS (
  SELECT dtr.discovery_artist_id, COUNT(DISTINCT t.id) AS repost_count
  FROM discovery_track_reposters dtr
  INNER JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
  INNER JOIN tracks t ON t.soundcloud_id = dt.soundcloud_id
  GROUP BY dtr.discovery_artist_id
),
first_loved AS (
  SELECT amr.discovery_artist_id, t.id AS track_id, t.title, t.artist, r.timestamp AS loved_at
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id AND r.rating_type = 'love'
  WHERE r.timestamp = (
    SELECT MIN(r2.timestamp) FROM ratings r2
    INNER JOIN tracks t2 ON t2.id = r2.track_id
    WHERE t2.artist_normalized = amr.local_name AND r2.rating_type = 'love'
  )
  GROUP BY amr.discovery_artist_id
),
last_loved AS (
  SELECT amr.discovery_artist_id, MAX(r.timestamp) AS last_loved_at
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id AND r.rating_type = 'love'
  GROUP BY amr.discovery_artist_id
),
avg_elo AS (
  -- ELO is per-playlist; use global playlist ELO as a proxy (avg across all playlists)
  SELECT amr.discovery_artist_id, AVG(per.rating) AS avg_elo
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN playlist_elo_ratings per ON per.track_id = t.id
  GROUP BY amr.discovery_artist_id
),
sc_liked AS (
  -- Tracks liked on SoundCloud (like markers synced from SC)
  SELECT amr.discovery_artist_id, COUNT(DISTINCT t.id) AS sc_liked_count
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id
    AND r.rating_type = 'like' AND r.source = 'soundcloud'
  GROUP BY amr.discovery_artist_id
),
playlist_counts AS (
  SELECT amr.discovery_artist_id, COUNT(DISTINCT pt.track_id) AS playlist_track_count
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN playlist_tracks pt ON pt.track_id = t.id
  GROUP BY amr.discovery_artist_id
)
SELECT da.id, da.soundcloud_user_id, da.slug, da.display_name, da.avatar_url,
       da.follower_count, da.is_following, da.ranking, da.tier, da.in_top_200,
       da.hit_rate, da.tracks_seen,
       da.upload_keep_rate, da.upload_rated_count,
       da.repost_keep_rate, da.repost_rated_count,
       COALESCE(lc.library_count, 0) AS library_track_count,
       COALESCE(rc.repost_count, 0) AS repost_in_library_count,
       COALESCE(fs.noise_7d, 0) AS feed_noise_7d,
       COALESCE(fs.noise_30d, 0) AS feed_noise_30d,
       fs.last_activity_at,
       fl.track_id AS first_loved_id, fl.title AS first_loved_title,
       fl.artist AS first_loved_artist, fl.loved_at AS first_loved_at,
       ll.last_loved_at,
       ae.avg_elo,
       COALESCE(sl.sc_liked_count, 0) AS sc_liked_count,
       COALESCE(pc.playlist_track_count, 0) AS playlist_track_count
FROM discovery_artists da
LEFT JOIN library_counts lc ON lc.discovery_artist_id = da.id
LEFT JOIN feed_stats fs ON fs.discovery_artist_id = da.id
LEFT JOIN repost_counts rc ON rc.discovery_artist_id = da.id
LEFT JOIN first_loved fl ON fl.discovery_artist_id = da.id
LEFT JOIN last_loved ll ON ll.discovery_artist_id = da.id
LEFT JOIN avg_elo ae ON ae.discovery_artist_id = da.id
LEFT JOIN sc_liked sl ON sl.discovery_artist_id = da.id
LEFT JOIN playlist_counts pc ON pc.discovery_artist_id = da.id

UNION ALL

-- Local-only artists (tracks with artist_normalized that never resolves to a discovery_artists row)
SELECT NULL AS id, NULL, NULL, t.artist AS display_name, NULL,
       NULL, 0, NULL, NULL, 0, NULL, 0,
       NULL, 0, NULL, 0,
       COUNT(DISTINCT t.id) AS library_track_count,
       0, 0, 0, NULL,
       NULL, NULL, NULL, NULL,
       MAX(CASE WHEN r.rating_type = 'love' THEN r.timestamp END) AS last_loved_at,
       AVG(per.rating) AS avg_elo,
       COUNT(DISTINCT CASE WHEN r.rating_type = 'like' AND r.source = 'soundcloud'
                           THEN t.id END) AS sc_liked_count,
       COALESCE(MAX(plc.pc), 0) AS playlist_track_count
FROM tracks t
LEFT JOIN ratings r ON r.track_id = t.id
LEFT JOIN playlist_elo_ratings per ON per.track_id = t.id
LEFT JOIN (
  SELECT t2.artist_normalized AS an, COUNT(DISTINCT pt.track_id) AS pc
  FROM tracks t2
  INNER JOIN playlist_tracks pt ON pt.track_id = t2.id
  GROUP BY t2.artist_normalized
) plc ON plc.an = t.artist_normalized
WHERE t.artist_normalized NOT IN (SELECT local_name FROM artist_match_resolved)
  AND t.artist_normalized IS NOT NULL
  AND t.artist_normalized != ''
GROUP BY t.artist_normalized
"""

# Sort ORDER BY clauses (appended to the CTE query)
_SORT_CLAUSES: dict[str, str] = {
    "name": "ORDER BY display_name COLLATE NOCASE ASC",
    "rank": "ORDER BY ranking ASC NULLS LAST, display_name COLLATE NOCASE ASC",
    "library": "ORDER BY library_track_count DESC, display_name COLLATE NOCASE ASC",
    "reposts": "ORDER BY repost_in_library_count DESC, display_name COLLATE NOCASE ASC",
    "hit_rate": "ORDER BY repost_keep_rate DESC NULLS LAST, display_name COLLATE NOCASE ASC",
    "noise": "ORDER BY feed_noise_7d DESC, display_name COLLATE NOCASE ASC",
    "last_loved": "ORDER BY last_loved_at DESC NULLS LAST, display_name COLLATE NOCASE ASC",
}

# Source filter WHERE clauses (applied as outer wrapping query)
_SOURCE_FILTERS: dict[str, str] = {
    "soundcloud": "id IS NOT NULL",
    "local": "id IS NULL",
    "following": "is_following = 1",
    "all": "",
}

# Unfollowed discovery artists stay hidden unless the user kept some of their
# songs: liked (SC like), loved, or placed in any playlist. Local-only rows
# (id IS NULL) are never affected.
_VISIBILITY_FILTER = (
    "(id IS NULL OR is_following = 1 OR sc_liked_count > 0 "
    "OR playlist_track_count > 0 OR last_loved_at IS NOT NULL)"
)


def _derive_activity_state(last_activity_at: str | None) -> str:
    """Derive activity_state from last_activity_at ISO string.

    active  = within 7 days
    silent  = 7–30 days
    dormant = older than 30 days or null
    """
    if not last_activity_at:
        return "dormant"
    try:
        last = datetime.fromisoformat(last_activity_at.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta_days = (now - last).total_seconds() / 86400
        if delta_days < 7:
            return "active"
        if delta_days < 30:
            return "silent"
        return "dormant"
    except (ValueError, TypeError):
        return "dormant"


def _build_first_loved(row: dict[str, Any]) -> dict[str, Any] | None:
    """Build nested first_loved_track object from flat row columns."""
    if row.get("first_loved_id") is None:
        return None
    return {
        "track_id": row["first_loved_id"],
        "title": row["first_loved_title"],
        "artist": row["first_loved_artist"],
        "loved_at": row["first_loved_at"],
    }


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce raw SQLite row into ArtistStats shape."""
    return {
        "id": row["id"],
        "soundcloud_user_id": row["soundcloud_user_id"],
        "display_name": row["display_name"],
        "slug": row["slug"],
        "avatar_url": row["avatar_url"],
        "follower_count": row["follower_count"],
        "is_following": bool(row["is_following"]),
        "ranking": row["ranking"],
        # Legacy seeding left '' in tier for untiered artists — normalize to None
        "tier": row["tier"] or None,
        "in_top_200": bool(row["in_top_200"]),
        "hit_rate": row["hit_rate"],
        "tracks_seen": row["tracks_seen"],
        "upload_keep_rate": row["upload_keep_rate"],
        "upload_rated_count": row["upload_rated_count"],
        "repost_keep_rate": row["repost_keep_rate"],
        "repost_rated_count": row["repost_rated_count"],
        "library_track_count": row["library_track_count"],
        "repost_in_library_count": row["repost_in_library_count"],
        "sc_liked_count": row["sc_liked_count"],
        "playlist_track_count": row["playlist_track_count"],
        "feed_noise_7d": row["feed_noise_7d"],
        "feed_noise_30d": row["feed_noise_30d"],
        "last_loved_at": row["last_loved_at"],
        "first_loved_track": _build_first_loved(row),
        "avg_elo": row["avg_elo"],
        "last_activity_at": row["last_activity_at"],
        "activity_state": _derive_activity_state(row.get("last_activity_at")),
    }


def get_artist_stats(
    conn: sqlite3.Connection,
    source: str = "all",
    sort: str = "name",
) -> list[dict[str, Any]]:
    """Return artist stats using the single CTE query.

    Args:
        conn: Open SQLite connection.
        source: Filter — 'all', 'soundcloud', 'local', or 'following'.
        sort: Sort key — 'name', 'rank', 'library', 'reposts',
              'hit_rate', 'noise', or 'last_loved'.

    Returns:
        List of ArtistStats dicts ready for JSON serialisation.
    """
    source_filter = _SOURCE_FILTERS.get(source, "")
    order_clause = _SORT_CLAUSES.get(sort, _SORT_CLAUSES["name"])

    conditions = [_VISIBILITY_FILTER]
    if source_filter:
        conditions.append(source_filter)

    # Wrap CTE in a subquery so we can filter on the aliased columns
    sql = (
        f"SELECT * FROM ({ARTISTS_STATS_SQL.strip()}) sub\n"
        f"WHERE {' AND '.join(conditions)}\n"
        f"{order_clause}"
    )

    rows = conn.execute(sql).fetchall()
    return [_coerce_row(dict(r)) for r in rows]


def get_artist_detail(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
) -> dict[str, Any] | None:
    """Fetch full artist detail: stats row + feed events + library tracks + match overrides.

    Returns None if discovery_artist_id does not exist.
    """
    # Verify artist exists and fetch its stats row
    stats_sql = f"SELECT * FROM ({ARTISTS_STATS_SQL.strip()}) sub WHERE id = ?"
    row = conn.execute(stats_sql, (discovery_artist_id,)).fetchone()
    if row is None:
        return None

    artist = _coerce_row(dict(row))

    # Recent feed events (last 50) via discovery_track_reposters JOIN discovery_tracks
    feed_rows = conn.execute(
        """
        SELECT dt.soundcloud_id AS track_sc_id,
               dt.title AS track_title,
               dt.artist_name AS track_artist_name,
               dtr.seen_at,
               dtr.reposted_at
        FROM discovery_track_reposters dtr
        JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
        WHERE dtr.discovery_artist_id = ?
        ORDER BY dtr.seen_at DESC
        LIMIT 50
        """,
        (discovery_artist_id,),
    ).fetchall()
    recent_feed_events = [dict(r) for r in feed_rows]

    # Top library tracks via artist_match_resolved view (play_count computed from ratings)
    track_rows = conn.execute(
        """
        SELECT t.id, t.title, t.artist, t.album, t.genre, t.year,
               t.duration, t.local_path,
               (SELECT COUNT(*) FROM ratings r
                WHERE r.track_id = t.id
                  AND r.rating_type NOT IN ('archive', 'skip')) AS play_count
        FROM artist_match_resolved amr
        JOIN tracks t ON t.artist_normalized = amr.local_name
        WHERE amr.discovery_artist_id = ?
        ORDER BY play_count DESC, t.title COLLATE NOCASE ASC
        LIMIT 20
        """,
        (discovery_artist_id,),
    ).fetchall()
    top_library_tracks = [dict(r) for r in track_rows]

    # Match overrides
    override_rows = conn.execute(
        """
        SELECT id, local_artist_name, action, created_at
        FROM artist_match_overrides
        WHERE discovery_artist_id = ?
        ORDER BY created_at DESC
        """,
        (discovery_artist_id,),
    ).fetchall()
    match_overrides = [dict(r) for r in override_rows]

    return {
        "artist": artist,
        "recent_feed_events": recent_feed_events,
        "top_library_tracks": top_library_tracks,
        "match_overrides": match_overrides,
    }


def _parse_playlist_refs(refs: str | None) -> list[dict[str, str]]:
    """Parse GROUP_CONCAT'd `name<US>library` records separated by <RS>."""
    if not refs:
        return []
    playlists: list[dict[str, str]] = []
    for rec in refs.split(chr(30)):
        name, _, library = rec.partition(chr(31))
        playlists.append({"name": name, "library": library})
    return playlists


def _coerce_library_track_row(row: sqlite3.Row) -> dict[str, Any]:
    """Coerce a library-track row: bool is_liked, playlists as {name, library}."""
    d = dict(row)
    d["is_liked"] = bool(d["is_liked"])
    d["playlists"] = _parse_playlist_refs(d.pop("playlist_refs"))
    return d


def get_artist_library_tracks(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
) -> list[dict[str, Any]] | None:
    """Return ALL library tracks for a discovery artist, saved-first.

    Tracks the user has liked/loved or placed in a playlist sort to the top,
    then by play_count. Each playlist carries its library (local/soundcloud/
    spotify). Returns None if the artist does not exist.
    """
    exists = conn.execute(
        "SELECT 1 FROM discovery_artists WHERE id = ?", (discovery_artist_id,)
    ).fetchone()
    if exists is None:
        return None

    rows = conn.execute(
        """
        SELECT t.id, t.title, t.artist, t.album, t.genre, t.year,
               t.duration, t.local_path,
               (SELECT COUNT(*) FROM ratings r
                WHERE r.track_id = t.id
                  AND r.rating_type NOT IN ('archive', 'skip')) AS play_count,
               EXISTS(SELECT 1 FROM ratings r
                      WHERE r.track_id = t.id
                        AND r.rating_type IN ('like', 'love')) AS is_liked,
               (SELECT GROUP_CONCAT(p.name || char(31) || p.library, char(30))
                FROM playlist_tracks pt
                JOIN playlists p ON p.id = pt.playlist_id
                WHERE pt.track_id = t.id) AS playlist_refs
        FROM artist_match_resolved amr
        JOIN tracks t ON t.artist_normalized = amr.local_name
        WHERE amr.discovery_artist_id = ?
        ORDER BY (is_liked OR playlist_refs IS NOT NULL) DESC,
                 play_count DESC, t.title COLLATE NOCASE ASC
        """,
        (discovery_artist_id,),
    ).fetchall()

    return [_coerce_library_track_row(r) for r in rows]


def get_local_artist_library_tracks(
    conn: sqlite3.Connection,
    artist_name: str,
) -> list[dict[str, Any]]:
    """Return ALL library tracks for a local-only artist (no discovery row).

    Matches on tracks.artist_normalized using the same normalization as
    artist_match_overrides. Same shape/sort as get_artist_library_tracks.
    """
    rows = conn.execute(
        """
        SELECT t.id, t.title, t.artist, t.album, t.genre, t.year,
               t.duration, t.local_path,
               (SELECT COUNT(*) FROM ratings r
                WHERE r.track_id = t.id
                  AND r.rating_type NOT IN ('archive', 'skip')) AS play_count,
               EXISTS(SELECT 1 FROM ratings r
                      WHERE r.track_id = t.id
                        AND r.rating_type IN ('like', 'love')) AS is_liked,
               (SELECT GROUP_CONCAT(p.name || char(31) || p.library, char(30))
                FROM playlist_tracks pt
                JOIN playlists p ON p.id = pt.playlist_id
                WHERE pt.track_id = t.id) AS playlist_refs
        FROM tracks t
        WHERE t.artist_normalized =
              LOWER(TRIM(REPLACE(REPLACE(REPLACE(?, '.', ''), '!', ''), '?', '')))
        ORDER BY (is_liked OR playlist_refs IS NOT NULL) DESC,
                 play_count DESC, t.title COLLATE NOCASE ASC
        """,
        (artist_name,),
    ).fetchall()

    return [_coerce_library_track_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Tier / ranking management
# ---------------------------------------------------------------------------

ARTIST_TIERS: tuple[str, ...] = ("S", "A", "B", "C", "D")
_TIER_ORDER: dict[str, int] = {t: i for i, t in enumerate(ARTIST_TIERS)}

_RANKING_STATS_SQL = """
SELECT da.id, da.tier, da.ranking,
       COALESCE(sl.liked, 0) AS liked_count,
       COALESCE(lc.cnt, 0) AS library_count,
       COALESCE(da.follower_count, 0) AS follower_count,
       LOWER(COALESCE(da.display_name, da.slug, '')) AS name
FROM discovery_artists da
LEFT JOIN (
  SELECT amr.discovery_artist_id, COUNT(DISTINCT t.id) AS liked
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id
    AND r.rating_type = 'like' AND r.source = 'soundcloud'
  GROUP BY amr.discovery_artist_id
) sl ON sl.discovery_artist_id = da.id
LEFT JOIN (
  SELECT amr.discovery_artist_id, COUNT(DISTINCT t.id) AS cnt
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  GROUP BY amr.discovery_artist_id
) lc ON lc.discovery_artist_id = da.id
"""


def _tier_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        _TIER_ORDER[row["tier"]],
        -row["liked_count"],
        -row["library_count"],
        -row["follower_count"],
        row["name"],
    )


def _untiered_sort_key(row: dict[str, Any]) -> tuple[bool, int, str]:
    return (row["ranking"] is None, row["ranking"] or 0, row["name"])


def recompute_tier_rankings(conn: sqlite3.Connection) -> int:
    """Renumber all artist rankings from tiers + engagement stats.

    Tiered artists come first, ordered by tier (S best), then SC-liked
    count, library count, follower count, name. Untiered artists follow,
    keeping their existing relative ranking order. Returns rows changed.
    """
    rows = [dict(r) for r in conn.execute(_RANKING_STATS_SQL).fetchall()]
    tiered = sorted((r for r in rows if r["tier"] in _TIER_ORDER), key=_tier_sort_key)
    untiered = sorted(
        (r for r in rows if r["tier"] not in _TIER_ORDER), key=_untiered_sort_key
    )
    updates = [
        (rank, row["id"])
        for rank, row in enumerate([*tiered, *untiered], start=1)
        if row["ranking"] != rank
    ]
    conn.executemany("UPDATE discovery_artists SET ranking = ? WHERE id = ?", updates)
    return len(updates)


def set_artist_tier(
    conn: sqlite3.Connection, discovery_artist_id: int, tier: str | None
) -> bool:
    """Set (or clear) an artist's tier, then recompute all rankings.

    Returns False if the artist does not exist.
    """
    cursor = conn.execute(
        "UPDATE discovery_artists SET tier = ? WHERE id = ?",
        (tier, discovery_artist_id),
    )
    if cursor.rowcount == 0:
        return False
    changed = recompute_tier_rankings(conn)
    logger.info(
        f"set_artist_tier: artist={discovery_artist_id} tier={tier} "
        f"({changed} rankings renumbered)"
    )
    return True


def set_artist_ranking(
    conn: sqlite3.Connection, discovery_artist_id: int, ranking: int
) -> bool:
    """Manually place an artist at a ranking position (insert semantics).

    Artists at or below the target position shift down by one; no
    renumbering pass, so gaps elsewhere are preserved. Returns False if
    the artist does not exist.
    """
    exists = conn.execute(
        "SELECT 1 FROM discovery_artists WHERE id = ?", (discovery_artist_id,)
    ).fetchone()
    if exists is None:
        return False
    conn.execute(
        "UPDATE discovery_artists SET ranking = ranking + 1 "
        "WHERE ranking >= ? AND id != ?",
        (ranking, discovery_artist_id),
    )
    conn.execute(
        "UPDATE discovery_artists SET ranking = ? WHERE id = ?",
        (ranking, discovery_artist_id),
    )
    return True


# ---------------------------------------------------------------------------
# Artist connections — shared song credits (collabs, feats, remixes)
# ---------------------------------------------------------------------------

_FEAT_RE = re.compile(
    r"\b(?:feat|ft)\.?\s+([^()\[\]]+)|\bfeaturing\s+([^()\[\]]+)", re.IGNORECASE
)
_REMIX_WORDS = r"(?:remix|refix|edit|flip|bootleg|vip|rework|remake)"
_TITLE_REMIX_RE = re.compile(
    rf"[(\[]([^()\[\]]*?)\s+{_REMIX_WORDS}\s*[)\]]",
    re.IGNORECASE,
)
_DASH_REMIX_RE = re.compile(rf"-\s*([^-()\[\]]+?)\s+{_REMIX_WORDS}\s*$", re.IGNORECASE)
_CREDIT_SPLIT_RE = re.compile(
    r"\s*(?:,|&|\+|\bx\b|\bvs\.?\b|\band\b|\bb2b\b)\s*", re.IGNORECASE
)
_NORM_STRIP = str.maketrans("", "", ".!?")


def _normalize_name(name: str) -> str:
    """Mirror tracks.artist_normalized: strip .!? then lower/trim."""
    return name.translate(_NORM_STRIP).lower().strip()


def _split_credits(credit: str) -> list[str]:
    """Split a credit string on collab separators (, & + x vs and b2b)."""
    return [
        p.strip(" .,-–") for p in _CREDIT_SPLIT_RE.split(credit) if p.strip(" .,-–")
    ]


def _parse_title_remixers(title: str) -> list[str]:
    """Extract remixer names from '(X Remix)' or '… - X Remix' title suffixes."""
    match = _TITLE_REMIX_RE.search(title) or _DASH_REMIX_RE.search(title)
    return _split_credits(match.group(1)) if match else []


def _parse_track_credits(
    artist: str, title: str, remix_artist: str | None
) -> dict[str, list[str]]:
    """Extract primaries / feats / remixers from track credit strings.

    Remixers merge the remix_artist column with '(X Remix)' / '- X Remix'
    title suffixes. Remixers duplicated in primaries stay listed — the
    partner logic uses them to tell remixes from plain collabs.
    """
    primaries = _split_credits(artist)
    feat_match = _FEAT_RE.search(title or "")
    feats = (
        _split_credits(feat_match.group(1) or feat_match.group(2)) if feat_match else []
    )
    # remix_artist duplicating the whole artist string marks a non-remix row
    remixers: list[str] = []
    if remix_artist and _normalize_name(remix_artist) != _normalize_name(artist):
        remixers = _split_credits(remix_artist)
    remixers += [r for r in _parse_title_remixers(title or "") if r not in remixers]
    return {"primaries": primaries, "feats": feats, "remixers": remixers}


def _connection_partners(
    artist: str, credits: dict[str, list[str]], names: set[str]
) -> list[tuple[str, str]]:
    """Return (other_artist, relation) pairs from the page artist's perspective.

    Relations: collab (both primary), features (they feat on this artist's
    track), featured_on (this artist feats on theirs), remixed (this artist
    remixed their track), remixed_by (they remixed this artist's track).

    The artist string is only split into collab partners when the page artist
    matches one of its parts — protects duo names like 'Chase & Status'.
    """
    primaries, feats, remixers = (
        credits["primaries"],
        credits["feats"],
        credits["remixers"],
    )
    prim_norms = {_normalize_name(p) for p in primaries}
    remix_norms = {_normalize_name(r) for r in remixers}
    whole_is_page = _normalize_name(artist) in names
    page_in_parts = bool(prim_norms & names)
    page_is_feat = any(_normalize_name(f) in names for f in feats)
    page_is_remixer = bool(remix_norms & names)

    partners: list[tuple[str, str]] = []
    if whole_is_page or page_in_parts:
        if page_in_parts and not whole_is_page:
            # Spotify-style rows credit the remixer as co-artist — classify
            # each partner by whether they (or the page artist) did the remix.
            for p in primaries:
                p_norm = _normalize_name(p)
                if p_norm in names:
                    continue
                if p_norm in remix_norms:
                    relation = "remixed_by"
                elif page_is_remixer:
                    relation = "remixed"
                else:
                    relation = "collab"
                partners.append((p, relation))
        partners += [(f, "features") for f in feats if _normalize_name(f) not in names]
        partners += [
            (r, "remixed_by")
            for r in remixers
            if _normalize_name(r) not in names and _normalize_name(r) not in prim_norms
        ]
    else:
        if page_is_feat:
            partners.append((artist, "featured_on"))
        if page_is_remixer:
            partners.append((artist, "remixed"))
    return partners


def _fetch_credit_candidates(
    conn: sqlite3.Connection, names: set[str]
) -> list[sqlite3.Row]:
    """Fetch tracks whose artist / remix_artist / title mention any name."""
    norm_sql = "LOWER(REPLACE(REPLACE(REPLACE(COALESCE({col}, ''), '.', ''), '!', ''), '?', ''))"
    clauses: list[str] = []
    params: list[str] = []
    for name in names:
        like = f"%{name}%"
        clauses.append(
            f"(t.artist_normalized LIKE ? OR {norm_sql.format(col='t.remix_artist')} LIKE ? "
            f"OR {norm_sql.format(col='t.title')} LIKE ?)"
        )
        params += [like, like, like]
    sql = (
        "SELECT t.id, t.title, t.artist, t.remix_artist, t.local_path "
        f"FROM tracks t WHERE {' OR '.join(clauses)}"
    )
    return conn.execute(sql, params).fetchall()


def _resolve_discovery_artists(
    conn: sqlite3.Connection, norm_names: list[str]
) -> dict[str, dict[str, Any]]:
    """Map normalized artist name -> discovery_artists row (via match view)."""
    if not norm_names:
        return {}
    placeholders = ",".join("?" for _ in norm_names)
    rows = conn.execute(
        f"""
        SELECT amr.local_name, da.id, da.display_name, da.avatar_url,
               da.slug, da.is_following
        FROM artist_match_resolved amr
        JOIN discovery_artists da ON da.id = amr.discovery_artist_id
        WHERE amr.local_name IN ({placeholders})
        """,
        norm_names,
    ).fetchall()
    return {r["local_name"]: dict(r) for r in rows}


def _build_connections(
    conn: sqlite3.Connection,
    candidates: list[sqlite3.Row],
    names: set[str],
) -> list[dict[str, Any]]:
    """Group credit-partner hits by connected artist, shared_count DESC."""
    by_partner: dict[str, dict[str, Any]] = {}
    for row in candidates:
        d = dict(row)
        credits = _parse_track_credits(
            d["artist"] or "", d["title"] or "", d["remix_artist"]
        )
        for partner, relation in _connection_partners(
            d["artist"] or "", credits, names
        ):
            norm = _normalize_name(partner)
            if not norm:
                continue
            entry = by_partner.setdefault(
                norm, {"display_name": partner, "tracks": [], "seen_track_ids": set()}
            )
            if d["id"] in entry["seen_track_ids"]:
                continue
            entry["seen_track_ids"].add(d["id"])
            entry["tracks"].append(
                {
                    "track_id": d["id"],
                    "title": d["title"],
                    "artist": d["artist"],
                    "relation": relation,
                    "is_local": d["local_path"] is not None,
                }
            )

    resolved = _resolve_discovery_artists(conn, list(by_partner.keys()))
    connections: list[dict[str, Any]] = []
    for norm, entry in by_partner.items():
        da = resolved.get(norm)
        connections.append(
            {
                "artist_id": da["id"] if da else None,
                "display_name": da["display_name"] if da else entry["display_name"],
                "avatar_url": da["avatar_url"] if da else None,
                "slug": da["slug"] if da else None,
                "is_following": bool(da["is_following"]) if da else None,
                "shared_count": len(entry["tracks"]),
                "tracks": entry["tracks"],
            }
        )
    return sorted(
        connections,
        key=lambda c: (-c["shared_count"], (c["display_name"] or "").lower()),
    )


def get_artist_connections(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
) -> list[dict[str, Any]] | None:
    """Return artists sharing song credits with this one, plus those tracks.

    A connection is another artist on the same song: collab (both primary
    artists), feat (either direction), or remix (either direction). Parsed
    from library track credit strings (artist, remix_artist, title).
    Returns None if the artist does not exist.
    """
    row = conn.execute(
        "SELECT display_name FROM discovery_artists WHERE id = ?",
        (discovery_artist_id,),
    ).fetchone()
    if row is None:
        return None

    names = {_normalize_name(row["display_name"])}
    names |= {
        r["local_name"]
        for r in conn.execute(
            "SELECT local_name FROM artist_match_resolved WHERE discovery_artist_id = ?",
            (discovery_artist_id,),
        ).fetchall()
    }
    names.discard("")
    if not names:
        return []

    candidates = _fetch_credit_candidates(conn, names)
    return _build_connections(conn, candidates, names)


def mark_artist_unfollowed(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
) -> int:
    """Mark artist as unfollowed.

    Does NOT delete discovery_track_reposters rows: that data is shared with
    hit_rate and discovery-pipeline analytics. The feed_noise_7d/30d metric
    decays naturally since no new reposter rows will be written for this
    artist after is_following=0 (the sync skips them).

    Returns 0 for response-shape compatibility with the frontend.
    """
    conn.execute(
        "UPDATE discovery_artists SET is_following = 0 WHERE id = ?",
        (discovery_artist_id,),
    )
    return 0


def remove_artist_tracks_from_reposts_playlist(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
) -> int:
    """Remove an unfollowed artist's tracks from the local reposts playlist.

    Targets tracks the artist reposted or uploaded, but keeps any track that
    another currently-followed artist also reposted. Local DB only — the SC
    mirror playlist is a full rebuild on every discovery sync, so it catches
    up on the next run. Returns number of playlist rows deleted.
    """
    playlist_row = conn.execute(
        "SELECT id FROM playlists WHERE discovery_source = 'soundcloud_reposts'"
    ).fetchone()
    if playlist_row is None:
        return 0

    cursor = conn.execute(
        """
        DELETE FROM playlist_tracks
        WHERE playlist_id = :pid
          AND track_id IN (
            SELECT t.id
            FROM tracks t
            WHERE t.soundcloud_id IN (
                SELECT dt.soundcloud_id
                FROM discovery_track_reposters dtr
                JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
                WHERE dtr.discovery_artist_id = :aid
                UNION
                SELECT u.soundcloud_id
                FROM sc_artist_uploads u
                WHERE u.discovery_artist_id = :aid
            )
            AND NOT EXISTS (
                SELECT 1
                FROM discovery_tracks dt2
                JOIN discovery_track_reposters dtr2 ON dtr2.discovery_track_id = dt2.id
                JOIN discovery_artists da2 ON da2.id = dtr2.discovery_artist_id
                WHERE dt2.soundcloud_id = t.soundcloud_id
                  AND da2.id != :aid
                  AND da2.is_following = 1
            )
          )
        """,
        {"pid": playlist_row["id"], "aid": discovery_artist_id},
    )
    deleted = cursor.rowcount
    if deleted:
        conn.execute(
            "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (playlist_row["id"],),
        )
        logger.info(
            f"Unfollow artist {discovery_artist_id}: removed {deleted} tracks "
            f"from reposts playlist {playlist_row['id']}"
        )
    return deleted


def upsert_match_override(
    conn: sqlite3.Connection,
    discovery_artist_id: int,
    local_artist_name: str,
    action: str,
) -> int:
    """Upsert an artist match override. Returns the row id.

    Normalizes local_artist_name via SQL to match tracks.artist_normalized:
    LOWER(TRIM(REPLACE(REPLACE(REPLACE(x, '.', ''), '!', ''), '?', '')))
    """
    cursor = conn.execute(
        """
        INSERT INTO artist_match_overrides (discovery_artist_id, local_artist_name, action)
        VALUES (
            ?,
            LOWER(TRIM(REPLACE(REPLACE(REPLACE(?, '.', ''), '!', ''), '?', ''))),
            ?
        )
        ON CONFLICT(local_artist_name, discovery_artist_id)
        DO UPDATE SET action = excluded.action
        RETURNING id
        """,
        (discovery_artist_id, local_artist_name, action),
    )
    row = cursor.fetchone()
    return row[0]


def delete_match_override(conn: sqlite3.Connection, override_id: int) -> bool:
    """Delete a match override by id. Returns True if a row was deleted."""
    cursor = conn.execute(
        "DELETE FROM artist_match_overrides WHERE id = ?",
        (override_id,),
    )
    return cursor.rowcount > 0


def get_pareto_artists(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return artists producing 80% of feed volume in the last 30 days.

    Uses a window-function query with cumulative sum ordered by event_count DESC.
    The WHERE filter includes each artist whose predecessor-cumulative was below 80%
    (i.e. (cumulative - event_count) / total < 0.80), which correctly handles:
    - Single artist producing >80% alone (included as the first to cross threshold)
    - Ties at the boundary (ROWS frame with tiebreaker avoids over-including)
    - Empty events (returns zeros with empty list)
    """
    sql = """
    WITH feed_totals AS (
      SELECT discovery_artist_id, COUNT(*) AS event_count
      FROM discovery_track_reposters
      WHERE seen_at > datetime('now', '-30 days')
      GROUP BY discovery_artist_id
    ),
    ranked AS (
      SELECT discovery_artist_id,
             event_count,
             SUM(event_count) OVER () AS total,
             SUM(event_count) OVER (
               ORDER BY event_count DESC, discovery_artist_id ASC
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
             ) AS cumulative
      FROM feed_totals
    )
    SELECT discovery_artist_id, event_count, total
    FROM ranked
    WHERE (cumulative - event_count) * 1.0 / total < 0.80
    ORDER BY event_count DESC, discovery_artist_id ASC
    """
    rows = conn.execute(sql).fetchall()

    if not rows:
        # Check if there are any events at all (to distinguish empty table vs all artists)
        total_row = conn.execute(
            "SELECT COUNT(*) FROM discovery_track_reposters WHERE seen_at > datetime('now', '-30 days')"
        ).fetchone()
        total = total_row[0] if total_row else 0
        return {
            "artists_producing_80pct": 0,
            "total_events": total,
            "threshold_ids": [],
        }

    total = rows[0]["total"]
    ids = [r["discovery_artist_id"] for r in rows]
    return {
        "artists_producing_80pct": len(ids),
        "total_events": total,
        "threshold_ids": ids,
    }


def sync_followings(
    conn: sqlite3.Connection,
    followings: list[dict[str, Any]],
) -> dict[str, int]:
    """Upsert SoundCloud followings into discovery_artists.

    Strategy:
    1. Mark ALL currently is_following=1 rows as is_following=0.
    2. For each following: UPDATE if soundcloud_user_id matches, else INSERT.
    3. All done in a single transaction (caller must commit).

    Returns:
        {followings_synced, new_artists, unfollowed_remotely}
    """
    # Count artists that were following before sync
    cursor = conn.execute(
        "SELECT COUNT(*) FROM discovery_artists WHERE is_following = 1"
    )
    was_following_count: int = cursor.fetchone()[0]

    # Step 1: Reset all is_following flags
    conn.execute("UPDATE discovery_artists SET is_following = 0 WHERE is_following = 1")

    inserted = 0
    updated = 0

    for user in followings:
        sc_id = str(user.get("id", ""))
        username = user.get("permalink", "") or user.get("username", "") or sc_id
        display_name = user.get("full_name", "") or user.get("username", "") or username
        avatar_url: str | None = user.get("avatar_url")
        follower_count: int | None = user.get("followers_count")

        if not sc_id:
            logger.warning(f"sync_followings: skipping user with no id: {user}")
            continue

        # Check if artist exists by soundcloud_user_id
        row = conn.execute(
            "SELECT id FROM discovery_artists WHERE soundcloud_user_id = ?",
            (sc_id,),
        ).fetchone()

        if row:
            conn.execute(
                """
                UPDATE discovery_artists
                SET is_following = 1,
                    avatar_url = ?,
                    follower_count = ?,
                    display_name = ?,
                    last_sc_sync_at = CURRENT_TIMESTAMP
                WHERE soundcloud_user_id = ?
                """,
                (avatar_url, follower_count, display_name, sc_id),
            )
            updated += 1
        else:
            # Derive slug from username (permalink is the SC slug)
            slug = username.lower().strip()
            # Find a unique slug — append SC id suffix if collision
            existing_slug = conn.execute(
                "SELECT id FROM discovery_artists WHERE slug = ?", (slug,)
            ).fetchone()
            if existing_slug:
                slug = f"{slug}-{sc_id}"

            # New followings get a ranking at the end of the current list
            max_rank_row = conn.execute(
                "SELECT COALESCE(MAX(ranking), 0) FROM discovery_artists"
            ).fetchone()
            next_rank: int = max_rank_row[0] + 1

            conn.execute(
                """
                INSERT INTO discovery_artists
                    (soundcloud_user_id, slug, display_name, ranking,
                     avatar_url, follower_count, is_following, last_sc_sync_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (sc_id, slug, display_name, next_rank, avatar_url, follower_count),
            )
            inserted += 1

    unfollowed_remotely = max(0, was_following_count - updated)

    logger.info(
        f"sync_followings: {len(followings)} fetched, "
        f"{updated} updated, {inserted} inserted, "
        f"{unfollowed_remotely} newly unfollowed"
    )

    return {
        "followings_synced": updated + inserted,
        "new_artists": inserted,
        "unfollowed_remotely": unfollowed_remotely,
    }
