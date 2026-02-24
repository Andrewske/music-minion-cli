---
task: 01-add-essentia-dependency
status: done
depends: []
files:
  - path: pyproject.toml
    action: modify
  - path: src/music_minion/domain/library/metadata.py
    action: modify
---

# Add Essentia Dependency and Fix FLAC Support

## Context
Essentia is the audio analysis library that provides BPM detection (RhythmExtractor2013) and key detection (KeyExtractor). Must be installed before the analysis script can run.

Also fix FLAC metadata writing support which is currently missing from metadata.py.

## Files to Modify/Create
- pyproject.toml (modify)
- src/music_minion/domain/library/metadata.py (modify)

## Implementation Details

### 1. Add dependencies
```bash
uv add essentia tqdm
```

### 2. Fix FLAC support in metadata.py

Add FLAC import:
```python
from mutagen.flac import FLAC
```

Update isinstance checks to include FLAC (uses same Vorbis comments):
```python
elif isinstance(audio, (OggOpus, OggVorbis, FLAC)):
    _write_vorbis_metadata(...)
```

Apply to both `write_metadata_to_file()` and `write_elo_to_file()` functions.

### 3. Fix tag name inconsistency

In `extract_track_metadata()`, change `INITIAL_KEY` to `INITIALKEY` for consistency:
```python
key = get_tag_value(audio_file, ["TKEY", "KEY", "INITIALKEY", "initialkey", "\xa9key", "key"])
```

## Verification
```bash
# Verify Essentia installed
uv run python -c "import essentia; print(essentia.__version__)"

# Verify FLAC import works
uv run python -c "from mutagen.flac import FLAC; print('FLAC support OK')"
```
