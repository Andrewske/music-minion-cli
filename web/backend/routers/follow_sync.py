"""Follow action and tier review for new follows (step 0)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])
