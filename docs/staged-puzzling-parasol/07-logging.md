---
task: 07-logging
status: pending
depends: [06-write-metadata-to-file]
files:
  - path: scripts/enrich_metadata.py
    action: modify
---

# Request/Response Logging

## Context
Log every AI request and response to a JSONL file for cost tracking, debugging, and review of AI behavior.

## Files to Modify/Create
- scripts/enrich_metadata.py (modify)

## Implementation Details

### Log File Path
```python
LOG_FILE = Path(__file__).parent.parent / "logs" / "metadata_enrichment.jsonl"
```

Create `logs/` directory if it doesn't exist.

### Log Entry Structure
```python
import json
from datetime import datetime, timezone
from pathlib import Path

def log_enrichment(
    local_path: str,
    soundcloud_id: str,
    input_data: dict,
    response: dict,
    usage: dict,
    applied: bool,
) -> None:
    """Append enrichment record to JSONL log."""
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
```

### When to Log
Log after every AI call, regardless of whether changes were applied:
```python
# After AI parsing
parsed, usage = parse_with_ai(sc_data)

# After user decision
applied = False
if not args.dry_run and confirm_apply():
    write_metadata_atomic(local_path, prepare_metadata(parsed))
    applied = True

# Always log
log_enrichment(
    local_path=str(local_path),
    soundcloud_id=soundcloud_id,
    input_data=sc_data,
    response=parsed,
    usage=usage,
    applied=applied,
)
```

### Example Log Entry
```json
{
  "timestamp": "2024-01-15T10:30:00+00:00",
  "local_path": "/home/kevin/music/track.mp3",
  "soundcloud_id": "123456789",
  "input_data": {
    "title": "Artist - Track Name [Free DL]",
    "username": "SomeLabel",
    "metadata_artist": "Artist",
    "description": "...",
    "genre": "house",
    "label_name": "Some Label",
    "release_year": 2024,
    "tag_list": "house deep",
    "created_at": "2024-01-10T..."
  },
  "prompt_tokens": 342,
  "completion_tokens": 87,
  "response": {
    "title": "Track Name",
    "original_artists": ["Artist"],
    "featured_artists": [],
    "remix_artist": null,
    "genre": "House",
    "year": 2024,
    "label": "Some Label"
  },
  "applied": true
}
```

## Verification
```bash
# Run enrichment
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --dry-run

# Check log file
cat logs/metadata_enrichment.jsonl | jq .

# Verify token counts
cat logs/metadata_enrichment.jsonl | jq '{tokens: .prompt_tokens + .completion_tokens}'
```

Expected: Log file created with proper JSON entries, token counts visible.
