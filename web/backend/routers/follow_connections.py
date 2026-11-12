"""Connection-based follow suggestions: co-credits and favorites' followings (steps 2-3)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])
