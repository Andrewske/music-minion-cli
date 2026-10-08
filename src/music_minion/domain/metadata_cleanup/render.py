"""Deterministically assemble display strings from the model's structured parts.

The model never writes the final title. It returns base_title / featured /
remixers / version, and these functions apply separators consistently.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Separators:
    artists: str = "; "  # TPE1 / TPE4 join
    featured_in_title: str = " & "  # "Song ft. A & B"
    remixers_in_title: str = " x "  # "(A x B Flip)"


DEFAULT_SEPARATORS = Separators()


def render_version(remixers: list[str], version: str | None, sep: Separators) -> str:
    """'(A x B Flip)', '(VIP)', or '' when there is no version tag."""
    credit = sep.remixers_in_title.join(remixers)
    inner = " ".join(part for part in (credit, version or "") if part)
    return f"({inner})" if inner else ""


def render_title(parts: dict[str, Any], sep: Separators = DEFAULT_SEPARATORS) -> str:
    title = parts["base_title"].strip()
    if parts["featured"]:
        title += " ft. " + sep.featured_in_title.join(parts["featured"])
    version = render_version(parts["remixers"], parts.get("version"), sep)
    return f"{title} {version}" if version else title


def render_tags(
    parts: dict[str, Any], sep: Separators = DEFAULT_SEPARATORS
) -> dict[str, str]:
    """Final tag values. TPE1 = artists + featured (the established library format)."""
    credited = parts["artists"] + [
        f for f in parts["featured"] if f not in parts["artists"]
    ]
    return {
        "title": render_title(parts, sep),
        "artist": sep.artists.join(credited),
        "remixer": sep.artists.join(parts["remixers"]),
    }


def expected_view(parts: dict[str, Any]) -> dict[str, Any]:
    """Proposal as the comparable shape used by gold and review: title + name lists."""
    credited = parts["artists"] + [
        f for f in parts["featured"] if f not in parts["artists"]
    ]
    return {
        "title": render_title(parts),
        "credited_artists": credited,
        "remixers": parts["remixers"],
    }
