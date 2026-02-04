"""Stream URL resolution for non-local tracks using yt-dlp.

Extracts playable stream URLs from source permalinks (SoundCloud, YouTube, etc.)
with short-lived caching since stream URLs expire.
"""

from time import time
from typing import Optional

import yt_dlp
from loguru import logger

# Cache stream URLs for 10 minutes (SoundCloud URLs typically expire after ~15 min)
_stream_cache: dict[
    str, tuple[str, float]
] = {}  # source_url -> (stream_url, expires_at)
CACHE_TTL_SECONDS = 600  # 10 minutes


def resolve_stream_url(source_url: str) -> Optional[str]:
    """Resolve a source permalink to a playable stream URL using yt-dlp.

    Uses short-lived caching since stream URLs expire. Cache is checked first,
    and yt-dlp is only called if the cache misses or is expired.

    Args:
        source_url: Source track permalink (SoundCloud, YouTube, etc.)

    Returns:
        Direct stream URL or None if resolution fails
    """
    if not source_url:
        return None

    # Check cache first
    if source_url in _stream_cache:
        stream_url, expires_at = _stream_cache[source_url]
        if time() < expires_at:
            logger.debug(f"Stream URL cache hit for {source_url}")
            return stream_url
        else:
            # Expired - remove from cache
            del _stream_cache[source_url]

    # Extract with yt-dlp
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "extract_flat": False,  # Need actual URL, not just metadata
            # Don't download, just extract
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=False)

            if not info:
                logger.warning(f"yt-dlp returned no info for {source_url}")
                return None

            # Get the actual stream URL
            stream_url = info.get("url")

            if not stream_url:
                # Some extractors put URL in 'formats' list
                formats = info.get("formats", [])
                if formats:
                    # Prefer audio-only formats
                    audio_formats = [f for f in formats if f.get("acodec") != "none"]
                    if audio_formats:
                        # Get best audio quality
                        stream_url = audio_formats[-1].get("url")
                    elif formats:
                        stream_url = formats[-1].get("url")

            if stream_url:
                # Cache the result
                _stream_cache[source_url] = (stream_url, time() + CACHE_TTL_SECONDS)
                logger.debug(f"Resolved stream URL for {source_url}")
                return stream_url
            else:
                logger.warning(
                    f"No stream URL found in yt-dlp response for {source_url}"
                )
                return None

    except yt_dlp.utils.DownloadError as e:
        logger.warning(f"yt-dlp download error for {source_url}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error resolving stream URL for {source_url}")
        return None


def clear_stream_cache() -> None:
    """Clear the stream URL cache.

    Useful for testing or forcing fresh URL resolution.
    """
    _stream_cache.clear()
    logger.debug("Stream URL cache cleared")


def get_cache_stats() -> dict:
    """Get cache statistics for monitoring.

    Returns:
        Dict with cache size and entries (for debugging)
    """
    now = time()
    valid_entries = sum(1 for _, (_, exp) in _stream_cache.items() if exp > now)
    expired_entries = len(_stream_cache) - valid_entries

    return {
        "total_entries": len(_stream_cache),
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
    }


def prune_expired_cache() -> int:
    """Remove expired entries from cache.

    Called periodically to prevent memory growth.

    Returns:
        Number of entries removed
    """
    now = time()
    expired_keys = [k for k, (_, exp) in _stream_cache.items() if exp <= now]

    for key in expired_keys:
        del _stream_cache[key]

    if expired_keys:
        logger.debug(f"Pruned {len(expired_keys)} expired stream URL cache entries")

    return len(expired_keys)
