# Add yt-dlp Dependency

## Files to Modify
- `pyproject.toml` (modify)

## Implementation Details

Add yt-dlp to the project dependencies for YouTube video downloading functionality.

### Changes Required

Add to the dependencies section in `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies ...
    "yt-dlp>=2024.1.0",
]
```

### Runtime Requirement

**Important**: `ffmpeg` must be installed on the system for yt-dlp to work properly (used for muxing video/audio streams).

The provider initialization code should check for ffmpeg availability:
```python
import shutil
if not shutil.which("ffmpeg"):
    raise RuntimeError("ffmpeg not found - required for YouTube downloads")
```

## Acceptance Criteria

- [ ] yt-dlp added to pyproject.toml dependencies
- [ ] Dependency version is >= 2024.1.0
- [ ] Can run `uv pip list | grep yt-dlp` and see the package

## Dependencies

None - this is the foundational task.
