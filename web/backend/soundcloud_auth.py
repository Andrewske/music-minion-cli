"""SoundCloud auth helper for web backend."""
import json
from pathlib import Path

from music_minion.domain.library.provider import ProviderState


def get_web_provider_state() -> ProviderState | None:
    """Load SoundCloud ProviderState from saved tokens.

    Returns None if not authenticated.
    """
    token_path = Path.home() / ".music-minion" / "soundcloud_token.json"
    if not token_path.exists():
        return None
    try:
        token_data = json.loads(token_path.read_text())
        return ProviderState(authenticated=True, cache={"token_data": token_data})
    except (json.JSONDecodeError, KeyError):
        return None
