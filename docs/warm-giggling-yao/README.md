# Improve SoundCloud Track Matching for Remixes

## Overview
Fix incorrect SoundCloud track matching where "(feat. X)" tokens are weighted equally to remix indicators, causing "Light In The Dark (feat. JIM) (Cyclops Remix)" to match to "Light In The Dark (feat. JIM)" instead of "Light In The Dark (Cyclops Remix)".

Solution: Strip "(feat. X)" patterns before TF-IDF matching to remove noise (artist credits) while preserving signal (remix/version indicators).

## Task Sequence
1. [01-strip-featuring-artists.md](./01-strip-featuring-artists.md) - Add strip_featuring_artists() and apply to TF-IDF matching

## Success Criteria
1. SoundCloud playlist import correctly matches "Light In The Dark (feat. JIM) (Cyclops Remix)" to "Light In The Dark (Cyclops Remix)"
2. Existing matches continue to work (no regression)

## Dependencies
None - self-contained change to existing matching logic
