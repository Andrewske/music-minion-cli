"""Feed agent endpoints (#31): Jev mix classification and rule suggestions.

Both run on demand from Settings. The agent writes flags and suggestions
only; a rule exists only once Kevin accepts a suggestion.
"""

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from web.backend import feed_classifier
from web.backend.feed_filter_rules import MAX_PATTERN_LENGTH, MAX_RULE_NAME_LENGTH
from web.backend.queries import feed_agent
from web.backend.queries import feed_filters as filter_queries

router = APIRouter(prefix="/api/feed-filters", tags=["feed-agent"])

ClassificationStatus = Literal[
    "auto_flagged", "pending", "below_threshold", "confirmed", "dismissed"
]
SuggestionStatus = Literal["pending", "accepted", "dismissed"]


class ClassifyRequest(BaseModel):
    max_tracks: int = Field(
        default=feed_classifier.DEFAULT_MAX_TRACKS,
        ge=1,
        le=feed_classifier.MAX_TRACKS_PER_RUN,
    )


class SuggestionOverrides(BaseModel):
    name: str | None = Field(default=None, max_length=MAX_RULE_NAME_LENGTH)
    pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    threshold: float | None = None
    reason: Literal["live_mix", "podcast", "other"] | None = None


def _not_found(kind: str, item_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} {item_id} not found")


@router.post("/classify")
def classify(body: ClassifyRequest | None = None) -> dict[str, Any]:
    """Ask Jev about ambiguous unreviewed tracks (8-20 min, no rule hit)."""
    max_tracks = (body or ClassifyRequest()).max_tracks
    try:
        return feed_classifier.classify_ambiguous_tracks(max_tracks)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/classifications/unreadable")
def get_unreadable() -> dict[str, int]:
    """How many tracks got unreadable Jev answers and are no longer asked."""
    return {"count": feed_agent.count_invalid()}


@router.post("/classifications/unreadable/retry")
def retry_unreadable() -> dict[str, int]:
    """Reset unreadable tracks so the next classifier run asks about them again."""
    return {"reset": feed_agent.reset_invalid()}


@router.get("/classifications")
def get_classifications(status: ClassificationStatus = "pending") -> dict[str, Any]:
    return {"items": feed_agent.list_classifications(status)}


def _resolve(classification_id: int, confirm: bool) -> dict[str, Any]:
    try:
        resolved = feed_agent.resolve_classification(classification_id, confirm)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if resolved is None:
        raise _not_found("Classification", classification_id)
    return resolved


@router.post("/classifications/{classification_id}/confirm")
def confirm_classification(
    classification_id: int, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Kevin agrees it's a mix/show: the track gets his own flag.

    Like any flag, it changes which tracks count toward artist stats.
    """
    resolved = _resolve(classification_id, confirm=True)
    background_tasks.add_task(
        filter_queries.refresh_artist_stats_for, [resolved["soundcloud_id"]]
    )
    return resolved


@router.post("/classifications/{classification_id}/dismiss")
def dismiss_classification(classification_id: int) -> dict[str, Any]:
    """Not a mix: stays in the feed and becomes a negative example."""
    return _resolve(classification_id, confirm=False)


@router.post("/suggestions/mine")
def mine_suggestions() -> dict[str, Any]:
    """Re-mine flags and rescues; dismissed suggestions never come back."""
    return feed_agent.mine_rule_suggestions()


@router.get("/suggestions")
def get_suggestions(status: SuggestionStatus = "pending") -> dict[str, Any]:
    return {"suggestions": feed_agent.list_suggestions(status)}


def _pending_or_error(suggestion_id: int) -> None:
    suggestion = feed_agent.get_suggestion(suggestion_id)
    if suggestion is None:
        raise _not_found("Suggestion", suggestion_id)
    if suggestion["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Suggestion {suggestion_id} is already {suggestion['status']}",
        )


@router.post("/suggestions/{suggestion_id}/accept", status_code=201)
def accept_suggestion(
    suggestion_id: int, body: SuggestionOverrides | None = None
) -> dict[str, Any]:
    """Create a real rule; an invalid (edited) regex is a 422 with the cause."""
    _pending_or_error(suggestion_id)
    overrides = body.model_dump(exclude_none=True) if body else None
    try:
        accepted = feed_agent.accept_suggestion(suggestion_id, overrides)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if accepted is None:
        raise _not_found("Suggestion", suggestion_id)
    return accepted


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: int) -> dict[str, Any]:
    _pending_or_error(suggestion_id)
    dismissed = feed_agent.dismiss_suggestion(suggestion_id)
    if dismissed is None:
        raise _not_found("Suggestion", suggestion_id)
    return dismissed
