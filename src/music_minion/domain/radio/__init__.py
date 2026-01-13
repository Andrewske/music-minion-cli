"""
Radio domain module.

Provides personal radio station functionality with deterministic timeline
calculation, schedule management, and multi-source support.
"""

from .models import NowPlaying, ScheduleEntry, Station
from .schedule import (
    add_schedule_entry,
    delete_schedule_entry,
    get_schedule_entries,
    get_schedule_entry,
    get_schedule_for_time,
    reorder_schedule_entries,
    time_in_range,
    update_schedule_entry,
)
from .stations import (
    activate_station,
    create_station,
    deactivate_all_stations,
    delete_station,
    get_active_station,
    get_actual_now_playing,
    get_all_stations,
    get_station,
    get_station_by_name,
    record_now_playing,
    update_station,
)
from .timeline import (
    calculate_now_playing,
    clear_daily_skipped,
    deterministic_shuffle,
    get_next_track,
    get_skipped_tracks,
    get_upcoming_tracks,
    mark_track_skipped,
)
from .scheduler import (
    get_current_state,
    get_next_track_path,
    get_scheduler_info,
    handle_track_unavailable,
    reset_scheduler_state,
)

__all__ = [
    # Models
    "Station",
    "ScheduleEntry",
    "NowPlaying",
    # Station CRUD
    "create_station",
    "get_station",
    "get_station_by_name",
    "get_all_stations",
    "get_active_station",
    "get_actual_now_playing",
    "activate_station",
    "deactivate_all_stations",
    "update_station",
    "delete_station",
    "record_now_playing",
    # Schedule management
    "add_schedule_entry",
    "get_schedule_entries",
    "get_schedule_entry",
    "get_schedule_for_time",
    "update_schedule_entry",
    "delete_schedule_entry",
    "reorder_schedule_entries",
    "time_in_range",
    # Timeline calculation
    "calculate_now_playing",
    "deterministic_shuffle",
    "get_skipped_tracks",
    "mark_track_skipped",
    "clear_daily_skipped",
    "get_next_track",
    "get_upcoming_tracks",
    # Scheduler (Liquidsoap integration)
    "get_next_track_path",
    "get_current_state",
    "handle_track_unavailable",
    "get_scheduler_info",
    "reset_scheduler_state",
]
