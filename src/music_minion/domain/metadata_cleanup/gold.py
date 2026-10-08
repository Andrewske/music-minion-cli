"""Derive expected cleanup output from library months that were already fixed.

The fixed format (from the old music-library normalizer, then hand edits):
  TIT2 = "Title ft. Featured (Remixer Type)"
  TPE1 = original artists AND featured artists, ';'-separated
  TPE4 = remixers, ';'-separated (often missing; fall back to the title)
"""

import re
from typing import Any, Optional

# Months whose tags are considered fixed. Everything else is raw.
FIXED_MONTHS: dict[str, Optional[set[str]]] = {
    "2024": None,  # None = all months
    "2025": {"Feb 25", "Apr 25", "May 25", "Jun 25", "Jul 25", "Aug 25", "Sept 25"},
}

_UNFIXED_SIGNS = re.compile(r"free\s*(dl|download)|out now|，| - ", re.IGNORECASE)
_TITLE_REMIX_RE = re.compile(r"\(([^()]+?)\s+([\w'-]+)\)\s*$")
_SPLIT_RE = re.compile(r"\s*;\s*")


def is_fixed_month(track_id: str) -> bool:
    year, month = track_id.split("/")[:2]
    if year not in FIXED_MONTHS:
        return False
    months = FIXED_MONTHS[year]
    return months is None or month in months


def split_names(value: str) -> list[str]:
    return [name for name in _SPLIT_RE.split(value.strip()) if name]


def remixers_from_title(title: str) -> list[str]:
    """'Song (A x B Flip)' -> ['A', 'B']; non-credit mixes return []."""
    match = _TITLE_REMIX_RE.search(title)
    if not match or match.group(1).lower() in {"extended", "radio", "original"}:
        return []
    return [name.strip() for name in re.split(r"\s+x\s+|;", match.group(1))]


def expected_from_tags(tags: dict[str, str]) -> Optional[dict[str, Any]]:
    """Expected output from fixed tags, or None if the tags still look raw."""
    title, artist = tags.get("title", ""), tags.get("artist", "")
    if not title or not artist or _UNFIXED_SIGNS.search(title + artist):
        return None
    remixer = tags.get("remixer")
    return {
        "title": title,
        "credited_artists": split_names(artist),
        "remixers": split_names(remixer) if remixer else remixers_from_title(title),
    }


# Verdicts saved by the review page that keep a track in scoring.
SCORED_VERDICTS = {"gold", "model", "edited"}


def apply_corrections(
    rows: list[dict[str, Any]], corrections: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Swap in reviewed expectations; drop tracks marked unclear or excluded."""
    fixed = []
    for row in rows:
        correction = corrections.get(row["id"])
        if correction is None:
            fixed.append(row)
        elif correction["verdict"] in SCORED_VERDICTS:
            fixed.append({**row, "expected": correction["expected"]})
    return fixed
