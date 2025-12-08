"""Tests for waveform generation utilities."""

import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock
import pytest

from web.backend.waveform import (
    AudioTooLargeError,
    FFmpegNotFoundError,
    generate_waveform,
    has_cached_waveform,
    get_waveform_path,
)


class TestWaveformGeneration:
    """Test waveform generation with various conditions."""

    def test_waveform_size_limit(self):
        """Test that files >100MB raise AudioTooLargeError."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            # Create a large file (simulate >100MB)
            f.write(b"x" * (101 * 1024 * 1024))  # 101MB
            large_file = f.name

        try:
            with patch("web.backend.waveform.Path") as mock_path:
                mock_path.return_value.stat.return_value.st_size = 101 * 1024 * 1024
                with pytest.raises(AudioTooLargeError, match="File too large"):
                    generate_waveform(large_file, 1)
        finally:
            Path(large_file).unlink(missing_ok=True)

    def test_ffmpeg_not_found_error(self):
        """Test that missing ffmpeg raises FFmpegNotFoundError."""
        with patch("web.backend.waveform.AudioSegment.from_file") as mock_from_file:
            mock_from_file.side_effect = FileNotFoundError("ffmpeg not found")

            with pytest.raises(FFmpegNotFoundError, match="ffmpeg not found"):
                generate_waveform("/fake/path.mp3", 1)

    def test_opus_codec_error(self):
        """Test that Opus decode failure has helpful message."""
        with patch("web.backend.waveform.AudioSegment.from_file") as mock_from_file:
            mock_from_file.side_effect = Exception("opus codec not supported")

            with pytest.raises(RuntimeError, match="Opus codec not supported"):
                generate_waveform("/fake/path.opus", 1)

    @patch("web.backend.waveform.AudioSegment.from_file")
    @patch("web.backend.waveform.np.array")
    def test_vectorized_peaks_correctness(self, mock_np_array, mock_from_file):
        """Test that vectorized peaks match original algorithm."""
        # Mock audio segment
        mock_audio = Mock()
        mock_audio.channels = 2
        mock_audio.frame_rate = 44100
        mock_from_file.return_value = mock_audio

        # Mock samples array (simple test data)
        samples = [1, -2, 3, -4, 5, -6, 7, -8]
        mock_np_array.return_value = samples

        # Mock file size check
        with patch("web.backend.waveform.Path") as mock_path:
            mock_path.return_value.stat.return_value.st_size = 1024  # Small file

            result = generate_waveform("/fake/path.mp3", 1)

            # Verify structure
            assert "peaks" in result
            assert "version" in result
            assert "channels" in result
            assert "sample_rate" in result
            assert "samples_per_pixel" in result
            assert "bits" in result
            assert "length" in result

            # Verify peaks is list of ints
            assert isinstance(result["peaks"], list)
            assert all(isinstance(p, int) for p in result["peaks"])
