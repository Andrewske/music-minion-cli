#!/usr/bin/env python3
"""Backfill sc_likes.uploader_* for likes recorded before uploader capture.

Phase 1 copies uploader ids MM already has (discovery_tracks /
sc_artist_uploads, plus slug/name for known discovery_artists). Phase 2 asks
SoundCloud for the rest via GET /tracks?ids=, 50 ids per call, with backoff.
Only NULL uploader columns are written. Dry run by default.

Run on the pi (the DB owner):
  scripts/on-pi.sh scripts/backfill_like_uploaders.py            # dry run
  scripts/on-pi.sh scripts/backfill_like_uploaders.py --apply    # write
  scripts/on-pi.sh scripts/backfill_like_uploaders.py --apply --skip-api
"""

import argparse
import time

from loguru import logger

from music_minion.domain.library.providers.soundcloud.api import get_tracks_by_ids
from music_minion.domain.library.providers.soundcloud.like_uploaders import (
    LikeUploader,
    fill_like_uploaders,
    like_count,
    local_uploaders,
    missing_uploader_ids,
    uploaders_by_track,
)

BATCH_SIZE = 50
PAUSE_SECONDS = 0.5
RETRY_WAITS = (30, 60, 120)  # after a rate-limited batch


def phase1(apply: bool) -> int:
    found = local_uploaders()
    logger.info(f"phase 1: {len(found)} likes have an uploader id in local tables")
    if not apply:
        return len(found)
    filled = fill_like_uploaders(found)
    logger.info(f"phase 1: filled {filled} likes")
    return filled


def _fetch_batch(state, batch: list[str]):
    """One /tracks?ids= call, retried with growing waits when rate limited."""
    for wait in (*RETRY_WAITS, None):
        state, tracks, error = get_tracks_by_ids(state, batch)
        if error != "Rate limited" or wait is None:
            return state, tracks, error
        logger.warning(f"rate limited; waiting {wait}s")
        time.sleep(wait)
    return state, [], "Rate limited"


def phase2(state, ids: list[str], apply: bool) -> int:
    found: dict[str, LikeUploader] = {}
    batches = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    logger.info(f"phase 2: {len(ids)} likes left, {len(batches)} API calls")
    for n, batch in enumerate(batches, 1):
        state, tracks, error = _fetch_batch(state, batch)
        if error:
            logger.error(f"phase 2: batch {n} failed ({error}); stopping")
            break
        batch_found = uploaders_by_track(tracks)
        found.update(batch_found)
        if apply:
            fill_like_uploaders(batch_found)
        logger.info(f"phase 2: batch {n}/{len(batches)} -> {len(batch_found)} found")
        time.sleep(PAUSE_SECONDS)
    logger.info(
        f"phase 2: {len(found)} uploaders found ({len(ids) - len(found)} gone/private)"
    )
    return len(found)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="write to the DB")
    parser.add_argument("--skip-api", action="store_true", help="phase 1 only")
    args = parser.parse_args()

    total, missing = like_count(), len(missing_uploader_ids())
    logger.info(f"{total} likes, {missing} without an uploader")
    phase1(args.apply)
    if not args.skip_api:
        from web.backend.soundcloud_auth import get_web_provider_state

        state = get_web_provider_state()
        if state is None:
            logger.error("SoundCloud not authenticated; skipping phase 2")
        else:
            # A dry run can't know phase 1's writes, so it asks only about
            # likes that phase 1 would not fill.
            local = set(local_uploaders()) if not args.apply else set()
            phase2(
                state, [i for i in missing_uploader_ids() if i not in local], args.apply
            )
    logger.info(f"done: {len(missing_uploader_ids())} likes still without an uploader")


if __name__ == "__main__":
    main()
