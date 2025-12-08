"""Memoized selectors for expensive operations in the render path.

Redux-style memoization that caches results based on input equality.
Only recalculates when inputs actually change.
"""

from typing import Callable, TypeVar, Generic, Any
from functools import wraps
from loguru import logger

T = TypeVar("T")


class MemoizedSelector(Generic[T]):
    """Cache-based selector that only recalculates when inputs change.

    Compares new inputs to cached inputs using tuple equality.
    Returns cached result if inputs are identical.

    Usage:
        @MemoizedSelector
        def expensive_operation(arg1: str, arg2: list[dict]) -> list[dict]:
            # Expensive computation here
            return result
    """

    def __init__(self, func: Callable[..., T]) -> None:
        self.func = func
        self._cache: dict[tuple[str, str], T] = {}
        wraps(func)(self)

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        # Create hashable cache key from inputs
        # Use repr() to convert to string, which handles nested structures
        try:
            cache_key = (repr(args), repr(tuple(sorted(kwargs.items()))))
        except TypeError:
            # Fallback: if repr fails, use str
            cache_key = (str(args), str(tuple(sorted(kwargs.items()))))

        # Check cache
        if cache_key in self._cache:
            logger.trace(f"Cache hit for {self.func.__name__}")
            return self._cache[cache_key]

        # Cache miss - compute result
        logger.trace(f"Cache miss for {self.func.__name__} - computing")
        result = self.func(*args, **kwargs)

        # Store in cache
        self._cache[cache_key] = result

        return result

    def clear_cache(self) -> None:
        """Clear cached results. Useful for testing or memory management."""
        self._cache.clear()


# Track filtering selector
@MemoizedSelector
def filter_search_tracks(query: str, tracks: tuple[dict, ...]) -> list[dict]:
    """Filter tracks by search query with fuzzy matching.

    Expensive operation that performs fuzzy string matching on track metadata.
    Memoized to avoid recalculation during typing.

    Note: tracks is a tuple (immutable) for proper cache key comparison.
    Convert from list to tuple when calling.

    Matches implementation from track_search.py:filter_tracks()
    """
    if not query:
        return list(tracks)  # Return all tracks if no query

    query_lower = query.lower()
    matches = []

    for track in tracks:
        # Concatenate searchable fields (title, artist, album, genre, tags, notes)
        searchable = " ".join(
            [
                track.get("title", "") or "",
                track.get("artist", "") or "",
                track.get("album", "") or "",
                track.get("genre", "") or "",
                track.get("tags", "") or "",
                track.get("notes", "") or "",
            ]
        ).lower()

        if query_lower in searchable:
            matches.append(track)

    return matches


# Strategic pair selection selector
@MemoizedSelector
def select_strategic_pair_memoized(
    tracks_tuple: tuple[tuple[int, dict], ...],
    ratings_cache_tuple: tuple[tuple[int, tuple], ...],
) -> tuple[dict, dict]:
    """Select two tracks for comparison using strategic pairing algorithm.

    Memoized version of select_strategic_pair from elo.py.
    Expensive operation that analyzes track ratings and comparison counts.

    Note: All inputs must be tuples (immutable) for proper cache key comparison.
    Convert from dicts/lists to tuples when calling.

    Strategy:
    1. Bootstrap: If 2+ tracks have <10 comparisons, pair them randomly
    2. Under-compared: If tracks have <20 comparisons, pair with similar-rated track (±200 points)
    3. Random fallback: Pick any two tracks

    Args:
        tracks_tuple: Tuple of (track_id, track_dict) pairs
        ratings_cache_tuple: Tuple of (track_id, (rating, comparison_count)) pairs

    Returns:
        (track_a, track_b) tuple

    Raises:
        ValueError: If less than 2 tracks provided
    """
    import random

    # Convert back to working data structures
    tracks = [track_dict for _, track_dict in tracks_tuple]
    ratings_cache = {
        track_id: {"rating": rating, "comparison_count": comp_count}
        for track_id, (rating, comp_count) in ratings_cache_tuple
    }

    if len(tracks) < 2:
        raise ValueError("Need at least 2 tracks for comparison")

    # Bootstrap: pair tracks with <10 comparisons
    bootstrap = [
        t
        for t in tracks
        if ratings_cache.get(t["id"], {}).get("comparison_count", 0) < 10
    ]
    if len(bootstrap) >= 2:
        return tuple(random.sample(bootstrap, 2))

    # Under-compared: pair tracks with <20 comparisons with similar-rated opponents
    under_compared = [
        t
        for t in tracks
        if ratings_cache.get(t["id"], {}).get("comparison_count", 0) < 20
    ]
    if under_compared:
        track_a = random.choice(under_compared)
        rating_a = ratings_cache.get(track_a["id"], {}).get("rating", 1500.0)
        similar = [
            t
            for t in tracks
            if t["id"] != track_a["id"]
            and abs(ratings_cache.get(t["id"], {}).get("rating", 1500.0) - rating_a)
            <= 200
        ]
        track_b = (
            random.choice(similar)
            if similar
            else random.choice([t for t in tracks if t["id"] != track_a["id"]])
        )
        return (track_a, track_b)

    # Random fallback
    return tuple(random.sample(tracks, 2))
