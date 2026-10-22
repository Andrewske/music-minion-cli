"""Tag review: clear the metadata-cleanup pending queue from the web app.

Rows come from the ledger the nightly ingest writes (see
music_minion.domain.metadata_cleanup.ingest). A decision applies that one
track at once: tags written with a backup + undo log, ledger entry resolved
under the shared ledger lock, then the track's DB row refreshed.
"""

import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator

from music_minion.domain.metadata_cleanup import ingest, records
from web.backend.queries import cleanup as cleanup_queries

router = APIRouter(prefix="/api/cleanup", tags=["cleanup"])

Verdict = Literal["model", "alt", "edited", "gold", "unclear", "exclude"]


class EditedTags(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    credited_artists: list[str] = Field(max_length=50)
    remixers: list[str] = Field(max_length=50)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()

    @field_validator("credited_artists", "remixers")
    @classmethod
    def _clean_names(cls, names: list[str]) -> list[str]:
        return [name.strip() for name in names if name.strip()]


class DecisionRequest(BaseModel):
    id: str = Field(min_length=1, max_length=1000)
    verdict: Verdict
    expected: EditedTags | None = None

    @model_validator(mode="after")
    def _edited_needs_tags(self) -> "DecisionRequest":
        if self.verdict == "edited" and self.expected is None:
            raise ValueError("verdict 'edited' requires expected tags")
        return self


def _local_path(track_id: str) -> str:
    return str(records.MUSIC_ROOT / track_id)


@router.get("/pending")
def get_pending() -> dict[str, Any]:
    """Pending review rows with the music-minion track id for playback."""
    rows = ingest.pending_rows(ingest.load_ledger())
    ids = cleanup_queries.track_ids_by_path([_local_path(r["id"]) for r in rows])
    items = [{**row, "track_id": ids.get(_local_path(row["id"]))} for row in rows]
    return {"rows": items, "count": len(items)}


@router.get("/pending/count")
def get_pending_count() -> dict[str, int]:
    """Cheap badge count: ledger only, no file reads."""
    return {"count": ingest.pending_count(ingest.load_ledger())}


def _decide(body: DecisionRequest) -> dict[str, Any]:
    expected = body.expected.model_dump() if body.expected else None
    try:
        return ingest.decide_pending(
            body.id, {"verdict": body.verdict, "expected": expected}
        )
    except ingest.PendingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ingest.LedgerBusyError as error:
        logger.warning(f"Tag review {body.id!r}: {error}")
        raise HTTPException(status_code=503, detail=f"{error}; retry") from error
    except ingest.TagWriteError as error:
        logger.error(f"Tag review {body.id!r}: {error}")
        raise HTTPException(status_code=500, detail=str(error)) from error


def _refresh(track_id: str) -> int | None:
    """DB refresh after a write; the tags are already on disk, so never fatal."""
    try:
        return cleanup_queries.refresh_track_from_file(records.MUSIC_ROOT / track_id)
    except (sqlite3.Error, OSError):
        logger.exception(f"Tag review: DB refresh failed for {track_id!r}")
        return None


@router.post("/pending/decision")
def post_decision(body: DecisionRequest) -> dict[str, Any]:
    """Apply one decision now; returns the track's new state and the queue size."""
    result = _decide(body)
    db_track_id = _refresh(body.id) if result["written"] else None
    return {
        **result,
        "verdict": body.verdict,
        "db_refreshed": db_track_id is not None,
        "track_id": db_track_id,
        "remaining": ingest.pending_count(ingest.load_ledger()),
    }
