"""Local-timezone helpers for user-facing calendar labels.

The feed's monthly SoundCloud playlist ("Jul 26") must follow the user's
calendar, not the server clock (the Pi container runs in UTC).
"""

from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger

from .config import get_config_path, load_config


def resolve_timezone(name: str) -> tzinfo:
    """Return the IANA zone for `name`, or the machine's local zone when empty/invalid."""
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning(f"local_time: unknown timezone {name!r}; using system local")
    return datetime.now().astimezone().tzinfo or timezone.utc


def configured_feed_timezone() -> tzinfo:
    """Feed timezone from config (`[soundcloud].feed_timezone`), never creating files."""
    if not get_config_path().exists():
        return resolve_timezone("")
    return resolve_timezone(load_config().soundcloud.feed_timezone)


def month_label(instant: datetime, tz: tzinfo) -> str:
    """Calendar month of `instant` in `tz`, formatted like 'Jul 26'."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(tz).strftime("%b %y")
