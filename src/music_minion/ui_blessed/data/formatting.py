"""Formatting helper functions."""


def format_time(seconds: float) -> str:
    """
    Format seconds as MM:SS.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def format_bpm(bpm: int | None) -> str:
    """
    Format BPM with color coding.

    Args:
        bpm: Beats per minute

    Returns:
        Formatted BPM string
    """
    if bpm is None:
        return ""
    return f"♪ {bpm} BPM ♪"
