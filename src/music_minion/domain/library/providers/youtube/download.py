"""YouTube download functionality using yt-dlp."""

import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from loguru import logger

from .exceptions import (
    AgeRestrictedError,
    CopyrightBlockedError,
    InsufficientSpaceError,
    InvalidYouTubeURLError,
    VideoUnavailableError,
    YouTubeError,
)

# Type alias for playlist progress callback
PlaylistProgressCallback = Callable[
    [int, str, int, dict | None], None
]  # (current, step, progress, failure)

# Type alias for download progress callback
DownloadProgressCallback = Callable[[int], None]  # (percent: 0-100)


def _make_progress_hook(
    callback: Optional[DownloadProgressCallback],
    throttle_ms: int = 500,
) -> Callable[[dict], None]:
    """Create yt-dlp progress hook with throttling.

    Args:
        callback: Optional callback receiving download progress (0-100)
        throttle_ms: Minimum time between updates in milliseconds

    Returns:
        Progress hook function for yt-dlp
    """
    if callback is None:
        return lambda d: None

    state = {"last_update": 0.0, "last_percent": 0}

    def hook(d: dict) -> None:
        if d.get("status") != "downloading":
            return

        # Throttle updates to avoid lock contention
        now = time.time()
        if now - state["last_update"] < throttle_ms / 1000:
            return

        # Calculate progress
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)

        if total and total > 0:
            percent = int((downloaded / total) * 100)
        else:
            # Fallback: estimate from elapsed time (~50s to reach 95%)
            elapsed = d.get("elapsed", 0)
            percent = min(95, int(elapsed * 2))

        percent = min(95, max(0, percent))  # Cap at 95, reserve 100 for completion

        if percent != state["last_percent"]:
            state["last_update"] = now
            state["last_percent"] = percent
            try:
                callback(percent)
            except Exception:
                pass  # Don't fail download on callback error

    return hook


def sanitize_filename(title: str, extension: str = ".mp4") -> str:
    """Convert title to safe snake_case filename.

    Args:
        title: Video title to sanitize
        extension: File extension (default: .mp4)

    Returns:
        Sanitized filename in snake_case with extension

    Example:
        "Darude - Sandstorm" -> "darude_sandstorm.mp4"
    """
    # Split extension to handle truncation correctly
    base_name = title.lower()

    # Replace special characters with underscores
    base_name = re.sub(r"[^\w\s-]", "_", base_name)

    # Replace spaces and hyphens with underscores
    base_name = re.sub(r"[\s-]+", "_", base_name)

    # Remove consecutive underscores
    base_name = re.sub(r"_+", "_", base_name)

    # Truncate to ensure total length doesn't exceed 255 chars
    max_base_length = 200 - len(extension)
    if len(base_name) > max_base_length:
        base_name = base_name[:max_base_length]

    # Remove leading/trailing underscores
    base_name = base_name.strip("_")

    return f"{base_name}{extension}"


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL using yt-dlp.

    Uses yt-dlp's built-in URL parsing to handle all URL formats:
    - Standard: youtube.com/watch?v=ID
    - Short: youtu.be/ID
    - Embed: youtube.com/embed/ID
    - Shorts: youtube.com/shorts/ID
    - Mobile: m.youtube.com/watch?v=ID
    - Live: youtube.com/live/ID

    Args:
        url: YouTube URL

    Returns:
        11-character video ID

    Raises:
        InvalidYouTubeURLError: If URL is not a valid YouTube URL
    """
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # Don't download, just extract info
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info or "id" not in info:
                raise InvalidYouTubeURLError(f"Could not extract video ID from URL: {url}")

            return info["id"]

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "not a valid url" in error_msg or "unsupported url" in error_msg:
            raise InvalidYouTubeURLError(f"Invalid YouTube URL: {url}")
        raise InvalidYouTubeURLError(f"Failed to extract video ID: {e}")
    except Exception as e:
        raise InvalidYouTubeURLError(f"Unexpected error extracting video ID: {e}")


def check_available_space(
    output_dir: Path, video_count: int = 1, mb_per_video: int = 350
) -> bool:
    """Check if sufficient disk space is available for downloads.

    Args:
        output_dir: Directory where videos will be downloaded
        video_count: Number of videos to download
        mb_per_video: Estimated MB per video (default: 350MB for hour-long videos)

    Returns:
        True if sufficient space, False otherwise

    Raises:
        InsufficientSpaceError: If disk space is insufficient
    """
    required_bytes = video_count * mb_per_video * 1024 * 1024

    # Get filesystem stats
    stat = os.statvfs(output_dir)
    available_bytes = stat.f_bavail * stat.f_frsize

    if available_bytes < required_bytes:
        required_gb = required_bytes / (1024**3)
        available_gb = available_bytes / (1024**3)
        raise InsufficientSpaceError(
            f"Insufficient disk space: need {required_gb:.2f}GB, have {available_gb:.2f}GB"
        )

    return True


def download_video(
    url: str,
    output_dir: Path,
    progress_callback: Optional[DownloadProgressCallback] = None,
) -> tuple[Path, dict]:
    """Download YouTube video with audio using yt-dlp.

    Downloads video+audio in mp4/webm format and extracts metadata.
    Handles file collisions by appending video ID if filename exists.

    Args:
        url: YouTube video URL
        output_dir: Directory to save downloaded file
        progress_callback: Optional callback receiving download progress (0-100)

    Returns:
        Tuple of (file_path, metadata_dict)
        Metadata dict contains: {"duration": float, "title": str, "uploader": str, "id": str}

    Raises:
        AgeRestrictedError: Video requires age verification
        VideoUnavailableError: Video is unavailable/deleted/private
        CopyrightBlockedError: Video blocked due to copyright
        YouTubeError: Other download errors
    """
    try:
        # Extract video ID first
        video_id = extract_video_id(url)

        # Create progress hook
        progress_hook = _make_progress_hook(progress_callback)

        # Configure yt-dlp options
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading first
            info = ydl.extract_info(url, download=False)

            if not info:
                raise VideoUnavailableError("Failed to extract video information")

            # Extract metadata
            title = info.get("title", "unknown")
            duration = float(info.get("duration", 0))
            uploader = info.get("uploader", "")
            video_id_from_info = info.get("id", video_id)

            # Sanitize filename
            ext = info.get("ext", "mp4")
            sanitized_name = sanitize_filename(title, f".{ext}")

            # Check for file collision
            base_path = output_dir / sanitized_name
            if base_path.exists():
                # Append video ID to make it unique
                name_parts = sanitized_name.rsplit(".", 1)
                sanitized_name = f"{name_parts[0]}_{video_id}.{name_parts[1]}"

            # Update output template with sanitized name
            final_path = output_dir / sanitized_name
            ydl_opts["outtmpl"] = str(output_dir / (sanitized_name.rsplit(".", 1)[0] + ".%(ext)s"))

            # Download the video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                ydl_download.download([url])

            # Find the actual downloaded file (extension might differ)
            downloaded_files = list(output_dir.glob(f"{sanitized_name.rsplit('.', 1)[0]}.*"))
            if not downloaded_files:
                raise YouTubeError("Download completed but file not found")

            final_path = downloaded_files[0]

            metadata = {
                "duration": duration,
                "title": title,
                "uploader": uploader,
                "id": video_id_from_info,
            }

            logger.info(f"Downloaded video: {title} ({video_id}) -> {final_path}")

            return final_path, metadata

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "sign in" in error_msg or "age" in error_msg:
            raise AgeRestrictedError("Video requires age verification (login not supported)")
        elif (
            "unavailable" in error_msg or "deleted" in error_msg or "private" in error_msg
        ):
            raise VideoUnavailableError("Video is unavailable, deleted, or private")
        elif "copyright" in error_msg or "blocked" in error_msg:
            raise CopyrightBlockedError("Video blocked due to copyright")
        else:
            raise YouTubeError(f"Download failed: {e}")
    except (InvalidYouTubeURLError, InsufficientSpaceError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.exception("Unexpected error during video download")
        raise YouTubeError(f"Unexpected error: {e}")


def get_playlist_info(playlist_id: str) -> dict:
    """Extract playlist metadata without downloading videos.

    Args:
        playlist_id: YouTube playlist ID

    Returns:
        Dict with keys:
        - title: Playlist title
        - video_count: Number of videos
        - videos: List of dicts with {id, title, duration}

    Raises:
        YouTubeError: If playlist cannot be accessed
    """
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # Don't download, just extract info
        }

        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

            if not info:
                raise YouTubeError("Failed to extract playlist information")

            videos = []
            for entry in info.get("entries", []):
                if entry:  # Skip unavailable videos
                    videos.append(
                        {
                            "id": entry.get("id", ""),
                            "title": entry.get("title", "Unknown"),
                            "duration": float(entry.get("duration", 0)),
                        }
                    )

            return {
                "title": info.get("title", "Unknown Playlist"),
                "video_count": len(videos),
                "videos": videos,
            }

    except yt_dlp.utils.DownloadError as e:
        raise YouTubeError(f"Failed to access playlist: {e}")
    except Exception as e:
        logger.exception("Unexpected error getting playlist info")
        raise YouTubeError(f"Unexpected error: {e}")


def download_playlist_videos(
    playlist_id: str,
    output_dir: Path,
    skip_ids: Optional[set[str]] = None,
    progress_callback: Optional[PlaylistProgressCallback] = None,
) -> tuple[list[tuple[Path, dict]], list[tuple[str, Exception]]]:
    """Download videos from a YouTube playlist.

    Args:
        playlist_id: YouTube playlist ID
        output_dir: Directory to save videos
        skip_ids: Set of video IDs to skip (for duplicate prevention)
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (successes, failures):
        - successes: List of (file_path, metadata) tuples
        - failures: List of (video_id, exception) tuples

    Note:
        Continues downloading even if individual videos fail
    """
    if skip_ids is None:
        skip_ids = set()

    successes = []
    failures = []

    def report(current: int, step: str, progress: int, failure: dict | None = None) -> None:
        if progress_callback:
            progress_callback(current, step, progress, failure)

    try:
        # Get playlist info first
        playlist_info = get_playlist_info(playlist_id)
        videos = playlist_info["videos"]

        # Filter to only videos we'll actually download
        videos_to_download = [v for v in videos if v["id"] not in skip_ids]
        total = len(videos_to_download)

        logger.info(
            f"Downloading playlist: {playlist_info['title']} ({total} videos to download)"
        )

        for idx, video in enumerate(videos_to_download, start=1):
            video_id = video["id"]
            video_title = video.get("title", "Unknown")

            # Create per-video progress callback (capture idx by value via default arg)
            def per_video_progress(percent: int, current_idx: int = idx) -> None:
                report(current_idx, "downloading", percent)

            report(idx, "downloading", 0)

            try:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                file_path, metadata = download_video(
                    video_url, output_dir, progress_callback=per_video_progress
                )
                successes.append((file_path, metadata))
                report(idx, "downloading", 100)
                logger.info(f"✓ Downloaded: {video_title}")

            except Exception as e:
                logger.warning(f"✗ Failed to download {video_title}: {e}")
                failures.append((video_id, e))
                # Report failure with video info
                report(
                    idx,
                    "downloading",
                    100,
                    failure={"video_id": video_id, "title": video_title, "error": str(e)},
                )

        logger.info(
            f"Playlist download complete: {len(successes)} succeeded, {len(failures)} failed"
        )

        return successes, failures

    except YouTubeError:
        # If we can't get playlist info at all, fail completely
        logger.exception("Failed to access playlist")
        raise
