# Playlist Builder Emoji Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add emoji tagging and filtering to the web PlaylistBuilder page.

**Architecture:** Extend existing emoji infrastructure (EmojiTrackActions, useTrackEmojis, batch_fetch_track_emojis) to PlaylistBuilder. Add emoji field to filter system.

**Tech Stack:** React, TypeScript, FastAPI, SQLite

---

## Task 1: Add emojis to Track type

**Files:**
- Modify: `web/frontend/src/api/builder.ts:12-24`

**Step 1: Update Track interface**

Add `emojis` field to Track interface:

```typescript
export interface Track {
  id: number;
  title: string;
  artist: string;
  album?: string;
  genre?: string;
  year?: number;
  bpm?: number;
  key_signature?: string;
  duration?: number;
  local_path?: string;
  elo_rating?: number;
  emojis?: string[];  // Add this line
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd web/frontend && npm run build`
Expected: Compiles without errors

**Step 3: Commit**

```bash
git add web/frontend/src/api/builder.ts
git commit -m "feat(builder): add emojis field to Track type"
```

---

## Task 2: Add emojis to backend candidates response

**Files:**
- Modify: `web/backend/routers/builder.py:265-304`

**Step 1: Import batch_fetch_track_emojis**

Add import at top of file:

```python
from ..queries.emojis import batch_fetch_track_emojis
```

**Step 2: Modify get_candidates endpoint**

Update the endpoint to fetch and attach emojis:

```python
@router.get("/candidates/{playlist_id}", response_model=CandidatesResponse)
async def get_candidates(
    playlist_id: int,
    limit: int = 100,
    offset: int = 0,
    sort_field: str = "artist",
    sort_direction: str = "asc",
):
    """Get paginated list of candidate tracks with server-side sorting."""
    try:
        _validate_manual_playlist(playlist_id)

        candidates, total = builder.get_candidate_tracks(
            playlist_id,
            sort_field=sort_field,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset,
        )

        # Batch-fetch emojis for all candidates
        if candidates:
            track_ids = [c["id"] for c in candidates]
            with get_db_connection() as conn:
                emojis_map = batch_fetch_track_emojis(track_ids, conn)

            # Attach emojis to each candidate
            for candidate in candidates:
                candidate["emojis"] = emojis_map.get(candidate["id"], [])

        return CandidatesResponse(
            candidates=candidates,
            total=total,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 3: Test manually**

Run: `curl http://localhost:8642/api/builder/candidates/1?limit=5 | jq '.candidates[0].emojis'`
Expected: Returns `[]` or list of emoji strings

**Step 4: Commit**

```bash
git add web/backend/routers/builder.py
git commit -m "feat(builder): include emojis in candidates response"
```

---

## Task 3: Add EmojiTrackActions to TrackDisplay

**Files:**
- Modify: `web/frontend/src/pages/PlaylistBuilder.tsx:320-334`

**Step 1: Import EmojiTrackActions**

Add import at top of file:

```typescript
import { EmojiTrackActions } from '../components/EmojiTrackActions';
```

**Step 2: Add state for track updates**

Add a state update handler in the PlaylistBuilder component (around line 26):

```typescript
const [localTrackOverrides, setLocalTrackOverrides] = useState<Record<number, { emojis?: string[] }>>({});

// Merge local overrides with candidates for display
const getTrackWithOverrides = (track: Track): Track => ({
  ...track,
  ...localTrackOverrides[track.id],
});
```

**Step 3: Add handleTrackEmojiUpdate function**

Add after the localTrackOverrides state:

```typescript
const handleTrackEmojiUpdate = (updatedTrack: { id: number; emojis?: string[] }) => {
  setLocalTrackOverrides(prev => ({
    ...prev,
    [updatedTrack.id]: { emojis: updatedTrack.emojis },
  }));
};
```

**Step 4: Update TrackDisplay component**

Replace the TrackDisplay component (lines 320-334) with emoji support:

```typescript
function TrackDisplay({ track, onEmojiUpdate }: { track: Track; onEmojiUpdate: (t: { id: number; emojis?: string[] }) => void }) {
  return (
    <div className="text-center">
      <h2 className="text-4xl font-bold mb-2">{track.title}</h2>
      <p className="text-2xl text-gray-300 mb-4">{track.artist}</p>
      {track.album && <p className="text-xl text-gray-400 mb-6">{track.album}</p>}
      <div className="flex gap-4 justify-center flex-wrap items-center">
        {track.genre && <span className="px-3 py-1 bg-purple-600 rounded-full">{track.genre}</span>}
        {track.year && <span className="px-3 py-1 bg-blue-600 rounded-full">{track.year}</span>}
        {track.bpm && <span className="px-3 py-1 bg-orange-600 rounded-full">{track.bpm} BPM</span>}
        {track.key_signature && <span className="px-3 py-1 bg-green-600 rounded-full">{track.key_signature}</span>}
        <EmojiTrackActions
          track={{ id: track.id, emojis: track.emojis }}
          onUpdate={onEmojiUpdate}
        />
      </div>
    </div>
  );
}
```

**Step 5: Update TrackDisplay usage**

Update where TrackDisplay is used (around line 220) to pass the handler and merged track:

```typescript
<TrackDisplay
  track={getTrackWithOverrides(currentTrack)}
  onEmojiUpdate={handleTrackEmojiUpdate}
/>
```

**Step 6: Verify in browser**

Run dev server, open PlaylistBuilder, verify:
- Emojis display inline with metadata badges
- "+ Add" button appears
- Clicking opens EmojiPicker
- Adding/removing emojis works

**Step 7: Commit**

```bash
git add web/frontend/src/pages/PlaylistBuilder.tsx
git commit -m "feat(builder): add emoji tagging to TrackDisplay"
```

---

## Task 4: Add emoji filter field to FilterEditor

**Files:**
- Modify: `web/frontend/src/components/builder/FilterEditor.tsx`
- Modify: `web/frontend/src/components/builder/filterUtils.ts`

**Step 1: Add emoji to field options**

In FilterEditor.tsx, add emoji to the field select (around line 103-111):

```typescript
<select
  id="field-select"
  value={field}
  onChange={(e) => {
    handleFieldChange(e.target.value);
    resetValidationError();
  }}
  className="w-full bg-slate-700 rounded px-3 py-2 text-white"
>
  <option value="">Choose field...</option>
  <option value="title">Title</option>
  <option value="artist">Artist</option>
  <option value="album">Album</option>
  <option value="genre">Genre</option>
  <option value="year">Year</option>
  <option value="bpm">BPM</option>
  <option value="key">Key</option>
  <option value="emoji">Emoji</option>
</select>
```

**Step 2: Add emoji operator section**

After the numeric operators section (around line 158), add:

```typescript
{field === 'emoji' && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label htmlFor="emoji-operator-select" className="text-xs text-gray-400 block mb-2">Condition</label>
    <select
      id="emoji-operator-select"
      value={operator}
      onChange={(e) => {
        setOperator(e.target.value);
        resetValidationError();
      }}
      className="w-full bg-slate-700 rounded px-3 py-2 text-white"
    >
      <option value="">Choose condition...</option>
      <option value="has">has emoji</option>
      <option value="not_has">does not have emoji</option>
    </select>
  </div>
)}
```

**Step 3: Add emoji value picker**

After the operator section, add emoji value input:

```typescript
{field === 'emoji' && operator && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label className="text-xs text-gray-400 block mb-2">Emoji</label>
    <EmojiValuePicker value={value} onChange={(v) => { setValue(v); resetValidationError(); }} />
  </div>
)}
```

**Step 4: Create EmojiValuePicker component**

Add at bottom of FilterEditor.tsx or as separate file:

```typescript
function EmojiValuePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [showPicker, setShowPicker] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowPicker(true)}
        className="w-full bg-slate-700 rounded px-3 py-2 text-white text-left"
      >
        {value || 'Select emoji...'}
      </button>
      {showPicker && (
        <EmojiPicker
          onSelect={(emoji) => { onChange(emoji); setShowPicker(false); }}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  );
}
```

**Step 5: Import EmojiPicker**

Add import at top:

```typescript
import { EmojiPicker } from '../EmojiPicker';
```

**Step 6: Update handleFieldChange for emoji**

Modify handleFieldChange to handle emoji field:

```typescript
const handleFieldChange = (newField: string) => {
  setField(newField);
  if (newField && operator) {
    const isNumericField = ['year', 'bpm'].includes(newField);
    const isEmojiField = newField === 'emoji';
    const isNumericOperator = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'].includes(operator);
    const isTextOperator = ['contains', 'equals', 'not_equals', 'starts_with', 'ends_with'].includes(operator);
    const isEmojiOperator = ['has', 'not_has'].includes(operator);

    if (isEmojiField && !isEmojiOperator) {
      setOperator('');
    } else if (isNumericField && !isNumericOperator) {
      setOperator('');
    } else if (!isNumericField && !isEmojiField && !isTextOperator) {
      setOperator('');
    }
  }
};
```

**Step 7: Update condition for text operators**

Update the condition on line 115 to exclude emoji:

```typescript
{field && ['title', 'artist', 'album', 'genre', 'key'].includes(field) && (
```

**Step 8: Commit**

```bash
git add web/frontend/src/components/builder/FilterEditor.tsx
git commit -m "feat(builder): add emoji filter field to FilterEditor"
```

---

## Task 5: Add emoji filter support to backend

**Files:**
- Modify: `src/music_minion/domain/playlists/filters.py`
- Modify: `src/music_minion/domain/playlists/builder.py`

**Step 1: Add emoji to VALID_FIELDS**

In filters.py, update VALID_FIELDS:

```python
VALID_FIELDS = {"title", "artist", "album", "genre", "year", "bpm", "key", "local_path", "emoji"}
```

**Step 2: Add EMOJI_OPERATORS**

Add after NUMERIC_OPERATORS:

```python
EMOJI_OPERATORS = {"has", "not_has"}
```

**Step 3: Update validate_filter**

Add emoji validation in validate_filter function:

```python
def validate_filter(field: str, operator: str, value: str) -> None:
    if field not in VALID_FIELDS:
        raise ValueError(f"Invalid field: {field}. Must be one of {VALID_FIELDS}")

    if field == "emoji":
        if operator not in EMOJI_OPERATORS:
            raise ValueError(
                f"Operator '{operator}' not valid for emoji field. "
                f"Use one of: {EMOJI_OPERATORS}"
            )
        # Value should be an emoji string (no additional validation needed)
        return

    # ... rest of existing validation
```

**Step 4: Update build_filter_query for emoji**

In build_filter_query, handle emoji field specially:

```python
for i, f in enumerate(filters):
    field = f["field"]
    operator = f["operator"]
    value = f["value"]

    # Handle emoji filters with subquery
    if field == "emoji":
        if operator == "has":
            where_parts.append(
                "EXISTS (SELECT 1 FROM track_emojis te WHERE te.track_id = t.id AND te.emoji_id = ?)"
            )
        else:  # not_has
            where_parts.append(
                "NOT EXISTS (SELECT 1 FROM track_emojis te WHERE te.track_id = t.id AND te.emoji_id = ?)"
            )
        params.append(value)
        continue

    # ... rest of existing logic
```

**Step 5: Test filter query**

Run Python REPL:
```python
from music_minion.domain.playlists.filters import build_filter_query
filters = [{"field": "emoji", "operator": "has", "value": "🔥", "conjunction": "AND"}]
print(build_filter_query(filters))
```

Expected: `('EXISTS (SELECT 1 FROM track_emojis te WHERE te.track_id = t.id AND te.emoji_id = ?)', ['🔥'])`

**Step 6: Commit**

```bash
git add src/music_minion/domain/playlists/filters.py
git commit -m "feat(builder): add emoji filter support to backend"
```

---

## Task 6: Update filterUtils validation (frontend)

**Files:**
- Modify: `web/frontend/src/components/builder/filterUtils.ts`

**Step 1: Read current file**

Check existing validation logic.

**Step 2: Add emoji to validateFilter**

Update validateFilter to accept emoji field:

```typescript
export function validateFilter(field: string, operator: string, value: string): string | null {
  if (!field) return 'Field is required';
  if (!operator) return 'Operator is required';
  if (!value) return 'Value is required';

  // Emoji field validation
  if (field === 'emoji') {
    if (!['has', 'not_has'].includes(operator)) {
      return 'Invalid operator for emoji field';
    }
    return null;
  }

  // ... rest of existing validation
}
```

**Step 3: Update getPlaceholder**

Add emoji case:

```typescript
export function getPlaceholder(field: string, operator: string): string {
  if (field === 'emoji') return 'Select an emoji';
  // ... rest of existing logic
}
```

**Step 4: Commit**

```bash
git add web/frontend/src/components/builder/filterUtils.ts
git commit -m "feat(builder): add emoji validation to filterUtils"
```

---

## Task 7: Integration testing

**Step 1: Start dev servers**

Run: `music-minion --web`

**Step 2: Test emoji tagging flow**

1. Open PlaylistBuilder for a manual playlist
2. Play a track
3. Click "+ Add" next to metadata badges
4. Select an emoji (e.g., 🔥)
5. Verify emoji appears inline
6. Click emoji to remove it
7. Verify removal works

**Step 3: Test emoji filter flow**

1. Add emoji to a few tracks
2. Open FilterPanel
3. Add filter: emoji → has → 🔥
4. Verify only tracks with 🔥 appear in candidates
5. Test "does not have" operator

**Step 4: Commit final changes**

```bash
git add -A
git commit -m "feat(builder): complete emoji integration testing"
```
