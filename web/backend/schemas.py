from pydantic import BaseModel
from typing import Optional


class TrackInfo(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
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
    emojis: list[str] = []
    # Playlist ranking fields
    playlist_rating: Optional[float] = None
    playlist_comparison_count: Optional[int] = None
    global_rating: Optional[float] = None


class ComparisonPair(BaseModel):
    track_a: TrackInfo
    track_b: TrackInfo


class ComparisonRequest(BaseModel):
    """Unified request schema for comparison operations."""
    playlist_id: int  # REQUIRED - no optional modes


class RecordComparisonRequest(BaseModel):
    playlist_id: int
    track_a_id: int
    track_b_id: int
    winner_id: int


class ComparisonProgress(BaseModel):
    compared: int
    total: int
    percentage: float


class ComparisonResponse(BaseModel):
    """Unified response schema for comparison operations."""
    pair: Optional[ComparisonPair]  # None when ranking complete
    progress: ComparisonProgress


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
    artist: Optional[str] = None
    rating: float
    comparison_count: int
    wins: int
    losses: int


class PlaylistBasicStats(BaseModel):
    total_tracks: int
    total_duration: float
    avg_duration: float
    year_min: Optional[int] = None
    year_max: Optional[int] = None


class PlaylistEloAnalysis(BaseModel):
    total_tracks: int
    rated_tracks: int
    compared_tracks: int
    coverage_percentage: float
    avg_playlist_rating: float
    min_playlist_rating: float
    max_playlist_rating: float
    avg_global_rating: float
    min_global_rating: float
    max_global_rating: float
    avg_playlist_comparisons: float
    total_playlist_comparisons: int


class PlaylistQualityMetrics(BaseModel):
    total_tracks: int
    missing_bpm: int
    missing_key: int
    missing_year: int
    missing_genre: int
    without_tags: int
    completeness_score: float


class ArtistStat(BaseModel):
    artist: str
    track_count: int


class GenreDistribution(BaseModel):
    genre: str
    count: int
    percentage: float


class PlaylistTrackEntry(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    rating: float
    wins: int
    losses: int
    comparison_count: int


class PlaylistTracksResponse(BaseModel):
    playlist_name: str
    tracks: list[PlaylistTrackEntry]


class PlaylistStatsResponse(BaseModel):
    playlist_name: str
    playlist_type: str
    basic: PlaylistBasicStats
    elo: PlaylistEloAnalysis
    quality: PlaylistQualityMetrics
    top_artists: list[ArtistStat]
    top_genres: list[GenreDistribution]
    avg_comparisons_per_day: float
    estimated_days_to_full_coverage: Optional[float] = None


# Playlist Builder Schemas


class BuilderStartSessionRequest(BaseModel):
    playlist_id: int


class BuilderStartSessionResponse(BaseModel):
    session_id: int
    playlist_id: int
    started_at: str
    updated_at: str


class SessionResponse(BaseModel):
    id: int
    playlist_id: int
    last_processed_track_id: Optional[int] = None
    started_at: str
    updated_at: str


class TrackActionResponse(BaseModel):
    success: bool


class Filter(BaseModel):
    field: str
    operator: str
    value: str
    conjunction: str = "AND"


class FilterResponse(BaseModel):
    """Filter with ID - used for smart playlist filters."""
    id: int
    field: str
    operator: str
    value: str
    conjunction: str


class UpdateFiltersRequest(BaseModel):
    filters: list[Filter]


class FiltersResponse(BaseModel):
    filters: list[Filter]


class SmartFiltersResponse(BaseModel):
    """Response for smart playlist filters."""
    filters: list[FilterResponse]


class CandidatesResponse(BaseModel):
    candidates: list[dict]
    total: int
    limit: int
    offset: int


class SkippedTracksResponse(BaseModel):
    skipped: list[dict]
    total: int


class CreatePlaylistRequest(BaseModel):
    name: str
    description: Optional[str] = None
