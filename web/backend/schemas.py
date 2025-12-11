from pydantic import BaseModel
from typing import Optional


class TrackInfo(BaseModel):
    id: int
    title: str
    artist: str
    album: Optional[str] = None
    year: Optional[int] = None
    bpm: Optional[int] = None
    genre: Optional[str] = None
    rating: float
    comparison_count: int
    wins: int
    losses: int
    duration: Optional[float] = None
    has_waveform: bool


class ComparisonPair(BaseModel):
    track_a: TrackInfo
    track_b: TrackInfo
    session_id: str


class StartSessionRequest(BaseModel):
    source_filter: Optional[str] = None
    genre_filter: Optional[str] = None
    year_filter: Optional[str] = None
    playlist_id: Optional[int] = None
    priority_path_prefix: Optional[str] = None  # e.g., "/music/2025" to prioritize


class StartSessionResponse(BaseModel):
    session_id: str
    total_tracks: int
    pair: ComparisonPair
    prefetched_pair: Optional[ComparisonPair] = None  # Next pair pre-calculated


class RecordComparisonRequest(BaseModel):
    session_id: str
    track_a_id: int
    track_b_id: int
    winner_id: int
    priority_path_prefix: Optional[str] = None  # Continue weighted pairing


class RecordComparisonResponse(BaseModel):
    success: bool
    comparisons_done: int
    next_pair: Optional[ComparisonPair] = None
    prefetched_pair: Optional[ComparisonPair] = None  # Pair after next, pre-calculated


class WaveformData(BaseModel):
    version: int = 2
    channels: int
    sample_rate: int
    samples_per_pixel: int
    bits: int = 8
    length: int
    peaks: list[int]

    model_config = {"frozen": True}  # Immutable


class GenreStat(BaseModel):
    genre: str
    track_count: int
    average_rating: float
    total_comparisons: int


class LeaderboardEntry(BaseModel):
    track_id: int
    title: str
    artist: str
    rating: float
    comparison_count: int
    wins: int
    losses: int


class StatsResponse(BaseModel):
    total_comparisons: int
    compared_tracks: int
    total_tracks: int
    coverage_percent: float
    average_comparisons_per_day: float
    estimated_days_to_coverage: Optional[float]
    prioritized_tracks: Optional[int] = None
    prioritized_coverage_percent: Optional[float] = None
    prioritized_estimated_days: Optional[float] = None
    top_genres: list[GenreStat]
    leaderboard: list[LeaderboardEntry]
