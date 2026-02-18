"""Pytest configuration for backend tests.

Handles circular import issues between queue_manager and player modules.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
from unittest import mock

# Add web directory to path
web_dir = Path(__file__).parent.parent.parent
if str(web_dir) not in sys.path:
    sys.path.insert(0, str(web_dir))


# Create a mock PlayContext to break circular import between queue_manager and player
@dataclass
class MockPlayContext:
    """Mock PlayContext matching the Pydantic model structure."""
    type: Literal["playlist", "track", "builder", "search", "comparison"] = "playlist"
    playlist_id: Optional[int] = 1
    builder_id: Optional[int] = None
    track_ids: Optional[list[int]] = None
    shuffle: bool = True


# Mock the player module before any imports happen
# This needs to be done at module level before pytest collects tests
mock_player_module = mock.MagicMock()
mock_player_module.PlayContext = MockPlayContext
sys.modules['backend.routers'] = mock.MagicMock()
sys.modules['backend.routers.player'] = mock_player_module
