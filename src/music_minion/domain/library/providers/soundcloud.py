"""
SoundCloud provider for Music Minion.

Implements OAuth 2.0 authentication and API access for SoundCloud.
Adapted from soundcloud-discovery project.
"""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..provider import ProviderConfig, ProviderState, TrackList

# SoundCloud API URLs
AUTHORIZE_URL = "https://secure.soundcloud.com/authorize"
TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
API_BASE_URL = "https://api.soundcloud.com"


def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize SoundCloud provider.

    Tries to load state from database first, then falls back to file tokens.

    Args:
        config: Provider configuration

    Returns:
        Initial provider state
    """
    from music_minion.core import database

    # Try to load state from database
    db_state = database.load_provider_state("soundcloud")

    if db_state and db_state.get("authenticated"):
        # Load cached auth data
        auth_data = db_state["auth_data"]

        # Check if token expired
        if not _is_token_expired(auth_data):
            return ProviderState(
                config=config,
                authenticated=True,
                last_sync=None,
                cache={"token_data": auth_data},
            )

    # Fall back to file-based tokens (for backward compatibility)
    token_data = _load_user_tokens()

    if token_data and not _is_token_expired(token_data):
        # Have valid token from file
        return ProviderState(
            config=config,
            authenticated=True,
            last_sync=None,
            cache={"token_data": token_data},
        )

    # Not authenticated or token expired
    return ProviderState(config=config, authenticated=False, last_sync=None, cache={})


def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
    """Authenticate with SoundCloud using OAuth 2.0 + PKCE.

    Opens browser for user authorization, then exchanges code for token.
    Falls back to manual URL paste for headless systems.

    Args:
        state: Current provider state

    Returns:
        (new_state, success)
    """
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, quote, urlparse

    # Get credentials from state cache (should be injected by caller)
    config_dict = state.cache.get("config", {})
    client_id = config_dict.get("client_id")
    client_secret = config_dict.get("client_secret")
    redirect_uri = config_dict.get("redirect_uri", "http://localhost:8080/callback")

    if not client_id or not client_secret:
        print("❌ SoundCloud credentials not configured")
        print("\nTo get SoundCloud API credentials:")
        print("1. Visit: https://soundcloud.com/you/apps/new")
        print("2. Register an application")
        print("3. Edit ~/.config/music-minion/config.toml:")
        print("\n   [soundcloud]")
        print("   enabled = true")
        print('   client_id = "YOUR_CLIENT_ID"')
        print('   client_secret = "YOUR_CLIENT_SECRET"')
        return state, False

    # Generate PKCE challenge
    pkce = _generate_pkce()
    code_verifier = pkce["code_verifier"]
    code_challenge = pkce["code_challenge"]

    # Generate CSRF state token
    csrf_state = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    )

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": csrf_state,
        "scope": "non-expiring",  # Request non-expiring token
    }
    auth_url = (
        AUTHORIZE_URL
        + "?"
        + "&".join(f"{k}={quote(str(v))}" for k, v in auth_params.items())
    )

    # Shared state for callback
    auth_result = {"code": None, "state": None, "error": None, "received": False}

    # HTTP callback handler
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Parse callback URL
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Extract code and state
            auth_result["code"] = params.get("code", [None])[0]
            auth_result["state"] = params.get("state", [None])[0]
            auth_result["error"] = params.get("error", [None])[0]
            auth_result["received"] = True

            # Send response to browser
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            if auth_result["code"]:
                html = """
                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #28a745;">✓ Authentication Successful!</h1>
                <p>You can close this window and return to Music Minion.</p>
                </body></html>
                """
            else:
                error_msg = auth_result["error"] or "Unknown error"
                html = f"""
                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #dc3545;">✗ Authentication Failed</h1>
                <p>Error: {error_msg}</p>
                <p>Please try again or check your credentials.</p>
                </body></html>
                """

            self.wfile.write(html.encode())

        def log_message(self, format, *args):
            pass  # Suppress server logs

    # Try to start local server
    server = None
    try:
        # Parse port from redirect_uri
        parsed_redirect = urlparse(redirect_uri)
        port = parsed_redirect.port or 8080

        server = HTTPServer(("localhost", port), CallbackHandler)
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.daemon = True
        server_thread.start()

        print("🔐 Starting SoundCloud authentication...")
        print(f"Callback server listening on port {port}")

        # Try to open browser
        browser_opened = False
        try:
            browser_opened = webbrowser.open(auth_url)
        except Exception:
            pass

        if browser_opened:
            print("✓ Browser opened for authorization")
        else:
            print("\n⚠ Could not open browser automatically")
            print("\nPlease open this URL in your browser:")
            print(f"\n{auth_url}\n")

        print("\n⏳ Waiting for authorization (120 seconds timeout)...")
        server_thread.join(timeout=120)  # 2 minute timeout

    except OSError as e:
        # Could not start server (port in use, etc.)
        print(f"\n⚠ Could not start callback server: {e}")
        print("\n📋 Manual authorization mode:")
        print(f"\n1. Open this URL in your browser:\n{auth_url}\n")
        print("2. After authorizing, you'll be redirected to a URL")
        print("3. Copy the FULL redirect URL and paste it here")

        try:
            callback_url = input("\nPaste the callback URL: ").strip()
            if callback_url:
                # Parse the pasted URL
                parsed = urlparse(callback_url)
                params = parse_qs(parsed.query)
                auth_result["code"] = params.get("code", [None])[0]
                auth_result["state"] = params.get("state", [None])[0]
                auth_result["error"] = params.get("error", [None])[0]
                auth_result["received"] = True
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Authorization cancelled")
            return state, False

    finally:
        if server:
            server.server_close()

    # Check result
    if not auth_result["received"]:
        print("❌ Authorization timeout - no response received")
        return state, False

    if auth_result["error"]:
        print(f"❌ Authorization error: {auth_result['error']}")
        return state, False

    if not auth_result["code"]:
        print("❌ No authorization code received")
        return state, False

    # Verify CSRF state
    if auth_result["state"] != csrf_state:
        print("❌ CSRF state mismatch - possible security attack!")
        print("Please try authenticating again.")
        return state, False

    # Exchange code for tokens
    print("\n🔄 Exchanging authorization code for access token...")

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "code": auth_result["code"],
            },
            timeout=30,
        )

        token_response.raise_for_status()
        token_data = token_response.json()

        # Add expiry timestamp
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        token_data["expires_at"] = expires_at.isoformat()

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
        if e.response:
            try:
                error_data = e.response.json()
                print(
                    f"Error details: {error_data.get('error_description', error_data)}"
                )
            except Exception:
                print(f"Response: {e.response.text}")
        return state, False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return state, False


def sync_library(state: ProviderState, incremental: bool = True) -> Tuple[ProviderState, TrackList]:
    """Sync SoundCloud likes/playlists.

    Performs incremental sync by default - only fetches new likes since last sync.
    Stops when encountering a track that's already been imported.

    Args:
        state: Current provider state
        incremental: If True, stop at first existing track; if False, fetch all (default: True)

    Returns:
        (new_state, [(track_id, metadata), ...])
    """
    if not state.authenticated:
        return state, []

    token_data = state.cache.get("token_data")
    if not token_data:
        return state, []

    # Check if token expired
    if _is_token_expired(token_data):
        # Try to refresh
        new_token_data = _refresh_token(token_data)
        if new_token_data:
            _save_user_tokens(new_token_data)
            state = state.with_cache(token_data=new_token_data)
            token_data = new_token_data
        else:
            return state.with_authenticated(False), []

    access_token = token_data["access_token"]

    # Get existing SoundCloud IDs for incremental sync
    from music_minion.core import database

    existing_ids = set()
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT soundcloud_id FROM tracks WHERE soundcloud_id IS NOT NULL AND source = 'soundcloud'"
            )
            existing_ids = {row[0] for row in cursor.fetchall()}

        if existing_ids:
            print(f"  Found {len(existing_ids)} existing SoundCloud tracks in database")
    except Exception as e:
        print(f"  Warning: Could not load existing tracks for incremental sync: {e}")
        print("  Proceeding with full sync...")

    # Fetch user's likes
    tracks = _fetch_user_likes(
        access_token, existing_ids=existing_ids, incremental=incremental
    )

    new_state = state.with_sync_time()
    return new_state, tracks


def search(state: ProviderState, query: str) -> Tuple[ProviderState, TrackList]:
    """Search SoundCloud tracks.

    Args:
        state: Current provider state
        query: Search query

    Returns:
        (state, [(track_id, metadata), ...])
    """
    # Use client credentials for public search
    try:
        token = _get_client_credentials_token()
    except Exception:
        return state, []

    # Search API
    url = f"{API_BASE_URL}/tracks"
    params = {"q": query, "limit": 50}
    headers = {"Authorization": f"OAuth {token}"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        tracks = []
        if "collection" in data:
            for track in data["collection"]:
                track_id = str(track["id"])
                metadata = _normalize_soundcloud_track(track)
                tracks.append((track_id, metadata))

        return state, tracks
    except Exception:
        return state, []


def get_stream_url(state: ProviderState, provider_id: str) -> Optional[str]:
    """Get SoundCloud stream URL.

    Args:
        state: Current provider state
        provider_id: SoundCloud track ID

    Returns:
        Stream URL or None
    """
    if not state.authenticated:
        return None

    token_data = state.cache.get("token_data")
    if not token_data:
        return None

    access_token = token_data["access_token"]

    # SoundCloud stream URL
    # MPV will follow the redirect to the actual progressive HTTP stream
    return f"{API_BASE_URL}/tracks/{provider_id}/stream?oauth_token={access_token}"


def get_playlists(state: ProviderState) -> Tuple[ProviderState, List[Dict[str, Any]]]:
    """Get user's SoundCloud playlists.

    Args:
        state: Current provider state

    Returns:
        (state, [{"id": "...", "name": "...", "track_count": N}, ...])
    """
    if not state.authenticated:
        return state, []

    token_data = state.cache.get("token_data")
    if not token_data:
        return state, []

    access_token = token_data["access_token"]

    # Fetch user's playlists
    url = f"{API_BASE_URL}/me/playlists"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"limit": 200}

    playlists = []

    try:
        while url:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Handle both list and dict responses
            if isinstance(data, list):
                collection = data
            elif isinstance(data, dict) and "collection" in data:
                collection = data["collection"]
            else:
                collection = []

            # Process playlists
            for playlist in collection:
                playlists.append(
                    {
                        "id": str(playlist["id"]),
                        "name": playlist.get("title", "Untitled"),
                        "track_count": playlist.get("track_count", 0),
                        "description": playlist.get("description"),
                        "permalink": playlist.get("permalink_url"),
                    }
                )

            # Next page (only for dict responses with pagination)
            url = data.get("next_href") if isinstance(data, dict) else None
            params = {}  # Pagination URL contains all params

        return state, playlists

    except Exception as e:
        print(f"Error fetching playlists: {e}")
        return state, []


def get_playlist_tracks(
    state: ProviderState, playlist_id: str
) -> Tuple[ProviderState, TrackList]:
    """Get tracks in a SoundCloud playlist.

    Args:
        state: Current provider state
        playlist_id: SoundCloud playlist ID

    Returns:
        (state, [(track_id, metadata), ...])
    """
    if not state.authenticated:
        return state, []

    token_data = state.cache.get("token_data")
    if not token_data:
        return state, []

    access_token = token_data["access_token"]

    # Fetch playlist tracks
    url = f"{API_BASE_URL}/playlists/{playlist_id}"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"show_tracks": True}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        tracks = []
        for track in playlist_data.get("tracks", []):
            if track:
                track_id = str(track["id"])
                metadata = _normalize_soundcloud_track(track)
                tracks.append((track_id, metadata))

        return state, tracks

    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return state, []


# ============================================================================
# Private helper functions (adapted from soundcloud-discovery)
# ============================================================================


def _generate_pkce() -> Dict[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    )
    challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")
    )

    return {"code_verifier": code_verifier, "code_challenge": code_challenge}


def _get_tokens_dir() -> Path:
    """Get directory for storing tokens."""
    from music_minion.core.config import get_data_dir

    tokens_dir = get_data_dir() / "soundcloud"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    return tokens_dir


def _load_user_tokens() -> Optional[Dict[str, Any]]:
    """Load user OAuth tokens from file."""
    tokens_file = _get_tokens_dir() / "user_tokens.json"

    if not tokens_file.exists():
        return None

    with open(tokens_file) as f:
        return json.load(f)


def _save_user_tokens(token_data: Dict[str, Any]) -> None:
    """Save user OAuth tokens to file with secure permissions."""
    tokens_file = _get_tokens_dir() / "user_tokens.json"

    with open(tokens_file, "w") as f:
        json.dump(token_data, f, indent=2)

    # Set file permissions to 0600 (owner read/write only)
    tokens_file.chmod(0o600)


def _is_token_expired(token_data: Dict[str, Any]) -> bool:
    """Check if token is expired (with 5-minute buffer)."""
    if "expires_at" not in token_data:
        return True

    expires_at = datetime.fromisoformat(token_data["expires_at"])
    buffer = timedelta(minutes=5)

    return datetime.now() >= (expires_at - buffer)


def _refresh_token(token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Refresh expired OAuth token.

    Args:
        token_data: Current token data with refresh_token

    Returns:
        New token data or None if refresh fails
    """
    # Load config to get client credentials
    from music_minion.core.config import load_config

    config = load_config()

    client_id = config.soundcloud.client_id
    client_secret = config.soundcloud.client_secret
    refresh_token = token_data.get("refresh_token")

    if not client_id or not client_secret or not refresh_token:
        return None

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )

        response.raise_for_status()
        new_token_data = response.json()

        # Add expiry timestamp
        expires_in = new_token_data.get("expires_in", 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        new_token_data["expires_at"] = expires_at.isoformat()

        # Save refreshed tokens
        _save_user_tokens(new_token_data)

        return new_token_data

    except Exception as e:
        print(f"Token refresh failed: {e}")
        return None


def _get_client_credentials_token() -> str:
    """Get access token using Client Credentials flow (for public data).

    Returns:
        Access token for client credentials

    Raises:
        ValueError: If client credentials are not configured
    """
    tokens_file = _get_tokens_dir() / "app_token.json"

    # Try cached token
    if tokens_file.exists():
        with open(tokens_file) as f:
            token_data = json.load(f)

        if not _is_token_expired(token_data):
            return token_data["access_token"]

    # Load config to get client credentials
    from music_minion.core.config import load_config

    config = load_config()

    client_id = config.soundcloud.client_id
    client_secret = config.soundcloud.client_secret

    if not client_id or not client_secret:
        raise ValueError("SoundCloud client credentials not configured in config.toml")

    # Request new token
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )

        response.raise_for_status()
        token_data = response.json()

        # Add expiry timestamp
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        token_data["expires_at"] = expires_at.isoformat()

        # Save to cache
        with open(tokens_file, "w") as f:
            json.dump(token_data, f, indent=2)

        return token_data["access_token"]

    except Exception as e:
        raise ValueError(f"Failed to get client credentials token: {e}")


def _fetch_user_likes(
    access_token: str, existing_ids: Optional[set] = None, incremental: bool = True
) -> TrackList:
    """Fetch user's liked tracks from SoundCloud.

    Args:
        access_token: OAuth access token
        existing_ids: Set of SoundCloud IDs already in database (for incremental sync)
        incremental: If True, stop fetching when encountering an existing track

    Returns:
        List of (track_id, metadata) tuples
    """
    if existing_ids is None:
        existing_ids = set()

    tracks = []
    url = f"{API_BASE_URL}/me/likes/tracks"
    headers = {"Authorization": f"OAuth {access_token}"}

    # Pagination
    params = {
        "limit": 200,
        "linked_partitioning": True,  # Enable cursor-based pagination
        "access": "playable",
    }

    page = 0
    stopped_early = False

    try:
        while url:
            page += 1
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Process tracks
            page_tracks = 0
            found_existing = False

            if "collection" in data:
                for item in data["collection"]:
                    # Filter to only tracks (API may return other kinds)
                    if not item or item.get("kind") != "track":
                        continue

                    track_id = str(item["id"])

                    # Incremental sync: stop if we've already imported this track
                    if incremental and track_id in existing_ids:
                        print(
                            f"  ✓ Found existing track {track_id} - stopping incremental sync"
                        )
                        found_existing = True
                        stopped_early = True
                        break

                    metadata = _normalize_soundcloud_track(item)
                    tracks.append((track_id, metadata))
                    page_tracks += 1

            # Progress update
            status = " (stopped - found existing)" if found_existing else ""
            print(
                f"  Page {page}: +{page_tracks} tracks (total: {len(tracks)}){status}"
            )

            # Stop if we found an existing track
            if found_existing:
                break

            # Next page
            url = data.get("next_href")
            params = {}  # Pagination URL contains all params

    except Exception as e:
        print(f"Error fetching likes: {e}")

    if stopped_early and len(tracks) > 0:
        print(f"  ✓ Incremental sync: fetched {len(tracks)} new tracks")

    return tracks


def _normalize_soundcloud_track(track: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize SoundCloud track data to standard metadata format."""
    metadata = {
        "title": track.get("title", "").strip(),
        "artist": (
            track.get("metadata_artist") or track.get("user", {}).get("username", "")
        ).strip(),
        "genre": track.get("genre", "").strip() if track.get("genre") else None,
        "duration": track.get("duration", 0) / 1000.0
        if track.get("duration")
        else None,  # ms to seconds
        "year": None,  # SoundCloud doesn't provide year in API
        "bpm": None,  # Initialize to None, set below if available
    }

    # BPM if available
    if track.get("bpm"):
        try:
            metadata["bpm"] = float(track["bpm"])
        except (ValueError, TypeError):
            pass

    # Keep None values for consistent field set across all tracks
    # This prevents "binding parameter" errors during batch insert
    return metadata
