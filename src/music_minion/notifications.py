"""Desktop notification helpers for Music Minion."""

import subprocess
import shutil
from typing import Literal


def notify(
    title: str, message: str, urgency: Literal["low", "normal", "critical"] = "normal"
) -> None:
    """
    Show a desktop notification using notify-send.

    Args:
        title: Notification title
        message: Notification message body
        urgency: Urgency level ('low', 'normal', 'critical')

    Note:
        Silently skips notification if notify-send is not available.
        Errors are logged but don't interrupt program flow.
    """
    # Check if notify-send is available
    if not shutil.which("notify-send"):
        return

    try:
        subprocess.run(
            [
                "notify-send",
                "--urgency",
                urgency,
                "--app-name",
                "Music Minion",
                title,
                message,
            ],
            check=False,  # Don't raise on error
            timeout=2.0,  # Timeout after 2 seconds
            capture_output=True,  # Suppress output
        )
    except (subprocess.TimeoutExpired, OSError):
        # Silently fail - notifications are nice-to-have
        pass


def notify_success(message: str) -> None:
    """Show a success notification with checkmark."""
    notify("✓ Music Minion", message, urgency="normal")


def notify_error(message: str) -> None:
    """Show an error notification with X mark."""
    notify("✗ Music Minion", message, urgency="critical")
