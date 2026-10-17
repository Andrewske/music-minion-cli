"""
Regression test: _read_comment must read the ID3 COMM frame for MP3s.
ID3 is dict-like (has .get), so it used to fall into the Vorbis branch and
always return None.
"""

from types import SimpleNamespace

from mutagen.id3 import COMM, ID3

from music_minion.domain.sync.engine import _read_comment


def test_reads_id3_comm_frame() -> None:
    tags = ID3()
    tags.add(COMM(encoding=3, lang="eng", desc="", text="mm:chill, mm:dark"))
    audio = SimpleNamespace(tags=tags)

    assert _read_comment(audio) == "mm:chill, mm:dark"


def test_id3_without_comm_returns_none() -> None:
    from mutagen.id3 import TIT2

    tags = ID3()
    tags.add(TIT2(encoding=3, text="Title"))
    assert _read_comment(SimpleNamespace(tags=tags)) is None


def test_reads_vorbis_comment() -> None:
    audio = SimpleNamespace(tags={"COMMENT": ["hello"]})
    assert _read_comment(audio) == "hello"


def test_none_audio_returns_none() -> None:
    assert _read_comment(None) is None
