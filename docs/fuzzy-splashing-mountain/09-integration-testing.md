# Integration Testing and Verification

## Files to Test
- All YouTube provider modules
- CLI commands
- Web API endpoints
- Radio integration

## Implementation Details

Perform end-to-end testing to verify the entire YouTube integration works correctly.

### Test Cases

#### 1. CLI Single Video Import

**Test**:
```bash
uv run music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --artist "Rick Astley" \
    --title "Never Gonna Give You Up" \
    --album "Whenever You Need Somebody"
```

**Verify**:
- [ ] File created at `~/music/youtube/never_gonna_give_you_up.mp4`
- [ ] Database track created with:
  - `youtube_id = "dQw4w9WgXcQ"`
  - `local_path` set correctly
  - `source = "youtube"`
  - `artist = "Rick Astley"`
  - `title = "Never Gonna Give You Up"`
  - `album = "Whenever You Need Somebody"`
- [ ] Track duration extracted correctly
- [ ] Success message logged

#### 2. CLI Playlist Import

**Test**:
```bash
uv run music-minion youtube add-playlist "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```

**Verify**:
- [ ] All videos downloaded to `~/music/youtube/`
- [ ] Database tracks created for all videos
- [ ] Album name = playlist title for all tracks
- [ ] Title = video title for each track
- [ ] Artist is empty for all tracks
- [ ] Statistics logged (N imported, M skipped)

#### 3. Duplicate Detection

**Test**:
Try importing same video twice:
```bash
# First import
uv run music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --artist "Rick Astley" --title "Never Gonna Give You Up"

# Second import (should fail)
uv run music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --artist "Rick Astley" --title "Never Gonna Give You Up"
```

**Verify**:
- [ ] Second import detects duplicate
- [ ] Error message: "Video already imported as track #X"
- [ ] No duplicate file downloaded
- [ ] No duplicate database entry

#### 4. Radio Playback Integration

**Note**: The commands below use existing Music Minion commands. Verify exact syntax by running `music-minion help` or checking existing command handlers before testing.

**Test**:
1. Import YouTube video
2. Create playlist (verify actual command syntax in codebase)
3. Add track to playlist
4. Create radio station from playlist
5. Activate station

**Example commands (verify syntax)**:
```bash
# These are example commands - verify actual syntax in your codebase
music-minion playlist create "Test YouTube Playlist"
music-minion playlist add-track {playlist_id} {track_id}
music-minion radio create-station "YouTube Test" {playlist_id}
music-minion radio activate {station_id}
```

**Verify**:
- [ ] Liquidsoap requests next track via `/next-track` endpoint
- [ ] Endpoint returns `local_path` of downloaded YouTube file
- [ ] Track plays successfully
- [ ] `radio_history` table records entry with:
  - `source_type = "youtube"`
  - `track_id` correct
  - `started_at` timestamp
- [ ] No errors in Liquidsoap logs

#### 5. Web UI Import

**Test**:
1. Open web interface
2. Navigate to YouTube import page
3. Fill form:
   - URL: `https://youtube.com/watch?v=dQw4w9WgXcQ`
   - Artist: "Rick Astley"
   - Title: "Never Gonna Give You Up"
   - Album: "Whenever You Need Somebody"
4. Submit form

**Verify**:
- [ ] Loading state shown
- [ ] Success message displayed
- [ ] Track appears in library
- [ ] Track has YouTube badge/icon
- [ ] Link to YouTube works

#### 6. Error Handling (Unit Tests with Mocking)

**Use mocking for reproducible error tests** - real YouTube videos change state over time.

Create unit tests in `tests/test_youtube_errors.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from music_minion.domain.library.providers.youtube import download
from music_minion.domain.library.providers.youtube.exceptions import (
    AgeRestrictedError,
    VideoUnavailableError,
    InvalidYouTubeURLError
)

@patch('yt_dlp.YoutubeDL')
def test_age_restricted_error(mock_ydl):
    """Mock yt-dlp to simulate age-restricted video."""
    mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = \
        Exception("Sign in to confirm your age")

    with pytest.raises(AgeRestrictedError):
        download.download_video("https://youtube.com/watch?v=test123", Path("/tmp"))

@patch('yt_dlp.YoutubeDL')
def test_unavailable_error(mock_ydl):
    """Mock yt-dlp to simulate deleted/unavailable video."""
    mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = \
        Exception("Video unavailable")

    with pytest.raises(VideoUnavailableError):
        download.download_video("https://youtube.com/watch?v=test123", Path("/tmp"))

def test_invalid_url_error():
    """Invalid URL should raise InvalidYouTubeURLError."""
    with pytest.raises(InvalidYouTubeURLError):
        download.extract_video_id("https://invalid.com/video")
```

**Verify each exception type maps correctly**:
- [ ] Age-restricted → `AgeRestrictedError`
- [ ] Unavailable/deleted → `VideoUnavailableError`
- [ ] Copyright blocked → `CopyrightBlockedError`
- [ ] Invalid URL → `InvalidYouTubeURLError`

#### 7. Filename Sanitization

**Test**:
Import video with special characters in title.

**Verify**:
- [ ] Filename is valid snake_case
- [ ] No special characters except underscores
- [ ] Lowercase
- [ ] No spaces or hyphens
- [ ] Truncated to 200 chars if needed

### Performance Testing

**Playlist import with 50+ videos**:
- [ ] Downloads complete without crashes
- [ ] Batch insert efficient (not N individual inserts)
- [ ] Progress logged at regular intervals
- [ ] Memory usage reasonable

### Radio Timeline Verification

**Test**:
1. Create station with mix of local and YouTube tracks
2. Activate station
3. Let it play through several tracks

**Verify**:
- [ ] `calculate_now_playing()` works with YouTube tracks
- [ ] Timeline calculation is source-agnostic
- [ ] History records source type correctly
- [ ] No errors switching between local and YouTube tracks

### Liquidsoap Format Compatibility (IMPORTANT)

**Test**: Verify Liquidsoap can extract and play audio from mp4/webm video containers.

```bash
# 1. Import a YouTube video
uv run music-minion youtube add "https://youtube.com/watch?v=dQw4w9WgXcQ" \
    --title "Test Video"

# 2. Test Liquidsoap can decode the file directly
liquidsoap -c 'output.dummy(single("/home/user/music/youtube/test_video.mp4"))'

# Expected: No errors, Liquidsoap decodes audio track
```

**If Liquidsoap fails to play mp4/webm**:
- Option A: Configure Liquidsoap to use ffmpeg decoder for these formats
- Option B: Add post-download audio extraction step (mp4 → mp3)
- Option C: Use `bestaudio` format in yt-dlp instead of video+audio

**Verify**:
- [ ] Liquidsoap plays mp4 container without errors
- [ ] Liquidsoap plays webm container without errors
- [ ] Audio quality is acceptable (no glitches, correct duration)
- [ ] No excessive CPU usage during playback

## Acceptance Criteria

All test cases pass:
- [ ] CLI single import works end-to-end
- [ ] CLI playlist import works end-to-end
- [ ] Duplicate detection prevents re-downloads
- [ ] Radio playback works with YouTube tracks
- [ ] Web UI import works
- [ ] All error cases handled gracefully
- [ ] Filename sanitization produces valid names
- [ ] Performance acceptable for large playlists
- [ ] Radio timeline works seamlessly

## Dependencies

All previous tasks (01-08) must be complete.

## Notes

**Manual testing required** - automate where possible but some tests (radio playback, web UI) require manual verification.

**Test data**: Use public, non-copyrighted YouTube videos for testing. Avoid music videos that may be region-blocked.
