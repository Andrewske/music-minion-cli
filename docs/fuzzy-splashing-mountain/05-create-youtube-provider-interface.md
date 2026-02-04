# Create YouTube Provider Interface

## Files to Create
- `src/music_minion/domain/library/providers/youtube/__init__.py` (new)

## Implementation Details

Create the provider interface that follows the existing pattern used by SoundCloud and Spotify providers.

### Required Function

#### `init_provider(config: ProviderConfig) -> ProviderState`

Initialize the YouTube provider with no authentication required.

**Implementation**:
```python
from music_minion.domain.library.provider import ProviderConfig, ProviderState

def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize YouTube provider.

    No authentication needed for YouTube downloads.

    Args:
        config: Provider configuration

    Returns:
        ProviderState with authenticated=True and output_dir in cache
    """
    from pathlib import Path

    output_dir = str(Path.home() / "music" / "youtube")

    return ProviderState(
        config=config,
        authenticated=True,  # No auth needed
        last_sync=None,
        cache={"output_dir": output_dir}
    )
```

### Re-exports

Export the import functions for external use:
```python
# Re-export import functions
from .import_handlers import import_single_video, import_playlist
from .download import download_video, extract_video_id

__all__ = [
    "init_provider",
    "import_single_video",
    "import_playlist",
    "download_video",
    "extract_video_id",
]
```

### Runtime Check

Add ffmpeg check and temp directory cleanup on initialization:
```python
import shutil
from pathlib import Path
from loguru import logger

def init_provider(config: ProviderConfig) -> ProviderState:
    # Check for ffmpeg
    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg not found - YouTube downloads may fail")
        logger.warning("Install ffmpeg: sudo apt install ffmpeg (Linux) or brew install ffmpeg (Mac)")

    # Clean up orphaned temp files from previous failed imports
    output_dir = Path.home() / "music" / "youtube"
    temp_dir = output_dir / ".tmp"
    if temp_dir.exists():
        for f in temp_dir.iterdir():
            logger.debug(f"Cleaning up orphaned temp file: {f}")
            f.unlink()

    # ... rest of initialization
```

### Known Limitations

**Authentication not supported**: This provider downloads public videos only.

The following content types are NOT accessible:
- **Age-restricted videos**: Require YouTube login for age verification
- **Private videos**: Require owner's account access
- **Unlisted videos with login requirement**: Some unlisted videos require authentication
- **Premium/member-only content**: Requires YouTube Premium or channel membership

yt-dlp supports cookies files for authentication, but this is intentionally not implemented to keep the provider simple. If needed in the future, add optional `cookies_file` parameter to ProviderConfig.

## Acceptance Criteria

- [ ] `init_provider()` returns ProviderState with authenticated=True
- [ ] output_dir is set to `~/music/youtube` in cache
- [ ] Import functions are properly re-exported
- [ ] Module follows same pattern as soundcloud/__init__.py
- [ ] ffmpeg availability warning logged if not found

## Dependencies

- Task 04 (import handlers) must be complete
