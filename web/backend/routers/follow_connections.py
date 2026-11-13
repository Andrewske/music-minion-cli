"""Connection-based follow suggestions: co-credits and favorites' followings (steps 2-3)."""

from typing import Any

from fastapi import APIRouter

from web.backend.follow_connections import compute_connections

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])


@router.get("/connections")
def get_connections() -> dict[str, list[dict[str, Any]]]:
    """Top 50 co-credit and favorites-follow suggestions, best first.

    Computes in ~0.25s on the live-size snapshot, so there is no cache.
    Kevin's own account needs no special case: the nightly follow-caches
    job dismisses it, and dismissed accounts are excluded.
    """
    return compute_connections()
