"""
Locate opus files and match them to existing MP3 track records.

Used for migrating from MP3 to Opus format while preserving all track history
(ratings, ELO scores, playlist membership, etc.).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ...core import database
from .deduplication import normalize_string


@dataclass(frozen=True)
class LocateResult:
    """Result of locate-opus operation."""

    updated: List[Dict]  # Successfully updated tracks
    multiple_matches: List[Dict]  # Opus files with multiple potential matches
    no_match: List[Dict]  # Opus files with no matches found


def _get_folder_tracks(folder_path: Path) -> List[Dict]:
    """Get all MP3 tracks in database whose album matches the folder name.

    Args:
        folder_path: Path to the folder (used to derive album name)

    Returns:
        List of track dicts with MP3 local_path in this album
    """
    album_name = folder_path.name

    with database.get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, title, artist, album, local_path
            FROM tracks
            WHERE album = ?
              AND local_path LIKE '%.mp3'
              AND local_path IS NOT NULL
            """,
            (album_name,),
        )
        return [dict(row) for row in cursor.fetchall()]


def _match_tier1_filename(opus_stem: str, tracks: List[Dict]) -> List[Dict]:
    """Tier 1: Exact filename stem match.

    Args:
        opus_stem: Filename without extension (e.g., "Artist - Title")
        tracks: List of track dicts to search

    Returns:
        List of matching tracks (usually 0 or 1)
    """
    matches = []
    opus_stem_lower = opus_stem.lower()

    for track in tracks:
        local_path = track.get("local_path", "")
        if not local_path:
            continue

        mp3_stem = Path(local_path).stem.lower()
        if opus_stem_lower == mp3_stem:
            matches.append(track)

    return matches


def _match_tier2_title(opus_title: str, tracks: List[Dict]) -> List[Dict]:
    """Tier 2: Exact title match (case-insensitive).

    Args:
        opus_title: Title from opus file metadata
        tracks: List of track dicts to search

    Returns:
        List of matching tracks
    """
    matches = []
    opus_title_lower = opus_title.lower().strip()

    for track in tracks:
        track_title = (track.get("title") or "").lower().strip()
        if opus_title_lower == track_title:
            matches.append(track)

    return matches


def _match_tier3_fuzzy(opus_title: str, tracks: List[Dict], threshold: float = 0.85) -> List[Tuple[Dict, float]]:
    """Tier 3: Fuzzy title match using normalized string comparison.

    Args:
        opus_title: Title from opus file metadata
        tracks: List of track dicts to search
        threshold: Minimum similarity score (0.0-1.0)

    Returns:
        List of (track, score) tuples above threshold
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    if not tracks:
        return []

    opus_normalized = normalize_string(opus_title)
    if not opus_normalized:
        return []

    # Build strings for tracks
    track_strings = []
    for track in tracks:
        title = track.get("title") or ""
        track_strings.append(normalize_string(title))

    # Filter out empty strings
    valid_indices = [i for i, s in enumerate(track_strings) if s]
    if not valid_indices:
        return []

    valid_strings = [track_strings[i] for i in valid_indices]
    valid_tracks = [tracks[i] for i in valid_indices]

    try:
        vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
        track_vectors = vectorizer.fit_transform(valid_strings)
        opus_vector = vectorizer.transform([opus_normalized])

        similarities = cosine_similarity(opus_vector, track_vectors)[0]

        matches = []
        for i, score in enumerate(similarities):
            if score >= threshold:
                matches.append((valid_tracks[i], float(score)))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    except ValueError:
        # Empty vocabulary
        return []


def _extract_opus_metadata(opus_path: Path) -> Dict:
    """Extract metadata from opus file.

    Args:
        opus_path: Path to opus file

    Returns:
        Dict with title, artist, etc.
    """
    from mutagen import File as MutagenFile

    try:
        audio = MutagenFile(opus_path)
        if audio is None:
            return {"title": opus_path.stem, "artist": None}

        # Opus uses Vorbis comments
        title = None
        artist = None

        if hasattr(audio, "tags") and audio.tags:
            # OggOpus uses uppercase tag names
            title = audio.tags.get("TITLE", [None])[0] if "TITLE" in audio.tags else None
            artist = audio.tags.get("ARTIST", [None])[0] if "ARTIST" in audio.tags else None

            # Also try lowercase (some files use this)
            if not title:
                title = audio.tags.get("title", [None])[0] if "title" in audio.tags else None
            if not artist:
                artist = audio.tags.get("artist", [None])[0] if "artist" in audio.tags else None

        return {
            "title": title or opus_path.stem,
            "artist": artist,
        }

    except Exception as e:
        logger.warning(f"Failed to read metadata from {opus_path}: {e}")
        return {"title": opus_path.stem, "artist": None}


def _update_track_path(track_id: int, new_path: str) -> bool:
    """Update a track's local_path in the database.

    Args:
        track_id: Database track ID
        new_path: New local_path value

    Returns:
        True if update succeeded
    """
    try:
        with database.get_db_connection() as conn:
            conn.execute(
                """
                UPDATE tracks
                SET local_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_path, track_id),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update track {track_id}: {e}")
        return False


def locate_opus_replacements(
    folder_path: str,
    dry_run: bool = True,
) -> LocateResult:
    """Find opus files that can replace existing MP3 track records.

    Searches for .opus files in the specified folder and attempts to match
    them to existing MP3 tracks in the database using tiered matching:

    1. Exact filename stem match
    2. Exact title match (case-insensitive)
    3. Fuzzy title match (TF-IDF, 85% threshold)

    Args:
        folder_path: Path to folder containing opus files
        dry_run: If True, don't actually update database (default: True)

    Returns:
        LocateResult with updated, multiple_matches, and no_match lists
    """
    folder = Path(folder_path).expanduser().resolve()

    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder}")

    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder}")

    logger.info(f"Scanning for opus files in: {folder}")

    # Find all opus files in folder
    opus_files = list(folder.glob("*.opus"))
    logger.info(f"Found {len(opus_files)} opus files")

    if not opus_files:
        return LocateResult(updated=[], multiple_matches=[], no_match=[])

    # Get MP3 tracks for this album
    mp3_tracks = _get_folder_tracks(folder)
    logger.info(f"Found {len(mp3_tracks)} MP3 tracks in database for album '{folder.name}'")

    if not mp3_tracks:
        # All opus files are "no match" since there are no MP3 tracks
        no_match = [
            {
                "opus_path": str(f),
                "opus_stem": f.stem,
                "opus_title": f.stem,
                "reason": "No MP3 tracks in database for this album",
            }
            for f in opus_files
        ]
        return LocateResult(updated=[], multiple_matches=[], no_match=no_match)

    updated = []
    multiple_matches = []
    no_match = []

    for opus_path in opus_files:
        opus_stem = opus_path.stem
        opus_meta = _extract_opus_metadata(opus_path)
        opus_title = opus_meta.get("title", opus_stem)

        result_info = {
            "opus_path": str(opus_path),
            "opus_title": opus_title,
            "opus_stem": opus_stem,
        }

        # Tier 1: Exact filename match
        tier1_matches = _match_tier1_filename(opus_stem, mp3_tracks)

        if len(tier1_matches) == 1:
            match = tier1_matches[0]
            result_info["matched_track_id"] = match["id"]
            result_info["matched_title"] = match.get("title")
            result_info["matched_path"] = match.get("local_path")
            result_info["match_tier"] = 1
            result_info["match_reason"] = "filename_exact"

            if not dry_run:
                if _update_track_path(match["id"], str(opus_path)):
                    result_info["status"] = "updated"
                else:
                    result_info["status"] = "update_failed"
            else:
                result_info["status"] = "dry_run"

            updated.append(result_info)
            continue

        if len(tier1_matches) > 1:
            result_info["matches"] = [
                {"id": m["id"], "title": m.get("title"), "path": m.get("local_path")}
                for m in tier1_matches
            ]
            result_info["match_tier"] = 1
            result_info["match_reason"] = "filename_multiple"
            multiple_matches.append(result_info)
            continue

        # Tier 2: Exact title match
        tier2_matches = _match_tier2_title(opus_title, mp3_tracks)

        if len(tier2_matches) == 1:
            match = tier2_matches[0]
            result_info["matched_track_id"] = match["id"]
            result_info["matched_title"] = match.get("title")
            result_info["matched_path"] = match.get("local_path")
            result_info["match_tier"] = 2
            result_info["match_reason"] = "title_exact"

            if not dry_run:
                if _update_track_path(match["id"], str(opus_path)):
                    result_info["status"] = "updated"
                else:
                    result_info["status"] = "update_failed"
            else:
                result_info["status"] = "dry_run"

            updated.append(result_info)
            continue

        if len(tier2_matches) > 1:
            result_info["matches"] = [
                {"id": m["id"], "title": m.get("title"), "path": m.get("local_path")}
                for m in tier2_matches
            ]
            result_info["match_tier"] = 2
            result_info["match_reason"] = "title_multiple"
            multiple_matches.append(result_info)
            continue

        # Tier 3: Fuzzy title match
        tier3_matches = _match_tier3_fuzzy(opus_title, mp3_tracks)

        if len(tier3_matches) == 1:
            match, score = tier3_matches[0]
            result_info["matched_track_id"] = match["id"]
            result_info["matched_title"] = match.get("title")
            result_info["matched_path"] = match.get("local_path")
            result_info["match_tier"] = 3
            result_info["match_reason"] = "title_fuzzy"
            result_info["match_score"] = round(score, 3)

            if not dry_run:
                if _update_track_path(match["id"], str(opus_path)):
                    result_info["status"] = "updated"
                else:
                    result_info["status"] = "update_failed"
            else:
                result_info["status"] = "dry_run"

            updated.append(result_info)
            continue

        if len(tier3_matches) > 1:
            result_info["matches"] = [
                {"id": m["id"], "title": m.get("title"), "score": round(s, 3)}
                for m, s in tier3_matches
            ]
            result_info["match_tier"] = 3
            result_info["match_reason"] = "title_fuzzy_multiple"
            multiple_matches.append(result_info)
            continue

        # No match found
        result_info["reason"] = "no_match_found"
        no_match.append(result_info)

    return LocateResult(
        updated=updated,
        multiple_matches=multiple_matches,
        no_match=no_match,
    )
