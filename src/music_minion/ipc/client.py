"""IPC client for sending commands to running Music Minion instance."""

import socket
import json
import os
from pathlib import Path
from typing import Tuple, List


def get_socket_path() -> Path:
    """
    Get the path to the Music Minion control socket.

    Returns:
        Path to Unix socket
    """
    # Use XDG_RUNTIME_DIR if available, otherwise fall back to ~/.local/share
    runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    if runtime_dir:
        return Path(runtime_dir) / 'music-minion' / 'control.sock'
    else:
        data_dir = Path.home() / '.local' / 'share' / 'music-minion'
        return data_dir / 'control.sock'


def send_command(command: str, args: List[str] = None) -> Tuple[bool, str]:
    """
    Send a command to the running Music Minion instance.

    Args:
        command: Command name (e.g., 'like', 'add', 'composite')
        args: Command arguments (optional)

    Returns:
        (success, message) tuple
            success: True if command executed successfully
            message: Response message or error description
    """
    socket_path = get_socket_path()

    # Check if socket exists
    if not socket_path.exists():
        return False, "Music Minion is not running"

    # Prepare command payload
    payload = {
        'command': command,
        'args': args or []
    }

    try:
        # Connect to Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)  # 5 second timeout
        sock.connect(str(socket_path))

        # Send command as JSON
        message = json.dumps(payload) + '\n'
        sock.sendall(message.encode('utf-8'))

        # Receive response
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            # Check if we have a complete JSON response (ends with newline)
            if b'\n' in response_data:
                break

        sock.close()

        # Parse response
        if not response_data:
            return False, "No response from Music Minion"

        response = json.loads(response_data.decode('utf-8').strip())
        success = response.get('success', False)
        message = response.get('message', 'No message')

        return success, message

    except socket.timeout:
        return False, "Music Minion not responding (timeout)"
    except ConnectionRefusedError:
        return False, "Music Minion not running"
    except FileNotFoundError:
        return False, "Music Minion not running"
    except json.JSONDecodeError as e:
        return False, f"Invalid response from Music Minion: {e}"
    except Exception as e:
        return False, f"Failed to send command: {e}"
