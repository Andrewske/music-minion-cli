"""IPC server for receiving commands from external processes."""

import socket
import json
import os
import threading
import queue
import asyncio
from pathlib import Path
from typing import Optional, Callable, Tuple, Any, Set

from loguru import logger

from music_minion.context import AppContext
from music_minion import actions, notifications

# WebSocket support (optional)
WEBSOCKETS_AVAILABLE = False

# Builder WebSocket Messages:
#
# Add track:
# {
#   "type": "builder:add",
#   "playlist_id": 123,
#   "timestamp": "2026-01-19T12:00:00Z"
# }
#
# Skip track:
# {
#   "type": "builder:skip",
#   "playlist_id": 123,
#   "timestamp": "2026-01-19T12:00:00Z"
# }


def get_socket_path() -> Path:
    """
    Get the path to the Music Minion control socket.

    Returns:
        Path to Unix socket
    """
    # Use XDG_RUNTIME_DIR if available, otherwise fall back to ~/.local/share
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        socket_dir = Path(runtime_dir) / "music-minion"
    else:
        socket_dir = Path.home() / ".local" / "share" / "music-minion"

    # Ensure directory exists
    socket_dir.mkdir(parents=True, exist_ok=True)
    return socket_dir / "control.sock"


class IPCServer:
    """Unix socket server for IPC commands with WebSocket support for web control.

    Runs in a background thread and processes commands from external clients.
    Uses a queue to communicate with the main thread for thread-safe context updates.
    Also provides WebSocket server for web frontend control connections.
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

        # WebSocket support for web frontend connections
        self.websocket_server = None
        self.websocket_thread: Optional[threading.Thread] = None
        self.web_clients: Set[Any] = set()  # Connected web client WebSocket objects
        self.web_command_sync_queue: queue.Queue = (
            queue.Queue()
        )  # Thread-safe queue for main thread
        self.web_broadcast_queue: queue.Queue = (
            queue.Queue()
        )  # Thread-safe queue for broadcasts to web clients

    def start(self) -> None:
        """Start the IPC server and WebSocket server in background threads."""
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

        # Start WebSocket server for web frontend connections
        self.websocket_thread = threading.Thread(
            target=self._run_websocket_server, daemon=True
        )
        self.websocket_thread.start()

    def stop(self) -> None:
        """Stop the IPC server and cleanup."""
        self.running = False

        # Close server socket to unblock accept()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        # Wait for threads to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.websocket_thread and self.websocket_thread.is_alive():
            self.websocket_thread.join(timeout=2.0)

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

        except Exception:
            logger.exception("IPC server error")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def _run_websocket_server(self) -> None:
        """Run the WebSocket server for web frontend connections."""
        import threading

        # Mark thread as silent to prevent loguru output in blessed UI
        threading.current_thread().silent_logging = True  # type: ignore

        try:
            import websockets  # type: ignore[import]
            import logging as std_logging

            # Suppress benign handshake/connection error logs
            # Set to CRITICAL to suppress ERROR-level "opening handshake failed" messages
            # These occur during normal browser refresh/HMR/tab close and pollute blessed UI
            websockets_logger = std_logging.getLogger("websockets")
            websockets_logger.setLevel(std_logging.CRITICAL)

            # Defense in depth: Add NullHandler to prevent lastResort stderr fallback
            if not websockets_logger.handlers:
                websockets_logger.addHandler(std_logging.NullHandler())

            # CRITICAL: Suppress asyncio logger to prevent stderr output in blessed UI
            # Why suppression is safe:
            # 1. Real errors are caught/logged in websocket_handler (lines 181-193)
            # 2. asyncio logger just complains about exceptions we've already handled
            # 3. Prevents duplicate logging (asyncio stack trace + our logger.warning())
            # 4. Benign events (refresh, HMR, tab close) are normal lifecycle, not errors
            asyncio_logger = std_logging.getLogger("asyncio")
            asyncio_logger.setLevel(std_logging.CRITICAL)

            # Defense in depth: Add NullHandler to prevent lastResort stderr fallback
            if not asyncio_logger.handlers:
                asyncio_logger.addHandler(std_logging.NullHandler())

        except ImportError:
            logger.warning("websockets package not available, web control disabled")
            return

        async def websocket_handler(websocket, path=None):
            """Handle WebSocket connections from web frontends."""
            self.web_clients.add(websocket)

            try:
                # Send initial connection confirmation
                await websocket.send(json.dumps({"type": "connected"}))

                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "command":
                            # Web client sent a command - add to web command queue
                            self.web_command_sync_queue.put(data)
                        elif data.get("type") == "ping":
                            # Respond to ping
                            await websocket.send(json.dumps({"type": "pong"}))
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from web client: {message}")
            except websockets.ConnectionClosed:
                pass  # Normal closure
            except websockets.InvalidHandshake:
                pass  # Handshake failed - benign (HMR, refresh, etc.)
            except OSError as e:
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    pass  # Benign network error
                else:
                    logger.warning(f"WebSocket OSError: {e}")
            except asyncio.CancelledError:
                raise  # Re-raise for proper cleanup
            except Exception as e:
                logger.warning(f"WebSocket handler error: {e}")
            finally:
                self.web_clients.discard(websocket)

        async def run_server():
            # Start WebSocket server on localhost:8765
            server = await websockets.serve(websocket_handler, "localhost", 8765)
            logger.info("WebSocket server started on ws://localhost:8765")

            # Keep server running and process broadcast queue
            while self.running:
                # Process any pending broadcasts
                try:
                    while not self.web_broadcast_queue.empty():
                        message = self.web_broadcast_queue.get_nowait()
                        # Broadcast to all connected clients
                        for websocket in self.web_clients.copy():
                            try:
                                await websocket.send(json.dumps(message))
                            except Exception as e:
                                logger.warning(f"Failed to send to web client: {e}")
                                self.web_clients.discard(websocket)
                except Exception as e:
                    logger.warning(f"Error processing broadcast queue: {e}")

                await asyncio.sleep(0.1)  # Poll frequently for responsive broadcasts

            server.close()
            await server.wait_closed()

        try:
            asyncio.run(run_server())
        except Exception:
            logger.exception("WebSocket server error")

    def broadcast_to_web_clients(self, message: dict) -> None:
        """Broadcast a message to all connected web clients."""
        # Put message in queue for WebSocket thread to process
        self.web_broadcast_queue.put(message)

    def get_pending_web_commands(self) -> list:
        """
        Get all pending web commands from the queue.

        Returns:
            List of command data dictionaries
        """
        commands = []
        try:
            while not self.web_command_sync_queue.empty():
                commands.append(self.web_command_sync_queue.get_nowait())
        except Exception:
            pass
        return commands

    def get_web_commands(self) -> list:
        """
        Get all pending web commands from the queue.

        Returns:
            List of (command_data, ) tuples for compatibility with main thread processing
        """
        commands = []
        try:
            # Try to get commands without blocking (since this is called from sync context)
            while True:
                # For asyncio.Queue, we need to check if there's an event loop
                try:
                    import asyncio

                    loop = asyncio.get_running_loop()
                    # If we have a running loop, we can await
                    if loop.is_running():
                        # This is tricky - we can't await from sync context
                        # Let's use a different approach: store commands in a thread-safe list
                        break
                except RuntimeError:
                    # No event loop running, can't await
                    break

                # Fallback: if we can't access the asyncio queue safely, return empty
                break
        except Exception:
            pass
        return commands

    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a client connection.

        Args:
            client_socket: Connected client socket
        """
        try:
            # Receive data
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Check for newline (end of JSON message)
                if b"\n" in data:
                    break

            if not data:
                client_socket.close()
                return

            # Parse JSON command
            payload = json.loads(data.decode("utf-8").strip())
            command = payload.get("command", "")
            args = payload.get("args", [])

            # Send immediate notification for composite actions
            if command == "composite" and args:
                action_name = args[0]
                # Map action names to immediate notification messages
                immediate_messages = {
                    "like_and_add_dated": "👍 Liking and adding...",
                    "add_not_quite": "🤔 Adding to Not Quite...",
                    "add_not_interested_and_skip": "⏭️ Adding to Not Interested...",
                }
                if action_name in immediate_messages:
                    notifications.notify(
                        "Music Minion", immediate_messages[action_name], urgency="low"
                    )

            # Put command in queue for main thread
            request_id = id(payload)  # Unique ID for this request
            self.command_queue.put((request_id, command, args))

            # Wait for response from main thread (with timeout)
            try:
                response_id, success, message = self.response_queue.get(timeout=15.0)
                if response_id == request_id:
                    # Send response
                    response = {"success": success, "message": message}
                    response_json = json.dumps(response) + "\n"
                    client_socket.sendall(response_json.encode("utf-8"))
                else:
                    # Mismatched response (shouldn't happen with sequential processing)
                    error_response = {
                        "success": False,
                        "message": "Internal error: response mismatch",
                    }
                    client_socket.sendall(json.dumps(error_response).encode("utf-8"))
            except queue.Empty:
                # Timeout waiting for response
                error_response = {"success": False, "message": "Command timed out"}
                client_socket.sendall(json.dumps(error_response).encode("utf-8"))

        except json.JSONDecodeError as e:
            error_response = {"success": False, "message": f"Invalid JSON: {e}"}
            client_socket.sendall(json.dumps(error_response).encode("utf-8"))
        except Exception as e:
            error_response = {
                "success": False,
                "message": f"Error processing command: {e}",
            }
            try:
                client_socket.sendall(json.dumps(error_response).encode("utf-8"))
            except Exception:
                pass
        finally:
            client_socket.close()


def process_ipc_command(
    ctx: AppContext,
    command: str,
    args: list,
    add_to_history: Callable[[str], None],
    ipc_server: Optional["IPCServer"] = None,
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
    args_str = " ".join(args) if args else ""
    history_entry = f"[IPC] {command} {args_str}".strip()

    try:
        # Check if it's a web control command
        # web-winner and web-archive are context-aware - route through router
        if command.startswith("web-") and command not in ("web-winner", "web-archive"):
            # Web control commands - broadcast to web clients
            web_command = command[4:]  # Remove "web-" prefix
            message = {"type": "command", "command": web_command, "args": args or []}
            if ipc_server:
                ipc_server.broadcast_to_web_clients(message)

            # Add to history
            add_to_history(f"{history_entry} → Sent to web")

            return ctx, True, f"Sent {web_command} command to web interface"

        # Check if web clients are connected and also broadcast regular commands to web
        web_commands = {
            "like",
            "love",
            "skip",
        }  # Commands that make sense to route to web
        if ipc_server and ipc_server.web_clients and command in web_commands:
            # Web clients are connected, also broadcast command to web interface
            message = {"type": "command", "command": command, "args": args or []}
            ipc_server.broadcast_to_web_clients(message)

        # Check if it's a composite action
        if command == "composite":
            if not args:
                return ctx, False, "Composite action name required"

            action_name = args[0]
            ctx, success, message = actions.execute_composite_action(ctx, action_name)

            # Add to history with result
            add_to_history(f"{history_entry} → {message}")

            # Send notification if enabled
            if (
                ctx.config.notifications.enabled
                if hasattr(ctx.config, "notifications")
                else True
            ):
                if success:
                    if (
                        ctx.config.notifications.show_success
                        if hasattr(ctx.config.notifications, "show_success")
                        else True
                    ):
                        notifications.notify_success(message)
                else:
                    if (
                        ctx.config.notifications.show_errors
                        if hasattr(ctx.config.notifications, "show_errors")
                        else True
                    ):
                        notifications.notify_error(message)

            return ctx, success, message

        # Regular command - route through router
        from music_minion import router  # Lazy import to break circular dependency
        ctx, should_continue = router.handle_command(ctx, command, args)

        # Handle WebSocket broadcasts for context-aware web commands
        if command == "web-winner" and ctx.active_web_mode == "builder" and ipc_server:
            from datetime import datetime
            broadcast_message = {
                "type": "builder:add",
                "playlist_id": ctx.active_builder_playlist_id,
                "timestamp": datetime.now().isoformat()
            }
            ipc_server.broadcast_to_web_clients(broadcast_message)
        elif command == "web-winner" and ctx.active_web_mode == "comparison" and ipc_server:
            from datetime import datetime
            broadcast_message = {
                "type": "comparison:winner",
                "timestamp": datetime.now().isoformat()
            }
            ipc_server.broadcast_to_web_clients(broadcast_message)
        elif command == "web-archive" and ctx.active_web_mode == "builder" and ipc_server:
            from datetime import datetime
            broadcast_message = {
                "type": "builder:skip",
                "playlist_id": ctx.active_builder_playlist_id,
                "timestamp": datetime.now().isoformat()
            }
            ipc_server.broadcast_to_web_clients(broadcast_message)
        elif command == "web-archive" and ctx.active_web_mode == "comparison" and ipc_server:
            from datetime import datetime
            broadcast_message = {
                "type": "comparison:loser",
                "timestamp": datetime.now().isoformat()
            }
            ipc_server.broadcast_to_web_clients(broadcast_message)

        # Commands that succeed typically don't return explicit success messages
        # so we construct a generic success message
        message = f"Executed: {command} {args_str}".strip()

        # Add to history
        add_to_history(f"{history_entry} → Success")

        # Send notification if enabled
        if (
            ctx.config.notifications.enabled
            if hasattr(ctx.config, "notifications")
            else True
        ):
            if (
                ctx.config.notifications.show_success
                if hasattr(ctx.config.notifications, "show_success")
                else True
            ):
                notifications.notify_success(message)

        return ctx, True, message

    except Exception as e:
        error_message = f"Error: {str(e)}"

        # Add to history
        add_to_history(f"{history_entry} → {error_message}")

        # Send error notification if enabled
        if (
            ctx.config.notifications.enabled
            if hasattr(ctx.config, "notifications")
            else True
        ):
            if (
                ctx.config.notifications.show_errors
                if hasattr(ctx.config.notifications, "show_errors")
                else True
            ):
                notifications.notify_error(error_message)

        return ctx, False, error_message
