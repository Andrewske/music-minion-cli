"""Pure "not for feed" rule matching and validation (#30).

A rule is a dict with ``kind`` / ``pattern`` / ``threshold`` (plus id, name,
reason, enabled); a track is a dict with ``title`` / ``duration_ms`` /
``genre`` and optionally ``tags`` (the parsed SoundCloud ``tag_list``).
Nothing here touches the database, so the rules engine is unit-testable on
plain dicts.

Title regexes compile and match with the ``regex`` module, never ``re``, so a
pattern that passes validation is exactly what runs at match time. Each match
has a hard timeout; the stdlib parser check below is only a fast first filter.
"""

import re
import re._constants as sre_constants  # stdlib parser internals, stable since 3.11
import re._parser as sre_parser
from collections.abc import Callable, Iterable
from functools import lru_cache
from typing import Any

import regex

FLAG_REASONS: tuple[str, ...] = ("live_mix", "podcast", "other")
FLAG_SOURCES: tuple[str, ...] = ("user", "rule", "agent")
RULE_KINDS: tuple[str, ...] = ("duration_min", "title_regex", "tag_match")
MAX_RULE_NAME_LENGTH = 100
MAX_PATTERN_LENGTH = 500
MAX_DURATION_MINUTES = 600.0
MAX_REGEX_LENGTH = 200
# Titles are matched on a bounded prefix so even a slow pattern stays fast.
MAX_MATCHED_TITLE_LENGTH = 300
# Per-match wall clock bound. A timeout counts as no match.
MATCH_TIMEOUT_SECONDS = 0.05
# A rule that times out this many times in one run is disabled.
RULE_TIMEOUT_LIMIT = 3

_REPEATS = (
    sre_constants.MAX_REPEAT,
    sre_constants.MIN_REPEAT,
    sre_constants.POSSESSIVE_REPEAT,
)

_TAG_SPLIT = re.compile(r"[,;/|]")


def active_flag_exists_sql(column: str) -> str:
    """SQL predicate: the track in `column` has an unrescued not-for-feed flag."""
    return (
        "EXISTS (SELECT 1 FROM sc_track_flags fl "
        f"WHERE fl.soundcloud_id = {column} AND fl.rescued_at IS NULL)"
    )


def not_flagged_sql(column: str) -> str:
    """SQL predicate excluding flagged tracks from feeds, stats and training."""
    return f"NOT {active_flag_exists_sql(column)}"


def flaggable_track_sql(param: str) -> str:
    """SQL predicate checked at write time before a rule or the agent flags a track.

    The track must still be undecided and have no flag row at all: an active
    flag already hides it, and a rescued one is the user's permanent "this is
    a real track" exemption.
    """
    return (
        "NOT EXISTS (SELECT 1 FROM sc_track_decisions d "
        f"WHERE d.soundcloud_id = {param} AND d.is_current = 1) "
        "AND NOT EXISTS (SELECT 1 FROM sc_track_flags f "
        f"WHERE f.soundcloud_id = {param})"
    )


def split_tags(value: str | None) -> list[str]:
    """Lowercased, trimmed, non-empty tags from a comma/slash separated string."""
    if not value:
        return []
    return [tag.strip().lower() for tag in _TAG_SPLIT.split(value) if tag.strip()]


def _matches_duration(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    duration_ms = track.get("duration_ms") or 0
    return duration_ms > float(rule["threshold"]) * 60_000


@lru_cache(maxsize=64)
def _compiled_title_pattern(pattern: str) -> Any:
    """The one compile used by validation and matching; raises regex.error."""
    return regex.compile(pattern, regex.IGNORECASE)


def _matches_title(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Raises TimeoutError when the match exceeds MATCH_TIMEOUT_SECONDS."""
    title = (track.get("title") or "")[:MAX_MATCHED_TITLE_LENGTH]
    pattern = _compiled_title_pattern(rule["pattern"])
    return pattern.search(title, timeout=MATCH_TIMEOUT_SECONDS) is not None


def _matches_tags(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    track_tags = set(split_tags(track.get("genre")))
    track_tags.update(tag.strip().lower() for tag in track.get("tags") or [])
    return not track_tags.isdisjoint(split_tags(rule["pattern"]))


_MATCHERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], bool]] = {
    "duration_min": _matches_duration,
    "title_regex": _matches_title,
    "tag_match": _matches_tags,
}


def rule_matches(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    """True when an enabled rule catches the track; a timeout counts as no match."""
    try:
        return _rule_matches_or_timeout(track, rule)
    except TimeoutError:
        return False


def _rule_matches_or_timeout(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False
    return _MATCHERS[rule["kind"]](track, rule)


def match_rules(
    track: dict[str, Any], rules: Iterable[dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[int]]:
    """The first rule (in order) that catches the track, and ids of rules that timed out."""
    timed_out: list[int] = []
    for rule in rules:
        try:
            if _rule_matches_or_timeout(track, rule):
                return rule, timed_out
        except TimeoutError:
            timed_out.append(rule["id"])
    return None, timed_out


def match_each(
    tracks: Iterable[dict[str, Any]], rules: list[dict[str, Any]]
) -> tuple[list[dict[str, Any] | None], dict[int, int]]:
    """The first matching rule per track (None when none), plus timeouts per rule id.

    A rule that hits RULE_TIMEOUT_LIMIT timeouts is skipped for the rest of
    the run, so one slow pattern can't stall a scan of thousands of tracks.
    """
    matches: list[dict[str, Any] | None] = []
    timeouts: dict[int, int] = {}
    for track in tracks:
        live = [r for r in rules if timeouts.get(r["id"], 0) < RULE_TIMEOUT_LIMIT]
        rule, timed_out = match_rules(track, live)
        for rule_id in timed_out:
            timeouts[rule_id] = timeouts.get(rule_id, 0) + 1
        matches.append(rule)
    return matches, timeouts


def first_matching_rule(
    track: dict[str, Any], rules: Iterable[dict[str, Any]]
) -> dict[str, Any] | None:
    """The first rule (in the given order) that catches the track."""
    return match_rules(track, rules)[0]


def rule_precision(hits: int, rescues: int) -> float | None:
    """1 - rescues / hits; None until the rule has caught something."""
    if hits <= 0:
        return None
    return 1.0 - rescues / hits


def _sub_patterns(op: Any, av: Any) -> list[Any]:
    """Child sub-patterns of one parsed regex node."""
    if op in _REPEATS:
        return [av[2]]
    if op is sre_constants.SUBPATTERN:
        return [av[3]]
    if op is sre_constants.BRANCH:
        return list(av[1])
    if op is sre_constants.ATOMIC_GROUP:
        return [av]
    if op in (sre_constants.ASSERT, sre_constants.ASSERT_NOT):
        return [av[1]]
    if op is sre_constants.GROUPREF_EXISTS:
        return [child for child in av[1:] if child is not None]
    return []


def _has_nested_quantifier(pattern: Any, inside_repeat: bool = False) -> bool:
    """True when a repeated group holds another quantifier or an alternation.

    That shape (``(a+)+``, ``(a|a)*``) is what makes backtracking blow up
    (ReDoS). Rules are hand-written, so rejecting it outright is simpler than
    proving a particular pattern safe.
    """
    for op, av in pattern:
        if inside_repeat and (op in _REPEATS or op is sre_constants.BRANCH):
            return True
        repeats = op in _REPEATS and av[1] > 1
        children = _sub_patterns(op, av)
        if any(_has_nested_quantifier(c, inside_repeat or repeats) for c in children):
            return True
    return False


def _stdlib_parse(text: str) -> Any | None:
    """The stdlib parse tree, or None for syntax only the regex module knows."""
    try:
        return sre_parser.parse(text, re.IGNORECASE)
    except re.error:
        return None


def _validated_regex(text: str) -> None:
    if len(text) > MAX_REGEX_LENGTH:
        raise ValueError(f"Regex is longer than {MAX_REGEX_LENGTH} characters")
    try:
        _compiled_title_pattern(text)
    except regex.error as error:
        position = "" if error.pos is None else f" at position {error.pos}"
        raise ValueError(f"Invalid regex {text!r}: {error.msg}{position}") from error
    parsed = _stdlib_parse(text)
    if parsed is not None and _has_nested_quantifier(parsed):
        raise ValueError(
            f"Regex {text!r} repeats a group that contains a quantifier or "
            "alternation (like (a+)+), which can hang matching; flatten it"
        )


def _validated_pattern(kind: str, pattern: Any) -> str:
    text = str(pattern or "").strip()
    if not text:
        raise ValueError(f"A {kind} rule needs a pattern")
    if len(text) > MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern is longer than {MAX_PATTERN_LENGTH} characters")
    if kind == "tag_match" and not split_tags(text):
        raise ValueError("A tag_match rule needs at least one comma-separated tag")
    if kind == "title_regex":
        _validated_regex(text)
    return text


def _validated_threshold(threshold: Any) -> float:
    try:
        minutes = float(threshold)
    except (TypeError, ValueError) as error:
        raise ValueError("A duration_min rule needs a threshold in minutes") from error
    if not 0 < minutes <= MAX_DURATION_MINUTES:
        raise ValueError(
            f"Duration threshold must be between 0 and {MAX_DURATION_MINUTES:g} minutes"
        )
    return minutes


def _validated_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        raise ValueError("A rule needs a name")
    if len(text) > MAX_RULE_NAME_LENGTH:
        raise ValueError(f"Rule name is longer than {MAX_RULE_NAME_LENGTH} characters")
    return text


def validate_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Normalized copy of a rule's editable fields; ValueError says what's wrong."""
    kind = rule.get("kind")
    if kind not in RULE_KINDS:
        raise ValueError(f"Invalid rule kind {kind!r}; valid kinds are {RULE_KINDS}")
    reason = rule.get("reason")
    if reason not in FLAG_REASONS:
        raise ValueError(f"Invalid reason {reason!r}; valid reasons are {FLAG_REASONS}")
    is_duration = kind == "duration_min"
    return {
        "name": _validated_name(rule.get("name")),
        "kind": kind,
        "reason": reason,
        "enabled": bool(rule.get("enabled", True)),
        "pattern": None
        if is_duration
        else _validated_pattern(kind, rule.get("pattern")),
        "threshold": _validated_threshold(rule.get("threshold"))
        if is_duration
        else None,
    }
