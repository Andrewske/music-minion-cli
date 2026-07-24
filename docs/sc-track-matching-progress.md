# SoundCloud Track Matching — Progress & Findings

**Goal:** Link ~5,800 unlinked local tracks to their SoundCloud counterparts (already in DB as `source='soundcloud'`). This enables fetching artwork URLs and displaying track images in the web UI.

**Date:** 2026-05-08

## Current State

- **5,809 local tracks** with no `soundcloud_id` (98% originated from SoundCloud)
- **8,969 SC tracks** already in DB with `soundcloud_id`s
- **105 local tracks** already linked
- No `artwork_url` column exists yet on tracks table
- SC API returns `artwork_url` on track objects but `_normalize_soundcloud_track()` drops it
- Matching infrastructure exists in `src/music_minion/domain/library/deduplication.py` (TF-IDF)
- `library match soundcloud` command referenced in tips but never implemented

## Data Characteristics

### Local tracks
- Title/artist metadata often cleaned up (renamed by Kevin)
- Album field = SC playlist name or monthly bucket ("Nov 23", "BassHeadsDelight", etc.)
- Filenames preserve original SC title format (gold for matching)
- Filenames have prefixes: "Nov 23_", "Dec 24_", track numbers "01 - "

### SC tracks in DB
- Artist field often wrong — contains label/reposter name ("Barong Family", "Trap Sounds") instead of actual artist
- Title often has format "Artist - Real Title [Free Download]" or "Artist - Artist - Title"
- `metadata_artist` field in API has real artist but many SC tracks imported before we captured it
- SC playlists reorganized (178→21, yearly a/b splits) so playlist names don't match local albums 1:1

## Strategies Tested

### Baseline: TF-IDF (existing deduplication.py)
- Uses `find_best_matches_tfidf()` from `deduplication.py`
- Builds TF-IDF vectors from artist+title+filename, cosine similarity
- **Results:** 20.5% at >=0.95, 51.0% at >=0.85, 68.7% at >=0.70
- **Problems:** Downweights common words like "Remix" that are critical discriminators. Wrong remix matches score high.

### Strategy 1: Clean Keyword Overlap (Jaccard)
- Strip album, track numbers, noise words. Pure token intersection/union.
- **Results:** 53.3% at >=0.90, 61.0% at >=0.80
- **Problems:** Short-title tracks fail (LRAD, The Game — only 2-3 tokens)

### Strategy 2: Title-Focused
- Match primarily on title (80% weight), artist secondary (20%)
- Parse SC title: split on " - ", take last segment as real title
- **Results:** 49.6% at >=0.90, 62.7% at >=0.80
- **Insight:** SC title splitting helps. Artist de-emphasis handles label-as-artist.

### Strategy 3: Containment + Critical Token Penalties
- Score = |intersection| / |local_tokens| (containment, not Jaccard)
- Critical token penalty: if remix/feat artist name missing from SC, multiply by 0.5
- **Results:** 55.6% at >=0.90, 65.3% at >=0.80
- **Best at high confidence.** Correctly pushes bad matches down.
- **Issue:** Digit-only tokens from filenames ("01", "47") are biggest noise source.

### Strategy 4: Hybrid TF-IDF × Keyword
- TF-IDF for candidate selection, keyword containment for re-scoring
- 50/50 blend of TF-IDF score and keyword containment
- **Results:** 52.7% at >=0.90, 67.4% at >=0.80, 77.1% at >=0.70
- **Best mid-range coverage.** TF-IDF narrows candidates, keywords validate.

### Merged v1: TF-IDF candidates + S3 containment scoring
- TF-IDF top-10 candidates per local track
- SC title parsing (split on " - ", strip bracket suffixes)
- S3's containment scoring with critical token penalties
- **Results:** 60.6% at >=0.90, 68.4% at >=0.80, 73.8% at >=0.70

### Merged v2: v1 + 3 fixes
**Script:** `scripts/test_strategy_merged_v2.py`

Three fixes applied:
1. **Synonym normalization:** ft→feat, featuring→feat, x→&, and→&
2. **Reverse remix penalty:** If SC has remix indicators but local doesn't, multiply by 0.5 (fixes LRAD matching wrong remix)
3. **Better filename cleaning:** Split on underscores, strip album-name prefixes, strip digit-only tokens

**Results:**
| Bucket | Count | % |
|--------|-------|---|
| 0.90+ | 4,141 | 71.3% |
| 0.80-0.89 | 290 | 5.0% |
| 0.70-0.79 | 131 | 2.3% |
| 0.60-0.69 | 199 | 3.4% |
| 0.50-0.59 | 236 | 4.1% |
| < 0.50 | 812 | 14.0% |

**Cumulative:** >=0.90: 71.3%, >=0.80: 76.3%, >=0.70: 78.5%, >=0.50: 86.0%

### Merged v3: v2 + 3 experiments merged
**Script:** `scripts/test_strategy_merged_v3.py`

Parallel experiments tested 5 ideas. Three had positive signal and were merged with safety guards:

1. **Artist-weighted containment (EXP3):** Artist tokens count 2x in containment scoring. 1.1x boost when all artist tokens match — but only fires when non-artist token coverage > 0.5 (prevents artist-only wrong-title inflation like "Martin Garrix - Animals" → "Martin Garrix - Bouncybob")
2. **Exact title substring pre-filter (EXP1):** If cleaned local title is substring of SC title (or vice versa), blend 50/50 with 1.0. Guards: skip when any penalty < 1.0 (preserve remix/critical penalties), require >=2 meaningful words (prevent single-word false matches like "bounce" → "Bounce That Booty")
3. **Levenshtein boost (EXP4):** For scores < 0.90, if normalized edit distance > 0.80, blend 60/40 containment/lev. Guard: combined "artist - title" comparison only — title-only removed because generic titles ("Alive", "Recess") matched wrong artists

Rejected experiments:
- **Character trigrams (EXP2):** -24.9% at >=0.90. SC label prefixes in titles inflate Jaccard denominator, dragging perfect matches down to 0.80.
- **Enhanced SC title parsing (EXP5):** +0.0%. Current `parse_sc_real_title()` already handles multi-dash formats. No real data movement.

**Results:**
| Bucket | Count | % |
|--------|-------|---|
| 0.90+ | 4,472 | 77.0% |
| 0.80-0.89 | 159 | 2.7% |
| 0.70-0.79 | 136 | 2.3% |
| 0.60-0.69 | 210 | 3.6% |
| 0.50-0.59 | 172 | 3.0% |
| < 0.50 | 660 | 11.4% |

**Cumulative:** >=0.90: 77.0%, >=0.80: 79.7%, >=0.70: 82.1%, >=0.50: 88.6%

**Boost firing rates:** Substring: 56.6%, Levenshtein: 1.1% (63 tracks), Artist boost: selective (guard prevents most artist-only matches)

### Merged v4 (current best): v3 + EXP8 (filename-as-ground-truth)
**Script:** `scripts/test_strategy_merged_v4.py`

Parallel experiments tested 5 ideas. One had strong positive signal:

1. **Filename-as-ground-truth scoring (EXP8):** Filenames preserve original SC titles (before Kevin cleaned up metadata). Independent scoring path: cleaned filename stem scored against SC tracks using containment + substring matching. Final score = max(v3_score, filename_score). Guards: require >=2 meaningful tokens, >=2 meaningful words for substring boost.

Rejected experiments:
- **Metadata artist / top_level_artist (EXP6):** +0.0%. Field duplicates existing artist tokens for 99.2% of SC tracks.
- **Token order bigrams (EXP7):** +0.2%. 46 tracks boosted — word order rarely the bottleneck in this domain.
- **SC title prefix parsing (EXP9):** +0.0%. 2-segment "Artist - Title" artist already captured by SC artist field. 3+ segment case only 1% of tracks.
- **Negative evidence penalty (EXP10):** -0.7% at >=0.90. Correctly penalizes wrong matches but also hurts legit ones with label-name tokens. Needs tuning.

**Results:**
| Bucket | Count | % |
|--------|-------|---|
| 0.90+ | 4,648 | 80.0% |
| 0.80-0.89 | 173 | 3.0% |
| 0.70-0.79 | 179 | 3.1% |
| 0.60-0.69 | 312 | 5.4% |
| 0.50-0.59 | 229 | 3.9% |
| < 0.50 | 268 | 4.6% |

**Cumulative:** >=0.90: 80.0%, >=0.80: 83.0%, >=0.70: 86.1%, >=0.50: 95.4%

**Path breakdown:** Filename path won 880 tracks (15.1%), of which 570 via filename-substring boost. V3 path won 4,929 tracks (84.9%).

## Spot Check Results (Merged v4)

| Track | v3 Score | v4 Score | Path | Correct? | Notes |
|-------|----------|----------|------|----------|-------|
| Knife Party - Boss Mode | 1.000 | 1.000 | V3+sub+art | YES | |
| Brillz - Hawt | 1.000 | 1.000 | V3+art | YES | |
| GTA - Red Lips (Skrillex Remix) | 1.000 | 1.000 | V3+art | YES | |
| Jauz - Get On Up (Getter Remix) | 1.000 | 1.000 | V3+sub+art | YES | |
| Nightowls - Nap In The Club | 1.000 | 1.000 | V3+sub+art | YES | |
| Vincent - Only | 1.000 | 1.000 | V3+art | YES | |
| Bun Up The Dance (Dreamer Remix) | 0.856 | 0.856 | V3+art | WRONG | Dreamer Remix not in SC. Matched Styrka Flip. |
| Knife Party - LRAD | 0.800 | 0.800 | V3 | WRONG | Matched Boss Mode (stays in review bucket) |
| #SELFIE (Botnek remix) | 0.600 | 0.667 | FILENAME | WRONG | Filename path slightly better but still wrong match |
| Curfew - The Game | 0.200 | 0.625 | FILENAME+fn-sub | WRONG | No SC match exists, filename inflates score |

## Spot Check Results (Merged v3)

| Track | v2 Score | v3 Score | Boosts | Correct? | Notes |
|-------|----------|----------|--------|----------|-------|
| Knife Party - Boss Mode | 1.000 | 1.000 | sub+art | YES | |
| Brillz - Hawt | 1.000 | 1.000 | art | YES | |
| GTA - Red Lips (Skrillex Remix) | 1.000 | 1.000 | art | YES | |
| Jauz - Get On Up (Getter Remix) | 1.000 | 1.000 | sub+art | YES | |
| Nightowls - Nap In The Club | 1.000 | 1.000 | sub+art | YES | |
| Vincent - Only | 1.000 | 1.000 | art | YES | |
| Bun Up The Dance (Dreamer Remix) | 0.714 | 0.856 | art | WRONG | Dreamer Remix not in SC. Matched Styrka Flip. |
| Knife Party - LRAD | 0.667 | 0.800 | - | WRONG | Matched Boss Mode (artist-weight pushed up but stays in review bucket) |
| #SELFIE (Botnek remix) | 0.500 | 0.600 | - | WRONG | # stripped, substring guard blocks (<2 words) |
| Curfew - The Game | 0.250 | 0.200 | - | CORRECT LOW | No SC match exists |

## Spot Check Results (Merged v2)

| Track | Score | Correct? | Notes |
|-------|-------|----------|-------|
| Knife Party - Boss Mode | 1.000 | YES | Album noise eliminated |
| Brillz - Hawt | 1.000 | YES | Matched Brillz & Ghastly correctly |
| GTA - Red Lips (Skrillex Remix) | 1.000 | YES | ft/feat synonym fix helped |
| Jauz - Get On Up (Getter Remix) | 1.000 | YES | Remix tokens matched correctly |
| KRANE - Feel It (Vincent Remix) | 1.000 | YES | ft/feat fix: 0.889→1.000 |
| Nightowls - Nap In The Club (Dapp Rework) | 1.000 | YES | Correct version matched |
| Knife Party - LRAD | 0.667 | WRONG | Matched Boss Mode (few tokens). Reverse remix penalty correctly blocked remix match though. |
| Bun Up The Dance (Dreamer Remix) | 0.714 | WRONG | Dreamer Remix not in SC library. Matched Styrka Flip instead. |
| #SELFIE (Botnek remix) | 0.500 | WRONG | # stripped as punctuation, "selfie" too rare in index |
| Curfew - The Game | 0.250 | CORRECT LOW | No SC match exists, correctly scored low |

## Known Remaining Issues

1. **Short-title tracks** (2-3 tokens like "LRAD", "The Game") — not enough signal for containment to discriminate.
2. **# symbol stripped** — #SELFIE becomes "selfie". Could preserve # in tokenization.
3. **Tracks not in SC library** (~4.6%) — genuinely no match available. These need manual search or are non-SC tracks.
4. **Filename path false positives** — "Curfew - The Game" inflated from 0.200 → 0.625 via filename. Filename path can match wrong SC tracks when correct match doesn't exist.

## Implementation Plan

Algorithm iteration is done (80% at >=0.90, diminishing returns). No production matching module needed — this is a one-time backfill, not a recurring operation.

### Step 1: Backfill script
- Extend v4 script to `UPDATE tracks SET soundcloud_id = ? WHERE id = ?` for >=0.90 matches
- Run once, auto-link ~4,648 tracks
- Output the 0.50-0.89 candidates to a JSON file for review UI

### Step 2: DB migration + API capture
- Add `artwork_url` column to tracks table
- Update `_normalize_soundcloud_track()` to capture artwork_url from SC API responses

### Step 3: Review UI (the real production feature)
- Web UI for 0.50-0.89 band (~893 tracks)
- Show local track + top SC candidate side-by-side
- Human clicks accept/reject/search-manually
- This is what's needed for fixing errors going forward

### Step 4: Artwork backfill
- After linking, bulk fetch artwork URLs from SC API for all linked tracks

## File Locations

- Current best: `scripts/test_strategy_merged_v4.py`
- Previous: `scripts/test_strategy_merged_v3.py`, `scripts/test_sc_matching.py`, `scripts/test_sc_matching_v2.py`, `scripts/test_strategy_merged_v2.py`
- v4 experiments: `scripts/test_exp6_metadata_artist.py`, `scripts/test_exp7_bigram_order.py`, `scripts/test_exp8_filename_priority.py`, `scripts/test_exp9_title_prefix.py`, `scripts/test_exp10_negative_evidence.py`
- v3 experiments: `scripts/test_exp1_substring.py`, `scripts/test_exp2_trigram.py`, `scripts/test_exp3_artist_weight.py`, `scripts/test_exp4_levenshtein.py`, `scripts/test_exp5_title_parse.py`
- Earlier strategies: `scripts/test_strategy1_clean_keyword.py`, `scripts/test_strategy2_title_focused.py`, `scripts/test_strategy3_containment.py`, `scripts/test_strategy4_hybrid.py`
- Existing matching code: `src/music_minion/domain/library/deduplication.py`
- SC API: `src/music_minion/domain/library/providers/soundcloud/api.py`
- DB schema: `src/music_minion/core/database.py`

## Evolution Summary

```
TF-IDF baseline     → 20.5% at 0.95+
Clean keyword        → 53.3% at 0.90+  (strip noise, Jaccard)
Containment+penalty  → 55.6% at 0.90+  (containment > Jaccard, critical tokens)
Merged v1            → 60.6% at 0.90+  (TF-IDF candidates + containment)
Merged v2            → 71.3% at 0.90+  (+ synonyms, reverse remix penalty, better filename cleaning)
Merged v3            → 77.0% at 0.90+  (+ artist weighting, substring boost, levenshtein boost)
Merged v4            → 80.0% at 0.90+  (+ filename-as-ground-truth dual scoring path)
```

Key insights:
- TF-IDF is great for candidate selection (narrows 9K→10), but containment-based scoring with domain-specific penalties (remix, feat, noise) drives accuracy. Simple keyword matching beat TF-IDF scoring 3.5x at high confidence.
- Artist-weighted containment was the single biggest v3 gain (+5.1% alone) — artist match is a much stronger signal than generic title words.
- Filename-as-ground-truth was the biggest v4 gain (+3.0%). Filenames preserve original SC titles before metadata cleanup — an independent scoring path that catches 880 tracks where cleaned metadata diverged too far from the SC original.
