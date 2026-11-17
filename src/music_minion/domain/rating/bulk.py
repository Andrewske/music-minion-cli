"""Bulk ELO from a manual best-first ordering (organizer "Apply rating").

A bucket's existing ratings are re-dealt in the new order, so a theme bucket
keeps its own spread and level instead of being stretched to the playlist's
full range. A bucket with no spread (all unrated) gets a fixed linear band.
"""

DEFAULT_RATING = 1500.0
FALLBACK_HALF_WIDTH = 100.0  # unrated bucket -> 1600 .. 1400
MIN_SPREAD = 1.0  # pool spread below this counts as "unrated"


def band_ratings(n: int, center: float) -> list[float]:
    """Evenly spaced ratings from center+H (first) down to center-H (last)."""
    step = 2 * FALLBACK_HALF_WIDTH / (n - 1)
    return [center + FALLBACK_HALF_WIDTH - i * step for i in range(n)]


def compute_rank_ratings(
    ordered_track_ids: list[int], current: dict[int, float]
) -> tuple[dict[int, float], str]:
    """Map a best-first order to new ratings.

    Args:
        ordered_track_ids: Track ids, best first.
        current: Existing ratings; missing tracks count as DEFAULT_RATING.

    Returns:
        ({track_id: new_rating}, method) where method is 'redistribute' or 'band'.

    Raises:
        ValueError: Fewer than 2 tracks.
    """
    n = len(ordered_track_ids)
    if n < 2:
        raise ValueError(f"Need at least 2 tracks to rank, got {n}")
    pool = [current.get(tid, DEFAULT_RATING) for tid in ordered_track_ids]
    if max(pool) - min(pool) >= MIN_SPREAD:
        new = sorted(pool, reverse=True)
        method = "redistribute"
    else:
        new = band_ratings(n, pool[0])
        method = "band"
    return dict(zip(ordered_track_ids, new)), method
