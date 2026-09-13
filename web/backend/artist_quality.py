"""Role-specific artist quality: uploader keep rate vs reposter keep rate.

Attribution semantics (covered by tests):

* Each decided track is exactly one observation, no matter how many artists
  touched it.
* The uploader receives the full observation in the ``upload`` role.
* Reposters share one observation in the ``repost`` role, split equally across
  the unique reposters of that track. Ten reposters on one track therefore add
  one rated unit in total, not ten.
* Rates are Beta-binomial posterior means around the population prior, so an
  artist with one keep does not jump to 100%.
* ``ranking`` and ``tier`` are editorial. Nothing here writes them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Sequence

from loguru import logger

from web.backend.keep_decisions import TrackDecision, load_track_decisions

DEFAULT_PRIOR = 0.22
DEFAULT_PRIOR_STRENGTH = 10.0


@dataclass(frozen=True)
class ArtistRoleStat:
    artist_id: int
    role: str
    kept_weight: float
    rated_weight: float
    keep_rate: float


def rate_or_prior(rate: float | None, prior: float = DEFAULT_PRIOR) -> float:
    """Read a stored role rate; NULL means never rated, so use the prior."""
    return prior if rate is None else float(rate)


def bayesian_keep_rate(
    kept: float,
    rated: float,
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> float:
    """Beta-binomial posterior mean for sparse artist outcomes."""
    if rated < 0 or kept < 0 or kept > rated + 1e-9:
        raise ValueError(f"expected 0 <= kept <= rated, got kept={kept} rated={rated}")
    if prior_strength < 0 or not 0 <= prior <= 1:
        raise ValueError(f"invalid prior {prior} / strength {prior_strength}")
    denominator = rated + prior_strength
    return prior if denominator == 0 else (kept + prior * prior_strength) / denominator


def role_attributions(decision: TrackDecision) -> list[tuple[int, str, float]]:
    """(artist_id, role, weight) contributions of one track-level decision."""
    output: list[tuple[int, str, float]] = []
    if decision.uploader_id is not None:
        output.append((decision.uploader_id, "upload", 1.0))
    reposter_ids = sorted({event.artist_id for event in decision.reposters})
    weight = 1.0 / len(reposter_ids) if reposter_ids else 0.0
    output.extend((artist_id, "repost", weight) for artist_id in reposter_ids)
    return output


def aggregate_artist_role_stats(
    decisions: Sequence[TrackDecision],
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> list[ArtistRoleStat]:
    """Smoothed per-role rates with one observation per decided track."""
    totals: dict[tuple[int, str], list[float]] = {}
    seen: set[str] = set()
    for decision in decisions:
        if decision.soundcloud_id in seen:
            continue
        seen.add(decision.soundcloud_id)
        for artist_id, role, weight in role_attributions(decision):
            values = totals.setdefault((artist_id, role), [0.0, 0.0])
            values[0] += decision.label * weight
            values[1] += weight
    return [
        ArtistRoleStat(
            artist_id=artist_id,
            role=role,
            kept_weight=kept,
            rated_weight=rated,
            keep_rate=bayesian_keep_rate(kept, rated, prior, prior_strength),
        )
        for (artist_id, role), (kept, rated) in sorted(totals.items())
    ]


def legacy_full_credit_stats(
    decisions: Sequence[TrackDecision],
) -> dict[int, tuple[float, float, float]]:
    """The pre-#60 combined ``hit_rate``: every actor gets full track credit.

    Returns ``artist_id -> (kept, rated, raw_rate)`` without smoothing.
    """
    totals: dict[int, list[float]] = {}
    for decision in decisions:
        actors = {event.artist_id for event in decision.reposters}
        if decision.uploader_id is not None:
            actors.add(decision.uploader_id)
        for artist_id in actors:
            values = totals.setdefault(artist_id, [0.0, 0.0])
            values[0] += decision.label
            values[1] += 1.0
    return {
        artist_id: (kept, rated, kept / rated if rated else 0.0)
        for artist_id, (kept, rated) in totals.items()
    }


def recalculate_artist_role_stats(
    conn: sqlite3.Connection,
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> int:
    """Persist role stats for every artist. Never touches ranking or tier.

    Artists without rated history in a role get NULL rate and zero count so
    readers can tell "cold" from "measured at the prior".
    """
    stats = aggregate_artist_role_stats(
        load_track_decisions(conn), prior=prior, prior_strength=prior_strength
    )
    by_key = {(stat.artist_id, stat.role): stat for stat in stats}
    updates = []
    for row in conn.execute("SELECT id FROM discovery_artists").fetchall():
        upload = by_key.get((row["id"], "upload"))
        repost = by_key.get((row["id"], "repost"))
        updates.append(
            (
                upload.keep_rate if upload else None,
                upload.rated_weight if upload else 0.0,
                repost.keep_rate if repost else None,
                repost.rated_weight if repost else 0.0,
                row["id"],
            )
        )
    conn.executemany(
        """
        UPDATE discovery_artists
        SET upload_keep_rate = ?, upload_rated_count = ?,
            repost_keep_rate = ?, repost_rated_count = ?
        WHERE id = ?
        """,
        updates,
    )
    logger.info(f"artist role stats: updated {len(updates)} artists")
    return len(updates)


def _artist_names(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, display_name, slug, ranking, tier, is_following FROM discovery_artists"
    ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def artist_quality_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """Before/after comparison on the current decided-track dataset."""
    decisions = load_track_decisions(conn)
    separated = aggregate_artist_role_stats(decisions)
    legacy = legacy_full_credit_stats(decisions)
    names = _artist_names(conn)
    by_artist: dict[int, dict[str, Any]] = {}
    for stat in separated:
        entry = by_artist.setdefault(stat.artist_id, {})
        entry[stat.role] = stat
    rows = []
    for artist_id, roles in by_artist.items():
        kept, rated, raw = legacy.get(artist_id, (0.0, 0.0, 0.0))
        upload = roles.get("upload")
        repost = roles.get("repost")
        rows.append(
            {
                "artist_id": artist_id,
                "name": names.get(artist_id, {}).get("display_name")
                or names.get(artist_id, {}).get("slug")
                or str(artist_id),
                "ranking": names.get(artist_id, {}).get("ranking"),
                "legacy_rated": rated,
                "legacy_kept": kept,
                "legacy_hit_rate": raw,
                "upload_rated": upload.rated_weight if upload else 0.0,
                "upload_keep_rate": upload.keep_rate if upload else None,
                "repost_rated": repost.rated_weight if repost else 0.0,
                "repost_keep_rate": repost.keep_rate if repost else None,
            }
        )
    rows.sort(key=lambda row: (-row["legacy_rated"], row["artist_id"]))
    reposter_rows = sum(len(decision.reposters) for decision in decisions)
    return {
        "decided_tracks": len(decisions),
        "keeps": sum(decision.label for decision in decisions),
        "reposter_rows": reposter_rows,
        "legacy_total_credit": sum(rated for _, rated, _ in legacy.values()),
        "separated_total_credit": sum(stat.rated_weight for stat in separated),
        "artists_with_legacy_stats": len(legacy),
        "artists_with_upload_stats": sum(1 for s in separated if s.role == "upload"),
        "artists_with_repost_stats": sum(1 for s in separated if s.role == "repost"),
        "uploader_sources": _count_by(decisions, "uploader_source"),
        "event_types": _count_by(decisions, "event_type"),
        "prior": DEFAULT_PRIOR,
        "prior_strength": DEFAULT_PRIOR_STRENGTH,
        "artists": rows,
    }


def _count_by(decisions: Sequence[TrackDecision], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        key = str(getattr(decision, field))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_artist_quality_markdown(report: dict[str, Any], top: int = 40) -> str:
    """Human-readable before/after report for docs/reports."""
    lines = [
        "# Artist quality: before and after role separation",
        "",
        "Generated by `uv run python scripts/report_artist_quality.py`.",
        "",
        "## Dataset",
        "",
        f"- Decided tracks: {report['decided_tracks']} "
        f"({report['keeps']} keeps, "
        f"{report['keeps'] / max(1, report['decided_tracks']):.1%} keep rate)",
        f"- Reposter rows on decided tracks: {report['reposter_rows']} "
        f"({report['reposter_rows'] / max(1, report['decided_tracks']):.1f} per track)",
        f"- Uploader resolution: {report['uploader_sources']}",
        f"- Event types: {report['event_types']}",
        "",
        "## Credit inflation",
        "",
        "| Scheme | Total rated credit | Artists with stats |",
        "|---|---:|---:|",
        f"| Legacy `hit_rate` (full credit per actor) | "
        f"{report['legacy_total_credit']:.0f} | {report['artists_with_legacy_stats']} |",
        f"| Separated (1 per track, reposters share) | "
        f"{report['separated_total_credit']:.0f} | "
        f"{report['artists_with_upload_stats']} upload / "
        f"{report['artists_with_repost_stats']} repost |",
        "",
        "Legacy credit counts every decided track once per reposter, so the same",
        "decision is replayed roughly nine times and every reposter converges to",
        "the population keep rate. Separated credit keeps one observation per",
        "track, gives the uploader its own rate, and smooths both toward the",
        f"{report['prior']:.0%} prior with strength {report['prior_strength']:.0f}.",
        "",
        f"## Top {top} artists by legacy sample size",
        "",
        "| Artist | Rank | Legacy rated | Legacy hit | Upload rated | Upload keep | "
        "Repost rated | Repost keep |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["artists"][:top]:
        lines.append(
            f"| {row['name']} | {row['ranking'] if row['ranking'] is not None else '—'} | "
            f"{row['legacy_rated']:.0f} | {_pct(row['legacy_hit_rate'])} | "
            f"{row['upload_rated']:.0f} | {_pct(row['upload_keep_rate'])} | "
            f"{row['repost_rated']:.1f} | {_pct(row['repost_keep_rate'])} |"
        )
    lines.append("")
    return "\n".join(lines)
