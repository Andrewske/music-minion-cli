"""Sync-time Jev keep-probability scoring for SoundCloud feed tracks.

Pure state-building plus one orchestration function. Every prediction is
appended to `sc_track_predictions` with the exact state string sent, so the
offline evaluation can replay precisely what the model saw.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection

from web.backend import jev_client

TASTE_PROFILE_PATH = Path(__file__).parent / "data" / "taste-profile.md"
MAX_REPOSTERS_IN_STATE = 5

NOUL_QUESTION = (
    "Given Kevin's taste profile and this track's stats, will Kevin choose "
    "'keep' (add to his library) when this track appears in his SoundCloud "
    "feed? Keep means he likes it enough to save; nope or hide means he passes."
)


def load_taste_profile() -> tuple[str, str] | None:
    """(text, version) of the editable taste profile; None when missing."""
    if not TASTE_PROFILE_PATH.exists():
        return None
    text = TASTE_PROFILE_PATH.read_text(encoding="utf-8")
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return text, version


def build_state(track: dict[str, Any], taste_profile: str) -> str:
    """Filtered JSON state for one Jev call; `track` uses the canonical keys
    produced by `_track_state_dict` (the eval cache builder emits the same)."""
    return json.dumps(
        {
            "taste_profile": taste_profile,
            "track": track["track"],
            "history": track["history"],
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _age_days(timestamp: str | None, now: datetime) -> float | None:
    if not timestamp:
        return None
    try:
        cleaned = timestamp.replace("/", "-").replace(" +0000", "+00:00")
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return round((now - parsed).total_seconds() / 86_400, 1)
    except ValueError:
        return None


def _overall_history(conn: Any) -> dict[str, Any]:
    row = conn.execute(
        """SELECT SUM(decision = 'keep') AS keeps, COUNT(*) AS total
        FROM sc_track_decisions WHERE is_current = 1
          AND decision IN ('keep', 'nope')"""
    ).fetchone()
    total = row["total"] or 0
    rate = round((row["keeps"] or 0) / total, 3) if total else None
    return {"overall_keep_rate": rate, "decisions_total": total}


def _reposters_for(conn: Any, soundcloud_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT da.display_name, da.ranking, da.repost_keep_rate,
                  da.repost_rated_count
        FROM discovery_tracks dt
        JOIN discovery_track_reposters dtr ON dtr.discovery_track_id = dt.id
        JOIN discovery_artists da
          ON da.id = dtr.discovery_artist_id AND da.is_following = 1
        WHERE dt.soundcloud_id = ?
        ORDER BY da.ranking IS NULL, da.ranking, da.id""",
        (soundcloud_id,),
    ).fetchall()
    return [
        {
            "name": row["display_name"],
            "rank": row["ranking"],
            "keep_rate": row["repost_keep_rate"],
            "rated_count": row["repost_rated_count"],
        }
        for row in rows
    ]


def _track_state_dict(conn: Any, row: Any, now: datetime) -> dict[str, Any]:
    reposters = _reposters_for(conn, row["soundcloud_id"])
    top200 = sum(1 for r in reposters if r["rank"] is not None and r["rank"] <= 200)
    return {
        "track": {
            "title": row["title"],
            "genre": row["genre"],
            "duration_min": round((row["duration_ms"] or 0) / 60_000, 2) or None,
            "event_type": "release" if row["is_release"] else "repost",
            "release_age_days": _age_days(row["released_at"], now),
            "uploader": {
                "name": row["uploader_name"],
                "followed": bool(row["uploader_followed"]),
                "rank": row["uploader_rank"],
                "keep_rate": row["upload_keep_rate"],
                "rated_count": row["upload_rated_count"],
            },
            "reposters": reposters[:MAX_REPOSTERS_IN_STATE],
            "reposter_count": len(reposters),
            "top200_reposter_count": top200,
        },
        "history": _overall_history(conn),
    }


_CANDIDATES_SQL = """
WITH feed_tracks AS (
    SELECT u.soundcloud_id, u.title, u.genre, u.duration_ms,
           COALESCE(u.released_at, u.uploaded_at) AS released_at,
           1 AS is_release,
           da.display_name AS uploader_name, da.is_following AS uploader_followed,
           da.ranking AS uploader_rank, da.upload_keep_rate, da.upload_rated_count,
           u.uploaded_at AS seen_order
    FROM sc_artist_uploads u
    JOIN discovery_artists da ON da.id = u.discovery_artist_id
    WHERE da.is_following = 1 AND (u.access IS NULL OR u.access = 'playable')
    UNION ALL
    SELECT dt.soundcloud_id, dt.title, dt.genre, dt.duration_ms,
           COALESCE(dt.released_at, dt.uploaded_at) AS released_at,
           0 AS is_release,
           COALESCE(uda.display_name, dt.artist_name),
           COALESCE(uda.is_following, 0),
           uda.ranking, uda.upload_keep_rate, uda.upload_rated_count,
           dt.first_seen
    FROM discovery_tracks dt
    LEFT JOIN discovery_artists uda
      ON uda.soundcloud_user_id = dt.uploader_soundcloud_id
    WHERE (dt.access IS NULL OR dt.access = 'playable')
      AND EXISTS (
          SELECT 1 FROM discovery_track_reposters dtr
          JOIN discovery_artists da
            ON da.id = dtr.discovery_artist_id AND da.is_following = 1
          WHERE dtr.discovery_track_id = dt.id
      )
)
SELECT * FROM feed_tracks f
WHERE NOT EXISTS (
      SELECT 1 FROM sc_track_decisions d
      WHERE d.soundcloud_id = f.soundcloud_id AND d.is_current = 1
  )
  AND NOT EXISTS (
      SELECT 1 FROM sc_track_predictions sp
      WHERE sp.soundcloud_id = f.soundcloud_id
        AND sp.model_id = :model_id
        AND sp.taste_profile_version = :profile_version
  )
GROUP BY f.soundcloud_id
ORDER BY f.seen_order DESC
LIMIT :limit
"""


def _insert_prediction(
    conn: Any,
    soundcloud_id: str,
    model_id: str,
    profile_version: str,
    prediction: jev_client.JevPrediction,
    state: str,
) -> None:
    conn.execute(
        """INSERT INTO sc_track_predictions
            (soundcloud_id, model_id, taste_profile_version,
             probability, confidence, state_sent)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            soundcloud_id,
            model_id,
            profile_version,
            prediction.probability,
            prediction.confidence,
            state,
        ),
    )


def score_new_tracks(limit: int = 200, sleep_s: float = 0.1) -> int:
    """Score undecided, not-yet-scored feed tracks; returns tracks scored."""
    config = jev_client.get_jev_config()
    if config is None:
        logger.info("jev: no JEV_API_KEY configured, skipping feed scoring")
        return 0
    profile = load_taste_profile()
    if profile is None:
        logger.warning(f"jev: taste profile missing at {TASTE_PROFILE_PATH}, skipping")
        return 0
    profile_text, profile_version = profile
    now = datetime.now(timezone.utc)
    scored = failed = 0
    with get_db_connection() as conn:
        rows = conn.execute(
            _CANDIDATES_SQL,
            {
                "model_id": config.model_id,
                "profile_version": profile_version,
                "limit": limit,
            },
        ).fetchall()
        for row in rows:
            state = build_state(_track_state_dict(conn, row, now), profile_text)
            try:
                prediction = jev_client.ask_noul(config, state, NOUL_QUESTION)
            except Exception:
                failed += 1
                logger.exception(f"jev: scoring failed for {row['soundcloud_id']}")
                if failed >= 5 and scored == 0:
                    break  # endpoint is down; don't burn the whole batch
                continue
            _insert_prediction(
                conn,
                row["soundcloud_id"],
                config.model_id,
                profile_version,
                prediction,
                state,
            )
            scored += 1
            # Periodic commits keep a crashed batch's work and let the feed
            # show scores while a long backfill is still running.
            if scored % 25 == 0:
                conn.commit()
            time.sleep(sleep_s)
        conn.commit()
    if scored or failed:
        logger.info(f"jev: scored {scored} tracks ({failed} failures)")
    return scored
