# Ideas

1. [8] SoundCloud + AI metadata enrichment with field-by-field approval
2. [2] Android browser notification shows current playing track metadata
3. [1] Keypad shortcuts for playlist-builder mode
4. [6] SoundCloud reposts sync and playlist-builder integrationsound
5. [3] Fix mobile comparison emoji picker
6. [2] Deduplicate play counts within time window (10-30 min)
7. [1] CRUD functions accept optional connection parameter

## 1. SoundCloud + AI Metadata Enrichment

**Context**: Track playback, metadata improvement workflow

**Idea**: When local track plays, automatically search for matching SoundCloud track (database first, then API), gather all metadata, send to AI (local or cloud) for metadata suggestions, present field-by-field approval UI.

**Components**:
- Providers: SoundCloud search (existing provider system)
- Matching: Database lookup → API search → fuzzy matching (TF-IDF)
- AI: Local LLM or cloud API integration (metadata analysis/suggestion)
- UI: Approval overlay showing current vs suggested metadata per field
- Metadata: Atomic write after approval

**Flow**:
1. Track starts playing
2. Search local SoundCloud database for match (title/artist)
3. If no match, query SoundCloud API
4. Compile metadata: local file + SoundCloud data
5. AI analyzes and suggests improvements (genre, tags, description, etc.)
6. Present field-by-field diff UI
7. User approves/rejects individual fields
8. Apply approved changes atomically

**Questions**:
- Which metadata fields should be updatable? (genre, tags, BPM, key, description?)
- Trigger automatically on play or manual button?
- Which AI model/API to use? (local vs cloud trade-offs)
- Confidence threshold for auto-suggestions vs requiring review?
- How to handle mismatches (SoundCloud track is different song)?

## 2. Android Browser Notification Shows Current Track Metadata

**Context**: Mobile web player (Android browser)

**Idea**: Use Media Session API to display current track information (title, artist, artwork) in Android's browser notification instead of generic "tab is playing" notification.

**Components**:
- Frontend: Media Session API integration (`navigator.mediaSession`)
- API: Metadata endpoint for current track
- Assets: Album artwork/thumbnail handling

**Implementation**:
- Set `navigator.mediaSession.metadata` with track title, artist, album, artwork
- Update on track changes
- Handle play/pause/skip controls in notification

**Questions**:
- Should notification controls (play/pause/skip) trigger API calls or use existing frontend state?
- How to handle artwork for tracks without album art? (fallback image?)

## 3. Keypad Shortcuts for Playlist-Builder Mode - 2026-02-15

Add numeric keypad shortcuts for common playlist-builder operations to speed up curation workflow.

**Context**: Blessed UI, playlist-builder keyboard event handlers (`ui/blessed/events/keys/builder.py`)

## 4. SoundCloud Reposts Sync and Playlist-Builder Integration - 2026-02-15

Auto-sync SoundCloud reposts (like `~/coding/soundcloud-discovery`) to keep an up-to-date list. Use playlist-builder to filter and curate monthly playlists (e.g., "Feb 26") from these reposts.

**Context**: SoundCloud provider, playlist-builder mode, cron job/sync system

**Components**:
- Cron job for periodic reposts sync
- SoundCloud track source in playlist-builder
- Filter/view for SoundCloud-only tracks
- Integration with existing playlist-builder UI

## 5. Fix Mobile Comparison Emoji Picker - 2026-02-17

Mobile comparison view: clicking emoji button stops the song, then emoji picker glitches (can't select emoji or close it). Likely interaction between swipe gestures and emoji picker popup.

**Context**: `web/frontend/src/components/ComparisonView.tsx`, `web/frontend/src/components/EmojiPicker.tsx`, `web/frontend/src/hooks/useSwipeGesture.ts`

## 6. Deduplicate Play Counts Within Time Window - 2026-02-22

Count all plays within a 10-30 minute window as a single play. Addresses false inflation from: going back and forth between tracks while comparing, and forgetting to stop playback (looping while focused elsewhere).

**Context**: `domain/radio/history.py`, play count calculation logic

## 7. CRUD Functions Accept Optional Connection Parameter - 2026-02-24

Add optional `conn` parameter to CRUD functions so FastAPI endpoints can pass their injected connection instead of each function opening its own. Fixes database lock contention at the architecture level.

**Context**: `domain/playlists/crud.py`, `web/backend/routers/*.py`, database locking during multi-operation endpoints

**Pattern**:
```python
def get_playlist_by_name(name: str, library: str = None, conn: Connection = None) -> Optional[dict]:
    def _query(c):
        cursor = c.execute("SELECT * FROM playlists WHERE name = ? AND library = ?", (name, library))
        return dict(cursor.fetchone()) if cursor.fetchone() else None

    if conn:
        return _query(conn)
    with get_db_connection() as c:
        return _query(c)
```

**Scope**: `create_playlist()`, `add_track_to_playlist()`, `get_playlist_by_name()`, `get_playlist_by_id()` - any CRUD function called from FastAPI endpoints that also use the injected `db` connection.

**Trade-off**: More invasive change but eliminates the root cause. Current workaround is inline SQL in endpoints.
