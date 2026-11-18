"""Playlist ELO comment prefix on MP3s: keep the existing comment, one frame."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import COMM
from mutagen.mp3 import MP3

from music_minion.domain.library.metadata import write_elo_to_file


@pytest.fixture(scope="session")
def mp3_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed; needed to build an mp3 fixture")
    path = tmp_path_factory.mktemp("mp3") / "template.mp3"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-t", "0.1", "-c:a", "libmp3lame", "-map_metadata", "-1", str(path)],
        check=True,
    )  # fmt: skip
    return path


def make_mp3(template: Path, path: Path, frames: list[COMM]) -> Path:
    shutil.copy(template, path)
    audio = MP3(path)
    if audio.tags is None:
        audio.add_tags()
    for frame in frames:
        audio.tags.add(frame)
    audio.save()
    return path


def comment_frames(path: Path) -> list[COMM]:
    return MP3(path).tags.getall("COMM")


def test_repeat_exports_keep_one_prefixed_comment(
    mp3_template: Path, tmp_path: Path
) -> None:
    note = COMM(encoding=3, lang="eng", desc="", text="S3 opener - big vocal")
    path = make_mp3(mp3_template, tmp_path / "t.mp3", [note])

    write_elo_to_file(str(path), playlist_elo=1623.0, update_comment=True)
    write_elo_to_file(str(path), playlist_elo=1700.0, update_comment=True)

    assert [f.text for f in comment_frames(path)] == [["1700 - S3 opener - big vocal"]]


def test_repairs_comment_split_by_older_writes(
    mp3_template: Path, tmp_path: Path
) -> None:
    split = COMM(encoding=3, lang="eng", desc="", text=["1700", "1623", "S3 opener"])
    path = make_mp3(mp3_template, tmp_path / "t.mp3", [split])

    write_elo_to_file(str(path), playlist_elo=1650.0, update_comment=True)

    assert [f.text for f in comment_frames(path)] == [["1650 - S3 opener"]]


def test_leaves_described_comment_frames_alone(
    mp3_template: Path, tmp_path: Path
) -> None:
    norm = COMM(encoding=3, lang="eng", desc="iTunNORM", text=" 0000 0000")
    path = make_mp3(mp3_template, tmp_path / "t.mp3", [norm])

    write_elo_to_file(str(path), playlist_elo=1650.0, update_comment=True)

    texts = {f.desc: f.text for f in comment_frames(path)}
    assert texts == {"iTunNORM": [" 0000 0000"], "": ["1650"]}
