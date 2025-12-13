"""
Web process launcher for Music Minion CLI.

Provides pure functions for managing FastAPI backend and Vite frontend processes.
Handles port checking, prerequisite validation, and graceful process lifecycle management.
"""

import shutil
import socket
import subprocess
from pathlib import Path


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
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def check_web_prerequisites() -> tuple[bool, str]:
    """
    Validate that all required dependencies and resources are available.

    Checks:
    - npm is installed
    - uvicorn is available in uv environment
    - Port 8000 is available (FastAPI backend)
    - Port 5173 is available (Vite frontend)
    - Frontend directory exists

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

    # Check port availability
    if not is_port_available(8000):
        return False, "Port 8000 already in use (FastAPI backend)"

    if not is_port_available(5173):
        return False, "Port 5173 already in use (Vite frontend)"

    # Check frontend directory exists
    frontend_dir = PROJECT_ROOT / "web" / "frontend"
    if not frontend_dir.exists():
        return False, "Frontend directory not found. Run from project root."

    return True, ""


def start_uvicorn_process() -> subprocess.Popen:
    """
    Start the FastAPI backend server.

    Command: uv run uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload

    Returns:
        subprocess.Popen instance for the uvicorn process
    """
    with UVICORN_LOG.open("w") as log_file:
        return subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "web.backend.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )


def start_vite_process() -> subprocess.Popen:
    """
    Start the Vite frontend dev server.

    Command: npm run dev -- --host

    Returns:
        subprocess.Popen instance for the vite process
    """
    frontend_dir = PROJECT_ROOT / "web" / "frontend"
    with VITE_LOG.open("w") as log_file:
        return subprocess.Popen(
            ["npm", "run", "dev", "--", "--host"],
            cwd=frontend_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )


def start_web_processes() -> tuple[subprocess.Popen, subprocess.Popen]:
    """
    Convenience function to start both web processes.

    Returns:
        (uvicorn_proc, vite_proc) tuple of subprocess.Popen instances
    """
    uvicorn_proc = start_uvicorn_process()
    vite_proc = start_vite_process()
    return uvicorn_proc, vite_proc


def stop_web_processes(
    uvicorn_proc: subprocess.Popen, vite_proc: subprocess.Popen
) -> None:
    """
    Gracefully stop both web processes.

    Shutdown sequence:
    1. Send SIGTERM to each subprocess
    2. Wait 5 seconds for graceful shutdown
    3. Force kill if timeout exceeded
    4. Ignore errors from already-terminated processes

    Args:
        uvicorn_proc: FastAPI backend process
        vite_proc: Vite frontend process
    """
    processes = [uvicorn_proc, vite_proc]

    # Send terminate signal to both processes
    for proc in processes:
        try:
            proc.terminate()
        except ProcessLookupError:
            # Process already terminated
            pass

    # Wait for graceful shutdown
    for proc in processes:
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            # Force kill if still running
            try:
                proc.kill()
                proc.wait(timeout=2.0)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                # Process already terminated or couldn't be killed
                pass
