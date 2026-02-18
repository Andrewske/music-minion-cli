"""
Playlist analytics for Music Minion CLI.
Provides comprehensive statistics about playlist content using efficient SQL aggregations.
"""

from typing import Any, Optional
from music_minion.core.database import get_db_connection
from .crud import get_playlist_by_id
from . import filters


def get_basic_stats(playlist_id: int) -> dict[str, Any]:
    """
    Get basic statistics about a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with total_tracks, total_duration, avg_duration, year_min, year_max
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {
            "total_tracks": 0,
            "total_duration": 0,
            "avg_duration": 0,
            "year_min": None,
            "year_max": None,
        }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Manual playlist - join with playlist_tracks
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_tracks,
                    COALESCE(SUM(t.duration), 0) as total_duration,
                    COALESCE(AVG(t.duration), 0) as avg_duration,
                    MIN(t.year) as year_min,
                    MAX(t.year) as year_max
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
            """,
                (playlist_id,),
            )
        else:
            # Smart playlist - use filter logic
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "total_tracks": 0,
                    "total_duration": 0,
                    "avg_duration": 0,
                    "year_min": None,
                    "year_max": None,
                }

            where_clause, params = filters.build_filter_query(playlist_filters)
            cursor = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total_tracks,
                    COALESCE(SUM(t.duration), 0) as total_duration,
                    COALESCE(AVG(t.duration), 0) as avg_duration,
                    MIN(t.year) as year_min,
                    MAX(t.year) as year_max
                FROM tracks t
                WHERE {where_clause}
            """,
                params,
            )

        row = cursor.fetchone()
        return (
            dict(row)
            if row
            else {
                "total_tracks": 0,
                "total_duration": 0,
                "avg_duration": 0,
                "year_min": None,
                "year_max": None,
            }
        )


def get_artist_analysis(playlist_id: int, top_n: int = 10) -> dict[str, Any]:
    """
    Analyze artist distribution in a playlist.

    Args:
        playlist_id: Playlist ID
        top_n: Number of top artists to return

    Returns:
        Dict with top_artists (list of dicts), total_unique_artists, diversity_ratio
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {"top_artists": [], "total_unique_artists": 0, "diversity_ratio": 0.0}

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get total tracks for diversity calculation
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total
                FROM playlist_tracks
                WHERE playlist_id = ?
            """,
                (playlist_id,),
            )
            total_tracks = cursor.fetchone()["total"]

            # Get top artists
            cursor = conn.execute(
                """
                SELECT
                    t.artist,
                    COUNT(*) as track_count
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.artist IS NOT NULL AND t.artist != ''
                GROUP BY t.artist
                ORDER BY track_count DESC
                LIMIT ?
            """,
                (playlist_id, top_n),
            )
            top_artists = [dict(row) for row in cursor.fetchall()]

            # Get total unique artists
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT t.artist) as unique_artists
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.artist IS NOT NULL AND t.artist != ''
            """,
                (playlist_id,),
            )
            unique_artists = cursor.fetchone()["unique_artists"]
        else:
            # Smart playlist
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "top_artists": [],
                    "total_unique_artists": 0,
                    "diversity_ratio": 0.0,
                }

            where_clause, params = filters.build_filter_query(playlist_filters)

            # Get total tracks
            cursor = conn.execute(
                f"""
                SELECT COUNT(*) as total
                FROM tracks t
                WHERE {where_clause}
            """,
                params,
            )
            total_tracks = cursor.fetchone()["total"]

            # Get top artists
            cursor = conn.execute(
                f"""
                SELECT
                    t.artist,
                    COUNT(*) as track_count
                FROM tracks t
                WHERE ({where_clause}) AND t.artist IS NOT NULL AND t.artist != ''
                GROUP BY t.artist
                ORDER BY track_count DESC
                LIMIT ?
            """,
                params + [top_n],
            )
            top_artists = [dict(row) for row in cursor.fetchall()]

            # Get total unique artists
            cursor = conn.execute(
                f"""
                SELECT COUNT(DISTINCT t.artist) as unique_artists
                FROM tracks t
                WHERE ({where_clause}) AND t.artist IS NOT NULL AND t.artist != ''
            """,
                params,
            )
            unique_artists = cursor.fetchone()["unique_artists"]

        # Calculate diversity ratio (tracks per artist)
        diversity_ratio = total_tracks / unique_artists if unique_artists > 0 else 0.0

        return {
            "top_artists": top_artists,
            "total_unique_artists": unique_artists,
            "diversity_ratio": diversity_ratio,
        }


def get_genre_distribution(playlist_id: int) -> dict[str, Any]:
    """
    Analyze genre distribution in a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with genres (list of dicts with genre, count, percentage)
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {"genres": []}

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get total tracks
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total
                FROM playlist_tracks
                WHERE playlist_id = ?
            """,
                (playlist_id,),
            )
            total_tracks = cursor.fetchone()["total"]

            # Get genre distribution
            cursor = conn.execute(
                """
                SELECT
                    COALESCE(t.genre, 'Unknown') as genre,
                    COUNT(*) as count
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
                GROUP BY t.genre
                ORDER BY count DESC
            """,
                (playlist_id,),
            )
        else:
            # Smart playlist
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {"genres": []}

            where_clause, params = filters.build_filter_query(playlist_filters)

            # Get total tracks
            cursor = conn.execute(
                f"""
                SELECT COUNT(*) as total
                FROM tracks t
                WHERE {where_clause}
            """,
                params,
            )
            total_tracks = cursor.fetchone()["total"]

            # Get genre distribution
            cursor = conn.execute(
                f"""
                SELECT
                    COALESCE(t.genre, 'Unknown') as genre,
                    COUNT(*) as count
                FROM tracks t
                WHERE {where_clause}
                GROUP BY t.genre
                ORDER BY count DESC
            """,
                params,
            )

        genres = []
        for row in cursor.fetchall():
            genres.append(
                {
                    "genre": row["genre"],
                    "count": row["count"],
                    "percentage": (row["count"] / total_tracks * 100)
                    if total_tracks > 0
                    else 0,
                }
            )

        return {"genres": genres}


def get_tag_analysis(playlist_id: int, top_n: int = 10) -> dict[str, Any]:
    """
    Analyze tag distribution in a playlist.

    Args:
        playlist_id: Playlist ID
        top_n: Number of top tags to return per source

    Returns:
        Dict with top_ai_tags, top_user_tags, top_file_tags, most_confident_ai_tags
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {
            "top_ai_tags": [],
            "top_user_tags": [],
            "top_file_tags": [],
            "most_confident_ai_tags": [],
        }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get top tags by source
            cursor = conn.execute(
                """
                SELECT
                    tag.tag_name,
                    tag.source,
                    COUNT(*) as count,
                    AVG(tag.confidence) as avg_confidence
                FROM tags tag
                JOIN playlist_tracks pt ON tag.track_id = pt.track_id
                WHERE pt.playlist_id = ? AND tag.source = 'ai' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                (playlist_id, top_n),
            )
            top_ai_tags = [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                """
                SELECT
                    tag.tag_name,
                    COUNT(*) as count
                FROM tags tag
                JOIN playlist_tracks pt ON tag.track_id = pt.track_id
                WHERE pt.playlist_id = ? AND tag.source = 'user' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                (playlist_id, top_n),
            )
            top_user_tags = [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                """
                SELECT
                    tag.tag_name,
                    COUNT(*) as count
                FROM tags tag
                JOIN playlist_tracks pt ON tag.track_id = pt.track_id
                WHERE pt.playlist_id = ? AND tag.source = 'file' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                (playlist_id, top_n),
            )
            top_file_tags = [dict(row) for row in cursor.fetchall()]

            # Most confident AI tags
            cursor = conn.execute(
                """
                SELECT
                    tag.tag_name,
                    COUNT(*) as count,
                    AVG(tag.confidence) as avg_confidence
                FROM tags tag
                JOIN playlist_tracks pt ON tag.track_id = pt.track_id
                WHERE pt.playlist_id = ? AND tag.source = 'ai' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY avg_confidence DESC
                LIMIT ?
            """,
                (playlist_id, top_n),
            )
            most_confident_ai_tags = [dict(row) for row in cursor.fetchall()]
        else:
            # Smart playlist
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "top_ai_tags": [],
                    "top_user_tags": [],
                    "top_file_tags": [],
                    "most_confident_ai_tags": [],
                }

            where_clause, params = filters.build_filter_query(playlist_filters)

            # Get top tags by source
            cursor = conn.execute(
                f"""
                SELECT
                    tag.tag_name,
                    tag.source,
                    COUNT(*) as count,
                    AVG(tag.confidence) as avg_confidence
                FROM tags tag
                JOIN tracks t ON tag.track_id = t.id
                WHERE ({where_clause}) AND tag.source = 'ai' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                params + [top_n],
            )
            top_ai_tags = [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                f"""
                SELECT
                    tag.tag_name,
                    COUNT(*) as count
                FROM tags tag
                JOIN tracks t ON tag.track_id = t.id
                WHERE ({where_clause}) AND tag.source = 'user' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                params + [top_n],
            )
            top_user_tags = [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                f"""
                SELECT
                    tag.tag_name,
                    COUNT(*) as count
                FROM tags tag
                JOIN tracks t ON tag.track_id = t.id
                WHERE ({where_clause}) AND tag.source = 'file' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY count DESC
                LIMIT ?
            """,
                params + [top_n],
            )
            top_file_tags = [dict(row) for row in cursor.fetchall()]

            # Most confident AI tags
            cursor = conn.execute(
                f"""
                SELECT
                    tag.tag_name,
                    COUNT(*) as count,
                    AVG(tag.confidence) as avg_confidence
                FROM tags tag
                JOIN tracks t ON tag.track_id = t.id
                WHERE ({where_clause}) AND tag.source = 'ai' AND tag.blacklisted = 0
                GROUP BY tag.tag_name
                ORDER BY avg_confidence DESC
                LIMIT ?
            """,
                params + [top_n],
            )
            most_confident_ai_tags = [dict(row) for row in cursor.fetchall()]

        return {
            "top_ai_tags": top_ai_tags,
            "top_user_tags": top_user_tags,
            "top_file_tags": top_file_tags,
            "most_confident_ai_tags": most_confident_ai_tags,
        }


def get_bpm_analysis(playlist_id: int) -> dict[str, Any]:
    """
    Analyze BPM distribution in a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with min, max, avg, median, distribution
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "distribution": {},
        }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get BPM stats and distribution in single query
            cursor = conn.execute(
                """
                SELECT
                    MIN(t.bpm) as min_bpm,
                    MAX(t.bpm) as max_bpm,
                    AVG(t.bpm) as avg_bpm,
                    COUNT(CASE WHEN t.bpm < 100 THEN 1 END) as under_100,
                    COUNT(CASE WHEN t.bpm >= 100 AND t.bpm < 120 THEN 1 END) as bpm_100_120,
                    COUNT(CASE WHEN t.bpm >= 120 AND t.bpm < 140 THEN 1 END) as bpm_120_140,
                    COUNT(CASE WHEN t.bpm >= 140 AND t.bpm < 160 THEN 1 END) as bpm_140_160,
                    COUNT(CASE WHEN t.bpm >= 160 THEN 1 END) as over_160
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.bpm IS NOT NULL
            """,
                (playlist_id,),
            )
        else:
            # Smart playlist
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "min": None,
                    "max": None,
                    "avg": None,
                    "median": None,
                    "distribution": {},
                }

            where_clause, params = filters.build_filter_query(playlist_filters)
            cursor = conn.execute(
                f"""
                SELECT
                    MIN(t.bpm) as min_bpm,
                    MAX(t.bpm) as max_bpm,
                    AVG(t.bpm) as avg_bpm,
                    COUNT(CASE WHEN t.bpm < 100 THEN 1 END) as under_100,
                    COUNT(CASE WHEN t.bpm >= 100 AND t.bpm < 120 THEN 1 END) as bpm_100_120,
                    COUNT(CASE WHEN t.bpm >= 120 AND t.bpm < 140 THEN 1 END) as bpm_120_140,
                    COUNT(CASE WHEN t.bpm >= 140 AND t.bpm < 160 THEN 1 END) as bpm_140_160,
                    COUNT(CASE WHEN t.bpm >= 160 THEN 1 END) as over_160
                FROM tracks t
                WHERE ({where_clause}) AND t.bpm IS NOT NULL
            """,
                params,
            )

        row = cursor.fetchone()
        if not row or row["min_bpm"] is None:
            return {
                "min": None,
                "max": None,
                "avg": None,
                "median": None,
                "distribution": {},
            }

        # Get median (approximate using percentile)
        if playlist["type"] == "manual":
            cursor = conn.execute(
                """
                SELECT t.bpm
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.bpm IS NOT NULL
                ORDER BY t.bpm
                LIMIT 1 OFFSET (
                    SELECT COUNT(*) / 2
                    FROM tracks t2
                    JOIN playlist_tracks pt2 ON t2.id = pt2.track_id
                    WHERE pt2.playlist_id = ? AND t2.bpm IS NOT NULL
                )
            """,
                (playlist_id, playlist_id),
            )
        else:
            cursor = conn.execute(
                f"""
                SELECT t.bpm
                FROM tracks t
                WHERE ({where_clause}) AND t.bpm IS NOT NULL
                ORDER BY t.bpm
                LIMIT 1 OFFSET (
                    SELECT COUNT(*) / 2
                    FROM tracks t2
                    WHERE ({where_clause}) AND t2.bpm IS NOT NULL
                )
            """,
                params + params,
            )

        median_row = cursor.fetchone()
        median = median_row["bpm"] if median_row else None

        return {
            "min": row["min_bpm"],
            "max": row["max_bpm"],
            "avg": row["avg_bpm"],
            "median": median,
            "distribution": {
                "<100": row["under_100"],
                "100-120": row["bpm_100_120"],
                "120-140": row["bpm_120_140"],
                "140-160": row["bpm_140_160"],
                "160+": row["over_160"],
            },
        }


def get_key_distribution(playlist_id: int) -> dict[str, Any]:
    """
    Analyze key signature distribution in a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with top_keys (list of dicts), total_unique_keys, harmonic_pairs_count
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {"top_keys": [], "total_unique_keys": 0, "harmonic_pairs_count": 0}

    # Basic Camelot wheel compatible keys (simplified)
    # Format: key_signature -> list of compatible keys for mixing
    harmonic_compatibility = {
        "C major": ["C major", "G major", "F major", "A minor"],
        "G major": ["G major", "D major", "C major", "E minor"],
        "D major": ["D major", "A major", "G major", "B minor"],
        "A major": ["A major", "E major", "D major", "F# minor"],
        "E major": ["E major", "B major", "A major", "C# minor"],
        "B major": ["B major", "F# major", "E major", "G# minor"],
        "F# major": ["F# major", "C# major", "B major", "D# minor"],
        "C# major": ["C# major", "G# major", "F# major", "A# minor"],
        "F major": ["F major", "C major", "Bb major", "D minor"],
        "Bb major": ["Bb major", "F major", "Eb major", "G minor"],
        "Eb major": ["Eb major", "Bb major", "Ab major", "C minor"],
        "Ab major": ["Ab major", "Eb major", "Db major", "F minor"],
        "A minor": ["A minor", "E minor", "D minor", "C major"],
        "E minor": ["E minor", "B minor", "A minor", "G major"],
        "B minor": ["B minor", "F# minor", "E minor", "D major"],
        "F# minor": ["F# minor", "C# minor", "B minor", "A major"],
        "C# minor": ["C# minor", "G# minor", "F# minor", "E major"],
        "G# minor": ["G# minor", "D# minor", "C# minor", "B major"],
        "D minor": ["D minor", "A minor", "G minor", "F major"],
        "G minor": ["G minor", "D minor", "C minor", "Bb major"],
        "C minor": ["C minor", "G minor", "F minor", "Eb major"],
        "F minor": ["F minor", "C minor", "Bb minor", "Ab major"],
    }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get key distribution
            cursor = conn.execute(
                """
                SELECT
                    t.key_signature,
                    COUNT(*) as count
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.key_signature IS NOT NULL AND t.key_signature != ''
                GROUP BY t.key_signature
                ORDER BY count DESC
            """,
                (playlist_id,),
            )
            top_keys = [dict(row) for row in cursor.fetchall()]

            # Get unique keys count
            total_unique_keys = len(top_keys)

            # Calculate harmonic pairs (simplified: count tracks with compatible keys)
            # This is approximate - counts potential transitions
            cursor = conn.execute(
                """
                SELECT t.key_signature
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.key_signature IS NOT NULL AND t.key_signature != ''
            """,
                (playlist_id,),
            )
            all_keys = [row["key_signature"] for row in cursor.fetchall()]
        else:
            # Smart playlist
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "top_keys": [],
                    "total_unique_keys": 0,
                    "harmonic_pairs_count": 0,
                }

            where_clause, params = filters.build_filter_query(playlist_filters)

            cursor = conn.execute(
                f"""
                SELECT
                    t.key_signature,
                    COUNT(*) as count
                FROM tracks t
                WHERE ({where_clause}) AND t.key_signature IS NOT NULL AND t.key_signature != ''
                GROUP BY t.key_signature
                ORDER BY count DESC
            """,
                params,
            )
            top_keys = [dict(row) for row in cursor.fetchall()]

            total_unique_keys = len(top_keys)

            cursor = conn.execute(
                f"""
                SELECT t.key_signature
                FROM tracks t
                WHERE ({where_clause}) AND t.key_signature IS NOT NULL AND t.key_signature != ''
            """,
                params,
            )
            all_keys = [row["key_signature"] for row in cursor.fetchall()]

        # Count harmonic pairs (approximate)
        harmonic_pairs = 0
        for i, key1 in enumerate(all_keys):
            for key2 in all_keys[i + 1 :]:
                if (
                    key1 in harmonic_compatibility
                    and key2 in harmonic_compatibility.get(key1, [])
                ):
                    harmonic_pairs += 1

        return {
            "top_keys": top_keys,
            "total_unique_keys": total_unique_keys,
            "harmonic_pairs_count": harmonic_pairs,
        }


def get_year_distribution(playlist_id: int) -> dict[str, Any]:
    """
    Analyze year/era distribution in a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with decade_distribution, recent_vs_classic
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {
            "decade_distribution": {},
            "recent_count": 0,
            "classic_count": 0,
            "recent_percentage": 0,
        }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            cursor = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN t.year >= 1970 AND t.year < 1980 THEN 1 END) as decade_70s,
                    COUNT(CASE WHEN t.year >= 1980 AND t.year < 1990 THEN 1 END) as decade_80s,
                    COUNT(CASE WHEN t.year >= 1990 AND t.year < 2000 THEN 1 END) as decade_90s,
                    COUNT(CASE WHEN t.year >= 2000 AND t.year < 2010 THEN 1 END) as decade_00s,
                    COUNT(CASE WHEN t.year >= 2010 AND t.year < 2020 THEN 1 END) as decade_10s,
                    COUNT(CASE WHEN t.year >= 2020 THEN 1 END) as decade_20s,
                    COUNT(CASE WHEN t.year >= 2020 THEN 1 END) as recent_count,
                    COUNT(CASE WHEN t.year < 2020 THEN 1 END) as classic_count,
                    COUNT(*) as total
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND t.year IS NOT NULL
            """,
                (playlist_id,),
            )
        else:
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "decade_distribution": {},
                    "recent_count": 0,
                    "classic_count": 0,
                    "recent_percentage": 0,
                }

            where_clause, params = filters.build_filter_query(playlist_filters)
            cursor = conn.execute(
                f"""
                SELECT
                    COUNT(CASE WHEN t.year >= 1970 AND t.year < 1980 THEN 1 END) as decade_70s,
                    COUNT(CASE WHEN t.year >= 1980 AND t.year < 1990 THEN 1 END) as decade_80s,
                    COUNT(CASE WHEN t.year >= 1990 AND t.year < 2000 THEN 1 END) as decade_90s,
                    COUNT(CASE WHEN t.year >= 2000 AND t.year < 2010 THEN 1 END) as decade_00s,
                    COUNT(CASE WHEN t.year >= 2010 AND t.year < 2020 THEN 1 END) as decade_10s,
                    COUNT(CASE WHEN t.year >= 2020 THEN 1 END) as decade_20s,
                    COUNT(CASE WHEN t.year >= 2020 THEN 1 END) as recent_count,
                    COUNT(CASE WHEN t.year < 2020 THEN 1 END) as classic_count,
                    COUNT(*) as total
                FROM tracks t
                WHERE ({where_clause}) AND t.year IS NOT NULL
            """,
                params,
            )

        row = cursor.fetchone()
        if not row:
            return {
                "decade_distribution": {},
                "recent_count": 0,
                "classic_count": 0,
                "recent_percentage": 0,
            }

        total = row["total"]
        recent_percentage = (row["recent_count"] / total * 100) if total > 0 else 0

        return {
            "decade_distribution": {
                "70s": row["decade_70s"],
                "80s": row["decade_80s"],
                "90s": row["decade_90s"],
                "00s": row["decade_00s"],
                "10s": row["decade_10s"],
                "20s+": row["decade_20s"],
            },
            "recent_count": row["recent_count"],
            "classic_count": row["classic_count"],
            "recent_percentage": recent_percentage,
        }


def get_rating_analysis(playlist_id: int) -> dict[str, Any]:
    """
    Analyze rating distribution in a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with rating_counts, most_loved_tracks
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {"rating_counts": {}, "most_loved_tracks": []}

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            # Get rating type distribution
            cursor = conn.execute(
                """
                SELECT
                    r.rating_type,
                    COUNT(DISTINCT r.track_id) as count
                FROM ratings r
                JOIN playlist_tracks pt ON r.track_id = pt.track_id
                WHERE pt.playlist_id = ?
                GROUP BY r.rating_type
            """,
                (playlist_id,),
            )
            rating_counts = {
                row["rating_type"]: row["count"] for row in cursor.fetchall()
            }

            # Get most loved tracks
            cursor = conn.execute(
                """
                SELECT
                    t.title,
                    t.artist,
                    r.timestamp
                FROM tracks t
                JOIN ratings r ON t.id = r.track_id
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ? AND r.rating_type = 'love'
                ORDER BY r.timestamp DESC
                LIMIT 10
            """,
                (playlist_id,),
            )
            most_loved_tracks = [dict(row) for row in cursor.fetchall()]
        else:
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {"rating_counts": {}, "most_loved_tracks": []}

            where_clause, params = filters.build_filter_query(playlist_filters)

            cursor = conn.execute(
                f"""
                SELECT
                    r.rating_type,
                    COUNT(DISTINCT r.track_id) as count
                FROM ratings r
                JOIN tracks t ON r.track_id = t.id
                WHERE ({where_clause})
                GROUP BY r.rating_type
            """,
                params,
            )
            rating_counts = {
                row["rating_type"]: row["count"] for row in cursor.fetchall()
            }

            cursor = conn.execute(
                f"""
                SELECT
                    t.title,
                    t.artist,
                    r.timestamp
                FROM tracks t
                JOIN ratings r ON t.id = r.track_id
                WHERE ({where_clause}) AND r.rating_type = 'love'
                ORDER BY r.timestamp DESC
                LIMIT 10
            """,
                params,
            )
            most_loved_tracks = [dict(row) for row in cursor.fetchall()]

        return {"rating_counts": rating_counts, "most_loved_tracks": most_loved_tracks}


def get_quality_metrics(playlist_id: int) -> dict[str, Any]:
    """
    Calculate quality/completeness metrics for a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with missing counts and completeness score
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {
            "total_tracks": 0,
            "missing_bpm": 0,
            "missing_key": 0,
            "missing_year": 0,
            "missing_genre": 0,
            "without_tags": 0,
            "completeness_score": 0,
        }

    with get_db_connection() as conn:
        if playlist["type"] == "manual":
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN t.bpm IS NULL THEN 1 END) as missing_bpm,
                    COUNT(CASE WHEN t.key_signature IS NULL OR t.key_signature = '' THEN 1 END) as missing_key,
                    COUNT(CASE WHEN t.year IS NULL THEN 1 END) as missing_year,
                    COUNT(CASE WHEN t.genre IS NULL OR t.genre = '' THEN 1 END) as missing_genre
                FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
            """,
                (playlist_id,),
            )
            row = cursor.fetchone()

            # Count tracks without any tags
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT pt.track_id) as without_tags
                FROM playlist_tracks pt
                LEFT JOIN tags tag ON pt.track_id = tag.track_id AND tag.blacklisted = 0
                WHERE pt.playlist_id = ? AND tag.id IS NULL
            """,
                (playlist_id,),
            )
            without_tags = cursor.fetchone()["without_tags"]
        else:
            playlist_filters = filters.get_playlist_filters(playlist_id)
            if not playlist_filters:
                return {
                    "total_tracks": 0,
                    "missing_bpm": 0,
                    "missing_key": 0,
                    "missing_year": 0,
                    "missing_genre": 0,
                    "without_tags": 0,
                    "completeness_score": 0,
                }

            where_clause, params = filters.build_filter_query(playlist_filters)

            cursor = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN t.bpm IS NULL THEN 1 END) as missing_bpm,
                    COUNT(CASE WHEN t.key_signature IS NULL OR t.key_signature = '' THEN 1 END) as missing_key,
                    COUNT(CASE WHEN t.year IS NULL THEN 1 END) as missing_year,
                    COUNT(CASE WHEN t.genre IS NULL OR t.genre = '' THEN 1 END) as missing_genre
                FROM tracks t
                WHERE {where_clause}
            """,
                params,
            )
            row = cursor.fetchone()

            cursor = conn.execute(
                f"""
                SELECT COUNT(DISTINCT t.id) as without_tags
                FROM tracks t
                LEFT JOIN tags tag ON t.id = tag.track_id AND tag.blacklisted = 0
                WHERE ({where_clause}) AND tag.id IS NULL
            """,
                params,
            )
            without_tags = cursor.fetchone()["without_tags"]

        total = row["total"]
        if total == 0:
            return {
                "total_tracks": 0,
                "missing_bpm": 0,
                "missing_key": 0,
                "missing_year": 0,
                "missing_genre": 0,
                "without_tags": 0,
                "completeness_score": 0,
            }

        # Calculate completeness score
        # Fields: bpm, key, year, genre, tags (5 fields)
        total_fields = total * 5
        missing_fields = (
            row["missing_bpm"]
            + row["missing_key"]
            + row["missing_year"]
            + row["missing_genre"]
            + without_tags
        )
        completeness_score = (
            ((total_fields - missing_fields) / total_fields * 100)
            if total_fields > 0
            else 0
        )

        return {
            "total_tracks": total,
            "missing_bpm": row["missing_bpm"],
            "missing_key": row["missing_key"],
            "missing_year": row["missing_year"],
            "missing_genre": row["missing_genre"],
            "without_tags": without_tags,
            "completeness_score": completeness_score,
        }


def get_playlist_analytics(
    playlist_id: int, sections: Optional[list[str]] = None
) -> dict[str, Any]:
    """
    Get comprehensive analytics for a playlist.

    Args:
        playlist_id: Playlist ID
        sections: Optional list of section names to include. If None, includes all.
                 Valid sections: 'basic', 'artists', 'genres', 'tags', 'bpm',
                                'keys', 'years', 'ratings', 'elo', 'quality'

    Returns:
        Dict with all analytics data
    """
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        return {"error": "Playlist not found"}

    # Define all available sections
    all_sections = {
        "basic": get_basic_stats,
        "artists": get_artist_analysis,
        "genres": get_genre_distribution,
        "tags": get_tag_analysis,
        "bpm": get_bpm_analysis,
        "keys": get_key_distribution,
        "years": get_year_distribution,
        "ratings": get_rating_analysis,
        "elo": get_elo_analysis,
        "quality": get_quality_metrics,
        "pace": lambda pid: {"pace": get_comparison_pace(pid)},
    }

    # Determine which sections to run
    if sections is None:
        sections_to_run = all_sections.keys()
    else:
        sections_to_run = [s for s in sections if s in all_sections]

    # Gather analytics
    result = {"playlist_name": playlist["name"], "playlist_type": playlist["type"]}

    for section_name in sections_to_run:
        result[section_name] = all_sections[section_name](playlist_id)

    return result


def get_comparison_pace(playlist_id: int, days: int = 7) -> float:
    """Calculate average comparisons per day over last N days.

    Args:
        playlist_id: Playlist to analyze
        days: Number of days to look back (default 7)

    Returns:
        Average comparisons per day (float). Returns 0.0 if no comparisons.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COUNT(*) as total
            FROM playlist_comparison_history
            WHERE playlist_id = ? AND timestamp >= datetime('now', ? || ' days')
            """,
            (playlist_id, f"-{days}"),
        )
        total = cursor.fetchone()["total"]
        return total / days if days > 0 else 0.0


def get_elo_analysis(playlist_id: int) -> dict[str, Any]:
    """
    Get ELO rating analysis for a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        Dict with ELO statistics
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_tracks,
                COUNT(per.rating) as rated_tracks,
                COUNT(CASE WHEN per.comparison_count > 0 THEN 1 END) as compared_tracks,
                COALESCE(AVG(per.rating), 0) as avg_playlist_rating,
                COALESCE(MIN(per.rating), 0) as min_playlist_rating,
                COALESCE(MAX(per.rating), 0) as max_playlist_rating,
                COALESCE(AVG(per.comparison_count), 0) as avg_playlist_comparisons,
                COALESCE(SUM(per.comparison_count), 0) as total_playlist_comparisons
            FROM playlist_tracks pt
            LEFT JOIN playlist_elo_ratings per ON pt.track_id = per.track_id
                AND per.playlist_id = ?
            WHERE pt.playlist_id = ?
        """,
            (playlist_id, playlist_id),
        )

        row = cursor.fetchone()

        if not row or row["total_tracks"] == 0:
            return {
                "total_tracks": 0,
                "rated_tracks": 0,
                "compared_tracks": 0,
                "coverage_percentage": 0.0,
                "avg_playlist_rating": 0.0,
                "min_playlist_rating": 0.0,
                "max_playlist_rating": 0.0,
                "avg_playlist_comparisons": 0.0,
                "total_playlist_comparisons": 0,
            }

        total_tracks = row["total_tracks"]
        rated_tracks = row["rated_tracks"]
        compared_tracks = row["compared_tracks"]

        return {
            "total_tracks": total_tracks,
            "rated_tracks": rated_tracks,
            "compared_tracks": compared_tracks,
            "coverage_percentage": (compared_tracks / total_tracks * 100)
            if total_tracks > 0
            else 0.0,
            "avg_playlist_rating": round(row["avg_playlist_rating"], 1),
            "min_playlist_rating": round(row["min_playlist_rating"], 1),
            "max_playlist_rating": round(row["max_playlist_rating"], 1),
            "avg_playlist_comparisons": round(row["avg_playlist_comparisons"], 1),
            "total_playlist_comparisons": row["total_playlist_comparisons"],
        }
