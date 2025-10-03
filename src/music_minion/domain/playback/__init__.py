"""Playback domain - MPV integration and state management.

This domain handles:
- MPV player integration via JSON IPC
- Player state management (playing, paused, stopped)
- Shuffle mode and sequential playback
- Playlist position tracking
"""

# Player integration
from .player import (
    PlayerState,
    check_mpv_available,
    start_mpv,
    stop_mpv,
    is_mpv_running,
    send_mpv_command,
    get_mpv_property,
    play_file,
    pause_playback,
    resume_playback,
    toggle_pause,
    stop_playback,
    seek_to_position,
    seek_relative,
    set_volume,
    update_player_status,
    get_player_status,
    get_progress_info,
    is_track_finished,
    format_time,
)

# State management
from .state import (
    get_shuffle_mode,
    set_shuffle_mode,
    update_playlist_position,
    get_playlist_position,
    clear_playlist_position,
    get_next_sequential_track,
    get_track_position_in_playlist,
)

__all__ = [
    # Player
    "PlayerState",
    "check_mpv_available",
    "start_mpv",
    "stop_mpv",
    "is_mpv_running",
    "send_mpv_command",
    "get_mpv_property",
    "play_file",
    "pause_playback",
    "resume_playback",
    "toggle_pause",
    "stop_playback",
    "seek_to_position",
    "seek_relative",
    "set_volume",
    "update_player_status",
    "get_player_status",
    "get_progress_info",
    "is_track_finished",
    "format_time",
    # State
    "get_shuffle_mode",
    "set_shuffle_mode",
    "update_playlist_position",
    "get_playlist_position",
    "clear_playlist_position",
    "get_next_sequential_track",
    "get_track_position_in_playlist",
]
