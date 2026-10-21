"""Mine Kevin's not-for-feed flags for rule suggestions (#31).

Pure: inputs are plain track dicts. Candidate rules come from what his own
flags share (title keywords and phrases, genre/tags, duration thresholds).
Each candidate is then scored with the real rule matcher, so the evidence
("14 of your 20 flags match") is exactly what the rule would do:

- support: flags the rule catches that no enabled rule already catches;
- counter: real tracks it would also catch, i.e. rescued / dismissed
  tracks plus tracks Kevin kept or rated not quite. Nopes are left out of
  the counter because older nopes include mixes noped before flags existed.

A candidate becomes a suggestion with support >= MIN_SUPPORT and precision
(support / (support + counter)) >= MIN_PRECISION. The agent only suggests;
Kevin accepts or dismisses.
"""

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from web.backend import feed_insights
from web.backend.feed_filter_rules import (
    first_matching_rule,
    rule_matches,
    split_tags,
    validate_rule,
)

MIN_SUPPORT = 3
MIN_PRECISION = 0.8
MAX_SUGGESTIONS = 12
DURATION_THRESHOLDS: tuple[float, ...] = (8, 10, 12, 15, 20, 30, 45, 60)

# Variant-merged keywords match every spelling in the raw title.
_VARIANT_REGEX: dict[str, str] = {
    "acapella": r"a\s*c+ap+el+as?",
    "dnb": r"d\s*n\s*b|d\s*&\s*b|drum\s*(?:&|and|n|'n')\s*bass",
    "b2b": r"b\s*2\s*b",
    "free download": r"free\s*(?:download|dl)",
}


def keyword_regex(keyword: str) -> str:
    """Case-insensitive title regex for a normalized keyword or phrase."""
    if keyword in _VARIANT_REGEX:
        return rf"\b(?:{_VARIANT_REGEX[keyword]})\b"
    # Group each variant: its alternatives must not swallow the other words.
    words = [
        f"(?:{_VARIANT_REGEX[word]})" if word in _VARIANT_REGEX else re.escape(word)
        for word in keyword.split()
    ]
    return r"\b" + r"\W+".join(words) + r"\b"


def _keyword_candidates(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keywords = Counter(
        keyword
        for flag in flags
        for keyword in feed_insights.title_keywords(flag.get("title"))
    )
    return [
        {
            "kind": "title_regex",
            "pattern": keyword_regex(keyword),
            "threshold": None,
            "name": f'Title has "{keyword}"',
            "label": f'contain "{keyword}"',
            "keyword": keyword,
        }
        for keyword, count in keywords.items()
        if count >= MIN_SUPPORT
    ]


def _track_tags(track: dict[str, Any]) -> set[str]:
    return set(split_tags(track.get("genre"))) | {
        tag.strip().lower() for tag in track.get("tags") or []
    }


def _tag_candidates(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tags = Counter(tag for flag in flags for tag in _track_tags(flag))
    return [
        {
            "kind": "tag_match",
            "pattern": tag,
            "threshold": None,
            "name": f'Genre/tag "{tag}"',
            "label": f'are tagged "{tag}"',
        }
        for tag, count in tags.items()
        if count >= MIN_SUPPORT and "," not in tag
    ]


def _duration_candidates() -> list[dict[str, Any]]:
    return [
        {
            "kind": "duration_min",
            "pattern": None,
            "threshold": float(minutes),
            "name": f"Longer than {minutes:g} min",
            "label": f"run longer than {minutes:g} min",
        }
        for minutes in DURATION_THRESHOLDS
    ]


def _acceptable(rule: dict[str, Any]) -> bool:
    """Passes the same validation accepting it will (regex guard included)."""
    try:
        validate_rule({**rule, "reason": "other"})
    except ValueError:
        return False
    return True


def candidate_rules(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every acceptable rule the flags could justify, before any scoring."""
    candidates = [
        *_keyword_candidates(flags),
        *_tag_candidates(flags),
        *_duration_candidates(),
    ]
    return [rule for rule in candidates if _acceptable(rule)]


def signature(rule: dict[str, Any]) -> str:
    """Stable identity, so a dismissed suggestion is recognized next time."""
    value = rule["pattern"] if rule["pattern"] is not None else f"{rule['threshold']:g}"
    return f"{rule['kind']}:{value}"


def _count(rule: dict[str, Any], tracks: Iterable[dict[str, Any]]) -> list[dict]:
    return [track for track in tracks if rule_matches(track, {**rule, "id": 0})]


def unique_tracks(tracks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per soundcloud_id (first wins), so a track that is both
    rescued and later kept counts once. Tracks without an id are kept."""
    seen: set[str] = set()
    unique = []
    for track in tracks:
        sc_id = track.get("soundcloud_id")
        if sc_id is None or sc_id not in seen:
            unique.append(track)
        if sc_id is not None:
            seen.add(sc_id)
    return unique


def _majority_reason(flags: list[dict[str, Any]]) -> str:
    reasons = Counter(flag.get("reason") or "other" for flag in flags)
    return reasons.most_common(1)[0][0]


def score_candidate(
    rule: dict[str, Any],
    new_flags: list[dict[str, Any]],
    total_flags: int,
    real_tracks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """The suggestion for one candidate, or None when it doesn't qualify."""
    caught = _count(rule, new_flags)
    counter = len(_count(rule, real_tracks))
    support = len(caught)
    if support < MIN_SUPPORT or support / (support + counter) < MIN_PRECISION:
        return None
    evidence = (
        f"{support} of your {total_flags} flags {rule['label']}; "
        f"{counter} real track{'s' if counter != 1 else ''} would also be caught"
    )
    fields = {k: rule[k] for k in ("kind", "pattern", "threshold", "name")}
    fields["keyword"] = rule.get("keyword")
    return {
        **fields,
        "signature": signature(rule),
        "reason": _majority_reason(caught),
        "support": support,
        "counter": counter,
        "evidence": evidence,
    }


def _covered_word(item: dict[str, Any], phrases: list[dict[str, Any]]) -> bool:
    """A single keyword a phrase containing it catches at least as often."""
    word = item.get("keyword")
    if not word or " " in word:
        return False
    return any(
        word in phrase["keyword"].split() and phrase["support"] >= item["support"]
        for phrase in phrases
    )


def _drop_redundant(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the loosest qualifying duration threshold, and drop a word
    when a phrase covers it ("radio" when "radio show" catches as many)."""
    durations = [s for s in suggestions if s["kind"] == "duration_min"]
    loosest = min(durations, key=lambda s: s["threshold"], default=None)
    phrases = [s for s in suggestions if " " in (s.get("keyword") or "")]
    return [
        item
        for item in suggestions
        if (item["kind"] != "duration_min" or item is loosest)
        and not _covered_word(item, phrases)
    ]


def mine_suggestions(
    flags: list[dict[str, Any]],
    not_mixes: list[dict[str, Any]],
    reviewed: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    resolved: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Ranked rule suggestions from Kevin's flags; see the module docstring.

    `resolved` holds signatures Kevin already accepted or dismissed. They
    are dropped before redundancy filtering and the top-N cut, so a
    dismissed suggestion never hides a new one.
    """
    existing = {signature(rule) for rule in rules} | set(resolved)
    new_flags = [flag for flag in flags if first_matching_rule(flag, rules) is None]
    real_tracks = unique_tracks(
        not_mixes
        + [track for track in reviewed if track["decision"] in ("keep", "not_quite")]
    )
    scored = (
        score_candidate(rule, new_flags, len(flags), real_tracks)
        for rule in candidate_rules(new_flags)
        if signature(rule) not in existing
    )
    suggestions = _drop_redundant([item for item in scored if item is not None])
    ranked = sorted(suggestions, key=lambda s: (-s["support"], s["counter"], s["name"]))
    return ranked[:MAX_SUGGESTIONS]
