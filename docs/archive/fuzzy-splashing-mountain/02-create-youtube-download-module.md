# Create YouTube Download Module

## Files to Create
- `src/music_minion/domain/library/providers/youtube/download.py` (new)
- `src/music_minion/domain/library/providers/youtube/exceptions.py` (new)

## Implementation Details

Create the core download infrastructure using yt-dlp for YouTube video downloads.

### Custom Exceptions (exceptions.py)

Create domain-specific exceptions for proper error handling:

```python
class YouTubeError(Exception):
    """Base exception for YouTube operations."""
    pass

class InvalidYouTubeURLError(YouTubeError):
    """Raised when URL is not a valid YouTube URL."""
    pass

class VideoUnavailableError(YouTubeError):
    """Raised when video is deleted or unavailable."""
    pass

class AgeRestrictedError(YouTubeError):
    """Raised when video requires age verification."""
    pass

class CopyrightBlockedError(YouTubeError):
    """Raised when video is blocked due to copyright."""
    pass

class DuplicateVideoError(YouTubeError):
    """Raised when video is already imported."""
    def __init__(self, track_id: int, message: str = None):
        self.track_id = track_id
        super().__init__(message or f"Video already imported as track #{track_id}")

class InsufficientSpaceError(YouTubeError):
    """Raised when disk space is insufficient."""
    pass
```

### Required Functions

#### `download_video(url: str, output_dir: Path) -> tuple[Path, dict]`
- Download video+audio using yt-dlp
- Format preference: `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`
- Sanitize filename to snake_case using `sanitize_filename()`
- Return tuple of (file_path, extracted_metadata)
- **Returned metadata dict must contain**: `{"duration": float, "title": str, "uploader": str}`
- Handle errors using custom exceptions (see below)

#### `sanitize_filename(title: str, extension: str = ".mp4") -> str`
- Convert to lowercase
- Replace special characters with underscores
- Replace spaces/hyphens with underscores
- **Split extension before truncating, re-add after**
- Truncate base name to (200 - len(extension)) characters
- Remove leading/trailing underscores
- Example: "Darude - Sandstorm" → "darude_sandstorm.mp4"

#### `extract_video_id(url: str) -> str`
- **Use yt-dlp's built-in URL extraction** instead of regex
- Call `yt_dlp.YoutubeDL().extract_info(url, download=False)` and get ID from result
- This handles ALL URL formats automatically (standard, short, embed, shorts, mobile, live, etc.)
- Raise `InvalidYouTubeURLError` for invalid URLs

#### `get_playlist_info(playlist_id: str) -> dict`
- Use yt-dlp to extract playlist metadata WITHOUT downloading
- Return: `{"title": str, "video_count": int, "videos": list[dict]}`
- Each video dict contains: `{"id": str, "title": str, "duration": float}`

#### `download_playlist_videos(playlist_id: str, output_dir: Path, skip_ids: set[str] = None) -> tuple[list[tuple[Path, dict]], list[tuple[str, Exception]]]`
- Download videos from a playlist, **skipping IDs in skip_ids set**
- Return tuple of (successes, failures):
  - successes: list of (file_path, metadata) tuples
  - failures: list of (video_id, exception) tuples
- Handle individual video failures gracefully (skip and continue)

#### `check_available_space(output_dir: Path, video_count: int = 1, mb_per_video: int = 350) -> bool`
- Estimate required space: `video_count * mb_per_video`
- Default 350MB per video (accounts for hour-long videos)
- Use `os.statvfs()` to get filesystem stats
- Return True if sufficient space, False otherwise

### Error Handling

Map yt-dlp exceptions to domain exceptions:

```python
try:
    # yt-dlp download
except yt_dlp.utils.DownloadError as e:
    error_msg = str(e).lower()
    if "sign in" in error_msg or "age" in error_msg:
        raise AgeRestrictedError("Video requires age verification (login not supported)")
    elif "unavailable" in error_msg or "deleted" in error_msg or "private" in error_msg:
        raise VideoUnavailableError("Video is unavailable, deleted, or private")
    elif "copyright" in error_msg or "blocked" in error_msg:
        raise CopyrightBlockedError("Video blocked due to copyright")
    else:
        raise YouTubeError(f"Download failed: {e}")
```

### File Collision Handling

If a file already exists with the sanitized name (different video with same title), append youtube_id:
- `video_title.mp4` (original)
- `video_title_dQw4w9WgXcQ.mp4` (collision - append video ID for uniqueness)

## Acceptance Criteria

- [ ] All 6 functions implemented with proper type hints
- [ ] Custom exception hierarchy in exceptions.py
- [ ] yt-dlp integration downloads video+audio in mp4/webm format
- [ ] Filename sanitization preserves extension when truncating
- [ ] Video ID extraction uses yt-dlp (handles all URL formats)
- [ ] Playlist download returns both successes and failures
- [ ] Disk space check estimates based on video count (350MB/video default)
- [ ] Error messages are clear with proper exception types

## Dependencies

- Task 01 (yt-dlp dependency) must be complete
