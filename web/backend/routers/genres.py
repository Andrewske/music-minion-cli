"""Genre API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..queries.genres import (
    get_all_genres_query,
    get_track_genres_query,
    rename_genre_mutation,
    delete_genre_mutation,
    set_track_genres_mutation,
    assign_genre_emoji_mutation,
)

router = APIRouter(prefix="/api", tags=["genres"])


class RenameGenreRequest(BaseModel):
    name: str


class AssignEmojiRequest(BaseModel):
    emoji_id: str | None


class UpdateTrackGenresRequest(BaseModel):
    genre_ids: list[int]


@router.get("/genres")
def list_genres() -> list[dict]:
    return get_all_genres_query()


@router.put("/genres/{genre_id}")
def rename_genre(genre_id: int, request: RenameGenreRequest) -> dict:
    return rename_genre_mutation(genre_id, request.name)


@router.put("/genres/{genre_id}/emoji")
def assign_emoji(genre_id: int, request: AssignEmojiRequest) -> dict:
    return assign_genre_emoji_mutation(genre_id, request.emoji_id)


@router.delete("/genres/{genre_id}")
def delete_genre(genre_id: int) -> dict:
    try:
        return delete_genre_mutation(genre_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracks/{track_id}/genres")
def get_track_genres(track_id: int) -> list[dict]:
    return get_track_genres_query(track_id)


@router.put("/tracks/{track_id}/genres")
def update_track_genres(track_id: int, request: UpdateTrackGenresRequest) -> list[dict]:
    return set_track_genres_mutation(track_id, request.genre_ids)
