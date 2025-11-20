"""
MPV player integration with JSON IPC for Music Minion CLI
Functional approach with explicit state management
"""

import json
import logging
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional, Tuple

from music_minion.core.config import Config

logger = logging.getLogger(__name__)


class PlayerState(NamedTuple):
    """Immutable player state."""

    socket_path: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    current_track: Optional[str] = None
    current_track_id: Optional[int] = None  # Database track ID for easier lookup
    is_playing: bool = False
    current_position: float = 0.0
    duration: float = 0.0


def check_mpv_available() -> bool:
    """Check if MPV is available on the system."""
    try:
        result = subprocess.run(
            ["mpv", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def start_mpv(config: Config) -> Optional[PlayerState]:
    """Start MPV with JSON IPC and return initial state."""
    # Create socket path
    if config.player.mpv_socket_path:
        socket_path = config.player.mpv_socket_path
    else:
        temp_dir = Path(tempfile.gettempdir())
        socket_path = str(temp_dir / f"mpv-socket-{os.getpid()}")

    logger.info(f"Starting MPV player with socket: {socket_path}")

    try:
        # Remove existing socket if it exists
        if os.path.exists(socket_path):
            logger.debug(f"Removing existing socket: {socket_path}")
            os.unlink(socket_path)

        # Start MPV with JSON IPC
        cmd = [
            "mpv",
            "--idle=yes",
            "--no-video",
            "--no-terminal",
            f"--input-ipc-server={socket_path}",
            f"--volume={config.player.volume}",
            "--keep-open=yes",
            "--load-scripts=no",
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # Wait for socket to be created
        timeout = 5.0
        start_time = time.time()
        while not os.path.exists(socket_path):
            if time.time() - start_time > timeout:
                logger.error(f"MPV socket creation timeout after {timeout}s")
                process.kill()
                return None
            time.sleep(0.1)

        # Test connection
        if send_mpv_command(socket_path, {"command": ["get_property", "idle-active"]}):
            logger.info("MPV started successfully")
            return PlayerState(socket_path=socket_path, process=process)
        else:
            logger.error("MPV socket connection test failed")
            process.kill()
            return None

    except (subprocess.SubprocessError, OSError) as e:
        logger.error(f"Failed to start MPV: {e}")
        print(f"Failed to start MPV: {e}")
        return None


def stop_mpv(state: PlayerState) -> None:
    """Stop MPV process and cleanup."""
    if state.process:
        try:
            send_mpv_command(state.socket_path, {"command": ["quit"]})
            state.process.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            state.process.kill()

    if state.socket_path and os.path.exists(state.socket_path):
        try:
            os.unlink(state.socket_path)
        except OSError:
            pass


def is_mpv_running(state: PlayerState) -> bool:
    """Check if MPV process is still running.

    Note: This function is called frequently (10Hz in UI loop).
    Logging only occurs on first failure detection to avoid spam.
    """
    if not state.process:
        return False

    # Check if process is still alive
    if state.process.poll() is not None:
        return False

    # Check if socket exists and is responsive
    if not state.socket_path or not os.path.exists(state.socket_path):
        return False

    return True


def send_mpv_command(socket_path: Optional[str], command: Dict[str, Any]) -> bool:
    """Send JSON IPC command to MPV."""
    if not socket_path or not os.path.exists(socket_path):
        return False

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(socket_path)

        # Send command
        command_json = json.dumps(command) + "\n"
        sock.send(command_json.encode("utf-8"))

        # Read response
        response = sock.recv(4096).decode("utf-8").strip()
        sock.close()

        if response:
            try:
                response_data = json.loads(response)
                return response_data.get("error") == "success"
            except json.JSONDecodeError:
                return False

        return True

    except (socket.error, OSError, json.JSONDecodeError):
        return False


def get_mpv_property(socket_path: Optional[str], property_name: str) -> Any:
    """Get a property value from MPV."""
    if not socket_path or not os.path.exists(socket_path):
        return None

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(socket_path)

        command = {"command": ["get_property", property_name]}
        command_json = json.dumps(command) + "\n"
        sock.send(command_json.encode("utf-8"))

        response = sock.recv(4096).decode("utf-8").strip()
        sock.close()

        if response:
            try:
                response_data = json.loads(response)
                if response_data.get("error") == "success":
                    return response_data.get("data")
            except json.JSONDecodeError:
                pass

        return None

    except (socket.error, OSError):
        return None


def play_file(state: PlayerState, local_path: str, track_id: Optional[int] = None) -> Tuple[PlayerState, bool]:
    """Play a specific audio file and return updated state.

    Args:
        state: Current player state
        local_path: Path or URL to play
        track_id: Optional database track ID for easier lookup

    Returns:
        Tuple of (updated_state, success)
    """
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["loadfile", local_path, "replace"]}
    )

    if success:
        # Poll for file load completion instead of blind sleep (faster startup)
        import time

        max_wait = 0.5
        poll_interval = 0.05
        elapsed = 0.0

        while elapsed < max_wait:
            # Check if file is loaded by querying duration
            duration = get_mpv_property(state.socket_path, "duration")
            if duration and duration > 0:
                break
            time.sleep(poll_interval)
            elapsed += poll_interval

        # Explicitly unpause to ensure playback starts
        send_mpv_command(
            state.socket_path, {"command": ["set_property", "pause", False]}
        )

        # Update status to get actual playback state
        updated_state = update_player_status(
            state._replace(current_track=local_path, current_track_id=track_id, is_playing=True)
        )
        return updated_state, True

    return state, False


def pause_playback(state: PlayerState) -> Tuple[PlayerState, bool]:
    """Pause playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["set_property", "pause", True]}
    )

    if success:
        return state._replace(is_playing=False), True

    return state, False


def resume_playback(state: PlayerState) -> Tuple[PlayerState, bool]:
    """Resume playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["set_property", "pause", False]}
    )

    if success:
        return state._replace(is_playing=True), True

    return state, False


def toggle_pause(state: PlayerState) -> Tuple[PlayerState, bool]:
    """Toggle pause/resume and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(state.socket_path, {"command": ["cycle", "pause"]})

    if success:
        return state._replace(is_playing=not state.is_playing), True

    return state, False


def stop_playback(state: PlayerState) -> Tuple[PlayerState, bool]:
    """Stop current playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(state.socket_path, {"command": ["stop"]})

    if success:
        return state._replace(current_track=None, is_playing=False), True

    return state, False


def seek_to_position(state: PlayerState, position: float) -> Tuple[PlayerState, bool]:
    """Seek to specific position in seconds and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["seek", position, "absolute"]}
    )

    if success:
        return update_player_status(state), True

    return state, False


def seek_relative(state: PlayerState, seconds: float) -> Tuple[PlayerState, bool]:
    """Seek relative to current position and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["seek", seconds, "relative"]}
    )

    if success:
        return update_player_status(state), True

    return state, False


def set_volume(state: PlayerState, volume: int) -> Tuple[PlayerState, bool]:
    """Set volume (0-100) and return updated state."""
    if not is_mpv_running(state):
        return state, False

    volume = max(0, min(100, volume))  # Clamp to 0-100
    success = send_mpv_command(
        state.socket_path, {"command": ["set_property", "volume", volume]}
    )

    return state, success


def update_player_status(state: PlayerState) -> PlayerState:
    """Update player status from MPV and return new state."""
    if not is_mpv_running(state):
        return state

    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0
    paused = get_mpv_property(state.socket_path, "pause")
    is_playing = not (paused if paused is not None else True)

    return state._replace(
        current_position=position, duration=duration, is_playing=is_playing
    )


def get_player_status(state: PlayerState) -> Dict[str, Any]:
    """Get current player status without modifying state."""
    if not is_mpv_running(state):
        return {
            "playing": False,
            "file": None,
            "position": 0.0,
            "duration": 0.0,
            "volume": 0,
        }

    # Get current values from MPV
    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0
    volume = get_mpv_property(state.socket_path, "volume") or 0
    paused = get_mpv_property(state.socket_path, "pause")
    is_playing = not (paused if paused is not None else True)

    return {
        "playing": is_playing,
        "file": state.current_track,
        "position": position,
        "duration": duration,
        "volume": volume,
    }


def get_progress_info(state: PlayerState) -> Tuple[float, float, float]:
    """Get position, duration, and progress percentage."""
    if not is_mpv_running(state):
        return 0.0, 0.0, 0.0

    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0

    if duration > 0:
        percent = (position / duration) * 100
    else:
        percent = 0.0

    return position, duration, percent


def is_track_finished(state: PlayerState) -> bool:
    """
    Check if the current track has finished playing.

    Args:
        state: Current player state

    Returns:
        True if track has ended, False otherwise
    """
    if not is_mpv_running(state):
        return False

    # Check MPV's eof-reached property (most reliable)
    eof = get_mpv_property(state.socket_path, "eof-reached")
    if eof is True:
        return True

    # Fallback: Check if position is at/near end of duration
    # Use a 0.5 second threshold to catch tracks that are effectively done
    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0

    if duration > 0 and position >= duration - 0.5:
        return True

    return False


def format_time(seconds: float) -> str:
    """Format time in seconds to MM:SS format."""
    if seconds < 0:
        return "00:00"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"
