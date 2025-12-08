"""Waveform generation and caching for audio visualization."""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional


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
    """Generate waveform data using audiowaveform CLI and cache it."""
    cache_path = get_waveform_path(track_id)

    # Run audiowaveform CLI
    cmd = [
        "audiowaveform",
        "-i",
        audio_path,
        "-o",
        str(cache_path),
        "--pixels-per-second",
        "50",
        "-b",
        "8",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Read the generated JSON
        with open(cache_path, "r") as f:
            waveform_data = json.load(f)

        return waveform_data

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to generate waveform: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("audiowaveform CLI not found. Please install it first.")
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse waveform JSON output")
