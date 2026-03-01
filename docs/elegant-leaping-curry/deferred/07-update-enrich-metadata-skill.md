---
task: 07-update-enrich-metadata-skill
status: pending
depends:
  - 01-database-migration
files:
  - path: .claude/skills/enrich-metadata/SKILL.md
    action: modify
---

# Update enrich-metadata Skill

## Context

With the new composite unique constraint on `(source, soundcloud_id)`, the enrich-metadata skill no longer needs to delete SC-only tracks when linking local tracks. Both records can coexist. Update the merge logic documentation.

## Files to Modify/Create

- `.claude/skills/enrich-metadata/SKILL.md` (modify)

## Implementation Details

### 1. Update "Merge Logic" section (lines 136-174)

Replace the entire section with simplified logic that doesn't delete SC tracks:

**Before (current SKILL.md lines 136-174):**
```markdown
## Merge Logic

When linking, SC tracks may already exist in DB without `local_path`. **Always preserve the local track** since it has ratings, bucket assignments, ELO scores, etc.

\`\`\`python
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
\`\`\`
```

**After:**
```markdown
## Merge Logic

With the composite unique constraint on `(source, soundcloud_id)`, local and SC tracks can coexist. No deletion needed.

\`\`\`python
# Check if local track already has this soundcloud_id
cursor = conn.execute(
    'SELECT id FROM tracks WHERE soundcloud_id = ? AND source = ?',
    (sc_id, 'local')
)
existing_local = cursor.fetchone()

if existing_local:
    # Local track already linked to this SC ID - skip
    print(f"Local track already linked to SC ID {sc_id}")
else:
    # Link local track - SC track with same ID can coexist (different source)
    conn.execute(
        'UPDATE tracks SET soundcloud_id = ? WHERE id = ?',
        (sc_id, local_track_id)
    )
    conn.commit()
\`\`\`

**Key change:** The constraint `UNIQUE(source, soundcloud_id)` allows both:
- `source='local', soundcloud_id='123'` (local track with SC link for enrichment)
- `source='soundcloud', soundcloud_id='123'` (SC track for streaming)
```

### 2. Update auto-link description (line 37)

**Before:**
```
3. **Auto-link high confidence (≥90%)**:
   - If SC track exists with `local_path IS NULL`: link local track to soundcloud_id, delete SC-only track
```

**After:**
```
3. **Auto-link high confidence (≥90%)**:
   - Update local track's `soundcloud_id` (no deletion needed - records coexist)
```

## Verification

1. Run enrich-metadata skill on a playlist
2. Verify SC tracks are NOT deleted when linking
3. Verify both local and SC records exist:
   ```sql
   SELECT source, soundcloud_id, local_path FROM tracks WHERE soundcloud_id = '<some_id>';
   -- Should show two rows: one local, one soundcloud
   ```
