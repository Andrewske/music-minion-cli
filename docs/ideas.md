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

## 8. Waveform Loading Inconsistent on Deployed Web UI - 2026-03-02

Waveform frequently fails to load on deployed web UI but works consistently in dev server. Likely related to production build differences, asset paths, or CORS/proxy configuration.

**Context**: `web/backend/waveform.py`, frontend waveform component, Vite build/deploy config

## 9. SoundCloud Import Downloads Missing Tracks via scdl - 2026-03-02

Extend SoundCloud import to automatically download tracks using `scdl` when no local match exists. Import would: check for match → if none found, download via scdl → then import the downloaded file.

**Context**: `domain/library/providers/soundcloud/`, existing TF-IDF matching logic, scdl CLI tool

## 10. Tie Buckets to Playlists in Playlist Organizer - 2026-03-02

Link a bucket in the playlist organizer to an actual playlist. When tracks are assigned to a bucket, they'd automatically sync to the associated playlist.

**Context**: Playlist organizer UI, bucket system, playlist CRUD

## 11. Playlist Organizer Bucket Click Resets Seekbar - 2026-03-05

Clicking a bucket to add a song resets the seekbar to 0 even though the audio keeps playing. Visual-only bug - playback continues normally but progress display breaks.

**Context**: `web/frontend/src/pages/PlaylistOrganizer.tsx`, `web/frontend/src/hooks/usePlaylistOrganizer.ts`, PlayerBar seekbar component

## 12. Bucket-to-Playlist Linking in Playlist Organizer - 2026-03-05

Allow buckets in playlist organizer to be linked to actual playlists. Options: create new playlist from bucket, or link to existing playlist (names don't need to match). When a track is added to a bucket, it syncs to the linked playlist.

**Inverse sync**: If a track is added to the linked playlist through other means and that track exists in the parent playlist being organized, it should appear in the bucket. Bucket shows intersection of (linked playlist) AND (parent playlist) - not all linked playlist tracks.

**Example**: Organizing "EDM" playlist with "dubstep" bucket linked to "Dubstep" playlist. Adding track to bucket → appears in Dubstep playlist. Track added to Dubstep playlist elsewhere → shows in dubstep bucket IF it's also in EDM. Tracks in Dubstep but not in EDM don't appear in bucket.

**Context**: `web/frontend/src/pages/PlaylistOrganizer.tsx`, `web/frontend/src/hooks/usePlaylistOrganizer.ts`, bucket system, playlist CRUD

## 13. Multiple Organizer Sessions with Dropdown Selection - 2026-03-05

Support multiple named playlist-organizer sessions selectable via dropdown. Default session always exists, plus button to create new sessions. Each session has its own buckets and track assignments. Switch between sessions at any time.

**Context**: `web/frontend/src/pages/PlaylistOrganizer.tsx`, `web/frontend/src/hooks/usePlaylistOrganizer.ts`, session state persistence

