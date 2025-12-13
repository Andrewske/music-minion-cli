"""
MPV player integration with JSON IPC for Music Minion CLI
Functional approach with explicit state management
"""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, NamedTuple, Optional

from loguru import logger

from music_minion.core.config import Config
from music_minion.core.database import start_listen_session, tick_listen_session

# Minimum valid duration (seconds) - durations below this indicate metadata errors
MIN_VALID_DURATION = 10.0

# Minimum playback time before allowing "track finished" (seconds)
MIN_PLAYBACK_TIME = 3.0


class PlayerState(NamedTuple):
    """Immutable player state."""

    socket_path: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    current_track: Optional[str] = None
    current_track_id: Optional[int] = None  # Database track ID for easier lookup
    is_playing: bool = False
    current_position: float = 0.0
    duration: float = 0.0
    playback_source: Optional[str] = None  # 'mpv' or 'spotify'
    current_session_id: Optional[int] = None  # Active listening session ID
    playback_started_at: Optional[float] = None  # NEW: Unix timestamp

    def __getattr__(self, name: str) -> Any:
        """Provide helpful error for missing attributes, especially with_* methods."""
        if name.startswith("with_"):
            raise AttributeError(
                f"PlayerState is a NamedTuple and does not have '{name}' method. "
                f"Use '._replace({name[5:]}=value)' instead. "
                f"For example: state._replace(current_track='new_track')"
            )
        raise AttributeError(f"PlayerState has no attribute '{name}'")


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
            state.process.kill()
            state.process.wait(timeout=2.0)
        except (OSError, subprocess.TimeoutExpired):
            pass  # Process already terminated or couldn't be killed
        except Exception as e:
            logger.warning(f"Unexpected error during MPV cleanup: {e}")

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


def send_mpv_command(socket_path: Optional[str], command: dict[str, Any]) -> bool:
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


def play_file(
    state: PlayerState,
    local_path: str,
    track_id: Optional[int] = None,
    playlist_id: Optional[int] = None,
) -> tuple[PlayerState, bool]:
    """Play a specific audio file and return updated state.

    Args:
        state: Current player state
        local_path: Path or URL to play
        track_id: Optional database track ID for easier lookup
        playlist_id: Optional playlist ID for session tracking

    Returns:
        Tuple of (updated_state, success)
    """
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["loadfile", local_path, "replace"]}
    )

    if success:
        # Wait for file metadata with stability checks
        import time

        max_wait = 2.0  # Increased from 0.5s for network streams
        poll_interval = 0.05
        elapsed = 0.0
        duration_loaded = False
        last_duration = None
        stable_reads = 0
        required_stable_reads = 2

        logger.debug(f"Loading file metadata for: {local_path}")

        while elapsed < max_wait:
            duration = get_mpv_property(state.socket_path, "duration")

            if duration and duration > 0:
                if last_duration is not None and abs(duration - last_duration) < 0.1:
                    stable_reads += 1
                    if stable_reads >= required_stable_reads:
                        logger.info(
                            f"Metadata loaded: duration={duration:.2f}s, elapsed={elapsed:.3f}s"
                        )
                        duration_loaded = True
                        break
                else:
                    stable_reads = 0

                last_duration = duration

            time.sleep(poll_interval)
            elapsed += poll_interval

        if not duration_loaded:
            logger.warning(
                f"Metadata load incomplete after {max_wait}s: duration={last_duration}"
            )

        # Explicitly unpause to ensure playback starts
        send_mpv_command(
            state.socket_path, {"command": ["set_property", "pause", False]}
        )

        # Start new listening session if we have a track_id
        session_id = None
        if track_id is not None:
            try:
                session_id = start_listen_session(track_id, playlist_id)
            except Exception:
                logger.exception(
                    f"Failed to start listening session: track_id={track_id}, playlist_id={playlist_id}"
                )

        # Update status to get actual playback state

        updated_state = update_player_status(
            state._replace(
                current_track=local_path,
                current_track_id=track_id,
                is_playing=True,
                playback_source="mpv",
                current_session_id=session_id,
                playback_started_at=time.time(),  # NEW
            )
        )
        return updated_state, True

    return state, False


def pause_playback(state: PlayerState) -> tuple[PlayerState, bool]:
    """Pause playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["set_property", "pause", True]}
    )

    if success:
        # Note: Session continues but won't be ticked while paused
        return state._replace(is_playing=False), True

    return state, False


def resume_playback(state: PlayerState) -> tuple[PlayerState, bool]:
    """Resume playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["set_property", "pause", False]}
    )

    if success:
        # Resume ticking the current session
        return state._replace(is_playing=True), True

    return state, False


def toggle_pause(state: PlayerState) -> tuple[PlayerState, bool]:
    """Toggle pause/resume and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(state.socket_path, {"command": ["cycle", "pause"]})

    if success:
        return state._replace(is_playing=not state.is_playing), True

    return state, False


def stop_playback(state: PlayerState) -> tuple[PlayerState, bool]:
    """Stop playback and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(state.socket_path, {"command": ["stop"]})

    if success:
        # Session ends when playback stops
        return state._replace(
            current_track=None,
            current_track_id=None,
            is_playing=False,
            current_position=0.0,
            duration=0.0,
            current_session_id=None,  # Clear session on stop
            playback_started_at=None,  # NEW
        ), True

    return state, False


def tick_session(state: PlayerState) -> PlayerState:
    """Tick the current listening session if playing.

    Should be called every second during playback.

    Args:
        state: Current player state

    Returns:
        Updated state (unchanged, but session is ticked)
    """
    if state.current_session_id is not None and state.is_playing:
        try:
            tick_listen_session(state.current_session_id, state.is_playing)
        except Exception:
            logger.exception(
                f"Failed to tick listening session: session_id={state.current_session_id}"
            )

    return state


def seek_to_position(state: PlayerState, position: float) -> tuple[PlayerState, bool]:
    """Seek to specific position in seconds and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["seek", position, "absolute"]}
    )

    if success:
        # Brief wait for MPV to process seek before querying status
        time.sleep(0.05)
        # Use position-only update to preserve is_playing state
        return update_player_position_only(state), True

    return state, False


def seek_relative(state: PlayerState, seconds: float) -> tuple[PlayerState, bool]:
    """Seek relative to current position and return updated state."""
    if not is_mpv_running(state):
        return state, False

    success = send_mpv_command(
        state.socket_path, {"command": ["seek", seconds, "relative"]}
    )

    if success:
        # Brief wait for MPV to process seek before querying status
        time.sleep(0.05)
        # Use position-only update to preserve is_playing state
        return update_player_position_only(state), True

    return state, False


def set_volume(state: PlayerState, volume: int) -> tuple[PlayerState, bool]:
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

    position = get_mpv_property(state.socket_path, "time-pos")
    duration = get_mpv_property(state.socket_path, "duration")
    paused = get_mpv_property(state.socket_path, "pause")

    # Preserve previous state if query fails (None) to prevent 0:00 display during seek
    return state._replace(
        current_position=position if position is not None else state.current_position,
        duration=duration if duration is not None else state.duration,
        is_playing=not paused if paused is not None else state.is_playing,
    )


def update_player_position_only(state: PlayerState) -> PlayerState:
    """Update only position/duration after seek - preserves is_playing state.

    Used after seek operations to avoid MPV briefly reporting paused=True
    during seek processing, which would cause is_playing to become False
    and stop partial UI updates.
    """
    if not is_mpv_running(state):
        return state

    position = get_mpv_property(state.socket_path, "time-pos")
    duration = get_mpv_property(state.socket_path, "duration")

    return state._replace(
        current_position=position if position is not None else state.current_position,
        duration=duration if duration is not None else state.duration,
        # Deliberately NOT querying or updating is_playing
    )


def get_unified_player_status(
    state: PlayerState, spotify_player=None
) -> dict[str, Any]:
    """Get current player status for both MPV and Spotify players.

    Args:
        state: Current player state
        spotify_player: Optional SpotifyPlayer instance for Spotify tracks

    Returns:
        Unified status dict for both MPV and Spotify playback
    """
    # Check if current track is Spotify URI
    if state.current_track and state.current_track.startswith("spotify:"):
        if spotify_player:
            # Use Spotify player status
            position = spotify_player.get_time_pos() or 0.0
            duration = spotify_player.get_duration() or 0.0
            is_playing = spotify_player.is_playing()

            return {
                "playing": is_playing,
                "file": state.current_track,
                "position": position,
                "duration": duration,
                "volume": 0,  # Spotify doesn't expose volume via API
            }
        else:
            # No Spotify player available, but track is Spotify URI
            return {
                "playing": False,
                "file": state.current_track,
                "position": 0.0,
                "duration": 0.0,
                "volume": 0,
            }

    # Default to MPV player status
    return get_player_status(state)


def get_player_status(state: PlayerState) -> dict[str, Any]:
    """Get current player status without modifying state."""
    if not is_mpv_running(state):
        return {
            "playing": False,
            "file": None,
            "position": 0.0,
            "duration": 0.0,
            "volume": 0,
        }

    # Get current values from MPV - preserve previous on failure
    position = get_mpv_property(state.socket_path, "time-pos")
    duration = get_mpv_property(state.socket_path, "duration")
    volume = get_mpv_property(state.socket_path, "volume")
    paused = get_mpv_property(state.socket_path, "pause")

    # Preserve previous state if query fails (None) to prevent 0:00 display during seek
    return {
        "playing": not paused if paused is not None else state.is_playing,
        "file": state.current_track,
        "position": position if position is not None else state.current_position,
        "duration": duration if duration is not None else state.duration,
        "volume": volume if volume is not None else 0,
    }


def get_progress_info(state: PlayerState) -> tuple[float, float, float]:
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
    """Check if track finished with multiple validation layers.

    Safeguards:
    1. Minimum playback time (prevents incomplete metadata issues)
    2. Duration sanity check (detects corrupted/incomplete metadata)
    3. Position-based completion check
    4. EOF flag validation (with position confirmation)
    """
    if not is_mpv_running(state):
        return False

    position = get_mpv_property(state.socket_path, "time-pos") or 0.0
    duration = get_mpv_property(state.socket_path, "duration") or 0.0
    eof = get_mpv_property(state.socket_path, "eof-reached")

    # SAFEGUARD 1: Minimum playback time
    playback_elapsed = 0.0
    if state.playback_started_at is not None:
        playback_elapsed = time.time() - state.playback_started_at
        if playback_elapsed < MIN_PLAYBACK_TIME:
            logger.debug(
                f"is_track_finished: Too early (elapsed={playback_elapsed:.2f}s)"
            )
            return False

    # SAFEGUARD 2: Duration sanity check
    duration_is_suspicious = 0 < duration < MIN_VALID_DURATION
    if duration_is_suspicious:
        logger.warning(
            f"is_track_finished: Suspicious duration={duration:.2f}s, "
            f"ignoring position-based checks"
        )
        # Only trust eof when position is very close
        if eof is True and position >= duration - 0.1:
            return True
        return False

    # SAFEGUARD 3: Position-based check (primary)
    finished_by_position = duration > 0 and position >= duration - 0.5

    # SAFEGUARD 4: EOF flag check (secondary)
    finished_by_eof = eof is True and duration > 0 and position >= duration - 1.0

    result = finished_by_position or finished_by_eof

    logger.debug(
        "is_track_finished: pos={:.2f}, dur={:.2f}, elapsed={:.2f}s, suspicious={}, by_pos={}, by_eof={}, result={}",
        position,
        duration,
        playback_elapsed,
        duration_is_suspicious,
        finished_by_position,
        finished_by_eof,
        result,
    )

    return result


def format_time(seconds: float) -> str:
    """Format time in seconds to MM:SS format."""
    if seconds < 0:
        return "00:00"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"
