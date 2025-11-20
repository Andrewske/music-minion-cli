"""
SoundCloud OAuth 2.0 authentication and token management.

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

from ...provider import ProviderState

# SoundCloud OAuth URLs
AUTHORIZE_URL = "https://secure.soundcloud.com/authorize"
TOKEN_URL = "https://secure.soundcloud.com/oauth/token"


def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
    """Authenticate with SoundCloud using OAuth 2.0 + PKCE.

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

    client_id = config.soundcloud.client_id
    client_secret = config.soundcloud.client_secret
    refresh_token_value = token_data.get("refresh_token")

    if not client_id or not client_secret or not refresh_token_value:
        return None

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token_value,
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

    except Exception:
        # Silently fail - caller will handle None return
        return None
