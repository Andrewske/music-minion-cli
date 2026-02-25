# SoundCloud Metadata Enrichment Script

## Overview
A single-track script that enriches local audio file metadata using SoundCloud data and GPT-4o-mini parsing. Designed for new tracks that need metadata cleanup before being added to the curated library.

**Workflow:**
1. Input local track path
2. Find matching SoundCloud track (via DB lookup, fuzzy match, or API search)
3. Fetch full track details from SoundCloud API
4. Send to GPT-4o-mini for intelligent parsing
5. Preview changes, confirm, write to file metadata
6. Log request/response/tokens for cost tracking

## Task Sequence
1. [01-setup-dependencies.md](./01-setup-dependencies.md) - Verify OpenAI SDK (already installed)
2. [02-soundcloud-lookup-cascade.md](./02-soundcloud-lookup-cascade.md) - Core lookup logic (DB → fuzzy → API)
3. [03-fetch-soundcloud-details.md](./03-fetch-soundcloud-details.md) - Fetch full track from SC API
4. [04-gpt4o-mini-parsing.md](./04-gpt4o-mini-parsing.md) - AI parsing with structured output
5. [05-preview-and-confirm.md](./05-preview-and-confirm.md) - Side-by-side preview and confirmation
6. [06-write-metadata-to-file.md](./06-write-metadata-to-file.md) - Atomic write to ID3/Vorbis/MP4
7. [07-logging.md](./07-logging.md) - JSONL logging for cost tracking

## CLI Options
```bash
uv run python scripts/enrich_metadata.py /path/to/track.mp3 [options]

Options:
  --dry-run    Preview only, no writes
  --auto       Skip confirmation for high-confidence matches (>0.85)
  --search     Enable SoundCloud API search fallback (off by default)
  --sc-url URL Bypass lookup, use this SoundCloud URL directly
```

## Success Criteria
End-to-end test:
```bash
# Run on a track with messy metadata
uv run python scripts/enrich_metadata.py /path/to/messy_track.mp3

# Expected:
# 1. SoundCloud track found (via DB or fuzzy match)
# 2. Match confidence score displayed
# 3. Clean metadata preview displayed
# 4. Confirmation prompt works (or auto-apply with --auto)
# 5. File metadata updated correctly
# 6. soundcloud_id saved to DB for future lookups
# 7. Log entry written to logs/metadata_enrichment.jsonl
# 8. Cost ~$0.0001-0.0002 per track

# Test with manual URL override
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --sc-url https://soundcloud.com/artist/track

# Test with API search fallback
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --search
```

Verify across formats:
- MP3 (ID3 tags)
- Opus (Vorbis comments)
- FLAC (Vorbis comments)

## Dependencies
- `openai` SDK (already in pyproject.toml)
- `OPENAI_API_KEY` in `.env` (user-provided)
- Existing: `mutagen`, `sklearn`, `requests`, `rapidfuzz`

## Key Files
| File | Purpose |
|------|---------|
| `scripts/enrich_metadata.py` | Main script (created) |
| `logs/metadata_enrichment.jsonl` | AI request/response log (created) |

## Existing Code Reused
- `core/database.py` - DB queries, track updates
- `domain/playlists/matching.py` - Ensemble matching (TF-IDF + RapidFuzz + Jaro-Winkler)
- `domain/library/providers/soundcloud/api.py` - SC API search
- `domain/library/providers/soundcloud/auth.py` - Token management
- `domain/library/metadata.py` - Metadata reading/writing
