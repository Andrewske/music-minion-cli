"""Waveform generation and caching for audio visualization."""

import json
from pathlib import Path
from pydub import AudioSegment
import numpy as np


MAX_AUDIO_SIZE_MB = 100  # Prevent OOM


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
