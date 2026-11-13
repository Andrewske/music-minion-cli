"""Connection-based follow suggestions: co-credits and favorites' followings (steps 2-3)."""

import os
from typing import Any

from fastapi import APIRouter

from web.backend.follow_connections import compute_connections

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])

# Kevin's own SC user id, so his account never shows up in favorites_follow.
SELF_USER_ID_ENV = "SC_SELF_USER_ID"


@router.get("/connections")
def get_connections() -> dict[str, list[dict[str, Any]]]:
    """Top 50 co-credit and favorites-follow suggestions, best first.

    Computes in ~0.25s on the live-size snapshot, so there is no cache.
    """
    return compute_connections(os.environ.get(SELF_USER_ID_ENV) or None)
