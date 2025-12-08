"""Waveform generation and caching for audio visualization."""

import json
from pathlib import Path
from pydub import AudioSegment
import numpy as np


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

        # Get raw audio data as numpy array
        samples = np.array(audio.get_array_of_samples())

        # Downsample to ~1000 peaks for web display
        target_peaks = 1000
        chunk_size = max(1, len(samples) // target_peaks)

        # Extract min/max for each chunk
        peaks = []
        for i in range(0, len(samples), chunk_size):
            chunk = samples[i : i + chunk_size]
            if len(chunk) > 0:
                peaks.append(int(chunk.min()))
                peaks.append(int(chunk.max()))

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
