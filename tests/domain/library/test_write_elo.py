"""Writing playlist ELO into audio files (the playlist export's sync_metadata path)."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.mp4 import MP4

from music_minion.domain.library.metadata import write_elo_to_file

ELO_ATOM = "----:com.apple.iTunes:PLAYLIST_ELO"


@pytest.fixture(scope="session")
def m4a_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed; needed to build an m4a fixture")
    path = tmp_path_factory.mktemp("m4a") / "template.m4a"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-t", "0.1", "-c:a", "aac", "-map_metadata", "-1", str(path)],
        check=True,
    )  # fmt: skip
    return path


def test_writes_playlist_elo_and_comment_prefix(
    m4a_template: Path, tmp_path: Path
) -> None:
    path = tmp_path / "t.m4a"
    shutil.copy(m4a_template, path)

    assert write_elo_to_file(str(path), playlist_elo=1623.4, update_comment=True)

    audio = MP4(path)
    assert bytes(audio[ELO_ATOM][0]) == b"1623.4"
    assert audio["\xa9cmt"][0] == "1623"


def test_skips_unrated_tracks(m4a_template: Path, tmp_path: Path) -> None:
    path = tmp_path / "t.m4a"
    shutil.copy(m4a_template, path)

    assert write_elo_to_file(str(path), playlist_elo=1500.0, update_comment=True)

    assert ELO_ATOM not in MP4(path)
