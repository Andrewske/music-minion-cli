"""Decide what to write for each track from two independent runs + review decisions.

Both runs agree -> auto. Otherwise the track waits for a review decision.
All functions are pure; file IO lives in apply.py.
"""

import re
from typing import Any

from music_minion.domain.metadata_cleanup.render import Separators, expected_view

FIELDS = ("title", "credited_artists", "remixers")
_RAW_SPLIT = re.compile(r"\s*[;，]\s*")

Row = dict[str, Any]


def current_view(tags: dict[str, str]) -> Row:
    """File tags in the comparable shape (raw yt-dlp lists use '，' or ';')."""
    split = lambda value: [n for n in _RAW_SPLIT.split(value.strip()) if n]  # noqa: E731
    return {
        "title": tags.get("title", ""),
        "credited_artists": split(tags.get("artist", "")),
        "remixers": split(tags.get("remixer", "")),
    }


def _fold(value: str | list[str]) -> str | list[str]:
    return (
        [v.casefold() for v in value] if isinstance(value, list) else value.casefold()
    )


def field_diff(left: Row, right: Row, exact: bool = False) -> dict[str, bool]:
    """True per field where the two views differ (case-insensitive unless exact)."""
    norm = (lambda v: v) if exact else _fold
    return {f: norm(left[f]) != norm(right[f]) for f in FIELDS}


def build_apply_row(record: Row, tags: dict[str, str], a: Row, b: Row) -> Row:
    view_a, view_b = expected_view(a), expected_view(b)
    diff = field_diff(view_a, view_b)
    return {
        "id": record["id"],
        "current": current_view(tags),
        "a": view_a,
        "b": view_b,
        "auto": not any(diff.values()),
        "diff": diff,
        "confidence": min(a["confidence"], b["confidence"]),
        "notes": a["notes"]
        if a["notes"] == b["notes"]
        else f"A: {a['notes']} | B: {b['notes']}",
    }


def resolve_final(row: Row, decision: Row | None) -> Row | None:
    """The view to write, or None to leave the file alone."""
    if decision is None:
        return row["a"] if row["auto"] else None
    verdict = decision["verdict"]
    if verdict == "model":
        return row["a"]
    if verdict == "alt":
        return row["b"]
    if verdict == "edited":
        return decision["expected"]
    return None  # gold (= keep current), unclear, exclude


def to_tags(view: Row, sep: Separators) -> dict[str, str]:
    return {
        "title": view["title"].strip(),
        "artist": sep.artists.join(view["credited_artists"]),
        "remixer": sep.artists.join(view["remixers"]),
    }


def tag_changes(
    current: dict[str, str], new: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """Exact per-tag differences {tag: (old, new)}; empty when nothing changes."""
    return {
        key: (current.get(key, ""), value)
        for key, value in new.items()
        if current.get(key, "").strip() != value
    }
