"""Deterministic cleanup applied to every model proposal before scoring/applying.

Guards against the model drifting from the guidelines: version words are
mapped onto a fixed vocabulary, and artists can never be empty or "Unknown".
"""

import re
from typing import Any

CANONICAL_VERSIONS = (
    "Remix", "Flip", "Edit", "Bootleg", "VIP", "VIP Edit", "Rework", "Refix",
    "Mashup", "Cover", "Reboot", "Remake", "Dub", "Extended Mix", "Radio Edit", "Club Mix",
)  # fmt: skip
_CANONICAL = {version.casefold(): version for version in CANONICAL_VERSIONS}
_SYNONYMS = {
    "rmx": "Remix", "mix": "Remix", "refresh": "Remix", "reload": "Remix",
    "ædit": "Edit", "re-edit": "Edit", "reedit": "Edit", "rebook": "Edit",
    "re-trip": "Flip", "retrip": "Flip", "booped": "Flip", "bossed": "Flip",
    "probed": "Flip", "grogged": "Flip", "v.i.p": "VIP", "v.i.p.": "VIP",
    "vip mix": "VIP", "bootleg remix": "Bootleg", "mash-up": "Mashup",
}  # fmt: skip
# Genre qualifiers that may prefix a version ("Jersey Club Edit", "UKG Remix").
GENRE_QUALIFIERS = (
    "Jersey Club", "UKG", "DnB", "Drum & Bass", "Dubstep", "Riddim", "Trap",
    "Techno", "House", "Tech House", "Garage", "Hardstyle", "Drill", "Halftime",
    "Footwork", "Amapiano", "Breaks", "Moombahton", "Wave", "Phonk", "Bass",
)  # fmt: skip
_QUALIFIERS = {q.casefold(): q for q in GENRE_QUALIFIERS}
_PLACEHOLDER_ARTISTS = {"", "unknown", "unknown artist", "various artists", "n/a"}


def _canonical_word(text: str) -> str | None:
    key = text.casefold().strip()
    return _CANONICAL.get(key) or _SYNONYMS.get(key)


def normalize_version(version: str | None) -> str | None:
    """Map a version tag onto the fixed list, keeping a genre qualifier if present."""
    if not version or not version.strip():
        return None
    if (exact := _canonical_word(version)) is not None:
        return exact
    for qualifier_key, qualifier in _QUALIFIERS.items():
        if version.casefold().startswith(qualifier_key + " "):
            base = _canonical_word(version[len(qualifier_key) + 1 :])
            if base:
                return f"{qualifier} {base}"
    words = re.split(r"\s+", version.strip())
    return _canonical_word(words[-1]) or version.strip()


def _clean_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned = []
    for name in (n.strip() for n in names):
        if name.casefold() in _PLACEHOLDER_ARTISTS or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        cleaned.append(name)
    return cleaned


def normalize_proposal(
    proposal: dict[str, Any], uploader: str | None
) -> dict[str, Any]:
    """Return a cleaned copy; falls back to the uploader when no artist survives."""
    artists = _clean_names(proposal["artists"])
    taken = {name.casefold() for name in artists}
    featured = [
        f for f in _clean_names(proposal["featured"]) if f.casefold() not in taken
    ]
    fixed = {
        **proposal,
        "artists": artists,
        "featured": featured,
        "remixers": _clean_names(proposal["remixers"]),
        "version": normalize_version(proposal.get("version")),
    }
    if not artists and uploader:
        fixed["artists"] = [uploader]
        fixed["confidence"] = min(proposal["confidence"], 0.5)
        fixed["notes"] = (
            f"{proposal['notes']} [no artist returned; fell back to uploader]".strip()
        )
    return fixed
