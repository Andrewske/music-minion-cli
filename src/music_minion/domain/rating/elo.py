"""
Elo rating system for track comparisons.

Pure functional implementation with no side effects or database access.
All state is passed explicitly via parameters and returned as new values.
"""

import random


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Calculate expected win probability for player A vs player B using Elo formula.

    Formula: 1 / (1 + 10^((rating_b - rating_a) / 400))

    Args:
        rating_a: Current Elo rating of player A
        rating_b: Current Elo rating of player B

    Returns:
        Expected score for player A (0.0 to 1.0, where 0.5 = 50% chance)

    Examples:
        >>> expected_score(1500, 1500)
        0.5
        >>> expected_score(1700, 1500)  # A is 200 points higher
        0.76  # ~76% win probability
    """
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_ratings(
    winner_rating: float, loser_rating: float, k_factor: float
) -> tuple[float, float]:
    """
    Update Elo ratings after a comparison.

    Args:
        winner_rating: Current rating of winning track
        loser_rating: Current rating of losing track
        k_factor: K-factor (how much ratings change). Higher = more volatile.

    Returns:
        (new_winner_rating, new_loser_rating)

    Examples:
        >>> update_ratings(1500, 1500, k_factor=32)
        (1516.0, 1484.0)  # Equal ratings, winner gains 16, loser loses 16
    """
    expected_winner = expected_score(winner_rating, loser_rating)
    expected_loser = expected_score(loser_rating, winner_rating)

    new_winner_rating = winner_rating + k_factor * (1.0 - expected_winner)
    new_loser_rating = loser_rating + k_factor * (0.0 - expected_loser)

    return (new_winner_rating, new_loser_rating)


def get_k_factor(comparison_count: int) -> float:
    """
    Get adaptive K-factor based on number of comparisons.

    - <10 comparisons: K=40 (bootstrap, high volatility)
    - 10-29 comparisons: K=24 (refinement)
    - 30+ comparisons: K=16 (stable)

    Args:
        comparison_count: Number of times this track has been compared

    Returns:
        Appropriate K-factor
    """
    if comparison_count < 10:
        return 40.0
    elif comparison_count < 30:
        return 24.0
    else:
        return 16.0


def select_strategic_pair(
    tracks: list[dict], ratings_cache: dict[int, dict]
) -> tuple[dict, dict]:
    """
    Select two tracks for comparison using strategic pairing algorithm.

    Strategy:
    1. Bootstrap: If 2+ tracks have <10 comparisons, pair them randomly
    2. Under-compared: If tracks have <20 comparisons, pair with similar-rated track (±200 points)
    3. Random fallback: Pick any two tracks

    Args:
        tracks: List of track dictionaries (must have 'id' field)
        ratings_cache: Dict mapping track_id -> {'rating': float, 'comparison_count': int}

    Returns:
        (track_a, track_b) tuple

    Raises:
        ValueError: If less than 2 tracks provided
    """
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


def select_weighted_pair(
    all_tracks: list[dict],
    priority_tracks: list[dict],
    ratings_cache: dict[int, dict],
    target_comparisons: int = 5,
) -> tuple[dict, dict]:
    """
    Select pair with one track from priority set, one from full library.

    Track A is always from priority_tracks (preferring under-compared).
    Track B is from all_tracks (for cross-library ELO calibration).

    Args:
        all_tracks: Full list of tracks (including priority tracks)
        priority_tracks: Subset of tracks to prioritize
        ratings_cache: Dict mapping track_id -> {'rating': float, 'comparison_count': int}
        target_comparisons: Target comparisons per track (default 5)

    Returns:
        (track_a, track_b) tuple

    Raises:
        ValueError: If not enough tracks
    """
    if len(all_tracks) < 2:
        raise ValueError("Need at least 2 tracks for comparison")

    # Filter priority tracks that haven't hit target coverage yet
    under_target = [
        t
        for t in priority_tracks
        if ratings_cache.get(t["id"], {}).get("comparison_count", 0)
        < target_comparisons
    ]

    # If all priority tracks have full coverage, fall back to standard pairing
    if not under_target:
        return select_strategic_pair(all_tracks, ratings_cache)

    # Track A: from priority tracks, prefer least compared
    under_target.sort(
        key=lambda t: ratings_cache.get(t["id"], {}).get("comparison_count", 0)
    )
    # Pick from bottom 20% (least compared) with some randomness
    pool_size = max(1, len(under_target) // 5)
    track_a = random.choice(under_target[:pool_size])

    # Track B: from all tracks, prefer similar rating for ELO accuracy
    rating_a = ratings_cache.get(track_a["id"], {}).get("rating", 1500.0)
    candidates = [t for t in all_tracks if t["id"] != track_a["id"]]

    # Try to find similar-rated opponent (±200 points)
    similar = [
        t
        for t in candidates
        if abs(ratings_cache.get(t["id"], {}).get("rating", 1500.0) - rating_a) <= 200
    ]

    track_b = random.choice(similar) if similar else random.choice(candidates)

    return (track_a, track_b)
