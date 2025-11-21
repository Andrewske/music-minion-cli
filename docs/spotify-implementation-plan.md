# Spotify Provider Implementation Plan

## Overview
Implement Spotify as a library provider with OAuth 2.0 + PKCE authentication, library sync, playlist management, and Spotify Connect API playback control using thin class wrappers around pure functions.

## Prerequisites
- Spotify Premium account (required for playback)
- Spotify app installed and open on at least one device
- Spotify API credentials (client_id, client_secret)

## Architecture Approach

### Playback Architecture: Thin Class Wrappers
Use minimal classes as thin wrappers around pure functions:
- **Pragmatic**: Matches existing `MusicPlayer` pattern
- **Functional underneath**: Pure functions do the actual work
- **No complex OOP**: Just simple wrapper classes, no inheritance hierarchies

```python
# Pure functions do the work
def _spotify_play_internal(provider_state, track_id, device_id) -> bool:
    # ... API call logic

# Class is thin wrapper
class SpotifyPlayer:
    def __init__(self, provider_state, device_id=None):
        self.provider_state = provider_state
        self.device_id = device_id

    def play(self, spotify_id: str) -> bool:
        return _spotify_play_internal(self.provider_state, spotify_id, self.device_id)
```

### Routing Pattern
```python
# AppContext tracks current player
if track.source == 'spotify':
    context.player = SpotifyPlayer(provider_state, device_id)
else:
    context.player = MPVPlayer(socket_path)  # existing

# Unified interface at call sites
context.player.play(source)
context.player.pause()
pos = context.player.get_time_pos()
```

## Implementation Phases

### Phase 1: Core Provider Infrastructure (2-3 hours)

**Files to create:**
- `src/music_minion/domain/library/providers/spotify/__init__.py`
- `src/music_minion/domain/library/providers/spotify/auth.py`
- `src/music_minion/domain/library/providers/spotify/api.py`

**Database (verify schema v11 exists):**
```sql
-- Already exists from SoundCloud implementation
spotify_id TEXT (in tracks table)
spotify_playlist_id TEXT (in playlists table)
provider_state table (for tokens)
```

**Tasks:**

#### 1. Create `auth.py` - OAuth 2.0 + PKCE flow
- Endpoints:
  - Auth: `https://accounts.spotify.com/authorize`
  - Token: `https://accounts.spotify.com/api/token`
- PKCE: SHA256 code challenge (same as SoundCloud pattern)
- CSRF: State token verification
- Scopes:
  ```python
  SPOTIFY_SCOPES = [
      "user-library-read",
      "user-library-modify",
      "playlist-read-private",
      "playlist-read-collaborative",
      "playlist-modify-public",
      "playlist-modify-private",
      "user-read-playback-state",
      "user-modify-playback-state",
  ]
  ```
- Local callback server on `localhost:8080/callback`
- Token storage: `provider_state` table + file backup (`~/.local/share/music-minion/spotify/user_tokens.json`)
- Token refresh with 5-minute safety buffer
- Functions:
  - `authenticate(state) -> (ProviderState, bool)`
  - `refresh_token(token_data) -> Optional[dict]`
  - `is_token_expired(token_data) -> bool`

#### 2. Create `api.py` - Core API operations
- Rate limiting decorator:
  ```python
  def retry_on_rate_limit(max_retries=3):
      def decorator(func):
          def wrapper(*args, **kwargs):
              for attempt in range(max_retries):
                  try:
                      return func(*args, **kwargs)
                  except requests.HTTPError as e:
                      if e.response.status_code == 429:
                          retry_after = int(e.response.headers.get('Retry-After', 2 ** attempt))
                          time.sleep(retry_after)
                      elif e.response.status_code == 401:
                          raise  # Token expired, re-auth needed
                      elif e.response.status_code == 403:
                          raise Exception("Spotify Premium required")
                      else:
                          raise
              raise Exception(f"Max retries exceeded for {func.__name__}")
          return wrapper
      return decorator
  ```
- Token refresh check at start of each API call
- Base API call function with error handling
- **CRITICAL**: Use `logger` from `logging.getLogger(__name__)` for all logging, never `print()`

#### 3. Create `__init__.py`
- `init_provider(config) -> ProviderState`
  - Load tokens from database
  - Auto-refresh if expired
  - Return initialized state
- Re-export all public functions

#### 4. Add configuration to `src/music_minion/core/config.py`
```python
@dataclass
class SpotifyConfig:
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    sync_saved_tracks: bool = True
    sync_playlists: bool = True
    preferred_device_id: str = ""  # Optional: set via device command
```

### Phase 2: Library Sync & Track Management (2-3 hours)

**Pure functions in `api.py`:**

#### 1. `sync_library(state: ProviderState, incremental=True) -> Tuple[ProviderState, List[Tuple[str, dict]]]`
- Endpoint: `GET /v1/me/tracks` (limit=50, offset pagination)
- Incremental mode: Stop metadata fetch at first existing track
- Continue collecting all track IDs for like markers (SoundCloud pattern)
- Extract metadata:
  ```python
  {
      'title': track['name'],
      'artist': ', '.join([a['name'] for a in track['artists']]),
      'album': track['album']['name'],
      'year': int(track['album']['release_date'][:4]) if track['album']['release_date'] else None,
      'duration': track['duration_ms'] / 1000.0,
      'genre': None,  # Not in basic track object
      'bpm': None,    # Audio features API deprecated
      'key': None,    # Audio features API deprecated
  }
  ```
- Progress: Log every 50 tracks (Spotify's page size)
- Batch insert like markers with `INSERT OR IGNORE`

#### 2. `search(state: ProviderState, query: str) -> Tuple[ProviderState, List[Tuple[str, dict]]]`
- Endpoint: `GET /v1/search?type=track&q={query}&limit=20`
- Same metadata format as sync_library
- Return top 20 results

#### 3. `like_track(state: ProviderState, spotify_id: str) -> Tuple[ProviderState, bool, Optional[str]]`
- Endpoint: `PUT /v1/me/tracks?ids={spotify_id}`
- Also add rating marker to database with `source='spotify'`
- Return: (new_state, success, error_message)

#### 4. `unlike_track(state: ProviderState, spotify_id: str) -> Tuple[ProviderState, bool, Optional[str]]`
- Endpoint: `DELETE /v1/me/tracks?ids={spotify_id}`
- Also remove rating marker from database
- Return: (new_state, success, error_message)

#### 5. `get_stream_url(state: ProviderState, spotify_id: str) -> Optional[str]`
- Returns: `f"spotify:track:{spotify_id}"`
- Pure function - no side effects
- Playback layer detects "spotify:" prefix and routes to SpotifyPlayer

### Phase 3: Playback Integration (3-4 hours)

**Create thin wrapper class:**

#### File: `src/music_minion/domain/playback/spotify_player.py`

```python
"""
SpotifyPlayer - thin wrapper around pure Spotify API functions.
Provides unified interface matching MusicPlayer for seamless routing.
"""
import logging
logger = logging.getLogger(__name__)

class SpotifyPlayer:
    """Thin wrapper for Spotify playback control. Pure functions do the work."""

    def __init__(self, provider_state: ProviderState, device_id: Optional[str] = None):
        self.provider_state = provider_state
        self.device_id = device_id or self._get_active_device()
        self.current_track_id: Optional[str] = None

    def play(self, spotify_uri: str) -> bool:
        """Play track via Spotify Connect. spotify_uri format: 'spotify:track:{id}'"""
        track_id = spotify_uri.split(':')[-1] if ':' in spotify_uri else spotify_uri
        success = _spotify_play(self.provider_state, track_id, self.device_id)
        if success:
            self.current_track_id = track_id
            logger.info(f"Playing Spotify track: {track_id}")
        else:
            logger.error(f"Failed to play Spotify track: {track_id}")
        return success

    def pause(self) -> bool:
        """Pause Spotify playback."""
        success = _spotify_pause(self.provider_state)
        logger.debug("Paused Spotify playback")
        return success

    def resume(self) -> bool:
        """Resume Spotify playback."""
        success = _spotify_resume(self.provider_state)
        logger.debug("Resumed Spotify playback")
        return success

    def stop(self) -> bool:
        """Stop Spotify playback."""
        return _spotify_pause(self.provider_state)  # Spotify doesn't have stop, use pause

    def get_time_pos(self) -> Optional[float]:
        """Get current playback position in seconds."""
        playback = _spotify_get_current_playback(self.provider_state)
        return playback['progress_ms'] / 1000.0 if playback else None

    def seek(self, position: float) -> bool:
        """Seek to position in seconds."""
        position_ms = int(position * 1000)
        success = _spotify_seek(self.provider_state, position_ms)
        logger.debug(f"Seeked to position: {position}s")
        return success

    def is_playing(self) -> bool:
        """Check if currently playing."""
        playback = _spotify_get_current_playback(self.provider_state)
        return playback['is_playing'] if playback else False

    def get_duration(self) -> Optional[float]:
        """Get current track duration in seconds."""
        playback = _spotify_get_current_playback(self.provider_state)
        return playback['item']['duration_ms'] / 1000.0 if playback and playback.get('item') else None

    def _get_active_device(self) -> Optional[str]:
        """Get active device ID or first available."""
        devices = _spotify_get_devices(self.provider_state)
        for device in devices:
            if device['is_active']:
                logger.debug(f"Using active Spotify device: {device['name']}")
                return device['id']
        if devices:
            logger.debug(f"No active device, using first available: {devices[0]['name']}")
            return devices[0]['id']
        logger.warning("No Spotify devices available")
        return None
```

**Pure functions in `api.py` (called by SpotifyPlayer):**

```python
import logging
logger = logging.getLogger(__name__)

# Internal pure functions that do the actual work

@retry_on_rate_limit()
def _spotify_play(state: ProviderState, track_id: str, device_id: str) -> bool:
    """Internal: Start playback on device."""
    # PUT /v1/me/player/play
    # Body: {"uris": [f"spotify:track:{track_id}"], "device_id": device_id}
    logger.debug(f"Starting playback: track_id={track_id}, device_id={device_id}")

@retry_on_rate_limit()
def _spotify_pause(state: ProviderState) -> bool:
    """Internal: Pause playback."""
    # PUT /v1/me/player/pause

@retry_on_rate_limit()
def _spotify_resume(state: ProviderState) -> bool:
    """Internal: Resume playback."""
    # PUT /v1/me/player/play (no body)

@retry_on_rate_limit()
def _spotify_get_current_playback(state: ProviderState) -> Optional[dict]:
    """Internal: Get current playback state."""
    # GET /v1/me/player/currently-playing
    # Returns: {"progress_ms": int, "is_playing": bool, "item": {...}}

@retry_on_rate_limit()
def _spotify_seek(state: ProviderState, position_ms: int) -> bool:
    """Internal: Seek to position."""
    # PUT /v1/me/player/seek?position_ms={position_ms}

@retry_on_rate_limit()
def _spotify_get_devices(state: ProviderState) -> List[dict]:
    """Internal: Get available devices."""
    # GET /v1/me/player/devices
    # Returns: [{"id": str, "name": str, "is_active": bool, "type": str}]
```

**Device management functions (public):**

```python
def get_available_devices(state: ProviderState) -> Tuple[ProviderState, List[dict]]:
    """Get list of available Spotify devices."""
    devices = _spotify_get_devices(state)
    logger.info(f"Found {len(devices)} Spotify devices")
    return state, devices

def set_active_device(state: ProviderState, device_id: str) -> Tuple[ProviderState, bool]:
    """Set active playback device."""
    # PUT /v1/me/player with {"device_ids": [device_id], "play": false}
    logger.info(f"Set active device: {device_id}")
    return state, success
```

**Update playback commands** (`src/music_minion/commands/playback.py`):

```python
import logging
logger = logging.getLogger(__name__)

def handle_play(context: AppContext, args: list) -> Tuple[AppContext, bool]:
    """Play current or specified track."""
    track = context.current_track  # or get from args

    # Route to appropriate player based on source
    if track.source == 'spotify':
        logger.info(f"Playing Spotify track: {track.title}")
        # Initialize Spotify provider if needed
        if not hasattr(context, 'spotify_provider_state'):
            provider_state = init_provider(context.config.spotify)
            context = context.with_spotify_provider_state(provider_state)

        # Create SpotifyPlayer with preferred device
        player = SpotifyPlayer(
            context.spotify_provider_state,
            device_id=context.config.spotify.preferred_device_id or None
        )

        # Stop MPV if running
        if context.player:
            context.player.stop()

    elif track.source in ['local', 'soundcloud']:
        logger.info(f"Playing {track.source} track: {track.title}")
        # Use existing MPVPlayer
        player = context.player
        # Get stream URL from provider
        stream_url = get_stream_url_for_track(context, track)

    # Unified play call
    success = player.play(stream_url if track.source != 'spotify' else f"spotify:track:{track.spotify_id}")

    if success:
        context = context.with_player(player)
        context = context.with_current_track(track)
    else:
        logger.error(f"Failed to play track: {track.title}")

    return context, success
```

**Update UI polling** (`src/music_minion/ui/blessed/app.py`):

```python
# In event loop - check player type
if context.player:
    if isinstance(context.player, SpotifyPlayer):
        # Poll Spotify API for position
        time_pos = context.player.get_time_pos()
    else:
        # Poll MPV
        time_pos = context.player.get_time_pos()
```

### Phase 4: Playlist Management (2-3 hours)

**Pure functions in `api.py`:**

#### 1. `get_playlists(state: ProviderState) -> Tuple[ProviderState, List[dict]]`
- Endpoint: `GET /v1/me/playlists` (limit=50, offset pagination)
- Return: `(state, [{"id": str, "name": str, "track_count": int, "public": bool}])`

#### 2. `get_playlist_tracks(state: ProviderState, playlist_id: str) -> Tuple[ProviderState, List[Tuple[str, dict]]]`
- Endpoint: `GET /v1/playlists/{playlist_id}/tracks` (limit=100, offset pagination)
- Return: `(state, [(spotify_id, metadata)])`

#### 3. `create_playlist(state: ProviderState, name: str, description="", public=False) -> Tuple[ProviderState, Optional[str]]`
- Endpoint: `POST /v1/me/playlists`
- Body: `{"name": name, "description": description, "public": public}`
- Return: `(state, playlist_id or None)`

#### 4. `add_track_to_playlist(state: ProviderState, playlist_id: str, spotify_id: str) -> Tuple[ProviderState, bool]`
- Endpoint: `POST /v1/playlists/{playlist_id}/tracks`
- Body: `{"uris": [f"spotify:track:{spotify_id}"]}`
- Return: `(state, success)`

#### 5. `remove_track_from_playlist(state: ProviderState, playlist_id: str, spotify_id: str) -> Tuple[ProviderState, bool]`
- Endpoint: `DELETE /v1/playlists/{playlist_id}/tracks`
- Body: `{"tracks": [{"uri": f"spotify:track:{spotify_id}"}]}`
- Return: `(state, success)`

### Phase 5: Command Integration (1-2 hours)

**Update `src/music_minion/commands/library.py`:**

Add commands:
```python
import logging
logger = logging.getLogger(__name__)

def handle_library_auth(context, args):
    """library auth spotify"""
    if args[0] == 'spotify':
        logger.info("Starting Spotify authentication")
        state = init_provider(context.config.spotify)
        state, success = authenticate(state)
        if success:
            console.print("[green]✓[/green] Authenticated with Spotify")
            logger.info("Spotify authentication successful")
        else:
            console.print("[red]✗[/red] Authentication failed")
            logger.error("Spotify authentication failed")
        return context, success

def handle_library_sync(context, args):
    """library sync spotify [--full]"""
    provider_name = args[0]
    full = '--full' in args

    # ... existing logic for other providers

    if provider_name == 'spotify':
        logger.info(f"Starting Spotify library sync (incremental={not full})")
        state = init_provider(context.config.spotify)
        state, tracks = sync_library(state, incremental=not full)
        # Import tracks to database
        imported = batch_insert_provider_tracks(tracks, 'spotify')
        console.print(f"[green]Synced {imported} Spotify tracks[/green]")
        logger.info(f"Spotify sync completed: {imported} tracks imported")

def handle_library_devices(context, args):
    """library devices spotify - List available Spotify devices"""
    if args[0] == 'spotify':
        logger.debug("Listing Spotify devices")
        state = init_provider(context.config.spotify)
        state, devices = get_available_devices(state)

        console.print("\n[bold]Available Spotify Devices:[/bold]")
        for i, device in enumerate(devices, 1):
            active = "[green]●[/green]" if device['is_active'] else "○"
            console.print(f"{active} {i}. {device['name']} ({device['type']})")
            console.print(f"    ID: [dim]{device['id']}[/dim]")
        return context, True

def handle_library_device(context, args):
    """library device spotify <id|name> - Set preferred device"""
    if args[0] == 'spotify':
        identifier = ' '.join(args[1:])
        logger.info(f"Setting Spotify device: {identifier}")

        # Get devices and find match
        state = init_provider(context.config.spotify)
        state, devices = get_available_devices(state)

        device = None
        for d in devices:
            if identifier in [d['id'], d['name']]:
                device = d
                break

        if device:
            # Update config (persist to file)
            update_config_value('spotify.preferred_device_id', device['id'])
            console.print(f"[green]✓[/green] Set device to: {device['name']}")
            logger.info(f"Set preferred device: {device['name']} ({device['id']})")
            return context, True
        else:
            console.print(f"[red]Device not found:[/red] {identifier}")
            logger.warning(f"Device not found: {identifier}")
            return context, False
```

**Update provider registry** (`src/music_minion/domain/library/providers/__init__.py`):
```python
from . import local, soundcloud, spotify

PROVIDERS = {}
register_provider('local', local)
register_provider('soundcloud', soundcloud)
register_provider('spotify', spotify)
```

**Update `AppContext`** (`src/music_minion/context.py`):
```python
@dataclass
class AppContext:
    # ... existing fields
    player: Optional[MusicPlayer]  # Can be MPVPlayer or SpotifyPlayer
    spotify_provider_state: Optional[ProviderState] = None  # New
```

### Phase 6: Testing & Polish (2-3 hours)

**Critical test scenarios:**

1. **OAuth flow**
   - Run `library auth spotify`
   - Verify browser opens
   - Complete authorization
   - Check token saved to database
   - Test token refresh after expiry

2. **Library sync**
   - `library sync spotify` (full sync first time)
   - Verify tracks imported to database
   - `library sync spotify` again (incremental, should be fast)
   - Check like markers synced

3. **Playback**
   - `library active spotify`
   - `play` - should play on Spotify device
   - Verify progress bar updates
   - Test pause, resume, seek
   - Play local track - should switch to MPV
   - Play Spotify track again - should switch back

4. **Device management**
   - `library devices spotify` - list devices
   - `library device spotify "Desktop"` - set preferred
   - Verify playback uses preferred device

5. **Mixed playlists**
   - Create playlist with local + Spotify tracks
   - Play through playlist
   - Verify player switches seamlessly

6. **Playlist operations**
   - `playlist new smart spotify "high energy"` - create
   - Add Spotify tracks
   - Sync to Spotify
   - Verify playlist appears in Spotify app

7. **Like/unlike**
   - `like` on Spotify track - syncs to Spotify
   - `unlike` - removes from Spotify
   - Verify in Spotify app

8. **Error handling**
   - Close all Spotify apps → play track → "No devices available"
   - Revoke token → API call → re-auth prompt
   - Rate limit → auto-retry with backoff
   - Network error → clear error message

**Polish:**
- Clear error messages for all scenarios
- Progress indicators (every 50 tracks during sync)
- Device auto-selection (active → first → error)
- Graceful degradation when device unavailable
- All logging via `logger`, no `print()` statements

## Configuration

Add to `~/.config/music-minion/config.toml`:
```toml
[spotify]
enabled = true
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
redirect_uri = "http://localhost:8080/callback"
sync_saved_tracks = true
sync_playlists = true
# Set via: library device spotify "<name>"
preferred_device_id = ""
```

## Key API Endpoints Reference

**Authentication:**
- `GET https://accounts.spotify.com/authorize` - User authorization
- `POST https://accounts.spotify.com/api/token` - Token exchange/refresh

**Library:**
- `GET /v1/me/tracks` - Saved tracks (limit=50)
- `PUT /v1/me/tracks?ids={ids}` - Save tracks (max 50)
- `DELETE /v1/me/tracks?ids={ids}` - Remove tracks (max 50)
- `GET /v1/search?type=track&q={query}` - Search tracks

**Playlists:**
- `GET /v1/me/playlists` - User playlists
- `GET /v1/playlists/{id}/tracks` - Playlist tracks (limit=100)
- `POST /v1/me/playlists` - Create playlist
- `POST /v1/playlists/{id}/tracks` - Add tracks
- `DELETE /v1/playlists/{id}/tracks` - Remove tracks

**Playback:**
- `GET /v1/me/player/devices` - List devices
- `GET /v1/me/player/currently-playing` - Current playback state
- `PUT /v1/me/player/play` - Start/resume playback
- `PUT /v1/me/player/pause` - Pause
- `PUT /v1/me/player/seek?position_ms={ms}` - Seek
- `PUT /v1/me/player` - Transfer playback to device

## Estimated Timeline

- **Phase 1** (Core Infrastructure): 2-3 hours
- **Phase 2** (Library Sync): 2-3 hours
- **Phase 3** (Playback with thin class wrapper): 3-4 hours
- **Phase 4** (Playlist Management): 2-3 hours
- **Phase 5** (Command Integration): 1-2 hours
- **Phase 6** (Testing & Polish): 2-3 hours

**Total: 12-18 hours** (avg: 15 hours)

## Success Criteria

✅ OAuth 2.0 + PKCE authentication works
✅ Token refresh automatic and transparent
✅ Saved tracks sync with incremental mode
✅ SpotifyPlayer class provides unified interface
✅ Playback works via Spotify Connect API
✅ Device selection via command + auto-select active
✅ Mixed playlists play correctly (local + Spotify)
✅ Playlists sync bidirectionally
✅ Like/unlike syncs to Spotify
✅ Rate limiting with exponential backoff
✅ Error handling for all common scenarios
✅ Clear user messaging for Premium requirement
✅ All logging via centralized logger (no print statements)

## Implementation Notes

- **Thin classes**: SpotifyPlayer is a simple wrapper, pure functions do the work
- **No audio features**: API deprecated, cannot fetch BPM/key
- **Premium required**: Free tier doesn't support playback control
- **Device must be open**: At least one Spotify app running
- **Not MPV-based**: Uses Spotify Connect, not direct streaming
- **Skip match command**: No deduplication feature
- **Logging**: Use `logging.getLogger(__name__)` in all modules, never `print()`

## Common Pitfalls to Avoid

1. **Token expiry race conditions**: Always check/refresh tokens at API call start
2. **Incomplete pagination**: Use `while` loops, follow all pages
3. **Duplicate inserts**: Use `INSERT OR IGNORE` with unique constraints
4. **Over-aggressive rate limiting**: Return errors, let UI decide retry strategy
5. **Losing auth on shutdown**: Always save tokens to database after authenticate()
6. **Re-syncing inefficiency**: Implement incremental mode properly
7. **Slow imports**: Use `executemany()` instead of loop + execute()
8. **Data loss**: Track ownership with `source` column
9. **Print statements**: Always use logger, not print()
10. **No error context**: Use `logger.exception()` in except blocks for stack traces

## References

- **Spotify API Docs**: https://developer.spotify.com/documentation/web-api
- **SoundCloud Provider**: `src/music_minion/domain/library/providers/soundcloud/`
- **Provider Protocol**: `src/music_minion/domain/library/provider.py`
- **Database Schema**: `src/music_minion/core/database.py` (v17)
- **Logging System**: `src/music_minion/core/logging.py`
