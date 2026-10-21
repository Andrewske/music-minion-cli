"""Feed filter rules and the tracks they (or the user) flagged as not for feed."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from web.backend.feed_filter_rules import MAX_PATTERN_LENGTH, MAX_RULE_NAME_LENGTH
from web.backend.queries import feed_filters as filter_queries

router = APIRouter(prefix="/api/feed-filters", tags=["feed-filters"])

RuleKind = Literal["duration_min", "title_regex", "tag_match"]
FlagReason = Literal["live_mix", "podcast", "other"]
# 'filtered' = everything a rule or the agent caught (the Settings list).
FlaggedSource = Literal["filtered", "user", "rule", "agent"]
FlaggedSort = Literal["newest", "confidence"]
_SOURCES_BY_FILTER: dict[str, tuple[str, ...]] = {
    "filtered": ("rule", "agent"),
    "user": ("user",),
    "rule": ("rule",),
    "agent": ("agent",),
}


class RuleCreate(BaseModel):
    name: str = Field(max_length=MAX_RULE_NAME_LENGTH)
    kind: RuleKind
    reason: FlagReason
    pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    threshold: float | None = None
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=MAX_RULE_NAME_LENGTH)
    kind: RuleKind | None = None
    reason: FlagReason | None = None
    pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    threshold: float | None = None
    enabled: bool | None = None


def _invalid_rule(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


@router.get("/rules")
def get_rules() -> dict[str, Any]:
    return {"rules": filter_queries.list_rules()}


@router.post("/rules", status_code=201)
def create_rule(body: RuleCreate) -> dict[str, Any]:
    """Regex patterns are compiled here; an invalid one is a 422 with the cause."""
    try:
        return filter_queries.create_rule(body.model_dump())
    except ValueError as error:
        raise _invalid_rule(error) from error


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate) -> dict[str, Any]:
    try:
        updated = filter_queries.update_rule(
            rule_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise _invalid_rule(error) from error
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Filter rule {rule_id} not found")
    return updated


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int) -> dict[str, Any]:
    """Deleting a rule also drops its flags, so its tracks return to the feed."""
    if not filter_queries.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"Filter rule {rule_id} not found")
    return {"deleted": True, "id": rule_id}


@router.post("/run")
def run_rules() -> dict[str, Any]:
    """Apply enabled rules to unreviewed, never-flagged tracks in the feed window."""
    return {"flagged": filter_queries.apply_rules(None)}


@router.get("/tracks")
def get_flagged_tracks(
    source: FlaggedSource = "filtered",
    rule_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None, ge=1),
    sort: FlaggedSort = "newest",
    cursor_confidence: float | None = None,
) -> dict[str, Any]:
    """Active flags newest first, or lowest agent confidence first.

    `cursor` is the previous page's last flag_id; with sort=confidence also
    pass its `next_cursor_confidence`.
    """
    items = filter_queries.list_flagged(
        _SOURCES_BY_FILTER[source], rule_id, limit, cursor, sort, cursor_confidence
    )
    last = items[-1] if len(items) == limit else None
    return {
        "items": items,
        "next_cursor": last["flag_id"] if last else None,
        "next_cursor_confidence": last["confidence"] if last else None,
    }
