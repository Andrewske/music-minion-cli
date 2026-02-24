# BPM/Key Analysis Script with Essentia

## Overview
Create a standalone script that analyzes audio files in ~/Music/EDM that are missing BPM and/or key metadata. Uses Essentia library for audio analysis and Mutagen to write tags back to files. After running, use `sync full` to import the updated metadata into the database.

## Workflow
```
--dry-run → Show stats + preview what would be written
--force → Re-analyze even files with existing tags
--limit N → Process only first N files
(default) → Stats → Parallel scan → Parallel Essentia analysis → write_metadata_to_file() → sync local
```

## Task Sequence
1. [01-add-essentia-dependency.md](./01-add-essentia-dependency.md) - Add Essentia to pyproject.toml
2. [02-create-analysis-script.md](./02-create-analysis-script.md) - Create scripts/analyze_bpm_key.py

## Success Criteria
1. Install Essentia + tqdm: `uv add essentia tqdm`
2. Dry run to check scope: `uv run python scripts/analyze_bpm_key.py --dry-run`
3. Test on small batch: `uv run python scripts/analyze_bpm_key.py --limit 10`
4. Verify tags (Camelot format): `uv run python scripts/read_metadata.py ~/Music/EDM/some_track.mp3`
5. Full run: `uv run python scripts/analyze_bpm_key.py`
6. Import to database: `music-minion sync local`
7. Check database: verify BPM/key populated in UI

## Dependencies
- Essentia (audio analysis library)
- tqdm (progress bar)
- Mutagen (already installed - metadata reading/writing)
- loguru (already installed - logging)

## Risks
- **Essentia install**: May fail on some systems (has wheels for Python 3.12 on Linux x86_64)
- **Analysis time**: ~2-5 sec/track, mitigated by ProcessPoolExecutor parallelization
- **Accuracy**: Electronic music works well; use --compare to validate before full run
- **WAV files**: No tag support - excluded from processing, warning logged
- **Low confidence keys**: Written to low_confidence_keys.txt for manual review

## Design Decisions
- **Hardcoded path**: ~/Music/EDM (personal project, single music directory)
- **Reuse existing code**: Uses `write_metadata_to_file()` from metadata.py
- **Camelot notation**: DJ-standard key format (8A, 11B) instead of musical keys
- **Double-time BPM correction**: Auto-fix half-time detection errors for EDM
- **Key confidence threshold**: 0.5 - below this, key not written but logged to review file
- **Write validation**: Re-read tags after write to confirm success
- **Parallelization**: os.scandir + ThreadPool for scanning, ProcessPool for analysis
- **Progress bar**: tqdm with ETA for long runs
- **No caching**: One-time run, keep it simple
