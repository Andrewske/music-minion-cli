"""Database orchestration and rollout policy for preference scoring."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.preference_model import (
    DEFAULT_PRIOR,
    ModelArtifact,
    TrackFeatures,
    TrainingExample,
    artifact_from_json,
    artifact_to_json,
    calibration_bins,
    evaluate_model,
    evaluate_probabilities,
    explanation,
    fit_model,
    score_features,
)

DEFAULT_PRIOR_STRENGTH = 10.0
DEFAULT_RETRAIN_DECISIONS = 25
DEFAULT_EXPLORATION_SHARE = 0.12


@dataclass(frozen=True)
class ArtistRoleStat:
    artist_id: int
    role: str
    kept_weight: float
    rated_weight: float
    keep_rate: float


@dataclass(frozen=True)
class ScoredCandidate:
    soundcloud_id: str
    probability: float
    uploader_id: int | None
    reposter_ids: tuple[int, ...]
    payload: dict[str, Any]


def bayesian_keep_rate(
    kept: float,
    rated: float,
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> float:
    """Beta-binomial posterior mean for sparse artist outcomes."""
    if rated < 0 or kept < 0 or kept > rated:
        raise ValueError("expected 0 <= kept <= rated")
    if prior_strength < 0 or not 0 <= prior <= 1:
        raise ValueError("invalid prior")
    denominator = rated + prior_strength
    return prior if denominator == 0 else (kept + prior * prior_strength) / denominator


def aggregate_artist_role_stats(
    decisions: Sequence[dict[str, Any]],
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> list[ArtistRoleStat]:
    """Aggregate uploader and reposter quality without duplicating tracks.

    A definitive track decision contributes weight 1 to its uploader.  For the
    reposter role it contributes total weight 1, split evenly across the unique
    currently qualifying reposters.  Thus a ten-reposter track does not create
    ten training-equivalent observations, while each reposter gets transparent
    fractional attribution for the recommendation they participated in.
    """
    totals: dict[tuple[int, str], list[float]] = {}
    seen_tracks: set[str] = set()
    for row in sorted(
        decisions,
        key=lambda item: (str(item.get("decided_at", "")), str(item["soundcloud_id"])),
    ):
        sc_id = str(row["soundcloud_id"])
        if sc_id in seen_tracks:
            continue
        seen_tracks.add(sc_id)
        decision = row.get("decision")
        if decision not in {"keep", "nope"}:
            continue
        kept = float(decision == "keep")
        uploader_id = row.get("uploader_id")
        if uploader_id is not None:
            values = totals.setdefault((int(uploader_id), "upload"), [0.0, 0.0])
            values[0] += kept
            values[1] += 1.0
        reposter_ids = tuple(
            sorted({int(value) for value in row.get("reposter_ids", ())})
        )
        if reposter_ids:
            weight = 1.0 / len(reposter_ids)
            for reposter_id in reposter_ids:
                values = totals.setdefault((reposter_id, "repost"), [0.0, 0.0])
                values[0] += kept * weight
                values[1] += weight
    return [
        ArtistRoleStat(
            artist_id=artist_id,
            role=role,
            kept_weight=values[0],
            rated_weight=values[1],
            keep_rate=bayesian_keep_rate(values[0], values[1], prior, prior_strength),
        )
        for (artist_id, role), values in sorted(totals.items())
    ]


def load_current_decision_roles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.soundcloud_id, d.decision, d.decided_at,
               COALESCE(u.discovery_artist_id, uploader.id) AS uploader_id
        FROM sc_track_decisions d
        LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = d.soundcloud_id
        LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = d.soundcloud_id
        LEFT JOIN discovery_artists uploader
          ON uploader.soundcloud_user_id = dt.uploader_soundcloud_id
        WHERE d.is_current = 1 AND d.decision IN ('keep', 'nope')
        ORDER BY d.decided_at, d.id
        """
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        reposters = conn.execute(
            """
            SELECT DISTINCT dtr.discovery_artist_id
            FROM discovery_track_reposters dtr
            JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
            JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
            WHERE dt.soundcloud_id = ? AND da.is_following = 1
              AND COALESCE(dtr.reposted_at, dtr.seen_at) <= ?
            ORDER BY dtr.discovery_artist_id
            """,
            (row["soundcloud_id"], row["decided_at"]),
        ).fetchall()
        item = dict(row)
        item["reposter_ids"] = [value["discovery_artist_id"] for value in reposters]
        output.append(item)
    return output


def recalculate_artist_role_stats(
    conn: sqlite3.Connection,
    prior: float = DEFAULT_PRIOR,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> int:
    """Persist separated role stats while preserving manual rank and tier."""
    stats = aggregate_artist_role_stats(
        load_current_decision_roles(conn), prior=prior, prior_strength=prior_strength
    )
    by_artist: dict[int, dict[str, ArtistRoleStat]] = {}
    for stat in stats:
        by_artist.setdefault(stat.artist_id, {})[stat.role] = stat
    rows = conn.execute("SELECT id FROM discovery_artists").fetchall()
    updates = []
    for row in rows:
        artist_stats = by_artist.get(row["id"], {})
        upload = artist_stats.get("upload")
        repost = artist_stats.get("repost")
        updates.append(
            (
                upload.keep_rate if upload else prior,
                upload.rated_weight if upload else 0.0,
                repost.keep_rate if repost else prior,
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


def artist_quality_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compare legacy full-credit repost attribution with separated stats."""
    decisions = load_current_decision_roles(conn)
    separated = aggregate_artist_role_stats(decisions)
    legacy: dict[int, list[float]] = {}
    unique_tracks = {str(row["soundcloud_id"]) for row in decisions}
    for row in decisions:
        if row["decision"] not in {"keep", "nope"}:
            continue
        kept = float(row["decision"] == "keep")
        actor_ids = set(row.get("reposter_ids", ()))
        if row.get("uploader_id") is not None:
            actor_ids.add(row["uploader_id"])
        for artist_id in actor_ids:
            values = legacy.setdefault(int(artist_id), [0.0, 0.0])
            values[0] += kept
            values[1] += 1.0
    legacy_rows = [
        {
            "artist_id": artist_id,
            "kept": values[0],
            "rated": values[1],
            "raw_keep_rate": values[0] / values[1] if values[1] else 0,
        }
        for artist_id, values in sorted(legacy.items())
    ]
    return {
        "decision_rows": len(decisions),
        "unique_decided_tracks": len(unique_tracks),
        "multi_reposter_semantics": "one track weight split equally across unique qualifying reposters",
        "legacy_full_credit": legacy_rows,
        "separated_bayesian": [stat.__dict__ for stat in separated],
    }


def features_from_feed_item(
    item: dict[str, Any], as_of: str | None = None
) -> TrackFeatures:
    uploader = item.get("uploader") or item.get("artist") or {}
    reposters = item.get("reposters") or []
    uploaded_at = item.get("released_at") or item.get("uploaded_at")
    event_at = item.get("event_at") or item.get("reposted_at") or uploaded_at
    reference = _parse_datetime(as_of) or datetime.now(timezone.utc)
    uploaded = _parse_datetime(uploaded_at)
    reposted = _parse_datetime(event_at)
    sources = set(item.get("sources") or ())
    inferred_event_type = (
        "both"
        if {"release", "repost"}.issubset(sources)
        else "release"
        if "release" in sources
        else "repost"
    )
    return TrackFeatures(
        duration_ms=item.get("duration_ms"),
        followed_uploader=bool(uploader.get("is_following")),
        uploader_rank=uploader.get("ranking"),
        reposter_count=int(item.get("reposter_count") or len(reposters)),
        best_reposter_rank=item.get("best_reposter_rank"),
        uploader_keep_rate=uploader.get("upload_keep_rate"),
        uploader_rated_count=float(uploader.get("upload_rated_count") or 0),
        reposter_keep_rate=item.get("best_reposter_keep_rate"),
        reposter_rated_count=float(item.get("reposter_rated_count") or 0),
        event_type=str(
            item.get("event_type") or item.get("source") or inferred_event_type
        ),
        genre=item.get("genre"),
        title=item.get("title") or "",
        release_age_days=max(0.0, (reference - uploaded).total_seconds() / 86_400)
        if uploaded
        else None,
        repost_lag_days=max(0.0, (reposted - uploaded).total_seconds() / 86_400)
        if uploaded and reposted
        else None,
        as_of=reference.isoformat(),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    for fmt in ("%Y/%m/%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def training_examples_from_decisions(conn: sqlite3.Connection) -> list[TrainingExample]:
    """Load one leakage-safe example per definitive decision.

    New decisions use their contemporaneous feature snapshot.  Legacy rows are
    reconstructed conservatively: event joins are bounded by decision time,
    artist rates come only from earlier decisions, and metadata is used only
    when its recorded update time is not later than the decision.  Unknown
    values remain unknown instead of borrowing present-day state.
    """
    rows = conn.execute(
        """
        SELECT soundcloud_id, decision, decided_at, feature_snapshot
        FROM sc_track_decisions
        WHERE is_current = 1
          AND decision IN ('keep', 'nope')
          AND feature_snapshot IS NOT NULL
        ORDER BY decided_at, id
        """
    ).fetchall()
    examples: list[TrainingExample] = []
    seen: set[str] = set()
    valid_fields = set(TrackFeatures.__dataclass_fields__)
    history: dict[tuple[int, str], list[float]] = {}
    for row in rows:
        sc_id = str(row["soundcloud_id"])
        if sc_id in seen:
            continue
        features: TrackFeatures | None = None
        if row["feature_snapshot"]:
            try:
                payload = json.loads(row["feature_snapshot"])
                values = {
                    key: value for key, value in payload.items() if key in valid_fields
                }
                features = TrackFeatures(**values)
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning(
                    f"preference model: invalid feature snapshot for {sc_id}"
                )
        actors = _actors_at_decision(conn, sc_id, row["decided_at"])
        if features is None:
            features = _legacy_features_at_decision(
                conn, sc_id, row["decided_at"], actors, history
            )
        seen.add(sc_id)
        examples.append(
            TrainingExample(
                soundcloud_id=sc_id,
                decided_at=row["decided_at"],
                label=int(row["decision"] == "keep"),
                features=features,
            )
        )
        _update_role_history(history, actors, row["decision"] == "keep")
    return examples


def _actors_at_decision(
    conn: sqlite3.Connection, soundcloud_id: str, decided_at: str
) -> dict[str, Any]:
    uploader = conn.execute(
        """
        SELECT discovery_artist_id, uploaded_at
        FROM sc_artist_uploads
        WHERE soundcloud_id = ? AND uploaded_at <= ?
        """,
        (soundcloud_id, decided_at),
    ).fetchone()
    reposters = conn.execute(
        """
        SELECT dtr.discovery_artist_id,
               COALESCE(dtr.raw_reposted_at, dtr.reposted_at, dtr.seen_at) AS event_at,
               da.ranking
        FROM discovery_track_reposters dtr
        JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
        JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
        WHERE dt.soundcloud_id = ?
          AND COALESCE(dtr.raw_reposted_at, dtr.reposted_at, dtr.seen_at) <= ?
        ORDER BY da.ranking IS NULL, da.ranking, dtr.discovery_artist_id
        """,
        (soundcloud_id, decided_at),
    ).fetchall()
    return {
        "uploader_id": uploader["discovery_artist_id"] if uploader else None,
        "uploaded_at": uploader["uploaded_at"] if uploader else None,
        "reposters": [dict(value) for value in reposters],
    }


def _legacy_features_at_decision(
    conn: sqlite3.Connection,
    soundcloud_id: str,
    decided_at: str,
    actors: dict[str, Any],
    history: dict[tuple[int, str], list[float]],
) -> TrackFeatures:
    metadata = conn.execute(
        """
        SELECT title, duration_ms, genre, released_at, first_seen,
               metadata_updated_at
        FROM discovery_tracks WHERE soundcloud_id = ?
        """,
        (soundcloud_id,),
    ).fetchone()
    # Title/duration/release time were part of the original discovery ingest,
    # so first_seen proves they predate the decision. Enriched genre requires
    # the stricter metadata provenance timestamp.
    core_metadata_safe = bool(
        metadata and metadata["first_seen"] and metadata["first_seen"] <= decided_at
    )
    enriched_metadata_safe = bool(
        metadata
        and metadata["metadata_updated_at"]
        and metadata["metadata_updated_at"] <= decided_at
    )
    uploader_id = actors["uploader_id"]
    uploader_history = history.get((uploader_id, "upload")) if uploader_id else None
    reposters = actors["reposters"]
    reposter_histories = [
        history[(row["discovery_artist_id"], "repost")]
        for row in reposters
        if (row["discovery_artist_id"], "repost") in history
    ]
    uploader_rate = bayesian_keep_rate(*uploader_history) if uploader_history else None
    reposter_rates = [bayesian_keep_rate(*values) for values in reposter_histories]
    decided = _parse_datetime(decided_at)
    released = _parse_datetime(metadata["released_at"] if core_metadata_safe else None)
    reposted = _parse_datetime(reposters[-1]["event_at"] if reposters else None)
    if uploader_id and reposters:
        event_type = "both"
    elif uploader_id:
        event_type = "release"
    else:
        event_type = "repost"
    return TrackFeatures(
        duration_ms=metadata["duration_ms"] if core_metadata_safe else None,
        followed_uploader=bool(uploader_id),
        uploader_rank=None,
        reposter_count=len(reposters),
        # Current manual ranking is deliberately excluded from legacy examples.
        best_reposter_rank=None,
        uploader_keep_rate=uploader_rate,
        uploader_rated_count=uploader_history[1] if uploader_history else 0.0,
        reposter_keep_rate=max(reposter_rates) if reposter_rates else None,
        reposter_rated_count=sum(values[1] for values in reposter_histories),
        event_type=event_type,
        genre=metadata["genre"] if enriched_metadata_safe else None,
        title=metadata["title"] if core_metadata_safe else "",
        release_age_days=(decided - released).total_seconds() / 86_400
        if decided and released
        else None,
        repost_lag_days=(reposted - released).total_seconds() / 86_400
        if reposted and released
        else None,
        as_of=decided_at,
    )


def _update_role_history(
    history: dict[tuple[int, str], list[float]],
    actors: dict[str, Any],
    kept: bool,
) -> None:
    uploader_id = actors["uploader_id"]
    if uploader_id is not None:
        values = history.setdefault((uploader_id, "upload"), [0.0, 0.0])
        values[0] += float(kept)
        values[1] += 1.0
    reposter_ids = sorted({row["discovery_artist_id"] for row in actors["reposters"]})
    if not reposter_ids:
        return
    weight = 1.0 / len(reposter_ids)
    for reposter_id in reposter_ids:
        values = history.setdefault((reposter_id, "repost"), [0.0, 0.0])
        values[0] += float(kept) * weight
        values[1] += weight


def artifact_identity(artifact: ModelArtifact) -> str:
    return hashlib.sha256(artifact_to_json(artifact).encode()).hexdigest()


def store_model(
    conn: sqlite3.Connection,
    artifact: ModelArtifact,
    status: str = "candidate",
    ship_gate_passed: bool = False,
) -> str:
    if status not in {"candidate", "active", "retired", "rejected"}:
        raise ValueError(f"invalid model status: {status}")
    identity = artifact_identity(artifact)
    conn.execute(
        """
        INSERT INTO preference_models
            (version, feature_schema_version, status, trained_at,
             training_start, training_end, sample_count, positive_count,
             validation_metrics, coefficients, artifact_identity, ship_gate_passed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(version) DO UPDATE SET
            feature_schema_version = excluded.feature_schema_version,
            status = excluded.status,
            trained_at = excluded.trained_at,
            training_start = excluded.training_start,
            training_end = excluded.training_end,
            sample_count = excluded.sample_count,
            positive_count = excluded.positive_count,
            validation_metrics = excluded.validation_metrics,
            coefficients = excluded.coefficients,
            artifact_identity = excluded.artifact_identity,
            ship_gate_passed = excluded.ship_gate_passed
        """,
        (
            artifact.version,
            artifact.feature_schema_version,
            status,
            artifact.trained_at,
            artifact.training_start,
            artifact.training_end,
            artifact.sample_count,
            artifact.positive_count,
            json.dumps(artifact.validation_metrics, sort_keys=True),
            artifact_to_json(artifact),
            identity,
            int(ship_gate_passed),
        ),
    )
    return identity


def load_active_model(conn: sqlite3.Connection) -> ModelArtifact | None:
    row = conn.execute(
        "SELECT coefficients FROM preference_models WHERE status = 'active' ORDER BY promoted_at DESC LIMIT 1"
    ).fetchone()
    return artifact_from_json(row["coefficients"]) if row else None


def promote_model(
    conn: sqlite3.Connection, version: str, promoted_at: str | None = None
) -> None:
    exists = conn.execute(
        "SELECT ship_gate_passed FROM preference_models WHERE version = ?", (version,)
    ).fetchone()
    if exists is None:
        raise ValueError(f"unknown model version: {version}")
    if not exists["ship_gate_passed"]:
        raise ValueError(f"model {version} has not passed the offline ship gate")
    timestamp = promoted_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE preference_models SET status = 'retired' WHERE status = 'active'"
    )
    conn.execute(
        "UPDATE preference_models SET status = 'active', promoted_at = ? WHERE version = ?",
        (timestamp, version),
    )


def rollback_model(conn: sqlite3.Connection) -> str | None:
    previous = conn.execute(
        """
        SELECT version FROM preference_models
        WHERE status = 'retired'
        ORDER BY promoted_at DESC LIMIT 1
        """
    ).fetchone()
    conn.execute(
        "UPDATE preference_models SET status = 'retired' WHERE status = 'active'"
    )
    if previous is None:
        return None
    promote_model(conn, previous["version"])
    return str(previous["version"])


def score_feed_items(
    conn: sqlite3.Connection,
    items: Sequence[dict[str, Any]],
    artifact: ModelArtifact | None = None,
    scored_at: str | None = None,
) -> list[dict[str, Any]]:
    model = artifact or load_active_model(conn)
    if model is None:
        return [dict(item) for item in items]
    timestamp = scored_at or datetime.now(timezone.utc).isoformat()
    output: list[dict[str, Any]] = []
    records: list[tuple[str, str, float, str, str, str]] = []
    for item in items:
        features = features_from_feed_item(item, timestamp)
        probability = score_features(model, features)
        sc_id = str(item["soundcloud_id"])
        records.append(
            (
                sc_id,
                model.version,
                probability,
                timestamp,
                json.dumps(features.__dict__, sort_keys=True),
                explanation(features),
            )
        )
        output.append(
            {
                **item,
                "keep_probability": probability,
                "prediction_model_version": model.version,
                "prediction_explanation": explanation(features),
            }
        )
    conn.executemany(
        """
        INSERT INTO preference_scores
            (soundcloud_id, model_version, keep_probability, scored_at,
             feature_snapshot, explanation)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(soundcloud_id, model_version) DO UPDATE SET
            keep_probability = excluded.keep_probability,
            scored_at = excluded.scored_at,
            feature_snapshot = excluded.feature_snapshot,
            explanation = excluded.explanation
        """,
        records,
    )
    return output


def should_retrain(
    new_decisions: int,
    last_promotion_at: str | None,
    now: datetime | None = None,
    threshold: int = DEFAULT_RETRAIN_DECISIONS,
) -> bool:
    if new_decisions < threshold:
        return False
    current = now or datetime.now(timezone.utc)
    promoted = _parse_datetime(last_promotion_at)
    return promoted is None or promoted.date() < current.date()


def builder_all_followed_enabled(conn: sqlite3.Connection) -> bool:
    """True only for an explicitly enabled, ship-gated model rollout."""
    try:
        row = conn.execute(
            """
            SELECT prs.builder_mode, prs.allow_all_followed, pm.ship_gate_passed
            FROM preference_rollout_state prs
            JOIN preference_models pm ON pm.version = prs.active_model_version
            WHERE prs.id = 1 AND pm.status = 'active'
            """
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(
        row
        and row["builder_mode"] == "model"
        and row["allow_all_followed"]
        and row["ship_gate_passed"]
    )


def model_order_builder_candidates(
    conn: sqlite3.Connection,
    tracks: Sequence[dict[str, Any]],
    limit: int,
) -> tuple[str, list[dict[str, Any]]] | None:
    """Return shadow/model ordering when a ship-gated active model exists."""
    try:
        rollout = conn.execute(
            """
            SELECT builder_mode, exploration_share,
                   per_uploader_cap, per_reposter_cap
            FROM preference_rollout_state WHERE id = 1
            """
        ).fetchone()
        artifact = load_active_model(conn)
    except sqlite3.OperationalError:
        return None
    if (
        rollout is None
        or artifact is None
        or rollout["builder_mode"] == "chronological"
    ):
        return None
    candidates: list[ScoredCandidate] = []
    for track in tracks:
        released = _parse_datetime(track.get("released_at") or track.get("created_at"))
        now = datetime.now(timezone.utc)
        features = TrackFeatures(
            duration_ms=track.get("duration"),
            followed_uploader=bool(track.get("followed_uploader")),
            uploader_rank=track.get("uploader_rank"),
            reposter_count=int(track.get("reposter_count") or 1),
            best_reposter_rank=track.get("best_reposter_rank"),
            reposter_keep_rate=track.get("artist_repost_keep_rate"),
            reposter_rated_count=float(track.get("artist_repost_rated_count") or 0),
            event_type=str(track.get("event_type") or "repost"),
            genre=track.get("genre"),
            title=track.get("title") or "",
            release_age_days=(now - released).total_seconds() / 86_400
            if released
            else None,
            as_of=now.isoformat(),
        )
        candidates.append(
            ScoredCandidate(
                soundcloud_id=str(track["id"]),
                probability=score_features(artifact, features),
                uploader_id=track.get("uploader_artist_id"),
                reposter_ids=(int(track["artist_id"]),)
                if track.get("artist_id") is not None
                else (),
                payload={
                    **track,
                    "keep_probability": score_features(artifact, features),
                    "prediction_model_version": artifact.version,
                    "prediction_explanation": explanation(features),
                },
            )
        )
    if rollout["builder_mode"] == "model":
        selected = select_with_exploration(
            candidates,
            limit,
            exploration_share=float(rollout["exploration_share"]),
            per_uploader_cap=int(rollout["per_uploader_cap"]),
            per_reposter_cap=int(rollout["per_reposter_cap"]),
            seed=0,
        )
    else:
        selected = sorted(
            candidates, key=lambda row: (-row.probability, row.soundcloud_id)
        )[:limit]
    return artifact.version, [row.payload for row in selected]


def select_with_exploration(
    candidates: Sequence[ScoredCandidate],
    limit: int,
    exploration_share: float = DEFAULT_EXPLORATION_SHARE,
    per_uploader_cap: int = 5,
    per_reposter_cap: int = 8,
    seed: int = 0,
) -> list[ScoredCandidate]:
    """Blend exploitation and exploration while enforcing diversity caps."""
    if not 0 <= exploration_share <= 1:
        raise ValueError("exploration_share must be between zero and one")
    exploration_count = min(limit, round(limit * exploration_share))
    exploitation_count = limit - exploration_count
    ranked = sorted(candidates, key=lambda row: (-row.probability, row.soundcloud_id))
    median = (
        sorted((row.probability for row in candidates))[len(candidates) // 2]
        if candidates
        else 0
    )
    exploration_pool = [
        row
        for row in candidates
        if row.probability <= median or row.uploader_id is None or not row.reposter_ids
    ]
    randomizer = random.Random(seed)
    randomizer.shuffle(exploration_pool)

    selected: list[ScoredCandidate] = []
    selected_ids: set[str] = set()
    uploader_counts: dict[int, int] = {}
    reposter_counts: dict[int, int] = {}

    def add_from(pool: Sequence[ScoredCandidate], target: int) -> None:
        for candidate in pool:
            if len(selected) >= target or candidate.soundcloud_id in selected_ids:
                continue
            if (
                candidate.uploader_id is not None
                and uploader_counts.get(candidate.uploader_id, 0) >= per_uploader_cap
            ):
                continue
            if candidate.reposter_ids and all(
                reposter_counts.get(value, 0) >= per_reposter_cap
                for value in candidate.reposter_ids
            ):
                continue
            selected.append(candidate)
            selected_ids.add(candidate.soundcloud_id)
            if candidate.uploader_id is not None:
                uploader_counts[candidate.uploader_id] = (
                    uploader_counts.get(candidate.uploader_id, 0) + 1
                )
            for reposter_id in candidate.reposter_ids:
                reposter_counts[reposter_id] = reposter_counts.get(reposter_id, 0) + 1

    add_from(ranked, exploitation_count)
    add_from(exploration_pool, min(limit, len(selected) + exploration_count))
    add_from(ranked, limit)
    return selected


def shadow_ordering_metrics(
    builder_ids: Sequence[str],
    model_ids: Sequence[str],
    limit: int = 100,
) -> dict[str, float]:
    """Compare model and current-builder order without affecting selection."""
    builder = [str(value) for value in builder_ids[:limit]]
    model = [str(value) for value in model_ids[:limit]]
    if not builder and not model:
        return {"top_overlap": 1.0, "mean_rank_shift": 0.0}
    overlap = set(builder) & set(model)
    builder_rank = {value: index for index, value in enumerate(builder)}
    model_rank = {value: index for index, value in enumerate(model)}
    fallback = max(len(builder), len(model), limit)
    universe = set(builder) | set(model)
    shift = sum(
        abs(builder_rank.get(value, fallback) - model_rank.get(value, fallback))
        for value in universe
    ) / max(1, len(universe))
    return {
        "top_overlap": len(overlap)
        / max(1, min(limit, len(set(builder) | set(model)))),
        "mean_rank_shift": float(shift),
    }


def record_shadow_comparison(
    conn: sqlite3.Connection,
    model_version: str,
    builder_ids: Sequence[str],
    model_ids: Sequence[str],
    recorded_at: str | None = None,
) -> dict[str, float]:
    metrics = shadow_ordering_metrics(builder_ids, model_ids)
    conn.execute(
        """
        INSERT INTO preference_shadow_metrics
            (model_version, recorded_at, candidate_count, top_overlap, mean_rank_shift)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            model_version,
            recorded_at or datetime.now(timezone.utc).isoformat(),
            len(set(builder_ids) | set(model_ids)),
            metrics["top_overlap"],
            metrics["mean_rank_shift"],
        ),
    )
    return metrics


def train_candidate(
    conn: sqlite3.Connection,
    version: str,
    validation_metrics: dict[str, float] | None = None,
) -> ModelArtifact:
    examples = training_examples_from_decisions(conn)
    artifact = fit_model(examples, version, validation_metrics=validation_metrics)
    store_model(conn, artifact, status="candidate")
    return artifact


def maybe_retrain_and_promote(
    conn: sqlite3.Connection,
    now: datetime | None = None,
) -> str | None:
    """Train after the configured decision increment and promote at most daily.

    A failed offline gate still stores an inspectable candidate but never changes
    active behavior. The caller owns the surrounding transaction.
    """
    current = now or datetime.now(timezone.utc)
    state = conn.execute(
        """
        SELECT decisions_at_last_training, retrain_decision_threshold,
               last_promotion_at
        FROM preference_rollout_state WHERE id = 1
        """
    ).fetchone()
    if state is None:
        return None
    examples = training_examples_from_decisions(conn)
    new_decisions = len(examples) - int(state["decisions_at_last_training"] or 0)
    threshold = int(state["retrain_decision_threshold"] or DEFAULT_RETRAIN_DECISIONS)
    if new_decisions < threshold:
        return None
    version = f"keep-{current:%Y%m%d}-{len(examples)}"
    artifact, report = evaluate_model(examples, version)
    store_model(
        conn,
        artifact,
        status="candidate",
        ship_gate_passed=report["ship_gate_passed"],
    )
    conn.execute(
        """
        UPDATE preference_rollout_state
        SET decisions_at_last_training = ?, last_training_at = ?
        WHERE id = 1
        """,
        (len(examples), current.isoformat()),
    )
    if report["ship_gate_passed"] and should_retrain(
        new_decisions,
        state["last_promotion_at"],
        now=current,
        threshold=threshold,
    ):
        promote_model(conn, version, promoted_at=current.isoformat())
        conn.execute(
            """
            UPDATE preference_rollout_state
            SET active_model_version = ?, last_promotion_at = ?
            WHERE id = 1
            """,
            (version, current.isoformat()),
        )
        return version
    return None


def scoring_health(conn: sqlite3.Connection, model_version: str) -> dict[str, float]:
    """Observable coverage, outcomes, novelty, and score-distribution drift."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS scored,
               AVG(ps.keep_probability) AS mean_score,
               AVG(CASE WHEN d.decision = 'keep' THEN 1.0
                        WHEN d.decision = 'nope' THEN 0.0 END) AS keep_rate,
               AVG(CASE WHEN da.ranking IS NULL OR da.ranking > 200 THEN 1.0 ELSE 0.0 END)
                   AS outside_top_200_rate
        FROM preference_scores ps
        LEFT JOIN sc_track_decisions d
          ON d.soundcloud_id = ps.soundcloud_id AND d.is_current = 1
        LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = ps.soundcloud_id
        LEFT JOIN discovery_artists da ON da.id = u.discovery_artist_id
        WHERE ps.model_version = ?
        """,
        (model_version,),
    ).fetchone()
    previous = conn.execute(
        """
        SELECT AVG(keep_probability) AS mean_score
        FROM preference_scores WHERE model_version != ?
        GROUP BY model_version ORDER BY MAX(scored_at) DESC LIMIT 1
        """,
        (model_version,),
    ).fetchone()
    mean_score = float(row["mean_score"] or 0)
    prior_mean = float(previous["mean_score"] or mean_score) if previous else mean_score
    total_candidates = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT soundcloud_id FROM sc_artist_uploads
            UNION
            SELECT dt.soundcloud_id
            FROM discovery_tracks dt
            JOIN discovery_track_reposters dtr ON dtr.discovery_track_id = dt.id
        )
        """
    ).fetchone()[0]
    outcomes = conn.execute(
        """
        SELECT CASE d.decision WHEN 'keep' THEN 1 ELSE 0 END AS label,
               ps.keep_probability
        FROM preference_scores ps
        JOIN sc_track_decisions d
          ON d.soundcloud_id = ps.soundcloud_id
         AND d.is_current = 1 AND d.decision IN ('keep', 'nope')
        WHERE ps.model_version = ?
        """,
        (model_version,),
    ).fetchall()
    result = {
        "scored_count": float(row["scored"] or 0),
        "coverage": float(row["scored"] or 0) / max(1, total_candidates),
        "mean_score": mean_score,
        "keep_rate": float(row["keep_rate"] or 0),
        "outside_top_200_rate": float(row["outside_top_200_rate"] or 0),
        "mean_score_drift": mean_score - prior_mean,
    }
    if outcomes:
        labels = [value["label"] for value in outcomes]
        probabilities = [value["keep_probability"] for value in outcomes]
        result.update(
            {
                key: value
                for key, value in evaluate_probabilities(labels, probabilities).items()
                if key in {"brier_score", "log_loss"}
            }
        )
        bins = calibration_bins(labels, probabilities)
        result["calibration_error"] = sum(
            abs(value["mean_prediction"] - value["keep_rate"]) * value["count"]
            for value in bins
        ) / len(outcomes)
    return result


def rescore_unresolved_feed(model_version: str | None = None) -> int:
    """Rescore current feed candidates after model promotion."""
    from web.backend.queries.feed import get_feed_page

    with get_db_connection() as conn:
        model = load_active_model(conn)
        if model is None or (model_version and model.version != model_version):
            return 0
        items = get_feed_page(limit=100)
        score_feed_items(conn, items, model)
        conn.commit()
        return len(items)
