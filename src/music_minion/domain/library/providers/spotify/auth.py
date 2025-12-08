"""
Spotify OAuth 2.0 authentication and token management.

Handles PKCE flow, token refresh, and secure token storage.
"""

import base64
import hashlib
import json
import secrets
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

import requests
from loguru import logger

from music_minion.core.output import log

from ...provider import ProviderState

# Spotify OAuth URLs
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Spotify API scopes
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


def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
    """Authenticate with Spotify using OAuth 2.0 + PKCE.

    Opens browser for user authorization, then exchanges code for token.
    Falls back to manual URL paste for headless systems.

    Args:
        state: Current provider state

    Returns:
        (new_state, success)
    """
    # Get credentials from state cache (should be injected by caller)
    config_dict = state.cache.get("config", {})
    client_id = config_dict.get("client_id")
    client_secret = config_dict.get("client_secret")
    redirect_uri = config_dict.get("redirect_uri", "http://localhost:8080/callback")

    if not client_id or not client_secret:
        log("❌ Spotify credentials not configured", level="error")
        log("\nTo get Spotify API credentials:", level="info")
        log("1. Visit: https://developer.spotify.com/dashboard", level="info")
        log("2. Create an application", level="info")
        log("3. Add redirect URI: http://localhost:8080/callback", level="info")
        log("4. Edit ~/.config/music-minion/config.toml:", level="info")
        log("\n   [spotify]", level="info")
        log("   enabled = true", level="info")
        log('   client_id = "YOUR_CLIENT_ID"', level="info")
        log('   client_secret = "YOUR_CLIENT_SECRET"', level="info")
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
    scope_string = " ".join(SPOTIFY_SCOPES)
    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": csrf_state,
        "scope": scope_string,
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

        log("🔐 Starting Spotify authentication...", level="info")
        log(f"Callback server listening on port {port}", level="info")
        logger.debug(f"Authorization URL: {auth_url}")

        # Try to open browser
        browser_opened = False
        try:
            browser_opened = webbrowser.open(auth_url)
        except Exception as e:
            logger.debug(f"Failed to open browser: {e}")

        if browser_opened:
            log("✓ Browser opened for authorization", level="info")
        else:
            log("\n⚠ Could not open browser automatically", level="warning")
            log("\nPlease open this URL in your browser:", level="info")
            log(f"\n{auth_url}\n", level="info")

        log("\n⏳ Waiting for authorization (120 seconds timeout)...", level="info")
        server_thread.join(timeout=120)  # 2 minute timeout

    except OSError as e:
        # Could not start server (port in use, etc.)
        log(f"\n⚠ Could not start callback server: {e}", level="warning")
        log("\n📋 Manual authorization mode:", level="info")
        log(f"\n1. Open this URL in your browser:\n{auth_url}\n", level="info")
        log("2. After authorizing, you'll be redirected to a URL", level="info")
        log("3. Copy the FULL redirect URL and paste it here", level="info")
        logger.warning(f"Callback server error: {e}")

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
            log("\n❌ Authorization cancelled", level="error")
            return state, False

    finally:
        if server:
            server.server_close()

    # Check result
    if not auth_result["received"]:
        log("❌ Authorization timeout - no response received", level="error")
        logger.warning("Authorization timeout after 120 seconds")
        return state, False

    if auth_result["error"]:
        log(f"❌ Authorization error: {auth_result['error']}", level="error")
        logger.error(f"Authorization error from Spotify: {auth_result['error']}")
        return state, False

    if not auth_result["code"]:
        log("❌ No authorization code received", level="error")
        logger.error("Missing authorization code in callback")
        return state, False

    # Verify CSRF state
    if auth_result["state"] != csrf_state:
        log("❌ CSRF state mismatch - possible security attack!", level="error")
        log("Please try authenticating again.", level="info")
        logger.error(
            f"CSRF state mismatch: expected {csrf_state}, got {auth_result['state']}"
        )
        return state, False

    # Exchange code for tokens
    log("\n🔄 Exchanging authorization code for access token...", level="info")
    logger.debug("Exchanging authorization code for tokens")

    try:
        # Spotify requires Basic auth for token exchange
        auth_header = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("utf-8")

        token_response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_result["code"],
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={"Authorization": f"Basic {auth_header}"},
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
        logger.info(f"Spotify authentication successful, token expires: {expires_at}")

        log("✓ Authentication successful!", level="info")
        log(
            f"Access token expires: {expires_at.strftime('%Y-%m-%d %H:%M')}",
            level="info",
        )

        # Update state
        new_state = state.with_authenticated(True)
        new_state = new_state.with_cache(token_data=token_data)

        return new_state, True

    except requests.HTTPError as e:
        log(f"❌ Token exchange failed: {e}", level="error")
        logger.exception("Token exchange HTTP error")
        if e.response:
            try:
                error_data = e.response.json()
                log(
                    f"Error details: {error_data.get('error_description', error_data)}",
                    level="error",
                )
                logger.error(f"Spotify API error: {error_data}")
            except Exception:
                log(f"Response: {e.response.text}", level="error")
                logger.error(f"Response text: {e.response.text}")
        return state, False
    except Exception as e:
        log(f"❌ Authentication error: {e}", level="error")
        logger.exception("Unexpected authentication error")
        return state, False


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

    tokens_dir = get_data_dir() / "spotify"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    return tokens_dir


def _load_user_tokens() -> Optional[Dict[str, Any]]:
    """Load user OAuth tokens from file."""
    tokens_file = _get_tokens_dir() / "user_tokens.json"

    if not tokens_file.exists():
        return None

    try:
        with open(tokens_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load Spotify tokens from file: {e}")
        return None


def _save_user_tokens(token_data: Dict[str, Any]) -> None:
    """Save user OAuth tokens to file with secure permissions."""
    tokens_file = _get_tokens_dir() / "user_tokens.json"

    with open(tokens_file, "w") as f:
        json.dump(token_data, f, indent=2)

    # Set file permissions to 0600 (owner read/write only)
    tokens_file.chmod(0o600)
    logger.debug(f"Saved Spotify tokens to {tokens_file}")


def is_token_expired(token_data: Dict[str, Any]) -> bool:
    """Check if token is expired (with 5-minute buffer)."""
    if "expires_at" not in token_data:
        return True

    expires_at = datetime.fromisoformat(token_data["expires_at"])
    buffer = timedelta(minutes=5)

    return datetime.now() >= (expires_at - buffer)


def refresh_token(token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Refresh expired OAuth token.

    Args:
        token_data: Current token data with refresh_token

    Returns:
        New token data or None if refresh fails
    """
    # Load config to get client credentials
    from music_minion.core.config import load_config

    config = load_config()

    client_id = config.spotify.client_id
    client_secret = config.spotify.client_secret
    refresh_token_value = token_data.get("refresh_token")

    if not client_id or not client_secret or not refresh_token_value:
        logger.warning("Missing credentials or refresh token for Spotify token refresh")
        return None

    try:
        # Spotify requires Basic auth for token refresh
        auth_header = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("utf-8")

        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token_value,
            },
            headers={"Authorization": f"Basic {auth_header}"},
            timeout=30,
        )

        response.raise_for_status()
        new_token_data = response.json()

        # Add expiry timestamp
        expires_in = new_token_data.get("expires_in", 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        new_token_data["expires_at"] = expires_at.isoformat()

        # Preserve refresh token if not included in response
        if "refresh_token" not in new_token_data:
            new_token_data["refresh_token"] = refresh_token_value

        # Save refreshed tokens
        _save_user_tokens(new_token_data)
        logger.info(f"Spotify token refreshed successfully, expires: {expires_at}")

        return new_token_data

    except requests.HTTPError as e:
        logger.warning(f"Failed to refresh Spotify token: {e}")
        if e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"Spotify token refresh error: {error_data}")
            except Exception:
                logger.error(f"Spotify response: {e.response.text}")
        return None
    except Exception as e:
        logger.warning(f"Failed to refresh Spotify token: {e}")
        return None
