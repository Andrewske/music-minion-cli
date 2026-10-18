"""Tests for waveform generation utilities."""

import json
from array import array
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from web.backend.waveform import (
    MAX_AUDIO_SIZE_MB,
    AudioTooLargeError,
    FFmpegNotFoundError,
    generate_waveform,
    get_waveform_path,
)

FROM_FILE = "web.backend.waveform.AudioSegment.from_file"


@pytest.fixture
def small_audio(tmp_path: Path) -> Path:
    """A tiny placeholder file; decoding is always mocked."""
    path = tmp_path / "song.mp3"
    path.write_bytes(b"\x00" * 1024)
    return path


class TestWaveformGeneration:
    """Test waveform generation with various conditions."""

    def test_waveform_size_limit(self, tmp_path: Path) -> None:
        """Oversized files raise AudioTooLargeError without ever being decoded."""
        large_file = tmp_path / "huge.mp3"
        with open(large_file, "wb") as f:
            # Sparse file: reports the size without writing 100MB to disk
            f.truncate((MAX_AUDIO_SIZE_MB + 1) * 1024 * 1024)

        with patch(FROM_FILE) as mock_from_file:
            with pytest.raises(AudioTooLargeError, match="File too large"):
                generate_waveform(str(large_file), 1)

        mock_from_file.assert_not_called()

    def test_ffmpeg_not_found_error(self, small_audio: Path) -> None:
        """Missing ffmpeg raises FFmpegNotFoundError."""
        with patch(FROM_FILE, side_effect=FileNotFoundError("ffmpeg not found")):
            with pytest.raises(FFmpegNotFoundError, match="ffmpeg not found"):
                generate_waveform(str(small_audio), 1)

    def test_opus_codec_error(self, small_audio: Path) -> None:
        """Opus decode failure has a helpful message."""
        with patch(FROM_FILE, side_effect=Exception("opus codec not supported")):
            with pytest.raises(RuntimeError, match="Opus codec not supported"):
                generate_waveform(str(small_audio), 1)

    def test_vectorized_peaks_correctness(self, small_audio: Path) -> None:
        """Vectorized peaks match a naive per-chunk min/max loop."""
        samples = [((i * 37) % 201) - 100 for i in range(4000)]
        mock_audio = Mock(channels=2, frame_rate=44100)
        mock_audio.get_array_of_samples.return_value = array("h", samples)

        with patch(FROM_FILE, return_value=mock_audio):
            result = generate_waveform(str(small_audio), 7)

        chunk = 4  # 4000 samples // 1000 target peaks
        expected: list[int] = []
        for start in range(0, len(samples), chunk):
            block = samples[start : start + chunk]
            expected += [min(block), max(block)]

        assert result["peaks"] == expected
        assert result["samples_per_pixel"] == chunk
        assert result["length"] == len(samples)
        assert result["channels"] == 2
        assert result["sample_rate"] == 44100
        assert json.loads(get_waveform_path(7).read_text()) == result
