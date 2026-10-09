"""Shared steps used by the CLI and the unattended `ingest` job."""

from pathlib import Path

from loguru import logger

from music_minion.domain.metadata_cleanup import batching, records
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings, run_batches
from music_minion.domain.metadata_cleanup.normalize import normalize_proposal
from music_minion.domain.metadata_cleanup.soundcloud_fetch import fetch_all

RECORDS_DIR = records.WORK_DIR / "records"
RUNS_DIR = records.WORK_DIR / "runs"
SC_CACHE = records.WORK_DIR / "soundcloud-cache.json"

Scanned = list[tuple[Path, dict[str, str]]]


def scan(folder: Path) -> Scanned:
    return [(path, records.read_tags(path)) for path in records.list_mp3s(folder)]


def resolve(scanned: Scanned) -> dict[str, dict | None]:
    urls = sorted({tags["source_url"] for _, tags in scanned if "source_url" in tags})
    logger.info(f"Resolving {len(urls)} SoundCloud permalinks (cached where possible)")
    return fetch_all(urls, SC_CACHE)


def raw_records(scanned: Scanned) -> list[dict]:
    """Model input records for files whose tags are still as downloaded."""
    sc = resolve(scanned)
    return [
        records.build_record(path, tags, sc.get(tags.get("source_url", "")), raw=True)
        for path, tags in scanned
    ]


def sort_key(record: dict) -> str:
    sc = record.get("soundcloud") or {}
    return (sc.get("uploader") or record["filename"]).casefold()


def clean_rows(
    rows: list[dict], settings: CodexSettings, batch_size: int = 10, workers: int = 3
) -> tuple[list[dict], list[dict]]:
    """Batch + run codex + normalize. Returns (proposals, raw batch results)."""
    batches = batching.make_batches(sorted(rows, key=sort_key), batch_size)
    logger.info(f"{len(rows)} tracks in {len(batches)} batches ({settings.model})")
    results = run_batches(batches, settings, workers)
    uploaders = {r["id"]: (r.get("soundcloud") or {}).get("uploader") for r in rows}
    proposals = [
        normalize_proposal(track, uploaders.get(track["id"]))
        for result in results
        for track in result["tracks"]
        if track["id"] in uploaders  # drop ids the model mangled
    ]
    return proposals, results
