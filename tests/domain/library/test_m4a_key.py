"""Reading the musical key from M4A freeform atoms, in Serato's casing."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.mp4 import MP4, MP4FreeForm

from music_minion.domain.library.metadata import extract_track_metadata


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


def make_m4a_with_key(template: Path, path: Path, atom: str, key: str) -> Path:
    shutil.copy(template, path)
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags[atom] = [MP4FreeForm(key.encode("utf-8"))]
    audio.tags["tmpo"] = [75]
    audio.save()
    return path


@pytest.mark.parametrize(
    "atom", ["----:com.apple.iTunes:initialkey", "----:com.apple.iTunes:INITIALKEY"]
)
def test_reads_key_from_either_atom_casing(
    m4a_template: Path, tmp_path: Path, atom: str
) -> None:
    path = make_m4a_with_key(m4a_template, tmp_path / "t.m4a", atom, "Abm")

    track = extract_track_metadata(str(path))

    assert track.key == "Abm"
    assert track.bpm == 75.0
