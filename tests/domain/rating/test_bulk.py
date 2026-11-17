"""compute_rank_ratings: best-first order -> ratings."""

import pytest

from music_minion.domain.rating.bulk import compute_rank_ratings


def test_redistribute_reuses_existing_ratings_in_new_order() -> None:
    current = {1: 1400.0, 2: 1600.0, 3: 1500.0}
    new, method = compute_rank_ratings([1, 2, 3], current)
    assert method == "redistribute"
    assert new == {1: 1600.0, 2: 1500.0, 3: 1400.0}
    assert sorted(new.values()) == sorted(current.values())


def test_redistribute_is_noop_when_order_already_matches() -> None:
    current = {1: 1700.0, 2: 1550.0, 3: 1420.0}
    new, _ = compute_rank_ratings([1, 2, 3], current)
    assert new == current


def test_missing_tracks_join_pool_at_1500() -> None:
    new, method = compute_rank_ratings([9, 1], {1: 1600.0})
    assert method == "redistribute"
    assert new == {9: 1600.0, 1: 1500.0}


def test_unrated_bucket_gets_band() -> None:
    new, method = compute_rank_ratings([1, 2, 3], {})
    assert method == "band"
    assert new == {1: 1600.0, 2: 1500.0, 3: 1400.0}


def test_equal_non_default_pool_bands_around_that_value() -> None:
    new, method = compute_rank_ratings([1, 2], {1: 1700.0, 2: 1700.0})
    assert method == "band"
    assert new == {1: 1800.0, 2: 1600.0}


def test_fewer_than_two_tracks_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        compute_rank_ratings([1], {})
