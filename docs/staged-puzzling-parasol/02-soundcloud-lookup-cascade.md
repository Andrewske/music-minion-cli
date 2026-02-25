---
task: 02-soundcloud-lookup-cascade
status: done
depends: [01-setup-dependencies]
files:
  - path: scripts/enrich_metadata.py
    action: create
---

# SoundCloud Lookup Cascade

## Context
Implement the core lookup logic that finds the matching SoundCloud track for a local file. This is the foundation of the enrichment script - we need to reliably find the SC track before we can extract metadata from it.

## Files to Modify/Create
- scripts/enrich_metadata.py (create - partial, will be extended in later tasks)

## Implementation Details

### CLI Entry Point
```python
# Usage: uv run python scripts/enrich_metadata.py /path/to/track.mp3
# Options:
#   --dry-run    Preview only, no writes
#   --auto       Skip confirmation for high-confidence matches (>0.85)
#   --search     Enable SoundCloud API search fallback (off by default)
#   --sc-url URL Bypass lookup, use this SoundCloud URL directly
```

Use argparse with:
- Positional arg: `local_path` (required)
- Flag: `--dry-run` (preview only, no writes)
- Flag: `--auto` (skip confirmation when confidence > 0.85 AND AI output validates)
- Flag: `--search` (enable API search fallback, off by default)
- Option: `--sc-url URL` (bypass lookup, extract track ID from URL)

### Lookup Cascade (3 steps)

**Step 1: Check existing soundcloud_id in DB**
```python
from music_minion.core.database import get_track_by_path

track = get_track_by_path(local_path)
if track and track.get("soundcloud_id"):
    return track["soundcloud_id"]
```

**Step 2: Fuzzy match in DB**
- Load all SoundCloud tracks from DB (`WHERE soundcloud_id IS NOT NULL`)
- Use `batch_score_candidates()` from `domain/playlists/matching.py` for ensemble matching (TF-IDF + RapidFuzz + Jaro-Winkler)
- Query with local track's title/artist/duration
- Threshold: 0.6 minimum confidence (matching.py default)

```python
def find_soundcloud_matches_for_local(
    local_track: dict,  # {title, artist, duration}
    min_confidence: float = 0.6,
    top_n: int = 5,
) -> list[MatchCandidate]:
    """Find SoundCloud tracks matching a local file."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT soundcloud_id, title, artist, duration
            FROM tracks WHERE soundcloud_id IS NOT NULL
        """)
        sc_candidates = [
            (row["soundcloud_id"], {"title": row["title"], "artist": row["artist"], "duration": row["duration"]})
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
```

- Present top matches, let user pick or continue to API search

**Step 0: Check for --sc-url override**
```python
if args.sc_url:
    # Extract track ID from URL (e.g., soundcloud.com/artist/track -> fetch by URL)
    # Bypass all lookup logic, go directly to fetch
    soundcloud_id = extract_id_from_url(args.sc_url)
```

**Step 3: SoundCloud API search fallback (only with --search flag)**
- Only runs if `--search` flag is provided
- Build query from filename or existing title/artist
- Use `search()` from `domain/library/providers/soundcloud/api.py`
- Present top 3-5 results, let user pick or skip

**Handling multiple matches (Step 2 or 3):**
```python
def prompt_for_match(matches: list[MatchCandidate]) -> str | None:
    """Simple numbered prompt for user to pick a match."""
    print("\nMultiple matches found:")
    for i, m in enumerate(matches[:5], 1):
        print(f"  [{i}] {m.soundcloud_artist} - {m.soundcloud_title} ({m.confidence_score:.2f})")
    print("  [s] Skip this track")

    choice = input("\nPick [1-5] or [s]: ").strip().lower()
    if choice == 's':
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx].soundcloud_id
    except ValueError:
        pass
    return None
```

**Handling no match found:**
```python
if not soundcloud_id:
    print(f"⚠ No SoundCloud match found for: {local_path}")
    if not args.search:
        print("  Tip: Try --search to enable API search fallback")
    sys.exit(0)  # Not an error, just no match
```

### Key Imports
```python
from music_minion.core.database import get_track_by_path, get_db_connection
from music_minion.domain.library.deduplication import normalize_string
from music_minion.domain.playlists.matching import batch_score_candidates, MatchCandidate
from music_minion.domain.library.providers.soundcloud.api import search
from music_minion.domain.library.providers.soundcloud import auth
```

**Update DB with soundcloud_id link:**
After finding a match, if the local track didn't already have a soundcloud_id, save the association:
```python
def link_track_to_soundcloud(local_path: str, soundcloud_id: str) -> None:
    """Update DB to link local track to its SoundCloud ID."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE tracks SET soundcloud_id = ? WHERE local_path = ? AND soundcloud_id IS NULL",
            (soundcloud_id, local_path)
        )
        conn.commit()
```
This makes future lookups instant (Step 1 will find it).

## Verification
```bash
# Test with a track that has soundcloud_id
uv run python scripts/enrich_metadata.py /path/to/known_track.mp3

# Test with a track without soundcloud_id (triggers fuzzy match)
uv run python scripts/enrich_metadata.py /path/to/local_only_track.mp3

# Test with --sc-url override
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --sc-url https://soundcloud.com/artist/track

# Test with --search fallback
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --search
```

Expected: Script finds and displays the matched SoundCloud track ID, links it in DB if new.
