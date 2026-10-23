"""UTC timestamp serialization for every JSON response.

SQLite stores timestamps as naive text in several shapes: CURRENT_TIMESTAMP
('2026-10-23 22:33:07'), Python isoformat ('2026-10-23T22:33:07.123456' or
'...+00:00') and SoundCloud's raw '2026/10/23 22:33:07 +0000'. All of them
are UTC, but a naive string makes JavaScript's Date parse it as local time,
which shifted History by the client's UTC offset ("-420m ago").

`UtcJSONResponse` is the app's default response class. Before encoding it
rewrites every timestamp-shaped string under a timestamp key (`*_at`, plus a
few legacy names) to 'YYYY-MM-DDTHH:MM:SS[.mmm]Z'. Date-only values and
anything unparseable pass through untouched.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi.responses import JSONResponse

EXTRA_TIMESTAMP_KEYS = frozenset({"timestamp", "first_seen", "last_checked"})

_SOUNDCLOUD_FORMAT = "%Y/%m/%d %H:%M:%S %z"


def is_timestamp_key(key: object) -> bool:
    """True for keys whose string values are serialized as UTC timestamps."""
    return isinstance(key, str) and (key.endswith("_at") or key in EXTRA_TIMESTAMP_KEYS)


def _has_time_part(value: str) -> bool:
    return len(value) >= 16 and value[10] in (" ", "T")


def _parse(value: str) -> datetime | None:
    try:
        if "/" in value[:10]:
            return datetime.strptime(value, _SOUNDCLOUD_FORMAT)
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_utc(dt: datetime) -> str:
    """Render a datetime as ISO-8601 UTC with a 'Z' suffix. Naive means UTC."""
    utc = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    base = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if utc.microsecond:
        base += f".{utc.microsecond // 1000:03d}"
    return base + "Z"


@lru_cache(maxsize=8192)
def normalize_utc_string(value: str) -> str:
    """Return `value` as a 'Z' timestamp, or unchanged if it isn't one."""
    if not _has_time_part(value):
        return value
    parsed = _parse(value)
    return format_utc(parsed) if parsed is not None else value


def to_utc_iso(value: datetime | str | None) -> str | None:
    """Normalize a datetime or stored timestamp string to UTC ISO with 'Z'."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return format_utc(value)
    return normalize_utc_string(value)


def _normalize_field(key: object, value: Any) -> Any:
    if is_timestamp_key(key) and isinstance(value, (str, datetime)):
        return to_utc_iso(value)
    return normalize_timestamps(value)


def normalize_timestamps(content: Any) -> Any:
    """Recursively rewrite timestamp fields in JSON-ready content (pure)."""
    if isinstance(content, Mapping):
        return {k: _normalize_field(k, v) for k, v in content.items()}
    if isinstance(content, (list, tuple)):
        return [normalize_timestamps(item) for item in content]
    return content


class UtcJSONResponse(JSONResponse):
    """JSONResponse that emits timestamp fields as explicit UTC.

    Framework requirement: FastAPI's default_response_class must be a
    Response subclass.
    """

    def render(self, content: Any) -> bytes:
        return super().render(normalize_timestamps(content))
