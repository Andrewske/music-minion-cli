# Multi-Source Library - Remaining Features Plan

**Status:** Implementation plan for Phase 8 (Playlist Shortcuts) and Full SoundCloud Integration
**Created:** 2025-11-18
**Estimated Total Time:** 5-8 hours

---

## Overview

This document outlines the implementation plan for the final two features needed to complete the multi-source library system:

1. **Phase 8: Playlist Shortcuts** - Quick-add tracks to playlists via keyboard shortcuts
2. **Full SoundCloud Integration** - Complete OAuth flow with browser authentication

Both features build on the foundation laid in Phases 1-7 and require minimal changes to existing code.

---

# Phase 8: Playlist Shortcuts

**Goal:** Enable quick-add to playlists via configurable keyboard shortcuts
**Estimated Time:** 1-2 hours
**Priority:** Medium
**Complexity:** Low

## Feature Description

Allow users to configure keyboard shortcuts (e.g., `1`, `2`, `3`, `s`) that instantly add the currently playing track to specific playlists. This dramatically speeds up curation workflows, especially during live DJ sets.

### User Stories

1. **As a DJ preparing for NYE 2025**, I want to press `1` to add the current track to my "NYE 2025" playlist without typing the full command
2. **As a music curator**, I want to press `s` to add tracks to my "SoundCloud Upload" playlist for later export
3. **As a power user**, I want to configure my own shortcuts in a simple config file

### Benefits

- **Speed:** Add to playlist in 1 keypress vs typing `add "playlist name"`
- **Flow State:** No context switching during active listening sessions
- **Flexibility:** User-defined shortcuts per workflow
- **Discoverability:** Shortcuts shown in UI status bar

---

## Implementation Plan

### Step 1: Extend Configuration Schema (15 minutes)

**File:** `src/music_minion/core/config.py`

Add `ShortcutConfig` dataclass:

```python
@dataclass
class ShortcutConfig:
    """Playlist shortcut configuration."""
    enabled: bool = True
    shortcuts: Dict[str, str] = field(default_factory=dict)
    # Example: {"1": "Favorites", "2": "Workout", "s": "SoundCloud Likes"}

@dataclass
class Config:
    # ... existing fields ...
    shortcuts: ShortcutConfig = field(default_factory=ShortcutConfig)
```

**TOML format:**

```toml
[shortcuts]
enabled = true

[shortcuts.keys]
"1" = "Favorites"
"2" = "Workout"
"3" = "Chill"
"s" = "SoundCloud Likes"
"n" = "NYE 2025"
```

---

### Step 2: Update Keyboard Handler (30 minutes)

**File:** `src/music_minion/ui/blessed/events/keyboard.py`

Add shortcut handling before command palette:

```python
def handle_keyboard_input(term, state: UIState, key, ctx: AppContext) -> UIState:
    """Handle keyboard input with shortcut support."""

    # Check for playlist shortcuts first
    if ctx.config.shortcuts.enabled and key in ctx.config.shortcuts.shortcuts:
        playlist_name = ctx.config.shortcuts.shortcuts[key]

        # Get current track
        if state.current_track:
            # Add to playlist
            from music_minion.commands import track
            _, success = track.handle_add_command(ctx, [playlist_name])

            if success:
                # Show notification
                notification = f"✓ Added to {playlist_name}"
                return state._replace(
                    notification=notification,
                    notification_time=time.time()
                )
            else:
                notification = f"✗ Failed to add to {playlist_name}"
                return state._replace(
                    notification=notification,
                    notification_time=time.time()
                )

    # Existing key handling...
    if key == '/':
        # Command palette...
```

**Key Points:**
- Check shortcuts **before** regular command handling
- Short-circuit on match (don't process as regular key)
- Show visual feedback via notification system
- Handle errors gracefully (playlist doesn't exist, no track playing)

---

### Step 3: UI Status Indicator (20 minutes)

**File:** `src/music_minion/ui/blessed/components/dashboard.py`

Add shortcut hints to status bar:

```python
def render_status_bar(term, state: UIState, ctx: AppContext, y: int) -> int:
    """Render status bar with shortcut hints."""

    # ... existing status rendering ...

    # Show active shortcuts if enabled
    if ctx.config.shortcuts.enabled and ctx.config.shortcuts.shortcuts:
        shortcuts_text = " | Shortcuts: "
        for key, playlist in list(ctx.config.shortcuts.shortcuts.items())[:3]:
            shortcuts_text += f"{key}→{playlist}  "

        term.move(y, term.width - len(shortcuts_text))
        print(term.dim(shortcuts_text), end='')

    return y + 1
```

**Display Example:**
```
Status: Playing | Duration: 3:45 | Shortcuts: 1→Favorites  2→Workout  s→SoundCloud
```

---

### Step 4: Validation & Error Handling (15 minutes)

**File:** `src/music_minion/core/config.py`

Add validation when loading config:

```python
def validate_shortcut_config(config: Config) -> List[str]:
    """Validate shortcut configuration.

    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []

    for key, playlist_name in config.shortcuts.shortcuts.items():
        # Check key length
        if len(key) != 1:
            warnings.append(f"Shortcut key '{key}' should be single character")

        # Check for reserved keys
        reserved = {'/', '\n', '\r', '\t', '\x1b'}  # Esc, Enter, Tab, /
        if key in reserved:
            warnings.append(f"Shortcut key '{key}' is reserved")

        # Check playlist exists (at runtime)
        # This will be checked when shortcut is pressed

    return warnings
```

---

### Step 5: Documentation Update (10 minutes)

**Files:**
- `src/music_minion/router.py` (help text)
- `README.md` or user guide

Add to help:

```markdown
Playlist Shortcuts:
  Configure in ~/.config/music-minion/config.toml under [shortcuts.keys]
  Press configured key while playing a track to instantly add to playlist

  Example config:
    [shortcuts.keys]
    "1" = "Favorites"
    "s" = "SoundCloud Likes"

  Usage:
    1. Play a track
    2. Press "1" to add to Favorites
    3. See confirmation notification
```

---

## Testing Strategy

### Manual Testing

1. **Config Loading**
   ```bash
   # Edit config.toml, add shortcuts
   music-minion
   # Verify shortcuts loaded (check status bar)
   ```

2. **Shortcut Execution**
   ```bash
   play
   # Press "1" → should add to playlist
   # Press "x" → should do nothing (undefined)
   # Press "s" → should add to SoundCloud playlist
   ```

3. **Edge Cases**
   - No track playing → show error notification
   - Playlist doesn't exist → show error notification
   - Track already in playlist → show warning
   - Disabled shortcuts → keys work as normal

### Automated Tests (Optional)

```python
def test_shortcut_config_validation():
    config = Config()
    config.shortcuts.shortcuts = {"1": "Favorites", "tab": "Invalid"}
    warnings = validate_shortcut_config(config)
    assert len(warnings) > 0
    assert "tab" in warnings[0]

def test_shortcut_adds_track():
    # Mock setup
    ctx = create_test_context()
    state = UIState()

    # Simulate shortcut press
    new_state = handle_keyboard_input(term, state, "1", ctx)

    # Verify notification shown
    assert "Added to Favorites" in new_state.notification
```

---

## Success Criteria

- ✅ User can configure shortcuts in `config.toml`
- ✅ Pressing shortcut adds current track to playlist
- ✅ Visual confirmation shown (notification)
- ✅ Invalid shortcuts show error message
- ✅ Shortcuts appear in status bar UI
- ✅ No shortcuts = normal keyboard behavior
- ✅ Documentation updated

---

## Known Limitations

1. **Single-key shortcuts only** - Multi-key combos (Ctrl+1) not supported (blessed limitation)
2. **No dynamic shortcut editing** - Must edit config file and restart
3. **First 3 shortcuts shown** - Status bar space limited
4. **Playlist must exist** - No auto-create on shortcut press

---

## Future Enhancements (Post-MVP)

- Visual shortcut picker UI (press `?` to show all shortcuts)
- Per-playlist shortcut counter (show how many tracks added this session)
- Temporary shortcuts (session-only, not persisted)
- Shortcut to remove from playlist (undo)

---

# Full SoundCloud Integration

**Goal:** Complete OAuth authentication flow with browser-based authorization
**Estimated Time:** 4-6 hours
**Priority:** High
**Complexity:** Medium-High

## Feature Description

Enable users to authenticate with SoundCloud using OAuth 2.0 + PKCE, fetch their complete library (likes, playlists, reposts), and sync tracks to the local database with automatic deduplication.

### User Stories

1. **As a SoundCloud user**, I want to authenticate once and have my credentials securely cached
2. **As a DJ**, I want to sync my 500+ SoundCloud likes and see them deduplicated against my local library
3. **As a curator**, I want to access my private SoundCloud playlists for playlist management

### Benefits

- **Unified Library:** All music (local + SoundCloud) in one interface
- **Deduplication:** Automatic linking of SoundCloud tracks to local files
- **Offline Browsing:** SoundCloud metadata cached locally, fast search
- **Portability:** SoundCloud IDs stored in file tags

---

## Implementation Plan

### Step 1: OAuth Configuration (30 minutes)

**File:** `src/music_minion/core/config.py`

Add SoundCloud credentials:

```python
@dataclass
class SoundCloudConfig:
    """SoundCloud provider configuration."""
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    cache_duration_hours: int = 24
    sync_likes: bool = True
    sync_playlists: bool = True
    sync_reposts: bool = False
    max_tracks: int = 10000

@dataclass
class ProviderConfigs:
    local: LocalProviderConfig = field(default_factory=LocalProviderConfig)
    soundcloud: SoundCloudConfig = field(default_factory=SoundCloudConfig)
```

**TOML Example:**

```toml
[providers.soundcloud]
enabled = true
client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
redirect_uri = "http://localhost:8080/callback"
sync_likes = true
sync_playlists = true
```

**Getting Credentials:**

Users need to register a SoundCloud app at:
`https://soundcloud.com/you/apps/new`

---

### Step 2: OAuth Flow Implementation (2-3 hours)

**File:** `src/music_minion/domain/library/providers/soundcloud.py`

Complete the authentication flow:

```python
def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
    """Authenticate with SoundCloud using OAuth 2.0 + PKCE.

    Flow:
    1. Generate PKCE codes
    2. Build authorization URL
    3. Start local HTTP server
    4. Open browser to auth URL
    5. Wait for callback
    6. Exchange code for token
    7. Save tokens
    """
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
    import threading

    # Get credentials from state
    config_dict = state.cache.get('config', {})
    client_id = config_dict.get('client_id')
    client_secret = config_dict.get('client_secret')
    redirect_uri = config_dict.get('redirect_uri', 'http://localhost:8080/callback')

    if not client_id or not client_secret:
        print("❌ SoundCloud credentials not configured")
        print("Add to config.toml:")
        print("  [providers.soundcloud]")
        print("  client_id = \"YOUR_CLIENT_ID\"")
        print("  client_secret = \"YOUR_CLIENT_SECRET\"")
        return state, False

    # Generate PKCE
    pkce = _generate_pkce()
    code_verifier = pkce['code_verifier']
    code_challenge = pkce['code_challenge']

    # Generate state for CSRF protection
    csrf_state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    # Build authorization URL
    auth_url = (
        f"{AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={csrf_state}"
    )

    # Shared state for callback
    auth_result = {'code': None, 'state': None, 'error': None}

    # HTTP callback handler
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Parse callback URL
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Extract code and state
            auth_result['code'] = params.get('code', [None])[0]
            auth_result['state'] = params.get('state', [None])[0]
            auth_result['error'] = params.get('error', [None])[0]

            # Send response to browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            if auth_result['code']:
                html = """
                <html><body>
                <h1>✓ Authentication Successful!</h1>
                <p>You can close this window and return to Music Minion.</p>
                </body></html>
                """
            else:
                html = f"""
                <html><body>
                <h1>✗ Authentication Failed</h1>
                <p>Error: {auth_result['error']}</p>
                </body></html>
                """

            self.wfile.write(html.encode())

        def log_message(self, format, *args):
            pass  # Suppress server logs

    # Start local server
    server = HTTPServer(('localhost', 8080), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.daemon = True
    server_thread.start()

    # Open browser
    print("🔐 Opening browser for SoundCloud authentication...")
    print(f"If browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    # Wait for callback (with timeout)
    print("⏳ Waiting for authorization...")
    server_thread.join(timeout=120)  # 2 minute timeout

    # Check result
    if auth_result['error']:
        print(f"❌ Authorization error: {auth_result['error']}")
        return state, False

    if not auth_result['code']:
        print("❌ Authorization timeout or cancelled")
        return state, False

    # Verify CSRF state
    if auth_result['state'] != csrf_state:
        print("❌ CSRF state mismatch - possible attack!")
        return state, False

    # Exchange code for token
    print("🔄 Exchanging authorization code for access token...")

    try:
        response = requests.post(TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
            'code': auth_result['code']
        }, timeout=30)

        response.raise_for_status()
        token_data = response.json()

        # Add expiry timestamp
        expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
        token_data['expires_at'] = expires_at.isoformat()

        # Save tokens
        _save_user_tokens(token_data)

        print("✓ Authentication successful!")
        print(f"Access token expires: {expires_at.strftime('%Y-%m-%d %H:%M')}")

        # Update state
        new_state = state.with_authenticated(True)
        new_state = new_state.with_cache(token_data=token_data)

        return new_state, True

    except requests.HTTPError as e:
        print(f"❌ Token exchange failed: {e}")
        print(f"Response: {e.response.text if e.response else 'No response'}")
        return state, False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return state, False
```

**Key Components:**

1. **PKCE Generation** - Already implemented in `_generate_pkce()`
2. **Local HTTP Server** - Handles OAuth callback on `localhost:8080`
3. **Browser Opening** - Uses `webbrowser` module
4. **State Verification** - CSRF protection
5. **Token Exchange** - POST to SoundCloud token endpoint
6. **Token Storage** - Save to `~/.local/share/music-minion/soundcloud/user_tokens.json`

---

### Step 3: Token Refresh Implementation (1 hour)

**File:** `src/music_minion/domain/library/providers/soundcloud.py`

Implement automatic token refresh:

```python
def _refresh_token(token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Refresh expired OAuth token.

    Args:
        token_data: Current token data with refresh_token

    Returns:
        New token data or None if refresh fails
    """
    # Load config from somewhere (TODO: pass via state)
    # For now, hardcode path to config
    from ...core.config import load_config
    config = load_config()

    client_id = config.providers.soundcloud.client_id
    client_secret = config.providers.soundcloud.client_secret
    refresh_token = token_data.get('refresh_token')

    if not client_id or not client_secret or not refresh_token:
        return None

    try:
        response = requests.post(TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }, timeout=30)

        response.raise_for_status()
        new_token_data = response.json()

        # Add expiry timestamp
        expires_at = datetime.now() + timedelta(seconds=new_token_data['expires_in'])
        new_token_data['expires_at'] = expires_at.isoformat()

        # Save refreshed tokens
        _save_user_tokens(new_token_data)

        return new_token_data

    except Exception as e:
        print(f"Token refresh failed: {e}")
        return None
```

**Auto-refresh in sync_library:**

```python
def sync_library(state: ProviderState) -> Tuple[ProviderState, TrackList]:
    """Sync SoundCloud likes/playlists."""

    # ... existing code ...

    # Check if token expired
    if _is_token_expired(token_data):
        # Try to refresh
        new_token_data = _refresh_token(token_data)
        if new_token_data:
            _save_user_tokens(new_token_data)
            state = state.with_cache(token_data=new_token_data)
            token_data = new_token_data
        else:
            print("❌ Token expired and refresh failed")
            print("Run: library auth soundcloud")
            return state.with_authenticated(False), []

    # ... proceed with sync ...
```

---

### Step 4: Playlist Sync Implementation (1-2 hours)

**File:** `src/music_minion/domain/library/providers/soundcloud.py`

Implement playlist fetching:

```python
def get_playlists(state: ProviderState) -> Tuple[ProviderState, List[Dict[str, Any]]]:
    """Get user's SoundCloud playlists.

    Returns:
        (state, [{"id": "...", "name": "...", "track_count": N}, ...])
    """
    if not state.authenticated:
        return state, []

    token_data = state.cache.get('token_data')
    if not token_data:
        return state, []

    access_token = token_data['access_token']

    # Fetch user's playlists
    url = f"{API_BASE_URL}/me/playlists"
    headers = {'Authorization': f'OAuth {access_token}'}
    params = {'limit': 200}

    playlists = []

    try:
        while url:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Process playlists
            if 'collection' in data:
                for playlist in data['collection']:
                    playlists.append({
                        'id': str(playlist['id']),
                        'name': playlist.get('title', 'Untitled'),
                        'track_count': playlist.get('track_count', 0),
                        'description': playlist.get('description'),
                        'permalink': playlist.get('permalink_url')
                    })

            # Next page
            url = data.get('next_href')
            params = {}

        return state, playlists

    except Exception as e:
        print(f"Error fetching playlists: {e}")
        return state, []


def get_playlist_tracks(state: ProviderState, playlist_id: str) -> Tuple[ProviderState, TrackList]:
    """Get tracks in a SoundCloud playlist.

    Returns:
        (state, [(track_id, metadata), ...])
    """
    if not state.authenticated:
        return state, []

    token_data = state.cache.get('token_data')
    if not token_data:
        return state, []

    access_token = token_data['access_token']

    # Fetch playlist tracks
    url = f"{API_BASE_URL}/playlists/{playlist_id}"
    headers = {'Authorization': f'OAuth {access_token}'}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        tracks = []
        for track in playlist_data.get('tracks', []):
            if track:
                track_id = str(track['id'])
                metadata = _normalize_soundcloud_track(track)
                tracks.append((track_id, metadata))

        return state, tracks

    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return state, []
```

---

### Step 5: Enhanced Sync Command (30 minutes)

**File:** `src/music_minion/commands/library.py`

Add playlist import support:

```python
def sync_library(ctx: AppContext, provider_name: Optional[str] = None) -> Tuple[AppContext, bool]:
    """Sync library from provider."""

    # ... existing code ...

    # After syncing likes, ask about playlists
    if provider_name == 'soundcloud' and stats['total'] > 0:
        safe_print(ctx, "")
        safe_print(ctx, "📋 Checking SoundCloud playlists...", style="yellow")

        provider = providers.get_provider('soundcloud')
        new_state, playlists = provider.get_playlists(state)

        if playlists:
            safe_print(ctx, f"Found {len(playlists)} playlists:")
            for i, pl in enumerate(playlists[:5], 1):
                safe_print(ctx, f"  {i}. {pl['name']} ({pl['track_count']} tracks)")

            if len(playlists) > 5:
                safe_print(ctx, f"  ... and {len(playlists) - 5} more")

            # TODO: Interactive selection or sync all
            safe_print(ctx, "")
            safe_print(ctx, "💡 Tip: Use 'playlist import soundcloud' to import playlists", style="dim")

    return ctx, True
```

---

### Step 6: Provider State Persistence (1 hour)

**File:** `src/music_minion/core/database.py`

Add functions to save/load provider state:

```python
def save_provider_state(provider: str, auth_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Save provider authentication state to database.

    Args:
        provider: Provider name ('soundcloud', 'spotify', etc.)
        auth_data: Authentication data (tokens, expiry)
        config: Provider configuration
    """
    import json

    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO provider_state (provider, authenticated, auth_data, config, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (provider, True, json.dumps(auth_data), json.dumps(config)))
        conn.commit()


def load_provider_state(provider: str) -> Optional[Dict[str, Any]]:
    """Load provider authentication state from database.

    Returns:
        {'authenticated': bool, 'auth_data': dict, 'config': dict} or None
    """
    import json

    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT authenticated, auth_data, config
            FROM provider_state
            WHERE provider = ?
        """, (provider,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'authenticated': bool(row['authenticated']),
            'auth_data': json.loads(row['auth_data']) if row['auth_data'] else {},
            'config': json.loads(row['config']) if row['config'] else {}
        }
```

**Update `init_provider()` to load from database:**

```python
def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize SoundCloud provider."""

    # Try to load state from database
    from ...core import database
    db_state = database.load_provider_state('soundcloud')

    if db_state and db_state.get('authenticated'):
        # Load cached auth data
        auth_data = db_state['auth_data']

        # Check if token expired
        if not _is_token_expired(auth_data):
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={'token_data': auth_data}
            )

    # Not authenticated or token expired
    return ProviderState(
        config=config,
        authenticated=False,
        last_sync=None,
        cache={}
    )
```

---

## Testing Strategy

### Manual Testing

1. **OAuth Flow**
   ```bash
   music-minion
   > library auth soundcloud
   # Browser opens → authorize app → callback → token saved
   # Verify: ~/.local/share/music-minion/soundcloud/user_tokens.json exists
   ```

2. **Sync Likes**
   ```bash
   > library sync soundcloud
   # Should fetch likes, show progress
   # Verify: Database has soundcloud_id populated
   ```

3. **Deduplication**
   ```bash
   # Before sync: Have local file "Artist - Song.mp3"
   # Like same song on SoundCloud
   > library sync soundcloud
   # Verify: Local file linked to soundcloud_id (no duplicate created)
   ```

4. **Playback Fallback**
   ```bash
   > library active soundcloud
   > play
   # Should play SoundCloud stream via MPV
   ```

5. **Token Refresh**
   ```bash
   # Manually edit token expiry to past date
   > library sync soundcloud
   # Should auto-refresh token without re-authenticating
   ```

### Edge Cases

- Network timeout during OAuth
- User denies authorization
- Invalid client credentials
- Token refresh fails (re-auth required)
- Large library (1000+ tracks) - pagination
- Private tracks (permission errors)

---

## Success Criteria

- ✅ User can authenticate via browser OAuth flow
- ✅ Tokens cached and auto-refreshed
- ✅ Likes synced to database
- ✅ Playlists fetched and displayed
- ✅ Deduplication links SoundCloud → local files
- ✅ SoundCloud tracks playable via MPV
- ✅ SoundCloud IDs written to file metadata
- ✅ Provider state persists across restarts
- ✅ Error messages clear and actionable

---

## Known Limitations

1. **Local HTTP server required** - Can't use on remote SSH without port forwarding
2. **Browser dependency** - Headless systems need manual URL copy/paste
3. **SoundCloud API rate limits** - ~15 requests/second (handled by existing retry logic)
4. **Token expiry** - Refresh tokens expire after ~1 year (re-auth required)
5. **Private tracks** - Require special permissions (may not sync)

---

## Future Enhancements

- **Headless mode:** Generate auth URL, let user paste callback URL manually
- **Repost sync:** Fetch tracks user reposted
- **Following sync:** Sync tracks from followed artists
- **Upload support:** Upload local files to SoundCloud
- **Metadata sync:** Push local ratings/tags to SoundCloud (via comments?)
- **Playlist export:** Create SoundCloud playlists from Music Minion playlists

---

# Implementation Order Recommendation

## Suggested Sequence

1. **Start with Phase 8 (Playlist Shortcuts)** - Quick win, immediate value
   - Low complexity, independent feature
   - Users can start using shortcuts right away
   - Builds muscle memory for workflows

2. **Then Full SoundCloud Integration** - Bigger feature, more time
   - More complex but high value
   - Requires careful testing
   - Benefits from shortcut feature being available

## Alternative: Parallel Development

- **Developer A:** Playlist shortcuts (UI/keyboard handling)
- **Developer B:** SoundCloud OAuth (backend/API)
- No dependencies between features, can work independently

---

# Dependencies

## Required Python Packages

All already installed:
- ✅ `requests` - HTTP client for API calls
- ✅ `mutagen` - File metadata reading/writing
- ✅ `python-dotenv` - Environment variables (optional)

## System Requirements

- **Python 3.12+** ✅
- **MPV media player** ✅ (already required)
- **Web browser** (for OAuth flow)
- **Network access** (for SoundCloud API)

## Configuration Files

- `~/.config/music-minion/config.toml` - User configuration
- `~/.local/share/music-minion/soundcloud/user_tokens.json` - OAuth tokens
- `~/.local/share/music-minion/music_minion.db` - SQLite database

---

# Risk Assessment

## Phase 8: Playlist Shortcuts

**Risk Level: LOW**

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Config parsing error | High | Low | Validate on load, show warnings |
| Shortcut key conflict | Medium | Medium | Reserved key list, validation |
| Playlist doesn't exist | Low | Medium | Show error, suggest creation |
| UI rendering issues | Low | Low | Test on various terminal sizes |

## Full SoundCloud Integration

**Risk Level: MEDIUM**

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| OAuth flow breaks | High | Low | Detailed error messages, fallback URL |
| Rate limiting | Medium | Medium | Retry logic, exponential backoff |
| Token refresh fails | Medium | Low | Force re-auth with clear message |
| Large library timeout | Medium | Low | Pagination, progress indicators |
| API changes | High | Low | Version pinning, error handling |
| Network issues | Low | Medium | Timeout handling, retry logic |

---

# Success Metrics

## Phase 8: Playlist Shortcuts

- **Adoption:** % of users who configure shortcuts
- **Usage:** Average shortcut uses per session
- **Speed:** Time to add track (before: ~5s typing, after: ~0.1s keypress)

## Full SoundCloud Integration

- **Sync Success Rate:** % of sync operations that complete successfully
- **Deduplication Accuracy:** % of SoundCloud tracks correctly matched to local files
- **Authentication Success:** % of OAuth flows that complete
- **Playback Success:** % of SoundCloud tracks that play without errors

---

# Rollout Plan

## Phase 8: Playlist Shortcuts

1. **Alpha** (Internal testing)
   - Test with 3-5 shortcuts
   - Verify config loading
   - Check UI rendering

2. **Beta** (Limited release)
   - Document setup process
   - Gather user feedback on key choices
   - Iterate on UX

3. **Release**
   - Full documentation
   - Example configs in repo
   - Blog post/demo video

## Full SoundCloud Integration

1. **Alpha** (Developer testing)
   - OAuth flow testing
   - Small library sync (< 100 tracks)
   - Token refresh validation

2. **Beta** (Power users)
   - Large library testing (500+ tracks)
   - Multiple playlist types
   - Edge case hunting

3. **Release**
   - Complete documentation
   - Setup guide with screenshots
   - FAQ for common issues

---

# Documentation Deliverables

## User Documentation

1. **Playlist Shortcuts Guide**
   - How to configure shortcuts
   - Example use cases (DJ, curator)
   - Troubleshooting

2. **SoundCloud Integration Guide**
   - Getting API credentials
   - OAuth authentication walkthrough
   - Sync workflow explanation
   - Deduplication examples

## Developer Documentation

1. **Provider Interface Specification**
   - How to add new providers
   - Protocol requirements
   - Testing guidelines

2. **Architecture Diagram**
   - OAuth flow visualization
   - Data flow: SoundCloud → Database → Files
   - Component interaction map

---

# Appendix A: SoundCloud API Endpoints

## Authentication

- **Authorize:** `GET https://secure.soundcloud.com/authorize`
- **Token Exchange:** `POST https://secure.soundcloud.com/oauth/token`
- **Token Refresh:** `POST https://secure.soundcloud.com/oauth/token`

## User Resources

- **Me:** `GET /me` - Get authenticated user info
- **Likes:** `GET /me/likes/tracks` - Paginated track likes
- **Playlists:** `GET /me/playlists` - User's playlists
- **Playlist Tracks:** `GET /playlists/{id}` - Tracks in playlist

## Track Resources

- **Track Details:** `GET /tracks/{id}` - Full track metadata
- **Stream URL:** `GET /tracks/{id}/stream` - Playback URL (redirect)
- **Search:** `GET /tracks?q={query}` - Search public tracks

## Rate Limits

- **Authenticated:** ~15 requests/second
- **Client Credentials:** ~10 requests/second
- **Burst:** 100 requests allowed, then throttle

---

# Appendix B: Example Workflows

## Workflow 1: First-Time SoundCloud Setup

```bash
# 1. Edit config
vim ~/.config/music-minion/config.toml
# Add SoundCloud credentials

# 2. Start Music Minion
music-minion

# 3. Authenticate
> library auth soundcloud
# Browser opens, user authorizes

# 4. Sync likes
> library sync soundcloud
# Fetches 500 tracks, deduplicates, saves

# 5. Switch to SoundCloud library
> library active soundcloud

# 6. Play
> play
# Streams from SoundCloud via MPV
```

## Workflow 2: DJ Set Preparation with Shortcuts

```bash
# 1. Configure shortcuts in config.toml
[shortcuts.keys]
"n" = "NYE 2025"

# 2. Start Music Minion
music-minion

# 3. Play music
> play

# 4. Quick-add to playlist
# Press "n" → track added to NYE 2025
# Press "n" → next track added
# Repeat...

# 5. View playlist
> playlist show "NYE 2025"
# 50 tracks added in 5 minutes!
```

## Workflow 3: Cross-Platform Sync

```bash
# Machine A (Linux)
> library sync soundcloud
# SoundCloud IDs written to MP3 tags

# Syncthing syncs ~/Music to Machine B

# Machine B (Windows/Serato)
# Serato reads MP3 tags
# SoundCloud IDs visible in file metadata
# Can search for tracks by SoundCloud ID
```

---

# Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-18 | 1.0 | Initial plan created |

---

**End of Implementation Plan**

For questions or clarifications, refer to the main multi-source architecture documentation in `docs/multi-source-remaining-features.md`.
