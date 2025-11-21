"""IPC (Inter-Process Communication) for Music Minion.

Enables external commands to communicate with running Music Minion instance.
"""

from .client import send_command

__all__ = ['send_command']
