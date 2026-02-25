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
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI

from music_minion.core.config import load_config
from music_minion.core.database import get_db_connection, get_track_by_path
from music_minion.domain.library.metadata import extract_track_metadata, write_metadata_to_file
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud import api as sc_api
from music_minion.domain.library.providers.soundcloud import auth as sc_auth
from music_minion.domain.playlists.matching import MatchCandidate, batch_score_candidates

# Load environment variables and initialize OpenAI client
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LOG_FILE = Path(__file__).parent.parent / "logs" / "metadata_enrichment.jsonl"

SYSTEM_PROMPT = """You are a music metadata parser. Parse SoundCloud track data into clean, structured metadata.

Rules:
- If username matches label_name or common label patterns (Records, Music, Recordings), don't include as artist
- Extract featured artists from "feat.", "ft.", "featuring", "with" patterns in title
- Identify remix artist from "(X Remix)", "(X Edit)", "(X Bootleg)", "[X Mix]" patterns
- Clean title: remove artist prefix, [Free DL], promo text, but keep remix attribution
- Genre: use the genre from SoundCloud as-is (preserve original)
- Year: prefer release_year, fall back to created_at year"""


def get_valid_access_token() -> Optional[str]:
    """Load token, refresh if expired, return access_token or None.

    Returns:
        Valid access token or None if not authenticated
    """
    token_data = sc_auth._load_user_tokens()
    if not token_data:
        print("❌ Not authenticated. Run: library auth soundcloud")
        return None

    if sc_auth.is_token_expired(token_data):
        refreshed = sc_auth.refresh_token(token_data)
        if not refreshed:
            print("❌ Token expired. Run: library auth soundcloud")
            return None
        token_data = refreshed

    return token_data["access_token"]


def fetch_soundcloud_track(soundcloud_id: str, access_token: str) -> dict:
    """Fetch full track details from SoundCloud API.

    Args:
        soundcloud_id: SoundCloud track ID
        access_token: Valid OAuth access token

    Returns:
        Track data dictionary with extracted fields

    Raises:
        requests.HTTPError: If API request fails
    """
    url = f"https://api.soundcloud.com/tracks/{soundcloud_id}"
    headers = {"Authorization": f"OAuth {access_token}"}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    track = response.json()

    # Extract key fields for AI parsing
    return {
        "title": track.get("title"),
        "username": track.get("user", {}).get("username"),
        "metadata_artist": track.get("metadata_artist"),
        "description": track.get("description"),
        "genre": track.get("genre"),
        "label_name": track.get("label_name"),
        "release_year": track.get("release_year"),
        "tag_list": track.get("tag_list"),
        "created_at": track.get("created_at"),
    }


def resolve_soundcloud_url(url: str, access_token: str) -> Optional[str]:
    """Resolve SoundCloud URL to track ID using /resolve endpoint.

    Args:
        url: SoundCloud URL (e.g., https://soundcloud.com/artist/track)
        access_token: Valid OAuth access token

    Returns:
        Track ID or None if URL is invalid or not a track
    """
    resolve_url = "https://api.soundcloud.com/resolve"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"url": url}

    try:
        response = requests.get(resolve_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Ensure it's a track (not a playlist, user, etc.)
        if data.get("kind") != "track":
            print(f"⚠ URL is not a track (got: {data.get('kind')})")
            return None

        return str(data.get("id"))
    except requests.HTTPError as e:
        print(f"❌ Failed to resolve URL: {e}")
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
    except (OSError, ValueError):
        # File missing or invalid JSON - not authenticated
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


def build_user_prompt(sc_data: dict) -> str:
    """Build user prompt for AI parsing from SoundCloud data.

    Args:
        sc_data: Dictionary containing SoundCloud track fields

    Returns:
        Formatted prompt string
    """
    # Safely extract fields with fallbacks
    description = sc_data.get('description') or ''
    description_preview = description[:500] if description else '(none)'

    return f"""Parse this SoundCloud track:

- Title: {sc_data.get('title') or '(unknown)'}
- Username (uploader): {sc_data.get('username') or '(unknown)'}
- Metadata Artist: {sc_data.get('metadata_artist') or '(none)'}
- Description: {description_preview}
- Genre: {sc_data.get('genre') or '(none)'}
- Label: {sc_data.get('label_name') or '(none)'}
- Release Year: {sc_data.get('release_year') or '(none)'}
- Tags: {sc_data.get('tag_list') or '(none)'}
- Created: {sc_data.get('created_at') or '(unknown)'}

Return JSON with exactly these fields:
{{"title": "...", "original_artists": [...], "featured_artists": [...], "remix_artist": "..." or null, "genre": "...", "year": ... or null}}"""


def log_enrichment(
    local_path: str,
    soundcloud_id: str,
    input_data: dict,
    response: dict,
    usage: dict,
    applied: bool,
) -> None:
    """Append enrichment record to JSONL log.

    Args:
        local_path: Path to local audio file
        soundcloud_id: SoundCloud track ID
        input_data: Input data sent to AI (SoundCloud track details)
        response: Parsed response from AI
        usage: Token usage statistics
        applied: Whether metadata was written to file
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_path": local_path,
        "soundcloud_id": soundcloud_id,
        "input_data": input_data,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "response": response,
        "applied": applied,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def parse_with_ai(sc_data: dict) -> tuple[dict, dict]:
    """Parse SoundCloud data with GPT-4o-mini.

    Args:
        sc_data: Dictionary containing SoundCloud track fields

    Returns:
        Tuple of (parsed_result, usage_stats)
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sc_data)},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,  # Low temp for consistent parsing
    )

    result = json.loads(response.choices[0].message.content)
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return result, usage


def format_artist_string(parsed: dict) -> str:
    """Format artists as: 'Artist1 x Artist2 ft. Featured1, Featured2'

    Uses 'x' for collaborations (not '&' which appears in artist names like 'Chase & Status').
    Remix artist is NOT included here - remix attribution should be in the title.

    Args:
        parsed: Parsed metadata dictionary

    Returns:
        Formatted artist string
    """
    parts = []

    # Original artists joined with ' x '
    if parsed.get("original_artists"):
        parts.append(" x ".join(parsed["original_artists"]))

    # Featured artists with 'ft.' prefix
    if parsed.get("featured_artists"):
        parts.append("ft. " + ", ".join(parsed["featured_artists"]))

    return " ".join(parts)


def preview_changes(current: dict, parsed: dict, usage: dict, match_confidence: float) -> None:
    """Display side-by-side comparison of current vs parsed metadata.

    Args:
        current: Current file metadata (Track object as dict)
        parsed: AI-parsed metadata
        usage: Token usage statistics
        match_confidence: Confidence score for SoundCloud match
    """
    print("\n" + "=" * 60)
    print(f"MATCH CONFIDENCE: {match_confidence:.2f}")
    print("=" * 60)

    print("\nCURRENT FILE METADATA:")
    print(f"  Title:  {current.get('title', '(none)')}")
    print(f"  Artist: {current.get('artist', '(none)')}")
    print(f"  Genre:  {current.get('genre', '(none)')}")
    print(f"  Year:   {current.get('year', '(none)')}")

    print("\nPARSED FROM SOUNDCLOUD:")
    print(f"  Title:  {parsed['title']}")
    print(f"  Artist: {format_artist_string(parsed)}")
    print(f"  Genre:  {parsed.get('genre', '(none)')}")
    print(f"  Year:   {parsed.get('year', '(none)')}")

    print(f"\n[Tokens: {usage['prompt_tokens']} in / {usage['completion_tokens']} out]")
    print("=" * 60)


def validate_parsed_output(parsed: dict) -> tuple[bool, str]:
    """Validate AI output before applying. Returns (valid, error_message).

    Args:
        parsed: AI-parsed metadata dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not parsed.get("title"):
        return False, "Missing title"
    if not parsed.get("original_artists"):
        return False, "Missing original_artists"
    if not isinstance(parsed.get("original_artists"), list):
        return False, "original_artists must be a list"
    return True, ""


def confirm_apply() -> bool:
    """Prompt user to confirm changes.

    Returns:
        True if user confirms, False otherwise
    """
    response = input("\nApply changes? [y/N]: ").strip().lower()
    return response in ("y", "yes")


def should_auto_apply(match_confidence: float, parsed: dict) -> bool:
    """Check if we can auto-apply without confirmation.

    Args:
        match_confidence: Confidence score for SoundCloud match
        parsed: AI-parsed metadata dictionary

    Returns:
        True if auto-apply is safe, False otherwise
    """
    if match_confidence < 0.85:
        return False
    valid, _ = validate_parsed_output(parsed)
    return valid


def prepare_metadata(parsed: dict) -> dict:
    """Convert AI output to display-ready metadata dict.

    Args:
        parsed: AI-parsed metadata dictionary

    Returns:
        Display-ready metadata dictionary
    """
    return {
        "title": parsed["title"],
        "artist": format_artist_string(parsed),
        "genre": parsed.get("genre"),
        "year": parsed.get("year"),
    }


def apply_enrichment(local_path: str, parsed: dict) -> bool:
    """Write AI-parsed metadata to file.

    Args:
        local_path: Path to local audio file
        parsed: AI-parsed metadata dictionary

    Returns:
        True if successful, False otherwise
    """
    return write_metadata_to_file(
        local_path=local_path,
        title=parsed["title"],
        artist=format_artist_string(parsed),
        genre=parsed.get("genre"),
        year=parsed.get("year"),
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

    # Validate OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set. Add it to your .env file.")
        return 1

    # Validate access token at script start
    access_token = get_valid_access_token()
    if not access_token:
        return 1

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
        print(f"🔗 Resolving SoundCloud URL: {args.sc_url}")
        soundcloud_id = resolve_soundcloud_url(args.sc_url, access_token)
        if not soundcloud_id:
            return 1
        print(f"✅ Resolved to SoundCloud ID: {soundcloud_id}")
        # Skip lookup, go directly to fetch
        matches = []  # No matches for confidence tracking

    # Step 1: Check existing soundcloud_id in DB
    elif track.get("soundcloud_id"):
        soundcloud_id = track["soundcloud_id"]
        print(f"✅ Track already linked to SoundCloud ID: {soundcloud_id}")
        matches = []  # No matches for confidence tracking

    else:
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

    # Fetch full SoundCloud track details
    print(f"\n🔍 Fetching SoundCloud track details for ID: {soundcloud_id}")
    try:
        track_details = fetch_soundcloud_track(soundcloud_id, access_token)
        print("\n📋 SoundCloud Track Details:")
        print(f"  Title: {track_details.get('title')}")
        print(f"  Username: {track_details.get('username')}")
        print(f"  Metadata Artist: {track_details.get('metadata_artist')}")
        print(f"  Genre: {track_details.get('genre')}")
        print(f"  Label: {track_details.get('label_name')}")
        print(f"  Release Year: {track_details.get('release_year')}")
        print(f"  Tags: {track_details.get('tag_list')}")
        print(f"  Created At: {track_details.get('created_at')}")
        if track_details.get('description'):
            desc = track_details['description']
            # Truncate long descriptions for display
            if len(desc) > 200:
                desc = desc[:200] + "..."
            print(f"  Description: {desc}")
    except requests.HTTPError as e:
        print(f"❌ Failed to fetch SoundCloud track details: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error fetching track details: {e}")
        return 1

    # Parse metadata with AI
    print("\n🤖 Parsing metadata with GPT-4o-mini...")
    try:
        parsed_metadata, usage_stats = parse_with_ai(track_details)
    except Exception as e:
        print(f"❌ Failed to parse metadata with AI: {e}")
        return 1

    # Read current file metadata
    current_metadata = extract_track_metadata(str(local_path))
    current_dict = {
        "title": current_metadata.title,
        "artist": current_metadata.artist,
        "genre": current_metadata.genre,
        "year": current_metadata.year,
    }

    # Calculate match confidence (use first match confidence if available)
    match_confidence = matches[0].confidence_score if matches else 0.0

    # Display preview
    preview_changes(current_dict, parsed_metadata, usage_stats, match_confidence)

    # Validate parsed output
    valid, error = validate_parsed_output(parsed_metadata)
    if not valid:
        print(f"\n⚠ Invalid AI output: {error}")
        print("[Skipping this track]")
        # Log even if validation failed
        log_enrichment(
            local_path=str(local_path),
            soundcloud_id=soundcloud_id,
            input_data=track_details,
            response=parsed_metadata,
            usage=usage_stats,
            applied=False,
        )
        return 1

    # Track whether metadata was applied
    applied = False

    # Dry run mode: exit without writing
    if args.dry_run:
        print("\n[Dry run - no changes applied]")
        log_enrichment(
            local_path=str(local_path),
            soundcloud_id=soundcloud_id,
            input_data=track_details,
            response=parsed_metadata,
            usage=usage_stats,
            applied=False,
        )
        return 0

    # Determine whether to apply changes
    if args.auto and should_auto_apply(match_confidence, parsed_metadata):
        print("\n[Auto-applying: high confidence match]")
        apply = True
    else:
        apply = confirm_apply()

    if not apply:
        print("\n[Skipped by user]")
        log_enrichment(
            local_path=str(local_path),
            soundcloud_id=soundcloud_id,
            input_data=track_details,
            response=parsed_metadata,
            usage=usage_stats,
            applied=False,
        )
        return 0

    # Apply metadata enrichment to file
    if apply_enrichment(str(local_path), parsed_metadata):
        print(f"\n✅ Metadata written to file: {local_path}")
        applied = True
    else:
        print(f"\n❌ Failed to write metadata to file: {local_path}")
        log_enrichment(
            local_path=str(local_path),
            soundcloud_id=soundcloud_id,
            input_data=track_details,
            response=parsed_metadata,
            usage=usage_stats,
            applied=False,
        )
        return 1

    # Link track to soundcloud_id
    if link_track_to_soundcloud(str(local_path), soundcloud_id):
        print(f"✅ Linked track to SoundCloud ID: {soundcloud_id}")
    else:
        print(
            "\n⚠ Track not linked (SoundCloud ID already in use by another track)"
        )
        log_enrichment(
            local_path=str(local_path),
            soundcloud_id=soundcloud_id,
            input_data=track_details,
            response=parsed_metadata,
            usage=usage_stats,
            applied=applied,
        )
        return 0  # Enrichment succeeded, linking is secondary

    # Log successful enrichment
    log_enrichment(
        local_path=str(local_path),
        soundcloud_id=soundcloud_id,
        input_data=track_details,
        response=parsed_metadata,
        usage=usage_stats,
        applied=applied,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
