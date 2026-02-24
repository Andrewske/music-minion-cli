---
task: 01-strip-featuring-artists
status: done
depends: []
files:
  - path: src/music_minion/domain/library/deduplication.py
    action: modify
  - path: tests/domain/library/test_deduplication.py
    action: create
---

# Strip Featuring Artists from Track Matching

## Context
SoundCloud track matching incorrectly prioritizes "(feat. X)" over remix indicators like "(Cyclops Remix)" because TF-IDF treats all parenthetical content equally. Stripping featuring artist credits before matching preserves the signal (remix indicators) while removing noise (artist credits).

## Files to Modify/Create
- src/music_minion/domain/library/deduplication.py (modify)

## Implementation Details

### 1. Add `strip_featuring_artists()` function after `normalize_string()`

```python
def strip_featuring_artists(s: str) -> str:
    """Remove featuring artist credits from string.

    Patterns matched:
    - (feat. Artist), (feat Artist)
    - (ft. Artist), (ft Artist)
    - (featuring Artist)
    - [feat. Artist], [ft. Artist], [featuring Artist]

    Returns string with featuring patterns removed.
    Safely fails (preserves original) if nested brackets detected.
    """
    if not s:
        return ""
    # Handle parentheses: (feat. X), (ft. X), (featuring X)
    # [^()]+ ensures safe failure on nested parens
    s = re.sub(r"\s*\((?:feat\.?|ft\.?|featuring)\s+[^()]+\)", "", s, flags=re.IGNORECASE)
    # Handle square brackets: [feat. X], [ft. X], [featuring X]
    s = re.sub(r"\s*\[(?:feat\.?|ft\.?|featuring)\s+[^\[\]]+\]", "", s, flags=re.IGNORECASE)
    return s
```

### 2. Apply in `find_best_matches_tfidf()` at two locations

**In the local track loop (~line 103):**
```python
combined = normalize_string(strip_featuring_artists(f"{artist} {title} {filename}"))
```

**In the SC track processing (~line 127):**
```python
sc_combined = normalize_string(strip_featuring_artists(f"{sc_artist} {sc_title}"))
```

### 3. Create unit tests `tests/domain/library/test_deduplication.py`

```python
"""Tests for track matching deduplication."""

import pytest

from music_minion.domain.library.deduplication import strip_featuring_artists


class TestStripFeaturingArtists:
    """Tests for strip_featuring_artists function."""

    def test_feat_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (feat. Artist)") == "Song"

    def test_feat_no_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (feat Artist)") == "Song"

    def test_ft_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (ft. Artist)") == "Song"

    def test_ft_no_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (ft Artist)") == "Song"

    def test_featuring_pattern(self) -> None:
        assert strip_featuring_artists("Song (featuring Artist)") == "Song"

    def test_case_insensitive(self) -> None:
        assert strip_featuring_artists("Song (FEAT. Artist)") == "Song"
        assert strip_featuring_artists("Song (Feat. Artist)") == "Song"
        assert strip_featuring_artists("Song (FT. Artist)") == "Song"

    def test_preserves_other_parentheticals(self) -> None:
        result = strip_featuring_artists("Song (feat. Artist) (Remix)")
        assert result == "Song (Remix)"

    def test_original_bug_case(self) -> None:
        """The case that motivated this fix."""
        result = strip_featuring_artists("Light In The Dark (feat. JIM) (Cyclops Remix)")
        assert result == "Light In The Dark (Cyclops Remix)"

    def test_multiple_artists(self) -> None:
        result = strip_featuring_artists("Song (feat. Artist A & Artist B)")
        assert result == "Song"

    def test_empty_string(self) -> None:
        assert strip_featuring_artists("") == ""

    def test_no_featuring(self) -> None:
        assert strip_featuring_artists("Song (Remix)") == "Song (Remix)"

    def test_square_brackets(self) -> None:
        assert strip_featuring_artists("Song [feat. Artist]") == "Song"
        assert strip_featuring_artists("Song [ft. Artist]") == "Song"
        assert strip_featuring_artists("Song [featuring Artist]") == "Song"

    def test_square_brackets_with_other_parens(self) -> None:
        result = strip_featuring_artists("Song [feat. Artist] (Remix)")
        assert result == "Song (Remix)"

    def test_nested_parens_safe_failure(self) -> None:
        """Nested parens should NOT match - safe failure preserves string."""
        original = "Song (feat. Artist (Stage Name))"
        assert strip_featuring_artists(original) == original

    def test_nested_brackets_safe_failure(self) -> None:
        """Nested brackets should NOT match - safe failure preserves string."""
        original = "Song [feat. Artist [Stage Name]]"
        assert strip_featuring_artists(original) == original
```

## Verification
1. Run `uv run pytest tests/domain/library/test_deduplication.py -v`
2. Run the SoundCloud playlist import for the problematic playlist
3. Verify "Light In The Dark (feat. JIM) (Cyclops Remix)" now matches to "Light In The Dark (Cyclops Remix)"
4. Spot check other matches haven't regressed
