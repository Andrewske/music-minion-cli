"""Leakage-safe training examples for the offline keep-probability model.

Every example is reconstructed as of its decision time proxy:

* reposters count only if the repost happened, and was observed, before the
  decision (observation times that predate the ``seen_at`` backfill are
  unknown and fall back to the repost time alone);
* uploader and reposter keep rates come only from decisions strictly earlier
  than the example's decision group, so tracks decided in the same sync cycle
  never inform each other;
* the label is never read from anything but the decision itself.

Known residual leakage, documented in the evaluation report: ``ranking`` and
``is_following`` have no history table, so their current values stand in for
their values at decision time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Sequence

from web.backend.artist_quality import bayesian_keep_rate, role_attributions
from web.backend.keep_decisions import ReposterEvent, TrackDecision
from web.backend.preference_model import TrackFeatures, TrainingExample

SEEN_AT_BACKFILL_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class RoleTally:
    kept: float = 0.0
    rated: float = 0.0

    def add(self, kept: float, rated: float) -> RoleTally:
        return RoleTally(self.kept + kept, self.rated + rated)


History = dict[tuple[int, str], RoleTally]


def seen_at_floor(decisions: Sequence[TrackDecision]) -> datetime | None:
    """End of the ``seen_at`` backfill window; earlier observations are unknown."""
    values = [
        event.seen_at
        for decision in decisions
        for event in decision.reposters
        if event.seen_at is not None
    ]
    return min(values) + SEEN_AT_BACKFILL_WINDOW if values else None


def known_reposters(
    decision: TrackDecision, floor: datetime | None
) -> tuple[ReposterEvent, ...]:
    """Reposters whose repost existed and was observable at decision time."""
    decided = decision.decided_at
    if decided is None:
        return decision.reposters
    kept: list[ReposterEvent] = []
    for event in decision.reposters:
        if event.event_at is not None and event.event_at > decided:
            continue
        observed_late = event.seen_at is not None and event.seen_at > decided
        backfilled = (
            floor is not None and event.seen_at is not None and event.seen_at <= floor
        )
        if observed_late and not backfilled:
            continue
        kept.append(event)
    return tuple(kept)


def _rank_key(event: ReposterEvent) -> tuple[bool, int, int]:
    return (event.ranking is None, event.ranking or 0, event.artist_id)


def _rate(
    history: History, artist_id: int | None, role: str
) -> tuple[float | None, float]:
    if artist_id is None:
        return None, 0.0
    tally = history.get((artist_id, role))
    if tally is None or tally.rated == 0:
        return None, 0.0
    return bayesian_keep_rate(tally.kept, tally.rated), tally.rated


def _days(later: datetime | None, earlier: datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds() / 86_400


def _legacy_hit_rate(history: History, artist_id: int | None) -> float | None:
    if artist_id is None:
        return None
    tally = history.get((artist_id, "legacy"))
    if tally is None or tally.rated == 0:
        return None
    return tally.kept / tally.rated


def features_at_decision(
    decision: TrackDecision, reposters: Sequence[ReposterEvent], history: History
) -> TrackFeatures:
    """Semantic features using only information available at decision time."""
    ranked = sorted(reposters, key=_rank_key)
    best = ranked[0] if ranked else None
    reposter_rates = [_rate(history, event.artist_id, "repost") for event in ranked]
    known_rates = [rate for rate, _ in reposter_rates if rate is not None]
    uploader_rate, uploader_rated = _rate(history, decision.uploader_id, "upload")
    best_rate, _ = _rate(history, best.artist_id if best else None, "repost")
    exact = [e.event_at for e in ranked if e.exact_time and e.event_at is not None]
    return TrackFeatures(
        duration_ms=decision.duration_ms,
        followed_uploader=decision.uploader_id is not None
        and decision.uploader_is_following,
        uploader_rank=decision.uploader_ranking,
        reposter_count=len(ranked),
        top200_reposter_count=sum(
            1 for e in ranked if e.ranking is not None and e.ranking <= 200
        ),
        best_reposter_rank=best.ranking if best else None,
        uploader_keep_rate=uploader_rate,
        uploader_rated_count=uploader_rated,
        reposter_keep_rate=max(known_rates) if known_rates else None,
        reposter_rated_count=sum(rated for _, rated in reposter_rates),
        best_reposter_keep_rate=best_rate,
        best_reposter_legacy_hit_rate=_legacy_hit_rate(
            history, best.artist_id if best else None
        ),
        event_type=decision.event_type,
        genre=decision.genre,
        title=decision.title,
        release_age_days=_days(decision.decided_at, decision.released_at),
        repost_lag_days=_days(min(exact), decision.released_at) if exact else None,
    )


def _record_decision(
    history: History, decision: TrackDecision, reposters: Sequence[ReposterEvent]
) -> History:
    """Fold one decision into role and legacy tallies (returns a new dict)."""
    updated = dict(history)
    as_of = replace(decision, reposters=tuple(reposters))
    for artist_id, role, weight in role_attributions(as_of):
        key = (artist_id, role)
        updated[key] = updated.get(key, RoleTally()).add(
            decision.label * weight, weight
        )
    actors = {event.artist_id for event in reposters}
    if decision.uploader_id is not None:
        actors.add(decision.uploader_id)
    for artist_id in actors:
        key = (artist_id, "legacy")
        updated[key] = updated.get(key, RoleTally()).add(float(decision.label), 1.0)
    return updated


def training_examples(decisions: Sequence[TrackDecision]) -> list[TrainingExample]:
    """Build chronological examples; same-time decisions share one history."""
    ordered = sorted(
        (d for d in decisions if d.decided_at is not None),
        key=lambda d: (d.decided_at, d.soundcloud_id),
    )
    floor = seen_at_floor(ordered)
    history: History = {}
    pending: list[tuple[TrackDecision, tuple[ReposterEvent, ...]]] = []
    output: list[TrainingExample] = []
    current_time: datetime | None = None
    for decision in ordered:
        if decision.decided_at != current_time:
            for done, done_reposters in pending:
                history = _record_decision(history, done, done_reposters)
            pending = []
            current_time = decision.decided_at
        reposters = known_reposters(decision, floor)
        output.append(
            TrainingExample(
                soundcloud_id=decision.soundcloud_id,
                decided_at=decision.decided_at.isoformat(),
                label=decision.label,
                features=features_at_decision(decision, reposters, history),
                decided_at_source=decision.decided_at_source,
            )
        )
        pending.append((decision, reposters))
    return output
