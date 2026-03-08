"""Waveform generation and caching for audio visualization."""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from loguru import logger
from pydub import AudioSegment


MAX_AUDIO_SIZE_MB = 100  # Prevent OOM
SOUNDCLOUD_WAVEFORM_HEIGHT = 140  # SoundCloud normalizes to this height


class AudioTooLargeError(Exception):
    """File exceeds size limit for waveform generation."""


class FFmpegNotFoundError(Exception):
    """ffmpeg not installed or not in PATH."""


def get_waveform_cache_dir() -> Path:
    """Get the directory for waveform cache files."""
    cache_dir = Path.home() / ".local" / "share" / "music-minion" / "waveforms"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_waveform_path(track_id: int) -> Path:
    """Get the cache path for a track's waveform data."""
    return get_waveform_cache_dir() / f"{track_id}.json"


def has_cached_waveform(track_id: int) -> bool:
    """Check if waveform data is cached for a track."""
    return get_waveform_path(track_id).exists()


def generate_waveform(audio_path: str, track_id: int) -> dict:
    """Generate waveform data using pydub and cache it."""
    cache_path = get_waveform_path(track_id)

    try:
        # Load audio file with pydub
        audio = AudioSegment.from_file(audio_path)
    except FileNotFoundError as e:
        if "ffmpeg" in str(e).lower():
            raise FFmpegNotFoundError(
                "ffmpeg not found. Install: apt install ffmpeg"
            ) from e
        raise
    except Exception as e:
        if "opus" in str(e).lower():
            raise RuntimeError(
                "Opus codec not supported. Ensure ffmpeg built with libopus."
            ) from e
        raise RuntimeError(f"Failed to decode audio: {type(e).__name__}") from e

    try:
        # Check file size before processing
        file_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_AUDIO_SIZE_MB:
            raise AudioTooLargeError(
                f"File too large: {file_size_mb:.1f}MB > {MAX_AUDIO_SIZE_MB}MB"
            )

        # Get raw audio data as numpy array
        samples = np.array(audio.get_array_of_samples())

        # Downsample to ~1000 peaks for web display
        target_peaks = 1000
        chunk_size = max(1, len(samples) // target_peaks)

        # Vectorized min/max computation (10-100x faster than Python loop)
        num_chunks = len(samples) // chunk_size
        truncated = samples[: num_chunks * chunk_size]
        chunks = truncated.reshape(num_chunks, chunk_size)

        min_vals = chunks.min(axis=1)
        max_vals = chunks.max(axis=1)

        # Interleave min/max for WaveSurfer format
        peaks = np.empty(num_chunks * 2, dtype=int)
        peaks[0::2] = min_vals
        peaks[1::2] = max_vals
        peaks = peaks.tolist()

        # Create waveform JSON structure (WaveSurfer format)
        waveform_data = {
            "version": 2,
            "channels": audio.channels,
            "sample_rate": audio.frame_rate,
            "samples_per_pixel": chunk_size,
            "bits": 8,
            "length": len(samples),
            "peaks": peaks,
        }

        # Cache to disk
        with open(cache_path, "w") as f:
            json.dump(waveform_data, f)

        return waveform_data

    except Exception as e:
        raise RuntimeError(f"Failed to generate waveform: {str(e)}")


def fetch_soundcloud_waveform(
    soundcloud_id: str, track_id: int, duration_seconds: float
) -> Optional[dict]:
    """Fetch waveform data from SoundCloud API and convert to WaveSurfer format.

    Args:
        soundcloud_id: SoundCloud track ID
        track_id: Local database track ID (for caching)
        duration_seconds: Track duration in seconds

    Returns:
        Waveform data dict compatible with WaveSurfer, or None on failure
    """
    from .soundcloud_auth import get_web_provider_state

    state = get_web_provider_state()
    if not state or not state.authenticated:
        logger.debug("SoundCloud not authenticated, cannot fetch waveform")
        return None

    token = state.cache.get("token_data", {}).get("access_token")
    if not token:
        return None

    try:
        # Get track metadata to find waveform_url
        response = requests.get(
            f"https://api.soundcloud.com/tracks/{soundcloud_id}",
            headers={"Authorization": f"OAuth {token}"},
            timeout=10,
        )
        if not response.ok:
            logger.warning(f"Failed to get SC track {soundcloud_id}: {response.status_code}")
            return None

        track_data = response.json()
        waveform_url = track_data.get("waveform_url")
        if not waveform_url:
            logger.warning(f"No waveform_url for SC track {soundcloud_id}")
            return None

        # Convert PNG URL to JSON URL
        json_url = waveform_url.replace(".png", ".json")

        # Fetch waveform JSON
        wf_response = requests.get(json_url, timeout=10)
        if not wf_response.ok:
            logger.warning(f"Failed to fetch SC waveform: {wf_response.status_code}")
            return None

        sc_waveform = wf_response.json()
        samples = sc_waveform.get("samples", [])
        if not samples:
            logger.warning(f"Empty waveform samples for SC track {soundcloud_id}")
            return None

        # Convert SoundCloud format (0-140 range) to WaveSurfer format (normalized peaks)
        # SoundCloud provides single values; WaveSurfer expects min/max pairs
        # We'll create symmetric peaks around zero
        normalized = [s / SOUNDCLOUD_WAVEFORM_HEIGHT for s in samples]

        # Downsample to ~1000 peaks if needed (SC provides 1800)
        target_peaks = 1000
        if len(normalized) > target_peaks:
            chunk_size = len(normalized) // target_peaks
            downsampled = []
            for i in range(0, len(normalized) - chunk_size + 1, chunk_size):
                chunk = normalized[i : i + chunk_size]
                downsampled.append(max(chunk))
            normalized = downsampled[:target_peaks]

        # Convert to WaveSurfer min/max format (symmetric around 0)
        # Scale to 16-bit range like local waveforms
        scale = 32767
        peaks = []
        for val in normalized:
            amplitude = int(val * scale)
            peaks.extend([-amplitude, amplitude])

        # Estimate sample rate from duration
        estimated_samples = int(duration_seconds * 44100) if duration_seconds else 0

        waveform_data = {
            "version": 2,
            "channels": 2,
            "sample_rate": 44100,
            "samples_per_pixel": max(1, estimated_samples // len(normalized)),
            "bits": 8,
            "length": estimated_samples,
            "peaks": peaks,
            "source": "soundcloud",
        }

        # Cache to disk
        cache_path = get_waveform_path(track_id)
        with open(cache_path, "w") as f:
            json.dump(waveform_data, f)

        logger.debug(f"Fetched and cached SC waveform for track {track_id}")
        return waveform_data

    except Exception as e:
        logger.warning(f"Failed to fetch SC waveform for {soundcloud_id}: {e}")
        return None
