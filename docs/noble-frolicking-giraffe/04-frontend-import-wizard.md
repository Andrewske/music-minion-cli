---
task: 04-frontend-import-wizard
status: done
depends:
  - 03-frontend-settings-tab
files:
  - path: web/frontend/src/components/Settings/SoundCloudImportSection.tsx
    action: create
  - path: web/frontend/src/components/Settings/TrackSearchAutocomplete.tsx
    action: create
  - path: web/frontend/src/api/soundcloud.ts
    action: modify
---

# Frontend: SoundCloud Import Wizard

## Context
The main import wizard component with playlist selection, match review, and playlist creation. Uses local state with `useReducer` (no Zustand store). This is the core UI for the feature.

## Files to Modify/Create
- `web/frontend/src/components/Settings/SoundCloudImportSection.tsx` (new)
- `web/frontend/src/components/Settings/TrackSearchAutocomplete.tsx` (new)
- `web/frontend/src/api/soundcloud.ts` (modify - add API functions)

## Implementation Details

### TypeScript Types

```typescript
interface ScPlaylistMatch {
  scTrackId: string;
  scTitle: string;
  scArtist: string;
  localTrackId: number | null;
  localTitle: string | null;
  localArtist: string | null;
  confidence: number;
  isApproved: boolean;  // From backend (confidence >= 0.85)
  isMissing: boolean;   // User marked as missing
  scPosition?: number;
  // Frontend-only state (not sent to backend):
  isFixed?: boolean;    // User manually corrected this match
}

interface ImportState {
  step: 'select' | 'matching' | 'review' | 'confirm' | 'done' | 'error';
  playlists: SoundCloudPlaylist[];
  selectedPlaylistId: string | null;
  playlistName: string;
  matches: ScPlaylistMatch[];
  error: string | null;
}

type ImportAction =
  | { type: 'SET_PLAYLISTS'; playlists: SoundCloudPlaylist[] }
  | { type: 'SELECT_PLAYLIST'; id: string }
  | { type: 'START_MATCHING' }
  | { type: 'MATCHING_COMPLETE'; matches: ScPlaylistMatch[]; playlistName: string }
  | { type: 'FIX_MATCH'; scTrackId: string; localTrackId: number; localTitle: string; localArtist: string }
  | { type: 'MARK_MISSING'; scTrackId: string }
  | { type: 'UPDATE_PLAYLIST_NAME'; name: string }
  | { type: 'PROCEED_TO_CONFIRM' }
  | { type: 'CREATE_SUCCESS'; playlistId: number }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'RESET' };
```

### Component Structure

```
SoundCloudImportSection
├── Step: select
│   ├── Playlist dropdown (fetches on mount)
│   └── "Start Import" button
├── Step: matching
│   └── Loading spinner with "Matching tracks..."
├── Step: review
│   ├── Stats: "X auto-approved, Y need review"
│   ├── Match table (only <0.85 confidence)
│   │   ├── SC Track column
│   │   ├── Local Match column (or "No match")
│   │   ├── Confidence column (color-coded)
│   │   └── Actions: Fix | Mark Missing
│   └── "Continue" button
├── Step: confirm
│   ├── Summary: "42 matched, 3 missing, 2 manually fixed, 5 unreviewed"
│   ├── Warning if unreviewed > 0: "5 low-confidence matches included as-is"
│   ├── Playlist name input (pre-populated)
│   └── "Create Playlist" button
└── Step: done
    ├── Success message with playlist link
    └── "Import Another" button
```

### Match Review Table

- Shows matches where `isApproved === false` (needs review)
- Sorted by confidence ascending (lowest first)
- Color-coded confidence:
  - Yellow (0.70-0.84): `bg-yellow-500/20`
  - Red (<0.70): `bg-red-500/20`
  - Gray (no match): `bg-gray-500/20`
- "Fix" button opens TrackSearchAutocomplete inline or in popover
- "Mark Missing" shows row with strikethrough + "Undo" button (not removed from view)
- **Continue button always enabled** - user can proceed without reviewing all

**Unreviewed matches:** Matches with `isApproved === false && isMissing === false && !isFixed` are included as-is when continuing. Summary shows count.

### TrackSearchAutocomplete Component

```tsx
interface TrackSearchAutocompleteProps {
  onSelect: (track: { id: number; title: string; artist: string }) => void;
  onCancel: () => void;
}
```

- Debounced input (300ms)
- Fetches from `GET /api/tracks/search?q={query}`
- Shows results as dropdown/list
- Click result calls `onSelect`

### API Functions (soundcloud.ts)

```typescript
export async function getSoundCloudPlaylists(): Promise<SoundCloudPlaylist[]>
export async function matchPlaylist(playlistId: string): Promise<MatchPlaylistResponse>
export async function createPlaylistFromMatches(request: CreatePlaylistRequest): Promise<CreatePlaylistResponse>
```

### State Flow

1. **Mount**: Fetch playlists, populate dropdown
2. **Select + Start**: Dispatch `START_MATCHING`, call `matchPlaylist()`
3. **Matching done**: Dispatch `MATCHING_COMPLETE` with matches
4. **Fix match**: Dispatch `FIX_MATCH` → updates match, sets `isFixed: true`, `isApproved: true`
5. **Mark missing**: Dispatch `MARK_MISSING` → sets `isMissing: true` (row stays visible with strikethrough)
6. **Undo missing**: Dispatch `UNDO_MISSING` → sets `isMissing: false`
7. **Continue**: Dispatch `PROCEED_TO_CONFIRM` (always enabled, no validation)
8. **Create**: Call API with all non-missing matches, dispatch `CREATE_SUCCESS`

**Add action type:**
```typescript
| { type: 'UNDO_MISSING'; scTrackId: string }
```

## Verification

1. Navigate to `/settings?tab=soundcloud`
2. Dropdown shows SoundCloud playlists
3. Select playlist, click "Start Import"
4. Spinner shows during matching
5. Only low-confidence matches shown in review
6. Click "Fix" → search autocomplete appears → select track → row updates
7. Click "Mark Missing" → row removed from review
8. "Continue" → summary shows correct counts
9. Edit name if needed, click "Create Playlist"
10. Success message with link to new playlist
