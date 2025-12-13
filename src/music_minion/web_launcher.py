"""
Web process launcher for Music Minion CLI.

Provides pure functions for managing FastAPI backend and Vite frontend processes.
Handles port checking, prerequisite validation, and graceful process lifecycle management.
"""

import shutil
import socket
import subprocess
from pathlib import Path
from typing import Optional

from .core.config import WebConfig


# Project root detection (where pyproject.toml exists)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Log file paths
UVICORN_LOG = Path("/tmp/music-minion-uvicorn.log")
VITE_LOG = Path("/tmp/music-minion-vite.log")


def is_port_available(port: int) -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if already in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Set socket options to avoid issues
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(1.0)  # Add timeout to avoid hanging
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def check_web_prerequisites(config: Optional["WebConfig"] = None) -> tuple[bool, str]:
    """
    Validate that all required dependencies and resources are available.

    Checks:
    - npm is installed
    - uvicorn is available in uv environment
    - Config ports are available (FastAPI backend and Vite frontend)
    - Frontend directory exists

    Args:
        config: Optional WebConfig with custom port settings

    Returns:
        (True, "") if all checks pass
        (False, "error message") with specific error if any check fails
    """
    # Check npm availability
    if not shutil.which("npm"):
        return False, "npm not found. Install Node.js first."

    # Check uvicorn availability in uv environment
    try:
        result = subprocess.run(
            ["uv", "run", "which", "uvicorn"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            return False, "uvicorn not found in uv environment."
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, "uv not found. Install uv first."

    # Get port values from config or defaults
    backend_port = config.backend_port if config else 8000
    frontend_port = config.frontend_port if config else 5173

    # Check port availability
    if not is_port_available(backend_port):
        return False, f"Port {backend_port} already in use (FastAPI backend)"

    if not is_port_available(frontend_port):
        return False, f"Port {frontend_port} already in use (Vite frontend)"

    # Check frontend directory exists
    frontend_dir = PROJECT_ROOT / "web" / "frontend"
    if not frontend_dir.exists():
        return False, "Frontend directory not found. Run from project root."

    return True, ""


def start_uvicorn_process(config: Optional[WebConfig] = None) -> subprocess.Popen:
    """
    Start the FastAPI backend server.

    Command: uv run uvicorn web.backend.main:app --host <host> --port <port> [--reload]

    Args:
        config: Optional WebConfig with custom host, port, and reload settings

    Returns:
        subprocess.Popen instance for the uvicorn process
    """
    host = config.backend_host if config else "0.0.0.0"
    port = config.backend_port if config else 8000
    reload_flag = "--reload" if (config.auto_reload if config else True) else ""

    command = [
        "uv",
        "run",
        "uvicorn",
        "web.backend.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload_flag:
        command.append(reload_flag)

    with UVICORN_LOG.open("w") as log_file:
        return subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )


def start_vite_process(config: Optional[WebConfig] = None) -> subprocess.Popen:
    """
    Start the Vite frontend dev server.

    Command: npm run dev -- --host --port <port>

    Args:
        config: Optional WebConfig with custom port setting

    Returns:
        subprocess.Popen instance for the vite process
    """
    port = config.frontend_port if config else 5173

    frontend_dir = PROJECT_ROOT / "web" / "frontend"
    with VITE_LOG.open("w") as log_file:
        return subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "--port", str(port)],
            cwd=frontend_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )


def start_web_processes(
    config: Optional[WebConfig] = None,
) -> tuple[subprocess.Popen, subprocess.Popen]:
    """
    Convenience function to start both web processes.

    Args:
        config: Optional WebConfig with custom settings

    Returns:
        (uvicorn_proc, vite_proc) tuple of subprocess.Popen instances
    """
    uvicorn_proc = start_uvicorn_process(config)
    vite_proc = start_vite_process(config)
    return uvicorn_proc, vite_proc


def stop_web_processes(
    uvicorn_proc: subprocess.Popen, vite_proc: subprocess.Popen
) -> None:
    """
    Immediately stop both web processes.

    Args:
        uvicorn_proc: FastAPI backend process
        vite_proc: Vite frontend process
    """
    processes = [uvicorn_proc, vite_proc]

    # Kill processes immediately
    for proc in processes:
        try:
            proc.kill()
            proc.wait(timeout=2.0)
        except Exception:
            # Process already terminated or couldn't be killed
            pass
