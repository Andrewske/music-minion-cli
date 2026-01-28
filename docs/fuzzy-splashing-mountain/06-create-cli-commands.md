# Create CLI Commands for YouTube Import

## Files to Modify
- `src/music_minion/commands/library.py` (modify)
- `src/music_minion/commands/__init__.py` (modify)

## Implementation Details

Add CLI command handlers for YouTube video and playlist imports.

### Commands to Add in `library.py`

#### `handle_youtube_add(ctx: AppContext, args: list[str]) -> tuple[AppContext, Any]`

**Usage**: `youtube add <url> [--artist <name>] [--title <name>] [--album <name>]`

**Implementation**:
1. Parse arguments using argparse (or match existing command parsing pattern):
   ```python
   import argparse
   parser = argparse.ArgumentParser(prog="youtube add")
   parser.add_argument("url", help="YouTube video URL")
   parser.add_argument("--artist", help="Artist name (default: video uploader)")
   parser.add_argument("--title", help="Track title (default: video title)")
   parser.add_argument("--album", help="Album name (default: empty)")
   parsed = parser.parse_args(args)
   ```
2. **Metadata is optional** - falls back to YouTube metadata if not provided
3. Import using `youtube.import_single_video(url, artist, title, album)`
4. Log success: `log(f"✓ Imported: {track.artist} - {track.title}", level="info")`
5. Log file location: `log(f"  File: {track.local_path}", level="info")`
6. Log track ID: `log(f"  Track ID: {track.id}", level="info")`

**Error handling**:
- Missing URL: argparse shows usage automatically
- Import failures: Catch domain exceptions, log appropriate error message
- Duplicate: Catch `DuplicateVideoError`, show existing track ID

**Example usage**:
```bash
music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --artist "Rick Astley" \
    --title "Never Gonna Give You Up" \
    --album "Whenever You Need Somebody"
```

#### `handle_youtube_add_playlist(ctx: AppContext, args: list[str]) -> tuple[AppContext, Any]`

**Usage**: `youtube add-playlist <playlist_id or url>`

**Implementation**:
1. Parse argument (playlist ID or URL) using argparse
2. Extract playlist ID if URL provided:
   - Pattern: `list=([a-zA-Z0-9_-]+)`
   - If no match, use arg as-is (assume it's already an ID)
3. Import using `youtube.import_playlist(playlist_id)` → returns `ImportResult`
4. **Format ImportResult for CLI output**:
   ```python
   result = youtube.import_playlist(playlist_id)

   log(f"✓ Playlist import complete!", level="info")
   log(f"  Imported: {result.imported_count} tracks", level="info")
   log(f"  Skipped: {result.skipped_count} duplicates", level="info")

   if result.failed_count > 0:
       log(f"  Failed: {result.failed_count} videos", level="warning")
       for video_id, error in result.failures:
           log(f"    - {video_id}: {error}", level="warning")
   ```

**Error handling**:
- Missing playlist ID: argparse shows usage
- Invalid playlist: Catch `YouTubeError`, log error message
- Partial failures: Display from `ImportResult.failures`

**Example usage**:
```bash
music-minion youtube add-playlist "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
music-minion youtube add-playlist "https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```

### Command Registration in `__init__.py`

Add to the command routing dictionary:
```python
"youtube": {
    "add": handle_youtube_add,
    "add-playlist": handle_youtube_add_playlist,
}
```

Import the provider at the top:
```python
from music_minion.domain.library.providers import youtube
```

## Acceptance Criteria

- [ ] `youtube add <url>` with metadata flags imports single video
- [ ] Metadata flags (--artist, --title, --album) parsed correctly
- [ ] `youtube add-playlist <id>` imports entire playlist
- [ ] Playlist URL parsing extracts ID correctly
- [ ] Success messages show track info and file paths
- [ ] Statistics shown for playlist imports (imported/skipped counts)
- [ ] Error messages are clear and actionable
- [ ] Commands registered in routing dictionary

## Dependencies

- Task 05 (provider interface) must be complete
