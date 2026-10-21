"""Pure "not for feed" rule matching and validation (#30).

A rule is a dict with ``kind`` / ``pattern`` / ``threshold`` (plus id, name,
reason, enabled); a track is a dict with ``title`` / ``duration_ms`` /
``genre`` and optionally ``tags``. Nothing here touches the database, so the
rules engine is unit-testable on plain dicts.
"""

import re
from collections.abc import Callable, Iterable
from typing import Any

FLAG_REASONS: tuple[str, ...] = ("live_mix", "podcast", "other")
FLAG_SOURCES: tuple[str, ...] = ("user", "rule", "agent")
RULE_KINDS: tuple[str, ...] = ("duration_min", "title_regex", "tag_match")
MAX_RULE_NAME_LENGTH = 100
MAX_PATTERN_LENGTH = 500
MAX_DURATION_MINUTES = 600.0

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


def split_tags(value: str | None) -> list[str]:
    """Lowercased, trimmed, non-empty tags from a comma/slash separated string."""
    if not value:
        return []
    return [tag.strip().lower() for tag in _TAG_SPLIT.split(value) if tag.strip()]


def _matches_duration(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    duration_ms = track.get("duration_ms") or 0
    return duration_ms > float(rule["threshold"]) * 60_000


def _matches_title(track: dict[str, Any], rule: dict[str, Any]) -> bool:
    return (
        re.search(rule["pattern"], track.get("title") or "", re.IGNORECASE) is not None
    )


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
    """True when an enabled rule catches the track."""
    if not rule.get("enabled", True):
        return False
    return _MATCHERS[rule["kind"]](track, rule)


def first_matching_rule(
    track: dict[str, Any], rules: Iterable[dict[str, Any]]
) -> dict[str, Any] | None:
    """The first rule (in the given order) that catches the track."""
    return next((rule for rule in rules if rule_matches(track, rule)), None)


def rule_precision(hits: int, rescues: int) -> float | None:
    """1 - rescues / hits; None until the rule has caught something."""
    if hits <= 0:
        return None
    return 1.0 - rescues / hits


def _validated_pattern(kind: str, pattern: Any) -> str:
    text = str(pattern or "").strip()
    if not text:
        raise ValueError(f"A {kind} rule needs a pattern")
    if len(text) > MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern is longer than {MAX_PATTERN_LENGTH} characters")
    if kind == "tag_match" and not split_tags(text):
        raise ValueError("A tag_match rule needs at least one comma-separated tag")
    if kind == "title_regex":
        try:
            re.compile(text, re.IGNORECASE)
        except re.error as error:
            raise ValueError(
                f"Invalid regex {text!r}: {error.msg} at position {error.pos}"
            ) from error
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
