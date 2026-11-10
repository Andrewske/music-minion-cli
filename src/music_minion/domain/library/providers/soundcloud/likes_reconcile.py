"""Reconcile sc_likes against the full SoundCloud likes list.

The hourly sync only adds likes. This drops likes Kevin undid directly on
SoundCloud, behind safety rails, because a wrong delete loses the red heart
on a track he still likes and nothing puts it back until he re-likes it:

- incomplete fetch: never delete (adds are still applied, they're safe)
- concurrency: never delete a row written at/after the fetch started
- empty fetch: never wipe the table unless forced
- mass delete: more than max(25, 5% of likes) removals is skipped unless forced
"""

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from loguru import logger

from music_minion.core import database
from music_minion.domain.library.providers.soundcloud.likes_fetch import (
    LikesSnapshot,
    fetch_all_liked_ids,
)

MASS_DELETE_MIN = 25
MASS_DELETE_FRACTION = 0.05
SAMPLE_SIZE = 20


@dataclass(frozen=True)
class ReconcilePlan:
    to_add: frozenset[str]
    to_remove: frozenset[str]
    protected: frozenset[str]  # absent from fetch but written after it started
    guard: str | None  # why deletions were skipped, if they were


@dataclass(frozen=True)
class ReconcileReport:
    fetched: int
    complete: bool
    reason: str
    current: int
    to_add: int
    to_remove: int
    protected: int
    guard: str | None
    applied: bool
    added: int = 0
    removed: int = 0
    remove_sample: list[str] = field(default_factory=list)

    @property
    def skipped_by_guard(self) -> int:
        """Removals the planner found but a guard held back."""
        return self.to_remove if self.guard else 0


def mass_delete_threshold(current_count: int) -> int:
    """Most removals one run may make without --force."""
    return max(MASS_DELETE_MIN, math.ceil(current_count * MASS_DELETE_FRACTION))


def _removal_guard(
    snapshot: LikesSnapshot, current_count: int, removal_count: int, force: bool
) -> str | None:
    if not snapshot.complete:
        return f"incomplete fetch: {snapshot.reason}"
    if force or removal_count == 0:
        return None
    if not snapshot.ids:
        return "empty fetch"
    limit = mass_delete_threshold(current_count)
    if removal_count > limit:
        return f"mass delete: {removal_count} > {limit}"
    return None


def plan_reconcile(
    current: Mapping[str, str | None],
    snapshot: LikesSnapshot,
    fetch_started_at: str,
    force: bool = False,
) -> ReconcilePlan:
    """Pure: current {soundcloud_id: synced_at} vs the fetched snapshot.

    `to_remove` is what would be deleted; when `guard` is set nothing is.
    An incomplete snapshot is never forced into deleting.
    """
    absent = set(current) - snapshot.ids
    protected = {i for i in absent if (current[i] or "") >= fetch_started_at}
    candidates = frozenset(absent - protected)
    guard = _removal_guard(snapshot, len(current), len(candidates), force)
    return ReconcilePlan(
        to_add=frozenset(snapshot.ids - set(current)),
        to_remove=candidates,
        protected=frozenset(protected),
        guard=guard,
    )


def _sample_titles(soundcloud_ids: frozenset[str]) -> list[str]:
    """'artist - title (id)' for up to SAMPLE_SIZE ids, from local tables."""
    ids = sorted(soundcloud_ids)[:SAMPLE_SIZE]
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    with database.get_db_connection() as conn:
        rows = conn.execute(
            f"""SELECT soundcloud_id, artist || ' - ' || title FROM tracks
            WHERE soundcloud_id IN ({placeholders})
            UNION ALL
            SELECT soundcloud_id, artist_name || ' - ' || title FROM discovery_tracks
            WHERE soundcloud_id IN ({placeholders})""",
            ids + ids,
        ).fetchall()
    names: dict[str, str] = {}
    for sc_id, name in rows:
        names.setdefault(sc_id, name)
    return [f"{names.get(i) or '(unknown)'} ({i})" for i in ids]


def _safe_fetch(access_token: str) -> LikesSnapshot:
    """The fetch, with any unexpected crash turned into an incomplete snapshot."""
    try:
        return fetch_all_liked_ids(access_token)
    except Exception as exc:  # noqa: BLE001 - any failure must mean "don't delete"
        logger.exception("sc likes full fetch crashed")
        return LikesSnapshot(frozenset(), False, f"fetch crashed: {exc}", 0)


def _build_report(
    snapshot: LikesSnapshot, current_count: int, plan: ReconcilePlan
) -> ReconcileReport:
    return ReconcileReport(
        fetched=len(snapshot.ids),
        complete=snapshot.complete,
        reason=snapshot.reason,
        current=current_count,
        to_add=len(plan.to_add),
        to_remove=len(plan.to_remove),
        protected=len(plan.protected),
        guard=plan.guard,
        applied=False,
        remove_sample=_sample_titles(plan.to_remove),
    )


def log_summary(report: ReconcileReport) -> None:
    """One structured line per run; a warning when a guard held deletes back."""
    line = (
        f"sc_likes_reconcile fetched={report.fetched} complete={report.complete} "
        f"current={report.current} to_add={report.to_add} "
        f"to_remove={report.to_remove} added={report.added} "
        f"removed={report.removed} protected={report.protected} "
        f"skipped_by_guard={report.skipped_by_guard} guard={report.guard!r} "
        f"applied={report.applied} reason={report.reason!r}"
    )
    if report.guard and report.to_remove:
        logger.warning(line)
    else:
        logger.info(line)


def report_json(report: ReconcileReport) -> str:
    """The report as JSON (stored on sc_feed_sync_state for debugging)."""
    return json.dumps({**asdict(report), "skipped_by_guard": report.skipped_by_guard})


def reconcile_sc_likes(
    access_token: str, apply: bool = False, force: bool = False
) -> ReconcileReport:
    """Full fetch, plan, and (when apply=True) write. Dry run by default."""
    fetch_started_at = database.sqlite_utc_now()
    snapshot = _safe_fetch(access_token)
    current = database.load_sc_likes_synced_at()
    plan = plan_reconcile(current, snapshot, fetch_started_at, force=force)
    report = _build_report(snapshot, len(current), plan)
    if apply:
        to_remove = frozenset() if plan.guard else plan.to_remove
        added, removed = database.apply_sc_likes_reconcile(
            plan.to_add, to_remove, fetch_started_at
        )
        report = replace(report, applied=True, added=added, removed=removed)
    log_summary(report)
    return report


def reconcile_for_provider(
    provider_state: Any, apply: bool = False, force: bool = False
) -> ReconcileReport | None:
    """reconcile_sc_likes with a fresh token; None when SC isn't authenticated."""
    from music_minion.domain.library.providers.soundcloud.api import (
        _ensure_valid_token,
    )

    _state, token_data = _ensure_valid_token(provider_state)
    if not token_data or not token_data.get("access_token"):
        logger.warning("sc_likes_reconcile skipped: SoundCloud not authenticated")
        return None
    return reconcile_sc_likes(token_data["access_token"], apply=apply, force=force)
