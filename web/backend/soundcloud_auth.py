"""SoundCloud auth helper for web backend."""
import json
import os
from pathlib import Path

from music_minion.domain.library.provider import ProviderConfig, ProviderState


def _get_token_path() -> Path:
    """Get the path to SoundCloud user tokens (same as CLI).

    Uses XDG_DATA_HOME if set, otherwise ~/.local/share/music-minion.
    """
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        data_dir = Path(data_home) / "music-minion"
    else:
        data_dir = Path.home() / ".local" / "share" / "music-minion"
    return data_dir / "soundcloud" / "user_tokens.json"


def get_web_provider_state() -> ProviderState | None:
    """Load SoundCloud ProviderState from saved tokens.

    Returns None if not authenticated.
    """
    token_path = _get_token_path()
    if not token_path.exists():
        return None
    try:
        token_data = json.loads(token_path.read_text())
        config = ProviderConfig(name="soundcloud")
        return ProviderState(
            config=config,
            authenticated=True,
            cache={"token_data": token_data},
        )
    except (json.JSONDecodeError, KeyError):
        return None
