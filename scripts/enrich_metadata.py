#!/usr/bin/env python3
"""
Enrich local track metadata with SoundCloud data.

Usage:
    uv run python scripts/enrich_metadata.py /path/to/track.mp3
    uv run python scripts/enrich_metadata.py /path/to/track.mp3 --dry-run
    uv run python scripts/enrich_metadata.py /path/to/track.mp3 --auto
    uv run python scripts/enrich_metadata.py /path/to/track.mp3 --search
    uv run python scripts/enrich_metadata.py /path/to/track.mp3 --sc-url https://soundcloud.com/artist/track
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from music_minion.core.config import load_config
from music_minion.core.database import get_db_connection, get_track_by_path
from music_minion.domain.library.deduplication import normalize_string
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud import api as sc_api
from music_minion.domain.library.providers.soundcloud import auth as sc_auth
from music_minion.domain.playlists.matching import MatchCandidate, batch_score_candidates


def extract_id_from_url(url: str) -> Optional[str]:
    """Extract SoundCloud track ID from URL.

    Args:
        url: SoundCloud URL (e.g., https://soundcloud.com/artist/track)

    Returns:
        Track ID or None if URL is invalid
    """
    # For now, we'll need to resolve the URL via the API
    # SoundCloud URLs don't contain numeric IDs directly
    # This would require calling /resolve endpoint
    # For this implementation, we'll return None and handle in the main function
    return None


def find_soundcloud_matches_for_local(
    local_track: dict,
    min_confidence: float = 0.6,
    top_n: int = 5,
) -> list[MatchCandidate]:
    """Find SoundCloud tracks matching a local file.

    Args:
        local_track: Dict with 'title', 'artist', 'duration' keys
        min_confidence: Minimum confidence threshold (default: 0.6)
        top_n: Maximum number of matches to return (default: 5)

    Returns:
        List of MatchCandidate objects sorted by confidence
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT soundcloud_id, title, artist, duration
            FROM tracks WHERE soundcloud_id IS NOT NULL
        """
        )
        sc_candidates = [
            (
                row["soundcloud_id"],
                {
                    "title": row["title"],
                    "artist": row["artist"],
                    "duration": row["duration"],
                },
            )
            for row in cursor.fetchall()
        ]

    if not sc_candidates:
        return []

    query_track = {
        "title": local_track.get("title", ""),
        "artist": local_track.get("artist", ""),
        "top_level_artist": local_track.get("artist", ""),
        "duration_ms": int((local_track.get("duration") or 0) * 1000),
    }

    matches = batch_score_candidates(query_track, sc_candidates)
    return [m for m in matches[:top_n] if m.confidence_score >= min_confidence]


def prompt_for_match(matches: list[MatchCandidate]) -> Optional[str]:
    """Simple numbered prompt for user to pick a match.

    Args:
        matches: List of MatchCandidate objects

    Returns:
        Selected soundcloud_id or None if user skips
    """
    print("\nMultiple matches found:")
    for i, m in enumerate(matches[:5], 1):
        print(
            f"  [{i}] {m.soundcloud_artist} - {m.soundcloud_title} ({m.confidence_score:.2f})"
        )
    print("  [s] Skip this track")

    choice = input("\nPick [1-5] or [s]: ").strip().lower()
    if choice == "s":
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx].soundcloud_id
    except ValueError:
        pass
    return None


def link_track_to_soundcloud(local_path: str, soundcloud_id: str) -> bool:
    """Update DB to link local track to its SoundCloud ID.

    Args:
        local_path: Path to local audio file
        soundcloud_id: SoundCloud track ID

    Returns:
        True if linked successfully, False if soundcloud_id already linked elsewhere
    """
    with get_db_connection() as conn:
        # Check if soundcloud_id is already used by another track
        cursor = conn.execute(
            "SELECT local_path FROM tracks WHERE soundcloud_id = ?",
            (soundcloud_id,),
        )
        existing = cursor.fetchone()
        if existing:
            print(
                f"⚠ SoundCloud ID {soundcloud_id} already linked to: {existing['local_path']}"
            )
            return False

        # Link the track
        conn.execute(
            "UPDATE tracks SET soundcloud_id = ? WHERE local_path = ? AND soundcloud_id IS NULL",
            (soundcloud_id, local_path),
        )
        conn.commit()
        return True


def create_provider_state() -> ProviderState:
    """Create initial provider state for SoundCloud API calls.

    Returns:
        ProviderState with loaded config and tokens
    """
    config = load_config()
    sc_config = config.soundcloud

    provider_config = ProviderConfig(
        name="soundcloud",
        enabled=sc_config.enabled,
    )

    # Load tokens from file if they exist
    token_data = None
    try:
        token_data = sc_auth._load_user_tokens()
    except Exception:
        pass

    cache = {
        "config": {
            "client_id": sc_config.client_id,
            "client_secret": sc_config.client_secret,
            "redirect_uri": "http://localhost:8080/callback",
        },
        "token_data": token_data,
    }

    return ProviderState(
        config=provider_config,
        authenticated=token_data is not None,
        cache=cache,
    )


def main() -> int:
    """Main entry point for metadata enrichment script.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        description="Enrich local track metadata with SoundCloud data"
    )
    parser.add_argument("local_path", help="Path to local audio file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, no writes",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip confirmation for high-confidence matches (>0.85)",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Enable SoundCloud API search fallback",
    )
    parser.add_argument(
        "--sc-url",
        metavar="URL",
        help="Bypass lookup, use this SoundCloud URL directly",
    )

    args = parser.parse_args()

    # Validate local path (don't resolve - keep as-is to match DB)
    local_path = Path(args.local_path).expanduser()
    if not local_path.exists():
        print(f"❌ File not found: {local_path}")
        return 1

    # Get track from database
    track = get_track_by_path(str(local_path))
    if not track:
        print(f"❌ Track not in database: {local_path}")
        print("  Tip: Run 'music-minion sync local' first")
        return 1

    soundcloud_id = None

    # Step 0: Check for --sc-url override
    if args.sc_url:
        print(f"⚠ URL-based lookup not yet implemented: {args.sc_url}")
        print("  Tip: Remove --sc-url to use fuzzy matching or API search")
        return 1

    # Step 1: Check existing soundcloud_id in DB
    if track.get("soundcloud_id"):
        soundcloud_id = track["soundcloud_id"]
        print(f"✅ Track already linked to SoundCloud ID: {soundcloud_id}")
        return 0

    # Step 2: Fuzzy match in DB
    print(f"\nSearching for matches for: {track.get('title')} - {track.get('artist')}")
    matches = find_soundcloud_matches_for_local(track)

    if matches:
        if len(matches) == 1 and (args.auto and matches[0].confidence_score > 0.85):
            # Auto-accept high confidence single match
            soundcloud_id = matches[0].soundcloud_id
            print(
                f"✅ Auto-matched (confidence: {matches[0].confidence_score:.2f}): "
                f"{matches[0].soundcloud_artist} - {matches[0].soundcloud_title}"
            )
        else:
            # Prompt user to pick
            soundcloud_id = prompt_for_match(matches)

    # Step 3: SoundCloud API search fallback (only with --search flag)
    if not soundcloud_id and args.search:
        print("\nNo DB matches found, searching SoundCloud API...")
        state = create_provider_state()

        if not state.authenticated:
            print("⚠ Not authenticated with SoundCloud")
            print("  Run 'music-minion' and authenticate to enable API search")
            return 1

        # Build query from track metadata
        query_parts = []
        if track.get("title"):
            query_parts.append(track["title"])
        if track.get("artist"):
            query_parts.append(track["artist"])
        query = " ".join(query_parts)

        if not query:
            # Fallback to filename
            query = local_path.stem

        state, search_results = sc_api.search(state, query)

        if search_results:
            # Convert to MatchCandidate format for consistent prompt
            search_matches = []
            for sc_id, metadata in search_results[:5]:
                # Create a dummy MatchCandidate for display
                # We can't compute confidence without batch scoring
                search_matches.append(
                    MatchCandidate(
                        soundcloud_id=sc_id,
                        soundcloud_title=metadata.get("title", ""),
                        soundcloud_artist=metadata.get("artist", ""),
                        soundcloud_duration=metadata.get("duration", 0.0),
                        title_similarity=0.0,
                        artist_similarity=0.0,
                        duration_match=0.0,
                        confidence_score=0.0,  # Unknown from search
                    )
                )

            if search_matches:
                print("\nAPI search results:")
                for i, m in enumerate(search_matches, 1):
                    duration_str = f"{int(m.soundcloud_duration)}s" if m.soundcloud_duration else "?"
                    print(f"  [{i}] {m.soundcloud_artist} - {m.soundcloud_title} ({duration_str})")
                print("  [s] Skip this track")

                choice = input("\nPick [1-5] or [s]: ").strip().lower()
                if choice != "s":
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(search_matches):
                            soundcloud_id = search_matches[idx].soundcloud_id
                    except ValueError:
                        pass

    # Handle no match found
    if not soundcloud_id:
        print(f"\n⚠ No SoundCloud match found for: {local_path}")
        if not args.search:
            print("  Tip: Try --search to enable API search fallback")
        return 0  # Not an error, just no match

    # Link track to soundcloud_id
    if args.dry_run:
        print(f"\n[DRY RUN] Would link track to SoundCloud ID: {soundcloud_id}")
    else:
        if link_track_to_soundcloud(str(local_path), soundcloud_id):
            print(f"\n✅ Linked track to SoundCloud ID: {soundcloud_id}")
        else:
            print(
                "\n⚠ Track not linked (SoundCloud ID already in use by another track)"
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
