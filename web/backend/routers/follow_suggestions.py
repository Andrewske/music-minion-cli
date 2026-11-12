"""Ranked follow suggestions from likes and keeps (step 1)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])
