"""Leakage guards for the offline keep-model dataset (#61)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from web.backend.artist_quality import bayesian_keep_rate
from web.backend.keep_decisions import ReposterEvent, TrackDecision
from web.backend.keep_model_dataset import (
    known_reposters,
    seen_at_floor,
    training_examples,
)

T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _at(days: float) -> datetime:
    return T0 + timedelta(days=days)


def _reposter(
    artist_id: int,
    ranking: int | None,
    event_days: float | None,
    seen_days: float | None,
    exact: bool = False,
) -> ReposterEvent:
    return ReposterEvent(
        artist_id=artist_id,
        ranking=ranking,
        is_following=True,
        event_at=_at(event_days) if event_days is not None else None,
        seen_at=_at(seen_days) if seen_days is not None else None,
        exact_time=exact,
    )


def _decision(
    sc_id: str,
    label: int,
    decided_days: float,
    reposters: tuple[ReposterEvent, ...] = (),
    uploader: int | None = None,
    released_days: float | None = None,
) -> TrackDecision:
    return TrackDecision(
        soundcloud_id=sc_id,
        label=label,
        event_type="both" if uploader and reposters else "repost",
        uploader_id=uploader,
        uploader_ranking=7 if uploader else None,
        uploader_is_following=True,
        uploader_source="upload_event" if uploader else "none",
        duration_ms=180_000,
        title="Track",
        genre=None,
        released_at=_at(released_days) if released_days is not None else None,
        first_seen=None,
        playlist_batch=None,
        reposters=reposters,
        decided_at=_at(decided_days),
        decided_at_source="test",
    )


def test_reposts_after_the_decision_are_excluded() -> None:
    before = _reposter(1, 10, event_days=-1, seen_days=-0.5)
    after = _reposter(2, 1, event_days=5, seen_days=6)
    decision = _decision("a", 1, decided_days=0, reposters=(before, after))
    assert known_reposters(decision, floor=None) == (before,)
    example = training_examples([decision])[0]
    assert example.features.reposter_count == 1
    assert example.features.best_reposter_rank == 10


def test_late_observation_is_excluded_unless_it_is_the_backfill() -> None:
    backfill_moment = _at(-30)
    floor = seen_at_floor(
        [
            _decision(
                "seed",
                0,
                decided_days=-40,
                reposters=(_reposter(9, 50, event_days=-45, seen_days=-30),),
            )
        ]
    )
    assert floor == backfill_moment + timedelta(hours=1)
    # Legacy row: repost time before decision, seen_at is the backfill stamp
    # even though the decision predates it -> counts.
    legacy = _reposter(1, 10, event_days=-50, seen_days=-30)
    # Row first observed well after the decision -> excluded.
    late = _reposter(2, 1, event_days=-50, seen_days=3)
    decision = _decision("a", 1, decided_days=-35, reposters=(legacy, late))
    assert known_reposters(decision, floor) == (legacy,)


def test_history_rates_come_only_from_earlier_decision_groups() -> None:
    reposter = _reposter(1, 10, event_days=-2, seen_days=-1)
    first = _decision("first", 1, decided_days=0, reposters=(reposter,), uploader=5)
    same_time = _decision("same", 1, decided_days=0, reposters=(reposter,), uploader=5)
    later = _decision("later", 0, decided_days=1, reposters=(reposter,), uploader=5)
    examples = {
        e.soundcloud_id: e for e in training_examples([later, same_time, first])
    }
    # Simultaneous decisions never see each other.
    assert examples["first"].features.reposter_keep_rate is None
    assert examples["same"].features.reposter_keep_rate is None
    assert examples["first"].features.uploader_keep_rate is None
    # The later decision sees both earlier keeps, nothing from itself.
    assert examples["later"].features.reposter_rated_count == pytest.approx(2.0)
    assert examples["later"].features.reposter_keep_rate == pytest.approx(
        bayesian_keep_rate(2, 2)
    )
    assert examples["later"].features.uploader_rated_count == 2
    assert examples["later"].features.best_reposter_legacy_hit_rate == pytest.approx(
        1.0
    )


def test_examples_are_chronological_and_carry_decision_time_source() -> None:
    examples = training_examples(
        [_decision("b", 0, decided_days=2), _decision("a", 1, decided_days=1)]
    )
    assert [e.soundcloud_id for e in examples] == ["a", "b"]
    assert examples[0].decided_at == _at(1).isoformat()
    assert examples[0].decided_at_source == "test"


def test_release_age_and_repost_lag_use_only_exact_repost_times() -> None:
    approximate = _reposter(1, 10, event_days=-9, seen_days=-1)
    exact = _reposter(2, 20, event_days=-3, seen_days=-1, exact=True)
    decision = _decision(
        "a", 1, decided_days=0, reposters=(approximate, exact), released_days=-10
    )
    features = training_examples([decision])[0].features
    assert features.release_age_days == pytest.approx(10)
    assert features.repost_lag_days == pytest.approx(7)
    without_exact = training_examples(
        [_decision("b", 1, decided_days=0, reposters=(approximate,), released_days=-10)]
    )[0].features
    assert without_exact.repost_lag_days is None


def test_top200_count_and_best_rank_ignore_unranked_reposters() -> None:
    reposters = (
        _reposter(1, None, event_days=-1, seen_days=-1),
        _reposter(2, 150, event_days=-1, seen_days=-1),
        _reposter(3, 40, event_days=-1, seen_days=-1),
        _reposter(4, 500, event_days=-1, seen_days=-1),
    )
    features = training_examples(
        [_decision("a", 0, decided_days=0, reposters=reposters)]
    )[0].features
    assert features.reposter_count == 4
    assert features.top200_reposter_count == 2
    assert features.best_reposter_rank == 40


def test_undated_decisions_are_dropped() -> None:
    undated = TrackDecision(
        **{**_decision("a", 1, decided_days=0).__dict__, "decided_at": None}
    )
    assert training_examples([undated]) == []
