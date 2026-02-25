---
task: 05-preview-and-confirm
status: done
depends: [04-gpt4o-mini-parsing]
files:
  - path: scripts/enrich_metadata.py
    action: modify
---

# Preview and Confirmation Flow

## Context
Display a side-by-side comparison of current file metadata vs AI-parsed metadata. Prompt user for confirmation before writing changes.

## Files to Modify/Create
- scripts/enrich_metadata.py (modify)

## Implementation Details

### Read Current File Metadata
```python
from music_minion.domain.library.metadata import extract_track_metadata

current = extract_track_metadata(local_path)
```

### Format Artist String
```python
def format_artist_string(parsed: dict) -> str:
    """Format artists as: 'Artist1 x Artist2 ft. Featured1, Featured2'

    Uses 'x' for collaborations (not '&' which appears in artist names like 'Chase & Status').
    Remix artist is NOT included here - remix attribution should be in the title.
    """
    parts = []

    # Original artists joined with ' x '
    if parsed.get("original_artists"):
        parts.append(" x ".join(parsed["original_artists"]))

    # Featured artists with 'ft.' prefix
    if parsed.get("featured_artists"):
        parts.append("ft. " + ", ".join(parsed["featured_artists"]))

    return " ".join(parts)
```

Note: Remix artist (e.g., "Someone") should already be in the title as "(Someone Remix)".
The AI prompt ensures remix attribution stays in the title field.

### Preview Display
```python
def preview_changes(current: dict, parsed: dict, usage: dict, match_confidence: float) -> None:
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
```

### Validate AI Output
Before applying, check that AI output is sane:
```python
def validate_parsed_output(parsed: dict) -> tuple[bool, str]:
    """Validate AI output before applying. Returns (valid, error_message)."""
    if not parsed.get("title"):
        return False, "Missing title"
    if not parsed.get("original_artists"):
        return False, "Missing original_artists"
    if not isinstance(parsed.get("original_artists"), list):
        return False, "original_artists must be a list"
    return True, ""
```

### Confirmation Prompt
```python
def confirm_apply() -> bool:
    """Prompt user to confirm changes."""
    response = input("\nApply changes? [y/N]: ").strip().lower()
    return response in ("y", "yes")
```

### Auto Mode
With `--auto` flag, skip confirmation for high-confidence matches:
```python
def should_auto_apply(match_confidence: float, parsed: dict) -> bool:
    """Check if we can auto-apply without confirmation."""
    if match_confidence < 0.85:
        return False
    valid, _ = validate_parsed_output(parsed)
    return valid
```

### Dry Run Mode
If `--dry-run` flag is set, skip confirmation and don't write:
```python
if args.dry_run:
    print("\n[Dry run - no changes applied]")
    return

# Main flow
valid, error = validate_parsed_output(parsed)
if not valid:
    print(f"\n⚠ Invalid AI output: {error}")
    print("[Skipping this track]")
    return

if args.auto and should_auto_apply(match_confidence, parsed):
    print("\n[Auto-applying: high confidence match]")
    apply = True
else:
    apply = confirm_apply()
```

## Verification
```bash
# Preview mode
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --dry-run

# Interactive mode (will prompt for confirmation)
uv run python scripts/enrich_metadata.py /path/to/track.mp3
```

Expected: Clear side-by-side comparison displayed, confirmation prompt works.
