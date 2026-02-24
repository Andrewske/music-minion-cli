#!/usr/bin/env python3
"""Analyze BPM and key for audio files missing metadata using Essentia."""

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger
from mutagen import File as MutagenFile
from tqdm import tqdm

import essentia.standard as es

from music_minion.domain.library.metadata import write_metadata_to_file

SUPPORTED_FORMATS = {'.mp3', '.m4a', '.opus', '.ogg', '.flac'}  # No .wav - no tag support
MUSIC_DIR = Path.home() / "Music" / "EDM"
KEY_CONFIDENCE_THRESHOLD = 0.5
LOW_CONFIDENCE_FILE = Path("low_confidence_keys.txt")

# Camelot wheel mapping (musical key → Camelot code)
CAMELOT_MAP = {
    "C": "8B", "Am": "8A",
    "G": "9B", "Em": "9A",
    "D": "10B", "Bm": "10A",
    "A": "11B", "F#m": "11A",
    "E": "12B", "C#m": "12A",
    "B": "1B", "G#m": "1A",
    "F#": "2B", "D#m": "2A",
    "Db": "3B", "Bbm": "3A",
    "Ab": "4B", "Fm": "4A",
    "Eb": "5B", "Cm": "5A",
    "Bb": "6B", "Gm": "6A",
    "F": "7B", "Dm": "7A",
}


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Analyze BPM/key for audio files")
    parser.add_argument("--dry-run", action="store_true", help="Show stats and what would be written, don't analyze")
    parser.add_argument("--limit", type=int, help="Process only first N files")
    parser.add_argument("--force", action="store_true", help="Re-analyze even if BPM/key already exist")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for analysis")
    return parser.parse_args()


def scan_file(file_path: Path) -> dict:
    """Fast metadata check - read only BPM/key tags.

    Args:
        file_path: Path to audio file

    Returns:
        Dict with path, has_bpm, has_key, bpm, key
    """
    try:
        # Check for .wav files
        if file_path.suffix.lower() == '.wav':
            logger.warning(f"Skipping WAV file (no tag support): {file_path}")
            return None

        audio = MutagenFile(file_path)
        if audio is None:
            return None

        # Try to get BPM
        has_bpm = False
        bpm = None
        for tag in ["TBPM", "BPM", "BEATS_PER_MINUTE", "\xa9bpm", "bpm"]:
            try:
                value = audio.get(tag)
                if value:
                    if isinstance(value, list) and value:
                        bpm = str(value[0])
                    else:
                        bpm = str(value)
                    has_bpm = True
                    break
            except (KeyError, ValueError):
                continue

        # Try to get key
        has_key = False
        key = None
        for tag in ["TKEY", "KEY", "INITIALKEY", "initialkey", "\xa9key", "key"]:
            try:
                value = audio.get(tag)
                if value:
                    if isinstance(value, list) and value:
                        key = str(value[0])
                    else:
                        key = str(value)
                    has_key = True
                    break
            except (KeyError, ValueError):
                continue

        return {
            "path": file_path,
            "has_bpm": has_bpm,
            "has_key": has_key,
            "bpm": bpm,
            "key": key,
        }

    except Exception as e:
        logger.debug(f"Error scanning {file_path}: {e}")
        return None


def scan_library(music_dir: Path, workers: int = 8) -> list[dict]:
    """Parallel scan of library using os.scandir and ThreadPoolExecutor.

    Args:
        music_dir: Directory to scan
        workers: Number of parallel threads

    Returns:
        List of scan result dicts
    """
    files_to_scan = []

    # Use os.scandir recursively (faster than Path.rglob)
    def walk_dir(path: Path):
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file():
                        if Path(entry.path).suffix.lower() in SUPPORTED_FORMATS:
                            files_to_scan.append(Path(entry.path))
                    elif entry.is_dir():
                        walk_dir(Path(entry.path))
        except PermissionError:
            logger.warning(f"Permission denied: {path}")

    walk_dir(music_dir)

    # Parallel scan with ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scan_file, f): f for f in files_to_scan}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Scanning library", unit="file"):
            result = future.result()
            if result is not None:
                results.append(result)

    return results


def analyze_audio(file_path: Path) -> tuple[float | None, str | None, float]:
    """Run Essentia analysis on audio file.

    Args:
        file_path: Path to audio file

    Returns:
        Tuple of (bpm, camelot_key, key_confidence)
    """
    try:
        # Load audio
        audio = es.MonoLoader(filename=str(file_path), sampleRate=44100)()

        # Extract BPM
        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, beats, confidence, *_ = rhythm_extractor(audio)

        # Double-time correction: if BPM < 100 and 2×BPM is in 120-160 range, double it
        if bpm < 100 and 120 <= 2 * bpm <= 160:
            bpm = bpm * 2

        bpm = round(bpm, 1)

        # Extract key
        key_extractor = es.KeyExtractor()
        key, scale, strength = key_extractor(audio)

        # Convert to Camelot notation
        musical_key = f"{key}{scale}"
        camelot_key = CAMELOT_MAP.get(musical_key)

        # If not in map, try just the key or scale
        if camelot_key is None:
            if scale == "minor":
                musical_key = f"{key}m"
            else:
                musical_key = key
            camelot_key = CAMELOT_MAP.get(musical_key)

        # TODO: Add genre detection with Essentia classifiers

        return (bpm, camelot_key, strength)

    except Exception as e:
        logger.exception(f"Error analyzing {file_path}: {e}")
        return (None, None, 0)


def process_file(file_info: dict, dry_run: bool = False, force: bool = False) -> dict:
    """Process a single file: analyze and write metadata.

    Args:
        file_info: Dict with file scan results
        dry_run: If True, don't write tags
        force: If True, re-analyze even if tags exist

    Returns:
        Dict with processing result
    """
    file_path = file_info["path"]

    # Skip if both tags exist and not forcing
    if not force and file_info["has_bpm"] and file_info["has_key"]:
        return {
            "path": file_path,
            "status": "skipped",
            "reason": "already_complete",
        }

    # Analyze
    bpm, camelot_key, key_confidence = analyze_audio(file_path)

    result = {
        "path": file_path,
        "bpm": bpm,
        "key": camelot_key,
        "key_confidence": key_confidence,
        "status": "analyzed",
        "validation_ok": None,
    }

    # Don't write low confidence keys
    write_key = camelot_key if key_confidence >= KEY_CONFIDENCE_THRESHOLD else None
    if camelot_key and key_confidence < KEY_CONFIDENCE_THRESHOLD:
        result["low_confidence"] = True

    # Write to file if not dry run
    if not dry_run:
        # Determine what to write
        write_bpm = bpm if not file_info["has_bpm"] or force else None
        if not write_key and file_info["has_key"] and not force:
            write_key = None  # Don't overwrite existing key with nothing

        # Write metadata
        if write_bpm or write_key:
            success = write_metadata_to_file(
                str(file_path),
                bpm=write_bpm,
                key=write_key,
            )

            if success:
                # Validate write by re-reading
                try:
                    audio = MutagenFile(file_path)

                    # Check BPM if written
                    if write_bpm:
                        bpm_tags = ["TBPM", "BPM", "BEATS_PER_MINUTE", "\xa9bpm", "bpm"]
                        found_bpm = False
                        for tag in bpm_tags:
                            value = audio.get(tag)
                            if value:
                                found_bpm = True
                                break
                        result["validation_ok"] = found_bpm

                    # Check key if written
                    if write_key:
                        key_tags = ["TKEY", "KEY", "INITIALKEY", "initialkey", "\xa9key", "key"]
                        found_key = False
                        for tag in key_tags:
                            value = audio.get(tag)
                            if value:
                                found_key = True
                                break
                        result["validation_ok"] = result.get("validation_ok", True) and found_key

                    result["status"] = "written"
                except Exception as e:
                    logger.warning(f"Validation failed for {file_path}: {e}")
                    result["validation_ok"] = False
            else:
                result["status"] = "write_failed"
        else:
            result["status"] = "no_write_needed"

    return result


def run_analysis(files_to_process: list[dict], args) -> None:
    """Run parallel analysis on files.

    Args:
        files_to_process: List of file info dicts
        args: Command-line arguments
    """
    # Respect limit
    if args.limit:
        files_to_process = files_to_process[:args.limit]

    low_confidence_entries = []
    errors = []
    written_count = 0
    skipped_count = 0

    # Use ProcessPoolExecutor for CPU-bound work
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_file, file_info, args.dry_run, args.force): file_info
            for file_info in files_to_process
        }

        with tqdm(total=len(futures), desc="Analyzing", unit="track") as pbar:
            for future in as_completed(futures):
                file_info = futures[future]
                try:
                    result = future.result()

                    # Update progress bar
                    pbar.update(1)

                    # Log result
                    if result["status"] == "skipped":
                        skipped_count += 1
                    elif result["status"] in ["written", "analyzed", "no_write_needed"]:
                        filename = result["path"].name
                        bpm_str = f"BPM={result['bpm']}" if result['bpm'] else "BPM=?"
                        key_str = f"Key={result['key']}" if result['key'] else "Key=?"
                        logger.info(f"{filename}: {bpm_str}, {key_str}")

                        if result["status"] == "written":
                            written_count += 1

                        # Collect low confidence keys
                        if result.get("low_confidence"):
                            low_confidence_entries.append({
                                "path": result["path"],
                                "key": result["key"],
                                "confidence": result["key_confidence"],
                            })
                    elif result["status"] == "write_failed":
                        errors.append(result["path"])
                        logger.error(f"Failed to write metadata: {result['path']}")

                except Exception as e:
                    logger.exception(f"Error processing {file_info['path']}: {e}")
                    errors.append(file_info["path"])
                    pbar.update(1)

    # Write low confidence keys to file
    if low_confidence_entries:
        with open(LOW_CONFIDENCE_FILE, "w") as f:
            f.write("# Tracks with key confidence < 0.5 - review manually\n")
            for entry in low_confidence_entries:
                f.write(f"{entry['path']}\tdetected={entry['key']}\tconfidence={entry['confidence']:.2f}\n")

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Analysis complete!")
    logger.info(f"  Written: {written_count}")
    logger.info(f"  Skipped: {skipped_count}")
    logger.info(f"  Errors: {len(errors)}")
    logger.info(f"  Low confidence keys: {len(low_confidence_entries)}")
    logger.info("=" * 60)


def print_stats(scan_results: list[dict]) -> None:
    """Print statistics about the library scan.

    Args:
        scan_results: List of scan result dicts
    """
    total = len(scan_results)
    missing_bpm_only = sum(1 for r in scan_results if not r["has_bpm"] and r["has_key"])
    missing_key_only = sum(1 for r in scan_results if r["has_bpm"] and not r["has_key"])
    missing_both = sum(1 for r in scan_results if not r["has_bpm"] and not r["has_key"])
    complete = sum(1 for r in scan_results if r["has_bpm"] and r["has_key"])

    logger.info("")
    logger.info("=" * 60)
    logger.info("Library Statistics")
    logger.info("=" * 60)
    logger.info(f"Total tracks:           {total}")
    logger.info(f"Complete (BPM + Key):   {complete} ({complete/total*100:.1f}%)")
    logger.info(f"Missing BPM only:       {missing_bpm_only}")
    logger.info(f"Missing key only:       {missing_key_only}")
    logger.info(f"Missing both:           {missing_both}")
    logger.info(f"Need processing:        {missing_bpm_only + missing_key_only + missing_both}")
    logger.info("=" * 60)
    logger.info("")


def main():
    """Main entry point."""
    args = parse_args()

    logger.info(f"Scanning {MUSIC_DIR}...")
    scan_results = scan_library(MUSIC_DIR)

    # Always print stats first
    print_stats(scan_results)

    # Filter to files needing analysis (unless --force)
    if args.force:
        files_to_process = scan_results
    else:
        files_to_process = [f for f in scan_results if not f["has_bpm"] or not f["has_key"]]

    if not files_to_process:
        logger.info("All files already have BPM and key metadata!")
        return

    logger.info(f"Will process {len(files_to_process)} files")

    if args.dry_run:
        logger.info("DRY RUN - showing what would be written, no files modified")
        # Show first N files that would be processed
        for f in files_to_process[:args.limit or 10]:
            print(f"  {f['path'].name}: needs BPM={not f['has_bpm']}, needs key={not f['has_key']}")
        return

    run_analysis(files_to_process, args)

    # Write low confidence keys to review file
    if LOW_CONFIDENCE_FILE.exists():
        logger.info(f"Low confidence keys written to {LOW_CONFIDENCE_FILE}")

    logger.info("Done! Run 'music-minion sync local' to import updated tags.")


if __name__ == "__main__":
    main()
