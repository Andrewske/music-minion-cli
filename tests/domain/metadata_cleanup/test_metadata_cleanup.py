from pathlib import Path

from music_minion.domain.metadata_cleanup import batching, evaluate, gold, records
from music_minion.domain.metadata_cleanup.codex_runner import (
    build_prompt,
    prompt_record,
)
from music_minion.domain.metadata_cleanup.render import (
    Separators,
    render_tags,
    render_title,
)


def _parts(**overrides: object) -> dict:
    base = {
        "base_title": "Song",
        "artists": ["A"],
        "featured": [],
        "remixers": [],
        "version": None,
    }
    return {**base, **overrides}


def _record(rid: str, title: str, uploader: str) -> dict:
    return {
        "id": rid,
        "filename": title,
        "soundcloud": {"title": title, "uploader": uploader},
    }


def test_clean_filename_strips_month_and_track_number() -> None:
    assert (
        records.clean_filename(Path("Jun 25_Belik - Maple Cafe.mp3"))
        == "Belik - Maple Cafe"
    )
    assert (
        records.clean_filename(Path("05. Gardella - PARTY.mp3")) == "Gardella - PARTY"
    )


def test_build_record_hides_tags_for_gold() -> None:
    path = records.MUSIC_ROOT / "2025" / "Sept 25" / "x.mp3"
    tags = {"title": "fixed", "artist": "fixed"}
    assert records.build_record(path, tags, None, raw=False)["file_tags"] is None
    assert (
        records.build_record(path, tags, None, raw=True)["file_tags"]["title"]
        == "fixed"
    )


def test_is_fixed_month() -> None:
    assert gold.is_fixed_month("2024/Jan 24/a.mp3")
    assert gold.is_fixed_month("2025/Sept 25/a.mp3")
    assert not gold.is_fixed_month("2025/Oct 25/a.mp3")
    assert not gold.is_fixed_month("2026/Jan 26/a.mp3")


def test_expected_from_tags_prefers_tpe4_then_title() -> None:
    tags = {"title": "Back to Black (Tape B x Effin Flip)", "artist": "Amy Winehouse"}
    assert gold.expected_from_tags(tags)["remixers"] == ["Tape B", "Effin"]
    tags["remixer"] = "Tape B; Effin"
    assert gold.expected_from_tags(tags)["remixers"] == ["Tape B", "Effin"]


def test_expected_from_tags_rejects_raw_looking_tags() -> None:
    assert gold.expected_from_tags({"title": "SONG [FREE DL]", "artist": "A"}) is None
    assert gold.expected_from_tags({"title": "A - Song", "artist": "A"}) is None
    assert gold.expected_from_tags({"title": "Song", "artist": "A， B"}) is None
    assert (
        gold.expected_from_tags({"title": "Song (Extended Mix)", "artist": "A"})[
            "remixers"
        ]
        == []
    )


def test_batches_group_shared_rare_keywords() -> None:
    rows = [
        _record("1", "Chase & Status - Baddadan", "Chase & Status"),
        _record("2", "Lonely Song", "Someone"),
        _record("3", "Other Tune", "Nobody"),
        _record("4", "Backbone (Chase & Status VIP)", "Chase & Status"),
    ]
    first = batching.make_batches(rows, size=2)[0]
    assert [r["id"] for r in first] == ["1", "4"]


def test_batches_cover_every_record_once() -> None:
    rows = [_record(str(i), f"Track {i}", f"u{i % 3}") for i in range(23)]
    batches = batching.make_batches(rows, size=10)
    assert [len(b) for b in batches] == [10, 10, 3]
    assert sorted(r["id"] for b in batches for r in b) == sorted(r["id"] for r in rows)


def test_render_title_variants() -> None:
    assert render_title(_parts()) == "Song"
    assert render_title(_parts(version="VIP")) == "Song (VIP)"
    flip = _parts(featured=["F1", "F2"], remixers=["R1", "R2"], version="Flip")
    assert render_title(flip) == "Song ft. F1 & F2 (R1 x R2 Flip)"
    assert (
        render_title(flip, Separators(featured_in_title=", "))
        == "Song ft. F1, F2 (R1 x R2 Flip)"
    )


def test_render_tags_puts_featured_in_artist_field() -> None:
    tags = render_tags(
        _parts(artists=["A", "B"], featured=["F"], remixers=["R"], version="Remix")
    )
    assert tags == {
        "title": "Song ft. F (R Remix)",
        "artist": "A; B; F",
        "remixer": "R",
    }


def test_compare_ignores_case_and_unions_featured() -> None:
    expected = {
        "title": "SONG ft. F (R Remix)",
        "credited_artists": ["A", "F"],
        "remixers": ["r"],
    }
    proposal = _parts(featured=["F"], remixers=["R"], version="Remix")
    match = evaluate.compare(expected, proposal)
    assert match == {
        "title_exact": False,
        "title_ignore_case": True,
        "artists": True,
        "remixers": True,
    }


def test_prompt_record_truncates_description_and_drops_empty() -> None:
    record = {
        "id": "x",
        "filename": "f",
        "soundcloud": {"description": "d" * 5000},
        "file_tags": None,
    }
    view = prompt_record(record)
    assert len(view["soundcloud"]["description"]) == 800
    assert "file_tags" not in view
    assert '"id": "x"' in build_prompt("rules", [record])


def test_apply_corrections_swaps_and_drops() -> None:
    rows = [{"id": i, "expected": {"title": "old"}} for i in ("a", "b", "c", "d")]
    corrections = {
        "a": {"verdict": "model", "expected": {"title": "new"}},
        "b": {"verdict": "unclear", "expected": None},
        "c": {"verdict": "exclude", "expected": None},
    }
    fixed = gold.apply_corrections(rows, corrections)
    assert [(r["id"], r["expected"]["title"]) for r in fixed] == [
        ("a", "new"),
        ("d", "old"),
    ]


def test_byte_range_parsing() -> None:
    from music_minion.domain.metadata_cleanup.review import _byte_range

    assert _byte_range(None, 100) == (0, 99)
    assert _byte_range("bytes=10-", 100) == (10, 99)
    assert _byte_range("bytes=10-19", 100) == (10, 19)
    assert _byte_range("bytes=-30", 100) == (70, 99)
    assert _byte_range("bytes=90-500", 100) == (90, 99)


def test_normalize_version_maps_to_fixed_list() -> None:
    from music_minion.domain.metadata_cleanup.normalize import normalize_version

    assert normalize_version("RMX") == "Remix"
    assert normalize_version("ÆDIT") == "Edit"
    assert normalize_version("Heavy Re-Trip") == "Flip"
    assert normalize_version("jersey club edit") == "Jersey Club Edit"
    assert normalize_version("UKG Edit") == "UKG Edit"
    assert normalize_version("vip") == "VIP"
    assert normalize_version("extended mix") == "Extended Mix"
    assert normalize_version("") is None


def test_normalize_proposal_falls_back_to_uploader() -> None:
    from music_minion.domain.metadata_cleanup.normalize import normalize_proposal

    raw = _parts(artists=["Unknown"], featured=["X", "X"], version="rmx")
    fixed = normalize_proposal({**raw, "confidence": 0.9, "notes": ""}, "Uploader")
    assert fixed["artists"] == ["Uploader"]
    assert fixed["featured"] == ["X"]
    assert fixed["version"] == "Remix"
    assert fixed["confidence"] == 0.5


def _proposal(**overrides: object) -> dict:
    return {**_parts(**overrides), "confidence": 0.9, "notes": ""}


def test_build_apply_row_auto_when_runs_agree_ignoring_case() -> None:
    from music_minion.domain.metadata_cleanup import plan

    record = {"id": "x"}
    tags = {"title": "SONG [FREE DL]", "artist": "A， B"}
    row = plan.build_apply_row(
        record, tags, _proposal(base_title="Song"), _proposal(base_title="SONG")
    )
    assert row["auto"] is True
    assert row["current"]["credited_artists"] == ["A", "B"]
    other = plan.build_apply_row(record, tags, _proposal(), _proposal(artists=["B"]))
    assert other["auto"] is False
    assert other["diff"] == {
        "title": False,
        "credited_artists": True,
        "remixers": False,
    }


def test_resolve_final_by_verdict() -> None:
    from music_minion.domain.metadata_cleanup import plan

    row = {"auto": False, "a": {"title": "A"}, "b": {"title": "B"}}
    assert plan.resolve_final(row, None) is None
    assert plan.resolve_final({**row, "auto": True}, None) == {"title": "A"}
    assert plan.resolve_final(row, {"verdict": "alt"}) == {"title": "B"}
    assert plan.resolve_final(
        row, {"verdict": "edited", "expected": {"title": "E"}}
    ) == {"title": "E"}
    for verdict in ("gold", "unclear", "exclude"):
        assert plan.resolve_final({**row, "auto": True}, {"verdict": verdict}) is None


def test_tag_changes_only_reports_real_differences() -> None:
    from music_minion.domain.metadata_cleanup import plan

    view = {
        "title": "Song (R Remix)",
        "credited_artists": ["A", "B"],
        "remixers": ["R"],
    }
    new = plan.to_tags(view, Separators())
    assert new == {"title": "Song (R Remix)", "artist": "A; B", "remixer": "R"}
    current = {"title": "Song (R Remix)", "artist": "A， B", "remixer": ""}
    assert plan.tag_changes(current, new) == {
        "artist": ("A， B", "A; B"),
        "remixer": ("", "R"),
    }


def test_write_tags_preserves_other_frames(tmp_path: Path) -> None:
    from mutagen.id3 import ID3, TBPM, TIT2, TPE2

    from music_minion.domain.metadata_cleanup.apply import write_tags

    path = tmp_path / "t.mp3"
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["old"]))
    tags.add(TPE2(encoding=3, text=["Kevin"]))
    tags.add(TBPM(encoding=3, text=["140"]))
    tags.save(path, v2_version=3)
    write_tags(path, {"title": "Ñew", "artist": "A; B", "remixer": ""})
    after = ID3(path)
    assert after.version == (2, 3, 0)
    assert (str(after["TIT2"]), str(after["TPE1"])) == ("Ñew", "A; B")
    assert str(after["TPE2"]) == "Kevin" and str(after["TBPM"]) == "140"
    assert "TPE4" not in after
