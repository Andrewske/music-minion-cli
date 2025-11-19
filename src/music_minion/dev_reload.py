"""
Hot-reload functionality for development.

Watches Python files in the music_minion package and reloads them when modified.
Only active when --dev flag is passed to the CLI.
"""

import importlib
import sys
import time
from pathlib import Path
from typing import Callable, Optional

try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object  # Fallback to object instead of None
    FileModifiedEvent = None


if WATCHDOG_AVAILABLE:

    class FileChangeHandler(FileSystemEventHandler):
        """Handles file modification events with debouncing."""

        def __init__(self, callback: Callable[[str], None], debounce_ms: int = 100):
            """
            Initialize file change handler.

            Args:
                callback: Function to call with file path when change detected
                debounce_ms: Milliseconds to wait after last change before triggering
            """
            self.callback = callback
            self.debounce_seconds = debounce_ms / 1000.0
            self.pending_changes: dict[str, float] = {}
            self.last_check = time.time()

        def on_modified(self, event):
            """Handle file modification event."""
            # Only process Python file modifications
            if event.is_directory or not event.src_path.endswith(".py"):
                return

            # Ignore __pycache__ and .pyc files
            if "__pycache__" in event.src_path or event.src_path.endswith(".pyc"):
                return

            # Add to pending changes with timestamp
            self.pending_changes[event.src_path] = time.time()

        def check_pending_changes(self) -> list[str]:
            """Check for debounced changes ready to process.

            Returns:
                List of file paths ready to reload
            """
            current_time = time.time()
            ready_files = []

            for local_path, timestamp in list(self.pending_changes.items()):
                # If enough time has passed since last modification, process it
                if current_time - timestamp >= self.debounce_seconds:
                    ready_files.append(local_path)
                    del self.pending_changes[local_path]

            return ready_files
else:
    # Dummy class when watchdog is not available
    class FileChangeHandler:
        def __init__(self, callback: Callable[[str], None], debounce_ms: int = 100):
            pass

        def check_pending_changes(self) -> list[str]:
            return []


def local_path_to_module_name(local_path: str, package_root: Path) -> Optional[str]:
    """
    Convert file path to Python module name.

    Args:
        local_path: Absolute path to Python file
        package_root: Root directory of the package (e.g., src/music_minion)

    Returns:
        Module name (e.g., "music_minion.commands.playlist") or None if invalid
    """
    try:
        path = Path(local_path).resolve()
        root = package_root.resolve()

        # Check if file is within package
        if not str(path).startswith(str(root)):
            return None

        # Get relative path from package root
        relative = path.relative_to(root.parent)

        # Convert to module name: path/to/file.py -> path.to.file
        module_parts = list(relative.parts[:-1])  # Remove filename
        module_parts.append(relative.stem)  # Add filename without .py

        return ".".join(module_parts)

    except (ValueError, OSError):
        return None


def reload_module(module_path: str) -> bool:
    """
    Reload a Python module by file path.

    Args:
        module_path: Path to .py file

    Returns:
        True if reload successful, False otherwise
    """
    # Get package root (src/music_minion directory)
    package_root = Path(__file__).parent

    # Convert file path to module name
    module_name = local_path_to_module_name(module_path, package_root)

    if not module_name:
        return False

    # Check if module is already imported
    if module_name not in sys.modules:
        return False

    try:
        module = sys.modules[module_name]
        importlib.reload(module)
        return True
    except Exception as e:
        # Log error but don't crash app
        print(f"❌ Failed to reload {module_name}: {e}")
        return False


def setup_file_watcher(
    callback: Callable[[str], None],
) -> Optional[tuple[Observer, FileChangeHandler]]:
    """
    Initialize file watcher for hot-reload.

    Args:
        callback: Function to call with file path when change detected

    Returns:
        Tuple of (Observer, FileChangeHandler) if successful, None otherwise
    """
    if not WATCHDOG_AVAILABLE:
        print("⚠️  watchdog not installed - hot-reload unavailable")
        print("   Install with: uv pip install watchdog")
        return None

    try:
        # Get package root directory to watch
        package_root = Path(__file__).parent

        # Create handler with debouncing
        handler = FileChangeHandler(callback, debounce_ms=100)

        # Create and configure observer
        observer = Observer()
        observer.schedule(handler, str(package_root), recursive=True)
        observer.start()

        return observer, handler

    except Exception as e:
        print(f"⚠️  Failed to setup file watcher: {e}")
        return None


def stop_file_watcher(observer: Observer) -> None:
    """
    Stop and cleanup file watcher.

    Args:
        observer: Observer instance to stop
    """
    if observer:
        try:
            observer.stop()
            observer.join(timeout=1.0)
        except Exception:
            pass  # Silent cleanup
