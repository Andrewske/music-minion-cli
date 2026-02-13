"""Sync router for triggering library synchronization via API."""

import logging
from typing import Any
from fastapi import APIRouter, BackgroundTasks

from music_minion.core import config
from music_minion.domain import sync

router = APIRouter()
logger = logging.getLogger(__name__)

# Track sync state to prevent concurrent syncs
_sync_in_progress = False


@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Trigger an incremental local sync.

    Detects changed files, imports metadata, and cleans up orphaned tracks.
    Runs in background to avoid blocking the response.
    """
    global _sync_in_progress

    if _sync_in_progress:
        return {"status": "skipped", "message": "Sync already in progress"}

    background_tasks.add_task(_run_sync)
    return {"status": "started", "message": "Sync started in background"}


@router.post("/sync/full")
async def trigger_full_sync(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Trigger a full local sync.

    Scans filesystem for new files, imports all metadata, exports DB to files,
    and cleans up orphaned tracks.
    """
    global _sync_in_progress

    if _sync_in_progress:
        return {"status": "skipped", "message": "Sync already in progress"}

    background_tasks.add_task(_run_full_sync)
    return {"status": "started", "message": "Full sync started in background"}


@router.get("/sync/status")
async def get_sync_status() -> dict[str, Any]:
    """Get current sync status."""
    cfg = config.load_config()
    status = sync.get_sync_status(cfg)
    status["in_progress"] = _sync_in_progress
    return status


def _run_sync() -> None:
    """Run incremental sync (background task)."""
    global _sync_in_progress
    _sync_in_progress = True

    try:
        cfg = config.load_config()

        # Phase 1: Scan for new files (quick scan, not full metadata extraction)
        from music_minion.core import database
        from music_minion.domain.library import scanner

        logger.info("Scanning for new files...")
        tracks = scanner.scan_music_library_optimized(cfg, show_progress=False)

        if tracks:
            logger.info(f"Found {len(tracks)} files, checking for new ones")
            added, updated = database.batch_upsert_tracks(tracks)
            if added > 0:
                logger.info(f"Added {added} new tracks")

        # Phase 2: Detect and import from changed files
        changed_tracks = sync.detect_file_changes(cfg)
        if changed_tracks:
            logger.info(f"Syncing {len(changed_tracks)} changed files")
            result = sync.sync_import(cfg, force_all=False, show_progress=False)
            logger.info(f"Imported {result.get('added', 0)} tags from files")
        else:
            logger.info("No changed files to sync")

        # Cleanup orphaned tracks
        cleanup = sync.detect_missing_and_moved_files(cfg)
        if cleanup["relocated"] > 0:
            logger.info(f"Relocated {cleanup['relocated']} moved files")
        if cleanup["deleted"] > 0:
            logger.info(f"Removed {cleanup['deleted']} orphaned tracks")

    except Exception:
        logger.exception("Sync failed")
    finally:
        _sync_in_progress = False


def _run_full_sync() -> None:
    """Run full sync (background task)."""
    global _sync_in_progress
    _sync_in_progress = True

    try:
        cfg = config.load_config()

        # Phase 1: Scan filesystem for new files
        from music_minion.core import database
        from music_minion.domain.library import scanner

        logger.info("Scanning filesystem for new files...")
        tracks = scanner.scan_music_library_optimized(cfg, show_progress=False)

        if tracks:
            logger.info(f"Processing {len(tracks)} tracks from filesystem")
            added, updated = database.batch_upsert_tracks(tracks)
            logger.info(f"Added {added} new tracks, updated {updated} existing")
        else:
            logger.info("No new files found")

        # Phase 2: Import metadata from files
        logger.info("Importing metadata from files")
        result = sync.sync_import(cfg, force_all=True, show_progress=False)
        logger.info(f"Imported {result.get('added', 0)} tags")

        # Export DB metadata to files
        logger.info("Exporting metadata to files")
        export_result = sync.sync_metadata_export(show_progress=False)
        logger.info(f"Exported to {export_result.get('success', 0)} files")

        # Export ELO ratings
        logger.info("Exporting ELO ratings")
        elo_result = sync.sync_elo_export(show_progress=False)
        logger.info(f"Exported ELO to {elo_result.get('success', 0)} files")

        # Cleanup
        cleanup = sync.detect_missing_and_moved_files(cfg)
        if cleanup["relocated"] > 0:
            logger.info(f"Relocated {cleanup['relocated']} moved files")
        if cleanup["deleted"] > 0:
            logger.info(f"Removed {cleanup['deleted']} orphaned tracks")

    except Exception:
        logger.exception("Full sync failed")
    finally:
        _sync_in_progress = False
