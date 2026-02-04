# YouTube Integration for Radio

## Overview

Add YouTube video downloads to Music Minion's radio system. Downloads are stored as local files (mp4/webm with video+audio) for both radio playback and future video page. No streaming logic needed - downloaded files integrate seamlessly with existing radio infrastructure.

### Key Design Decisions

1. **Download approach**: Video+audio to `~/music/youtube/{snake_case_title}.mp4`
2. **Radio integration**: Set `local_path` + `youtube_id` → scheduler returns path → Liquidsoap plays
3. **Two import modes**:
   - Single video: User provides URL + optional metadata (falls back to YouTube metadata)
   - Bulk playlist: Playlist ID → album=playlist title, title=video title, artist=uploader
4. **Async Web imports**: Background tasks with polling to avoid gateway timeouts
5. **Pre-download duplicate check**: Batch query existing IDs before downloading (saves bandwidth)
6. **Atomic file handling**: Download to temp → DB insert → move atomically
7. **Functional architecture**: Pure functions, no classes (except dataclasses), follows existing provider pattern

## Task Sequence

1. [01-add-yt-dlp-dependency.md](./01-add-yt-dlp-dependency.md) - Add yt-dlp to project dependencies
2. [02-create-youtube-download-module.md](./02-create-youtube-download-module.md) - Core download infrastructure with yt-dlp integration
3. [03-create-database-helpers.md](./03-create-database-helpers.md) - Database functions for YouTube track management
4. [04-create-import-handlers.md](./04-create-import-handlers.md) - Import orchestration for single videos and playlists
5. [05-create-youtube-provider-interface.md](./05-create-youtube-provider-interface.md) - Provider interface following existing patterns
6. [06-create-cli-commands.md](./06-create-cli-commands.md) - CLI commands for YouTube imports
7. [07-create-web-api-endpoints.md](./07-create-web-api-endpoints.md) - FastAPI endpoints for web UI
8. [08-create-frontend-ui.md](./08-create-frontend-ui.md) - React components for import forms
9. [09-integration-testing.md](./09-integration-testing.md) - End-to-end testing and verification

## Success Criteria

### End-to-End Testing

**CLI Single Import**:
```bash
uv run music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --artist "Rick Astley" --title "Never Gonna Give You Up" --album "Whenever You Need Somebody"
```
- ✓ File created in `~/music/youtube/never_gonna_give_you_up.mp4`
- ✓ Database track with `youtube_id`, `local_path`, `source='youtube'`

**CLI Bulk Import**:
```bash
uv run music-minion youtube add-playlist "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```
- ✓ All videos downloaded
- ✓ Album = playlist title, artist empty

**Web UI Import**:
- ✓ Form accepts URL and metadata
- ✓ Success message displays track info
- ✓ Track appears in library with YouTube badge

**Radio Playback**:
- ✓ Liquidsoap requests track via `/next-track`
- ✓ Endpoint returns local file path
- ✓ Track plays successfully
- ✓ `radio_history` shows source='youtube'

**Error Handling**:
- ✓ Duplicate videos detected before download
- ✓ Age-restricted videos show clear error
- ✓ Invalid URLs show parse error with guidance

## Execution Instructions

1. **Execute tasks in numerical order** (01 → 09)
2. **Each task file contains**:
   - Files to modify/create
   - Implementation details
   - Acceptance criteria
   - Dependencies
3. **Verify acceptance criteria** before moving to next task
4. **Run integration tests** (task 09) at the end

## Dependencies

### External Dependencies
- **yt-dlp** >= 2024.1.0 (Python package)
- **ffmpeg** (system package - must be installed)
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: Download from ffmpeg.org

### Database Schema
No schema changes needed - tracks table already has:
- `youtube_id TEXT` (with unique index)
- `local_path TEXT`
- `youtube_synced_at TIMESTAMP`
- `source TEXT`

### Existing Code
Radio integration requires **no changes**:
- `scheduler.py` already returns `local_path` for any track
- `timeline.py` is source-agnostic
- History tracking already supports `source_type`

## Key Architectural Points

1. **Functional design**: All functions pure, state passed explicitly via parameters
2. **No streaming**: Downloads complete before import, simplifies everything
3. **Radio seamless**: Downloaded files are just local files to the scheduler
4. **Provider pattern**: Follows existing SoundCloud/Spotify structure
5. **Duplicate detection**: Batch check `youtube_id` before download (saves bandwidth)
6. **Atomic operations**: Download to temp → DB insert → move file (no orphans)
7. **File organization**: Human-readable snake_case filenames in dedicated `youtube/` folder
8. **Metadata flexibility**: Optional user metadata, falls back to YouTube title/uploader
9. **Custom exceptions**: Domain-specific exception hierarchy for proper error handling
10. **Async web imports**: Background tasks with polling to avoid timeouts

## Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Download vs. Stream | Simpler, works offline, enables video page | Disk space (~50-400MB per track for hour-long videos) |
| Video+audio vs. audio-only | Supports future video page, minimal size difference | Slightly larger files, verify Liquidsoap compatibility |
| Optional metadata with fallback | Convenience (just paste URL) while allowing customization | May need manual cleanup of auto-detected metadata |
| Background tasks + polling | Avoids gateway timeouts, better UX | More complex than synchronous, requires job storage |
| Pre-download duplicate check | Saves bandwidth on re-imports | Extra DB query per playlist import |

## Known Limitations

- **No authentication**: Age-restricted, private, and premium content cannot be downloaded
- **No real-time progress**: Polling only shows status, not download percentage (would need WebSocket)
- **Single-instance job storage**: In-memory job dict doesn't persist across restarts

## Future Enhancements (Not in This Plan)

- Video page for playback with synchronized video
- YouTube search within Music Minion
- Auto-update for playlist changes
- WebSocket for real-time download progress
- Optional cookies file for authenticated downloads
