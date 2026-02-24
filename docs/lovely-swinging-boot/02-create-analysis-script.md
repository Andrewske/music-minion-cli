---
task: 02-create-analysis-script
status: pending
depends: [01-add-essentia-dependency]
files:
  - path: scripts/analyze_bpm_key.py
    action: create
---

# Create BPM/Key Analysis Script

## Context
Standalone script that scans ~/Music/EDM, identifies tracks missing BPM/key metadata, runs Essentia analysis, and writes results back to file tags using existing `write_metadata_to_file()`.

## Files to Modify/Create
- scripts/analyze_bpm_key.py (new)

## Implementation Details

### Imports and Constants

```python
#!/usr/bin/env python3
"""Analyze BPM and key for audio files missing metadata using Essentia."""

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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
```

### Command-Line Interface

```python
def parse_args():
    parser = argparse.ArgumentParser(description="Analyze BPM/key for audio files")
    parser.add_argument("--dry-run", action="store_true", help="Show stats and what would be written, don't analyze")
    parser.add_argument("--limit", type=int, help="Process only first N files")
    parser.add_argument("--force", action="store_true", help="Re-analyze even if BPM/key already exist")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for analysis")
    return parser.parse_args()
```

### Core Functions

**1. scan_file(file_path) -> dict** - Fast metadata check (parallelized with ThreadPoolExecutor)
- Open with MutagenFile, read ONLY bpm/key tags
- Return `{"path": path, "has_bpm": bool, "has_key": bool, "bpm": float|None, "key": str|None}`
- Early exit once both tags checked
- Log warning if .wav file encountered

**2. scan_library(music_dir, workers=8) -> list[dict]** - Parallel scan
- Use `os.scandir()` recursively (2-3x faster than Path.rglob())
- Use `ThreadPoolExecutor` for I/O-bound tag reads
- Submit scan_file tasks in parallel
- Return list of scan results

**3. analyze_audio(file_path) -> tuple[float|None, str|None, float]** - Essentia analysis
- Load audio: `es.MonoLoader(filename=str(file_path), sampleRate=44100)()`
- BPM: `es.RhythmExtractor2013(method="multifeature")(audio)` returns (bpm, beats, confidence, ...)
  - **Double-time correction**: If BPM < 100 and 2×BPM is in 120-160 range, double it (catches half-time errors)
- Key: `es.KeyExtractor()(audio)` returns (key, scale, strength)
- **Convert to Camelot notation** (DJ standard): Map musical key → Camelot code (e.g., Am → 8A, C → 8B)
  - Use CAMELOT_MAP dict: {"C": "8B", "Am": "8A", "G": "9B", "Em": "9A", ...}
- Return (bpm, camelot_key, key_confidence)
- Wrap in try/except - return (None, None, 0) on error, log exception
- # TODO: Add genre detection with Essentia classifiers

**4. process_file(file_info, dry_run=False, force=False) -> dict** - Single file processing
- Skip if both bpm and key exist (unless --force)
- Call analyze_audio()
- If key_confidence < KEY_CONFIDENCE_THRESHOLD: don't write key, flag for review
- If not dry_run: call `write_metadata_to_file(path, bpm=bpm, key=key)`
- **Validate write**: Re-read tags after write to confirm success
- Return result dict with status, values written, confidence, validation_ok

**5. run_analysis(files_to_process, args) -> None** - Parallel analysis
- Use `ProcessPoolExecutor` for CPU-bound Essentia work
- Respect --limit flag
- **Progress bar with tqdm**: `tqdm(files_to_process, desc="Analyzing", unit="track")`
- Show per-file output: `filename: BPM=X, Key=Y`
- Collect low-confidence keys to write to file at end

**6. print_stats(scan_results) -> None** - Stats display (always shown at start)
- Count: total files, missing BPM only, missing key only, missing both, complete
- Print summary table

### Main Flow

```python
def main():
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
```

### Key Details

- **No .wav support**: Log warning `"Skipping WAV file (no tag support): {path}"` when encountered
- **BPM rounding**: `round(bpm, 1)` for 1 decimal place
- **Double-time correction**: If BPM < 100 and 2×BPM in 120-160, double it
- **Camelot notation**: Output DJ-standard codes (8A, 11B) not musical keys
- **Write validation**: Re-read tags after write to confirm success
- **Progress bar**: tqdm with ETA for long runs
- **Error handling**: Per-file try/except, continue on error, report errors in summary
- **Parallelization**:
  - Scan: `os.scandir()` recursive + ThreadPoolExecutor (I/O-bound), 8+ workers
  - Analysis: ProcessPoolExecutor (CPU-bound), `--workers` flag (default 4)

### Low Confidence Output Format

```
# low_confidence_keys.txt
# Tracks with key confidence < 0.5 - review manually
/path/to/track1.mp3	detected=Am	confidence=0.32
/path/to/track2.m4a	detected=F#	confidence=0.41
```

## Verification

### 1. Dry run to see stats and scope
```bash
uv run python scripts/analyze_bpm_key.py --dry-run
# Expected: Shows stats table + first 10 files that need processing
```

### 2. Run on limited set and verify
```bash
uv run python scripts/analyze_bpm_key.py --limit 10
uv run python scripts/read_metadata.py ~/Music/EDM/path/to/analyzed/track.mp3
# Expected: BPM (Camelot) and Key tags populated, progress bar with ETA
```

### 3. Full run
```bash
uv run python scripts/analyze_bpm_key.py
# Then import to database:
music-minion sync local
```

### 4. Re-analyze with --force (if needed)
```bash
uv run python scripts/analyze_bpm_key.py --force --limit 5
# Expected: Re-analyzes even files with existing tags
```
