---
name: enrich-metadata
description: Enrich local track metadata using SoundCloud data. Use when user wants to enrich metadata, fix track metadata, or mentions a playlist needing metadata cleanup.
argument-hint: <playlist_id> [--force]
disable-model-invocation: true
---

# Enrich Metadata Skill

Enrich local track metadata using SoundCloud data with Claude-assisted parsing.

## Arguments
- `playlist_id` (required): Database ID of the playlist to process
- `--force`: Re-enrich tracks that have already been enriched

## Prerequisites
- SoundCloud authentication (run `library auth soundcloud` if needed)
- Valid playlist_id from database

## Workflow

### Phase 1: Linking

1. **Query local tracks** in the playlist that need linking:
   ```sql
   SELECT t.id, t.title, t.artist, t.local_path, t.duration, t.soundcloud_id
   FROM tracks t
   JOIN playlist_tracks pt ON t.id = pt.track_id
   WHERE pt.playlist_id = ? AND t.local_path IS NOT NULL
   ```

2. **Find DB matches first** using `find_soundcloud_matches_for_local()`:
   - Pass `{'title': title, 'artist': artist, 'duration': duration}` to get matches
   - Returns `MatchCandidate` objects with `confidence_score`, `soundcloud_id`, etc.

3. **Auto-link high confidence (≥90%)**:
   - If SC track exists with `local_path IS NULL`: link local track to soundcloud_id, delete SC-only track
   - If SC track has local_path already: skip (conflict)
   - Otherwise: update local track's `soundcloud_id`

4. **Batch confirm medium confidence (60-89%)**:
   - Show 10 tracks at a time in table format
   - User responds: `y` (all), `n` (skip), or corrections like `skip 3,7`

5. **Request URLs only for unmatched tracks**:
   - Show remaining tracks with no DB matches
   - User provides SoundCloud URLs (one per line) or `skip`
   - Resolve URLs via `resolve_soundcloud_url()` and link

### Phase 2: Batch Fetch

1. Query all linked tracks needing enrichment (`enriched_at IS NULL`)
2. Fetch SoundCloud metadata for each using `fetch_soundcloud_track()`
3. Save to `/tmp/sc_metadata_batch.json` for Phase 3

### Phase 3: Enrichment (Sonnet Subagent)

**Use Sonnet subagent to save tokens.** Process in batches of 5.

For each batch:

1. Extract track data (current title, artist, SC title, SC genre, SC tags)
2. Spawn Sonnet with track data embedded in prompt (don't make it read files)
3. Sonnet provides recommendations in this format:

```
**Batch X/Y** - My recommendations:

---

**1. [filename]**

Current:
- Title: [current]
- Artist: [current]

Recommended:
- Title: [cleaned title]
- Artist: [original artist]
- Genre: [from SC]

---
[repeat for each track]

Accept? (`y` / `n` / corrections)
```

4. User reviews and approves or provides corrections
5. Apply changes via `write_metadata_to_file()` and update DB `enriched_at`

### Kevin's Metadata Preferences

**Title formatting:**
- Remove artist prefix: "Artist - Song (Remix)" → "Song (Remix)"
- Remove suffixes: "[FREE DOWNLOAD]", "MASTER", "[Free DL]", etc.
- Use title case
- Keep remix type as-is: "Flip", "Remix", "Edit", "Redo", "Bootleg"

**Feature formatting:**
- Use "ft." not "feat."
- Put features BEFORE remix notation: "Song ft. Artist (Remix)"
- Example: "My Chick Bad ft. Nicki Minaj (PSCYTHE Remix)"

**Artist attribution:**
- For remixes: Artist = Original Artist, not the remixer
- For original collabs: Keep all artists
- For covers/redos: Artist = Original Artist

**Genre:**
- Use SoundCloud genre when available
- Common genres: Dubstep, Drum & Bass, Dance & EDM, Electronic, UK Garage, Jersey Club

### Sonnet Prompt Template

```
Analyze these 5 tracks and provide metadata recommendations.

**Track Data:**
[paste track data here]

**Rules:**
- For remixes: Title = "Song Name (Remixer Remix)", Artist = Original Artist
- For features: put "ft. X" BEFORE the remix notation
- Use "ft." not "feat."
- Keep "Flip" as "Flip", don't change to "Remix"
- Use title case
- Remove "[FREE DOWNLOAD]", "MASTER", etc suffixes
- Genre from SC data

**Output format:**
[show expected format]

Accept? (`y` / `n` / corrections)
```

## Merge Logic

When linking, SC tracks may already exist in DB without `local_path`. **Always preserve the local track** since it has ratings, bucket assignments, ELO scores, etc.

```python
# Check if SC track exists
cursor = conn.execute(
    'SELECT id, local_path FROM tracks WHERE soundcloud_id = ?',
    (sc_id,)
)
existing = cursor.fetchone()

if existing and existing['local_path'] is None:
    # SC-only track exists - link local track and delete SC-only track
    # This preserves all local track relationships (buckets, ratings, playlists)
    conn.execute(
        'UPDATE tracks SET soundcloud_id = ? WHERE id = ?',
        (sc_id, local_track_id)
    )
    # Move any playlist refs from SC track to local track
    conn.execute(
        'UPDATE OR IGNORE playlist_tracks SET track_id = ? WHERE track_id = ?',
        (local_track_id, existing['id'])
    )
    conn.execute('DELETE FROM playlist_tracks WHERE track_id = ?', (existing['id'],))
    # Delete the SC-only track (has no local file, no bucket assignments)
    conn.execute('DELETE FROM tracks WHERE id = ?', (existing['id'],))
    conn.commit()
elif existing and existing['local_path']:
    # SC track already has a local_path - conflict, skip
    print(f"⚠ SoundCloud ID {sc_id} already linked to: {existing['local_path']}")
else:
    # No existing SC track - just update local track
    conn.execute(
        'UPDATE tracks SET soundcloud_id = ? WHERE id = ?',
        (sc_id, local_track_id)
    )
    conn.commit()
```

## Files

- Skill definition: `.claude/skills/enrich-metadata/SKILL.md`
- Existing functions to reuse:
  - `scripts/enrich_metadata.py`: `fetch_soundcloud_track`, `resolve_soundcloud_url`, `find_soundcloud_matches_for_local`, `write_metadata_to_file`, `get_valid_access_token`
  - `music_minion/domain/playlists/matching.py`: `MatchCandidate`, `batch_score_candidates`
- Log output: `logs/metadata_enrichment.jsonl`
- Temp data: `/tmp/sc_metadata_batch.json`

## Example Session

```
User: /enrich-metadata 383

Claude: Processing playlist "Bre" (383)...

Found 97 local tracks:
- 25 already linked to SoundCloud
- 57 have potential DB matches
- 15 have no matches

## Auto-linking high confidence matches...
✓ Auto-linked 34 tracks (≥90% confidence)

## Medium confidence matches (23 tracks)

| # | Your Track | Best Match | Conf |
|---|------------|------------|------|
| 1 | "ALL I WANTED (OZZTIN X SETH DAVID FLIP)" | "PARAMORE - ALL I WANTED..." | 66% |
...

Accept all? (y/n/corrections): y
✓ Linked 23 tracks

## Tracks Needing SoundCloud Links (15)

1. Disco Stick [Free DL].mp3
2. ELECTRIC LOVE (AVELLO REMIX).mp3
...

Provide URLs (one per line, or 'skip'):

User: [provides URLs]

Claude: ✓ Linked 15/15 tracks

## Enrichment Phase (86 tracks)

[Spawns Sonnet for batch 1]

**Batch 1/18** - Recommendations:
...

Accept? y

✓ Batch 1 applied (5/86)
[continues...]
```
