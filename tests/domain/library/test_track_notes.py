"""Track notes read/write the COMMENT tag Serato shows, keeping every other tag."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import COMM, ID3, TBPM, TIT2
from mutagen.mp4 import MP4, MP4FreeForm

from music_minion.domain.library import track_notes

SERATO_ATOM = "----:com.serato.dj:markersv2"


@pytest.fixture
def mp3(tmp_path: Path) -> Path:
    path = tmp_path / "t.mp3"
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Song"]))
    tags.add(TBPM(encoding=3, text=["140"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["SoundCloud description"]))
    tags.add(COMM(encoding=3, lang="eng", desc="iTunNORM", text=["0000"]))
    tags.save(path, v2_version=3)
    return path


@pytest.fixture
def m4a(tmp_path: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed; needed to build an m4a fixture")
    path = tmp_path / "t.m4a"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-t", "0.1", "-c:a", "aac", "-map_metadata", "-1", str(path)],
        check=True,
    )  # fmt: skip
    audio = MP4(path)
    audio.tags["©nam"] = ["Song"]
    audio.tags["©cmt"] = ["SoundCloud description"]
    audio.tags[SERATO_ATOM] = [MP4FreeForm(b"\x01\x01serato-blob")]
    audio.save()
    return path


def test_mp3_reads_serato_comment_not_itunnorm(mp3: Path) -> None:
    assert track_notes.read_notes(mp3) == "SoundCloud description"


def test_mp3_write_replaces_comment_and_keeps_other_frames(mp3: Path) -> None:
    track_notes.write_notes(mp3, "rolling bass, good opener")
    after = ID3(mp3)
    assert after.version == (2, 3, 0)
    assert track_notes.read_notes(mp3) == "rolling bass, good opener"
    assert len([f for f in after.getall("COMM") if f.desc == ""]) == 1
    assert str(after["COMM:iTunNORM:eng"]) == "0000"
    assert str(after["TIT2"]) == "Song" and str(after["TBPM"]) == "140"
    assert not mp3.with_name("t.mp3.tmp").exists()


def test_mp3_empty_notes_delete_comment(mp3: Path) -> None:
    track_notes.write_notes(mp3, "")
    assert track_notes.read_notes(mp3) == ""


def test_mp3_without_tags(tmp_path: Path) -> None:
    path = tmp_path / "bare.mp3"
    path.write_bytes(b"\xff\xfb\x90\x00" * 64)
    assert track_notes.read_notes(path) == ""
    track_notes.write_notes(path, "note")
    assert track_notes.read_notes(path) == "note"


def test_m4a_write_keeps_serato_atom(m4a: Path) -> None:
    assert track_notes.read_notes(m4a) == "SoundCloud description"
    track_notes.write_notes(m4a, "my note")
    tags = MP4(m4a).tags
    assert tags["©cmt"] == ["my note"] and tags["©nam"] == ["Song"]
    assert bytes(tags[SERATO_ATOM][0]) == b"\x01\x01serato-blob"
    track_notes.write_notes(m4a, "")
    assert "©cmt" not in MP4(m4a).tags


def test_unsupported_format(tmp_path: Path) -> None:
    path = tmp_path / "t.opus"
    path.write_bytes(b"")
    assert not track_notes.supports_notes(path)
    with pytest.raises(ValueError, match="unsupported"):
        track_notes.read_notes(path)
