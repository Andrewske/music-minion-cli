"""Jev mix / set / podcast classifier for ambiguous feed tracks (#31).

Rules catch the obvious cases (over 15 minutes, "live at", "podcast"). This
asks Jev about the ones in between: unreviewed, never-flagged tracks of 8 to
20 minutes that no enabled rule catches. Up to ten tracks share one call,
each track getting its own Noul question.

Confidence policy (the probability that the track is a mix, set or show):
- >= 0.85 writes a ``source='agent'`` flag carrying that confidence;
- 0.5 to 0.85 becomes a suggestion Kevin can confirm or dismiss in Settings;
- below 0.5 only the classification record is kept, so it is not asked again.

Runs on demand only (a Settings button); there is no background schedule.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx
from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend import jev_client
from web.backend.feed_filter_rules import first_matching_rule
from web.backend.queries import feed_agent
from web.backend.queries import feed_filters as filter_queries

AUTO_FLAG_CONFIDENCE = 0.85
SUGGEST_CONFIDENCE = 0.5
PODCAST_REASON_THRESHOLD = 0.5
BATCH_SIZE = 10
AMBIGUOUS_MIN_MINUTES = 8.0
AMBIGUOUS_MAX_MINUTES = 20.0
MAX_EXAMPLES_PER_CLASS = 6
DEFAULT_MAX_TRACKS = 50
MAX_FAILED_BATCHES = 3

TASK = (
    "Kevin's SoundCloud feed should only show single tracks (songs, remixes, "
    "edits, VIPs, bootlegs). Decide for each track in `tracks` whether it is "
    "instead a DJ mix, live set, radio show or podcast episode. `examples` "
    "are tracks Kevin already labeled."
)


def is_ambiguous(track: dict[str, Any], rules: list[dict[str, Any]]) -> bool:
    """8 to 20 minutes long and caught by no enabled rule."""
    minutes = (track.get("duration_ms") or 0) / 60_000
    in_range = AMBIGUOUS_MIN_MINUTES <= minutes <= AMBIGUOUS_MAX_MINUTES
    return in_range and first_matching_rule(track, rules) is None


def classification_status(mix_probability: float) -> str:
    if mix_probability >= AUTO_FLAG_CONFIDENCE:
        return "auto_flagged"
    if mix_probability >= SUGGEST_CONFIDENCE:
        return "pending"
    return "below_threshold"


def flag_reason(podcast_probability: float | None) -> str:
    is_podcast = (podcast_probability or 0.0) > PODCAST_REASON_THRESHOLD
    return "podcast" if is_podcast else "live_mix"


def classifier_track(track: dict[str, Any]) -> dict[str, Any]:
    """The fields Jev sees: title, uploader, genre, tags and duration."""
    return {
        "title": track.get("title"),
        "uploader": track.get("uploader"),
        "genre": track.get("genre"),
        "tags": list(track.get("tags") or []),
        "duration_min": round((track.get("duration_ms") or 0) / 60_000, 1) or None,
    }


def build_state(
    batch: list[dict[str, Any]],
    mixes: list[dict[str, Any]],
    not_mixes: list[dict[str, Any]],
) -> str:
    examples = [
        {**classifier_track(track), "is_mix_or_show": is_mix}
        for is_mix, tracks in ((True, mixes), (False, not_mixes))
        for track in tracks[:MAX_EXAMPLES_PER_CLASS]
    ]
    payload = {
        "task": TASK,
        "examples": examples,
        "tracks": {f"t{i}": classifier_track(track) for i, track in enumerate(batch)},
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def build_questions(batch_size: int) -> dict[str, str]:
    """Two Noul questions per track: mix-or-show, and podcast-or-radio-show."""
    questions: dict[str, str] = {}
    for i in range(batch_size):
        questions[f"mix_t{i}"] = (
            f"Is track t{i} a DJ mix, live set, radio show or podcast episode "
            "rather than a single track?"
        )
        questions[f"podcast_t{i}"] = (
            f"Is track t{i} specifically a podcast or radio show episode?"
        )
    return questions


def batch_results(
    batch: list[dict[str, Any]], nouls: dict[str, float]
) -> list[dict[str, Any]]:
    """Classification rows for the tracks Jev answered."""
    results = []
    for i, track in enumerate(batch):
        mix = nouls.get(f"mix_t{i}")
        if mix is None:
            continue
        podcast = nouls.get(f"podcast_t{i}")
        results.append(
            {
                "soundcloud_id": track["soundcloud_id"],
                "mix_probability": mix,
                "podcast_probability": podcast,
                "status": classification_status(mix),
                "reason": flag_reason(podcast),
            }
        )
    return results


def chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _summary() -> dict[str, int]:
    return {
        "candidates": 0,
        "classified": 0,
        "auto_flagged": 0,
        "pending": 0,
        "failed_batches": 0,
    }


def _classify_batch(
    conn: Any,
    config: jev_client.JevConfig,
    batch: list[dict[str, Any]],
    examples: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    state = build_state(batch, *examples)
    nouls = jev_client.ask_nouls(config, state, build_questions(len(batch)))
    results = batch_results(batch, nouls)
    for result in results:
        feed_agent.save_classification(conn, result, config.model_id, state)
    conn.commit()
    return results


def _tally(summary: dict[str, int], results: list[dict[str, Any]]) -> None:
    summary["classified"] += len(results)
    for result in results:
        if result["status"] in ("auto_flagged", "pending"):
            summary[result["status"]] += 1


def _ambiguous_tracks(conn: Any, max_tracks: int) -> list[dict[str, Any]]:
    rules = filter_queries.enabled_rules(conn)
    pool = feed_agent.ambiguous_pool(conn)
    return [track for track in pool if is_ambiguous(track, rules)][:max_tracks]


def _run_batches(
    conn: Any,
    config: jev_client.JevConfig,
    tracks: list[dict[str, Any]],
    summary: dict[str, int],
) -> None:
    examples = (feed_agent.load_user_flags(), feed_agent.load_not_mix_examples())
    consecutive_failures = 0
    for batch in chunks(tracks, BATCH_SIZE):
        try:
            _tally(summary, _classify_batch(conn, config, batch, examples))
            consecutive_failures = 0
        except (httpx.HTTPError, ValueError):
            consecutive_failures += 1
            summary["failed_batches"] += 1
            logger.exception(f"feed agent: Jev batch of {len(batch)} failed")
            if consecutive_failures >= MAX_FAILED_BATCHES:
                break


def classify_ambiguous_tracks(max_tracks: int = DEFAULT_MAX_TRACKS) -> dict[str, int]:
    """Ask Jev about up to `max_tracks` ambiguous tracks; returns a summary.

    Raises RuntimeError when Jev isn't configured. A failed batch is logged
    and skipped; three failures in a row stop the run.
    """
    config = jev_client.get_jev_config()
    if config is None:
        raise RuntimeError("Jev is not configured (JEV_API_KEY / OPENROUTER_API_KEY)")
    summary = _summary()
    with get_db_connection() as conn:
        tracks = _ambiguous_tracks(conn, max_tracks)
        summary["candidates"] = len(tracks)
        _run_batches(conn, config, tracks, summary)
    logger.info(f"feed agent: classification run {summary}")
    return summary
