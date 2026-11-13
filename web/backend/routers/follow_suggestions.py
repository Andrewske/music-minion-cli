"""Ranked follow suggestions from likes and keeps (step 1)."""

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from music_minion.core.database import get_db_connection
from web.backend.follow_suggestions import split_suggestions
from web.backend.queries import follow_suggestions as queries

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])

MAX_ARTISTS = 200
MAX_LABELS = 100
# An SC user id, or "name:<name_key>" for a credited name with no account yet
_KEY_RE = re.compile(r"^(?:\d+|name:\w+)$")


class LabelBody(BaseModel):
    is_label: bool


def _valid_key(key: str) -> str:
    if not _KEY_RE.match(key):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid suggestion key {key!r}: expected an SC user id or name:<key>",
        )
    return key


@router.get("")
def get_follow_suggestions() -> dict[str, Any]:
    """Top artists and labels/channels, best score first."""
    with get_db_connection() as conn:
        ranked = queries.compute_ranked(conn)
    artists, labels = split_suggestions(ranked, MAX_ARTISTS, MAX_LABELS)
    return {
        "artists": artists,
        "labels": labels,
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/{key}/dismiss")
def dismiss_suggestion(key: str) -> dict[str, bool]:
    """Permanently hide an account (or unresolved name) from suggestions."""
    with get_db_connection() as conn:
        queries.dismiss(conn, _valid_key(key))
    return {"ok": True}


@router.post("/{key}/label")
def set_suggestion_label(key: str, body: LabelBody) -> dict[str, bool]:
    """Move a suggestion between the artists and labels sections."""
    with get_db_connection() as conn:
        queries.set_label_override(conn, _valid_key(key), body.is_label)
    return {"ok": True}
