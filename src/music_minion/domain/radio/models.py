"""
Radio domain models.

Contains data structures for representing radio stations, schedules, and playback state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from music_minion.domain.library.models import Track


@dataclass(frozen=True)
class Station:
    """Represents a radio station.

    A station is a playlist with radio-specific metadata (shuffle/queue mode).
    Only one station can be active at a time.
    """

    id: int
    name: str
    playlist_id: Optional[int]  # Links to existing playlist, None for meta-stations
    mode: str  # 'shuffle' | 'queue'
    source_filter: str  # 'all' | 'local' | 'youtube' | 'soundcloud' | 'spotify'
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ScheduleEntry:
    """Represents a time range in a station's schedule.

    Used by meta-stations (like "Main") to reference other stations
    during specific time periods.
    """

    id: int
    station_id: int  # The meta-station (e.g., Main)
    start_time: str  # "HH:MM" format
    end_time: str  # "HH:MM" format
    target_station_id: int  # Which station plays in this range
    position: int  # Order for overlapping ranges


@dataclass(frozen=True)
class NowPlaying:
    """Represents the current playback state.

    Calculated deterministically based on station and current time.
    """

    track: Track
    position_ms: int  # Position within current track
    next_track: Optional[Track]
    upcoming: list[Track]  # Next 5 tracks for queue display
    station_id: int
    source_type: str  # 'local' | 'youtube' | 'spotify' | 'soundcloud'
