"""Trimming YYYY-MM-DD year tags to YYYY on MP3 (ID3) and M4A files."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import GEOB, ID3, TDRC, TDRL, TIT2
from mutagen.mp4 import MP4, MP4FreeForm

from music_minion.domain.library import year_tags

SERATO_ATOM = "----:com.serato.dj:markersv2"


def make_mp3(path: Path, date: str, version: int = 4) -> Path:
    """An ID3-only file is enough: mutagen and list_audio only care about tags/suffix."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Song"]))
    tags.add(TDRC(encoding=3, text=[date]))
    tags.add(TDRL(encoding=3, text=["2019-05-01"]))
    tags.add(
        GEOB(
            encoding=0,
            mime="application/octet-stream",
            desc="Serato Markers2",
            data=b"blob",
        )
    )
    tags.save(path, v2_version=version)
    return path


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


def make_m4a(template: Path, path: Path, date: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(template, path)
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["©day"] = [date]
    audio.tags["©nam"] = ["Song"]
    audio.tags[SERATO_ATOM] = [MP4FreeForm(b"serato-blob")]
    audio.save()
    return path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-16", "2026"),
        ("2026-10-16T08:00:00", "2026"),
        ("2026", None),
        ("", None),
    ],
)
def test_year_only(value: str, expected: str | None) -> None:
    assert year_tags.year_only(value) == expected


@pytest.mark.parametrize("version", [3, 4])
def test_mp3_full_date_trimmed_other_frames_kept(tmp_path: Path, version: int) -> None:
    path = make_mp3(tmp_path / "a.mp3", "2026-10-16", version)

    assert year_tags.trim_file(path) == "2026"

    tags = ID3(path)
    assert str(tags["TDRC"].text[0]) == "2026"
    assert str(tags["TDRL"].text[0]) == "2019-05-01"
    assert tags.getall("GEOB")[0].data == b"blob"
    assert tags.version[1] == version
    assert not path.with_name("a.mp3.tmp").exists()


def test_m4a_full_date_trimmed_other_atoms_kept(
    tmp_path: Path, m4a_template: Path
) -> None:
    path = make_m4a(m4a_template, tmp_path / "a.m4a", "2026-09-24")

    assert year_tags.trim_file(path) == "2026"

    tags = MP4(path).tags
    assert tags["©day"] == ["2026"]
    assert tags["©nam"] == ["Song"]
    assert bytes(tags[SERATO_ATOM][0]) == b"serato-blob"


def test_bare_year_left_untouched(tmp_path: Path) -> None:
    path = make_mp3(tmp_path / "a.mp3", "2025")
    before = path.stat().st_mtime_ns

    assert year_tags.trim_file(path) is None
    assert path.stat().st_mtime_ns == before


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    path = make_mp3(tmp_path / "a.mp3", "2026-10-16")

    assert year_tags.trim_file(path, dry_run=True) == "2026"
    assert str(ID3(path)["TDRC"].text[0]) == "2026-10-16"


def test_trim_folder_counts_and_survives_bad_file(tmp_path: Path) -> None:
    make_mp3(tmp_path / "Oct 26" / "a.mp3", "2026-10-16")
    make_mp3(tmp_path / "Oct 26" / "b.mp3", "2026")
    (tmp_path / "Oct 26" / "broken.m4a").write_bytes(b"not an mp4")

    assert year_tags.trim_folder(tmp_path) == (1, 1)
