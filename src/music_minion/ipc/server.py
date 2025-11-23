"""IPC server for receiving commands from external processes."""

import socket
import json
import os
import threading
import queue
from pathlib import Path
from typing import Optional, Callable, Tuple, Dict, Any

from loguru import logger

from music_minion.context import AppContext
from music_minion import router, actions, notifications


def get_socket_path() -> Path:
    """
    Get the path to the Music Minion control socket.

    Returns:
        Path to Unix socket
    """
    # Use XDG_RUNTIME_DIR if available, otherwise fall back to ~/.local/share
    runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    if runtime_dir:
        socket_dir = Path(runtime_dir) / 'music-minion'
    else:
        socket_dir = Path.home() / '.local' / 'share' / 'music-minion'

    # Ensure directory exists
    socket_dir.mkdir(parents=True, exist_ok=True)
    return socket_dir / 'control.sock'


class IPCServer:
    """Unix socket server for IPC commands.

    Runs in a background thread and processes commands from external clients.
    Uses a queue to communicate with the main thread for thread-safe context updates.
    """

    def __init__(self, command_queue: queue.Queue, response_queue: queue.Queue):
        """
        Initialize IPC server.

        Args:
            command_queue: Queue for sending commands to main thread
            response_queue: Queue for receiving responses from main thread
        """
        self.command_queue = command_queue
        self.response_queue = response_queue
        self.socket_path = get_socket_path()
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the IPC server in a background thread."""
        if self.running:
            return

        # Remove stale socket if it exists
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop the IPC server and cleanup."""
        self.running = False

        # Close server socket to unblock accept()
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        # Remove socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

    def _run_server(self) -> None:
        """Run the Unix socket server loop."""
        try:
            # Create Unix socket
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(str(self.socket_path))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Poll every second

            while self.running:
                try:
                    # Accept connections with timeout
                    client_socket, _ = self.server_socket.accept()
                    # Handle in same thread (simple, sequential processing)
                    self._handle_client(client_socket)
                except socket.timeout:
                    # Timeout is normal, just check if we should continue
                    continue
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        logger.error(f"Error accepting connection: {e}")

        except Exception as e:
            logger.exception("IPC server error")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a client connection.

        Args:
            client_socket: Connected client socket
        """
        try:
            # Receive data
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Check for newline (end of JSON message)
                if b'\n' in data:
                    break

            if not data:
                client_socket.close()
                return

            # Parse JSON command
            payload = json.loads(data.decode('utf-8').strip())
            command = payload.get('command', '')
            args = payload.get('args', [])

            # Put command in queue for main thread
            request_id = id(payload)  # Unique ID for this request
            self.command_queue.put((request_id, command, args))

            # Wait for response from main thread (with timeout)
            try:
                response_id, success, message = self.response_queue.get(timeout=15.0)
                if response_id == request_id:
                    # Send response
                    response = {
                        'success': success,
                        'message': message
                    }
                    response_json = json.dumps(response) + '\n'
                    client_socket.sendall(response_json.encode('utf-8'))
                else:
                    # Mismatched response (shouldn't happen with sequential processing)
                    error_response = {
                        'success': False,
                        'message': 'Internal error: response mismatch'
                    }
                    client_socket.sendall(json.dumps(error_response).encode('utf-8'))
            except queue.Empty:
                # Timeout waiting for response
                error_response = {
                    'success': False,
                    'message': 'Command timed out'
                }
                client_socket.sendall(json.dumps(error_response).encode('utf-8'))

        except json.JSONDecodeError as e:
            error_response = {
                'success': False,
                'message': f'Invalid JSON: {e}'
            }
            client_socket.sendall(json.dumps(error_response).encode('utf-8'))
        except Exception as e:
            error_response = {
                'success': False,
                'message': f'Error processing command: {e}'
            }
            try:
                client_socket.sendall(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()


def process_ipc_command(
    ctx: AppContext,
    command: str,
    args: list,
    add_to_history: Callable[[str], None]
) -> Tuple[AppContext, bool, str]:
    """
    Process an IPC command and return updated context and response.

    Args:
        ctx: Application context
        command: Command name
        args: Command arguments
        add_to_history: Callback to add command to history

    Returns:
        (updated_context, success, message) tuple
    """
    # Format command for history
    args_str = ' '.join(args) if args else ''
    history_entry = f"[IPC] {command} {args_str}".strip()

    try:
        # Check if it's a composite action
        if command == 'composite':
            if not args:
                return ctx, False, "Composite action name required"

            action_name = args[0]
            ctx, success, message = actions.execute_composite_action(ctx, action_name)

            # Add to history with result
            add_to_history(f"{history_entry} → {message}")

            # Send notification if enabled
            if ctx.config.notifications.enabled if hasattr(ctx.config, 'notifications') else True:
                if success:
                    if ctx.config.notifications.show_success if hasattr(ctx.config.notifications, 'show_success') else True:
                        notifications.notify_success(message)
                else:
                    if ctx.config.notifications.show_errors if hasattr(ctx.config.notifications, 'show_errors') else True:
                        notifications.notify_error(message)

            return ctx, success, message

        # Regular command - route through router
        ctx, should_continue = router.handle_command(ctx, command, args)

        # Commands that succeed typically don't return explicit success messages
        # so we construct a generic success message
        message = f"Executed: {command} {args_str}".strip()

        # Add to history
        add_to_history(f"{history_entry} → Success")

        # Send notification if enabled
        if ctx.config.notifications.enabled if hasattr(ctx.config, 'notifications') else True:
            if ctx.config.notifications.show_success if hasattr(ctx.config.notifications, 'show_success') else True:
                notifications.notify_success(message)

        return ctx, True, message

    except Exception as e:
        error_message = f"Error: {str(e)}"

        # Add to history
        add_to_history(f"{history_entry} → {error_message}")

        # Send error notification if enabled
        if ctx.config.notifications.enabled if hasattr(ctx.config, 'notifications') else True:
            if ctx.config.notifications.show_errors if hasattr(ctx.config.notifications, 'show_errors') else True:
                notifications.notify_error(error_message)

        return ctx, False, error_message
