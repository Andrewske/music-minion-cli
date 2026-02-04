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
    # Playlist ranking fields
    playlist_rating: Optional[float] = None
    playlist_comparison_count: Optional[int] = None
    global_rating: Optional[float] = None


class ComparisonPair(BaseModel):
    track_a: TrackInfo
    track_b: TrackInfo
    session_id: str


class StartSessionRequest(BaseModel):
    source_filter: Optional[str] = None
    genre_filter: Optional[str] = None
    year_filter: Optional[str] = None
    playlist_id: Optional[int] = None
    ranking_mode: Optional[str] = None  # "playlist" for playlist-specific ranking
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
    ranking_mode: Optional[str] = None  # "playlist" for playlist-specific ranking
    playlist_id: Optional[int] = None  # Required when ranking_mode is "playlist"
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
    artist: Optional[str] = None
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


class UpdateFiltersRequest(BaseModel):
    filters: list[Filter]


class FiltersResponse(BaseModel):
    filters: list[Filter]


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
