"""
YouTube provider for Music Minion.

Downloads public YouTube videos for local playback.
No authentication required.
"""

import shutil
from pathlib import Path

from loguru import logger

from ...provider import ProviderConfig, ProviderState

# Import from submodules
from .import_handlers import ImportResult, cleanup_temp_directory, import_playlist, import_single_video


def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize YouTube provider.

    No authentication needed for YouTube downloads.
    Checks for ffmpeg availability and cleans up temp files from previous runs.

    Args:
        config: Provider configuration

    Returns:
        ProviderState with authenticated=True and output_dir in cache
    """
    # Check for ffmpeg (required for yt-dlp to mux video/audio)
    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg not found - YouTube downloads may fail")
        logger.warning(
            "Install ffmpeg: sudo apt install ffmpeg (Linux) or brew install ffmpeg (Mac)"
        )

    # Clean up orphaned temp files from previous failed imports
    cleanup_temp_directory()

    # Set output directory
    output_dir = str(Path.home() / "music" / "youtube")

    logger.debug("YouTube provider initialized")

    return ProviderState(
        config=config,
        authenticated=True,  # No auth needed
        last_sync=None,
        cache={"output_dir": output_dir},
    )


# Re-export import functions
from .download import download_video, extract_video_id

__all__ = [
    "init_provider",
    "import_single_video",
    "import_playlist",
    "download_video",
    "extract_video_id",
    "ImportResult",
]
