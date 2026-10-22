"""M4A (MP4 atom) support: read mapping, preserving writes, restore, ingest."""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.metadata_cleanup import ingest, records
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings

URL = "https://soundcloud.com/u/song"
SC_URL_ATOM = "----:com.apple.iTunes:WWWAUDIOFILE"
SERATO_ATOM = "----:com.serato.dj:markersv2"

MakeM4a = Callable[..., Path]


@pytest.fixture(scope="session")
def m4a_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A tiny real AAC/MP4 file (no tags), generated once with ffmpeg."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed; needed to build an m4a fixture")
    path = tmp_path_factory.mktemp("m4a") / "template.m4a"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-t", "0.1", "-c:a", "aac", "-map_metadata", "-1", str(path)],
        check=True,
    )  # fmt: skip
    MP4(path).delete()  # ffmpeg adds an encoder (©too) atom; start untagged
    return path


def scdl_tags(title: str, url: str) -> dict[str, list]:
    """The atoms scdl writes to a SoundCloud m4a download, plus a Serato atom."""
    return {
        "©nam": [title],
        "©ART": ["Uploader"],
        "©gen": ["House"],
        "©day": ["2026"],
        "©too": ["Lavf61"],
        "©cmt": ["desc"],
        "covr": [MP4Cover(b"\x89PNGfake", imageformat=MP4Cover.FORMAT_PNG)],
        "purl": [url],
        SC_URL_ATOM: [MP4FreeForm(url.encode("utf-8"))],
        SERATO_ATOM: [MP4FreeForm(b"\x01\x01serato-blob")],
    }


@pytest.fixture
def make_m4a(m4a_template: Path) -> MakeM4a:
    def _make(path: Path, tags: dict[str, list]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(m4a_template, path)
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.update(tags)
        audio.save()
        return path

    return _make


def test_list_audio_finds_mp3_and_m4a_but_skips_conflicts(tmp_path: Path) -> None:
    for name in ("a.mp3", "b.m4a", "c.sync-conflict-1.m4a", "d.flac", "e.txt"):
        (tmp_path / "sub").mkdir(exist_ok=True)
        (tmp_path / "sub" / name).write_bytes(b"")
    found = [p.name for p in records.list_audio(tmp_path)]
    assert found == ["a.mp3", "b.m4a"]


def test_read_tags_maps_mp4_atoms(tmp_path: Path, make_m4a: MakeM4a) -> None:
    tags = {**scdl_tags("Song (R Flip)", URL), "aART": ["Album Artist"]}
    tags[records.MP4_REMIXER] = [MP4FreeForm("Rëmixer".encode())]
    path = make_m4a(tmp_path / "t.m4a", tags)
    assert records.read_tags(path) == {
        "title": "Song (R Flip)",
        "artist": "Uploader",
        "album_artist": "Album Artist",
        "genre": "House",
        "date": "2026",
        "comment": "desc",
        "remixer": "Rëmixer",
        "source_url": URL,
    }


def test_read_tags_source_url_prefers_freeform_then_purl(
    tmp_path: Path, make_m4a: MakeM4a
) -> None:
    both = {"purl": ["https://purl"], SC_URL_ATOM: [MP4FreeForm(b"https://ff")]}
    assert records.read_tags(make_m4a(tmp_path / "a.m4a", both))["source_url"] == (
        "https://ff"
    )
    only_purl = {"purl": ["https://purl"]}
    assert records.read_tags(make_m4a(tmp_path / "b.m4a", only_purl))["source_url"] == (
        "https://purl"
    )


def test_read_tags_untagged_m4a_is_empty(tmp_path: Path, m4a_template: Path) -> None:
    path = tmp_path / "bare.m4a"
    path.write_bytes(m4a_template.read_bytes())
    assert records.read_tags(path) == {}


def test_read_and_write_reject_unknown_formats(tmp_path: Path) -> None:
    path = tmp_path / "x.flac"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="unsupported"):
        records.read_tags(path)
    with pytest.raises(ValueError, match="unsupported"):
        apply_mod.write_tags(path, {"title": "x"})


def test_write_tags_m4a_preserves_other_atoms(
    tmp_path: Path, make_m4a: MakeM4a
) -> None:
    path = make_m4a(tmp_path / "t.m4a", scdl_tags("RAW TITLE", URL))
    before = dict(MP4(path).tags)

    apply_mod.write_tags(path, {"title": "Ñew", "artist": "A; B", "remixer": "R"})

    after = MP4(path).tags
    assert after["©nam"] == ["Ñew"] and after["©ART"] == ["A; B"]
    assert bytes(after[records.MP4_REMIXER][0]) == b"R"
    for key in ("covr", "©cmt", "©gen", "©day", "©too", "purl"):
        assert after[key] == before[key], key
    for key in (SC_URL_ATOM, SERATO_ATOM):
        assert bytes(after[key][0]) == bytes(before[key][0]), key
    assert not path.with_name("t.m4a.tmp").exists()


def test_write_tags_m4a_empty_value_deletes_atom(
    tmp_path: Path, make_m4a: MakeM4a
) -> None:
    tags = {**scdl_tags("T", URL), records.MP4_REMIXER: [MP4FreeForm(b"Old")]}
    path = make_m4a(tmp_path / "t.m4a", tags)
    apply_mod.write_tags(path, {"remixer": "", "artist": ""})
    after = MP4(path).tags
    assert records.MP4_REMIXER not in after and "©ART" not in after
    assert after["©nam"] == ["T"]


def test_apply_then_restore_round_trips_m4a(
    tmp_path: Path, make_m4a: MakeM4a, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(records, "MUSIC_ROOT", tmp_path)
    monkeypatch.setattr(apply_mod, "BACKUPS_DIR", tmp_path / "backups")
    path = make_m4a(tmp_path / "2026/t.m4a", scdl_tags("RAW", URL))
    original = apply_mod.read_current(path)
    new = {"title": "Song", "artist": "A", "remixer": "R"}

    backup, written, failed = apply_mod.apply_changes(
        [{"id": "2026/t.m4a", "new": new}]
    )
    assert (written, failed) == (1, [])
    assert apply_mod.read_current(path) == new

    assert apply_mod.restore(backup) == 1
    assert (
        apply_mod.read_current(path)
        == original
        == {
            "title": "RAW",
            "artist": "Uploader",
            "remixer": "",
        }
    )
    assert records.MP4_REMIXER not in MP4(path).tags
    assert "covr" in MP4(path).tags


def test_run_ingest_cleans_new_m4a(
    tmp_path: Path, make_m4a: MakeM4a, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "EDM"
    monkeypatch.setattr(records, "MUSIC_ROOT", root)
    monkeypatch.setattr(ingest, "LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ingest, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(apply_mod, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(ingest, "raw_records", lambda scanned: [
        {"id": records.track_id(p), "filename": p.stem, "soundcloud": None, "file_tags": t}
        for p, t in scanned
    ])  # fmt: skip
    track_id = "2026/Oct 26/R - Artist - Song (R FLIP).m4a"
    make_m4a(root / track_id, scdl_tags("Artist - Song (R FLIP)", URL))
    proposal = {
        "id": track_id, "base_title": "Song", "artists": ["Artist"], "featured": [],
        "remixers": ["R"], "version": "Flip", "confidence": 0.9, "notes": "",
    }  # fmt: skip
    monkeypatch.setattr(ingest, "clean_rows", lambda rows, settings: ([proposal], []))

    summary = ingest.run_ingest("2026", CodexSettings(), None)

    assert summary == {
        "new": 1, "written": 1, "failed": 0, "pending": 0, "codex_missing": 0,
    }  # fmt: skip
    tags = MP4(root / track_id).tags
    assert tags["©nam"] == ["Song (R Flip)"] and tags["©ART"] == ["Artist"]
    assert bytes(tags[records.MP4_REMIXER][0]) == b"R"
    assert "covr" in tags and bytes(tags[SC_URL_ATOM][0]) == URL.encode()
    assert ingest.load_ledger()[URL]["status"] == "applied"
