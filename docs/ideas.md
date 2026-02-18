# Ideas

1. Clickable genre tags with popularity-sorted overlay for multi-genre selection
2. Genre settings page for mass rename/merge operations
3. SoundCloud + AI metadata enrichment with field-by-field approval
4. Android browser notification shows current playing track metadata
5. Keypad shortcuts for playlist-builder mode
6. SoundCloud reposts sync and playlist-builder integration

## 1. Clickable Genre Tags with Popularity Overlay

**Context**: Playlist builder, track viewer, anywhere genre tags display

**Idea**: Click on genre tag to open overlay showing all genres sorted by popularity (usage count in local library). Select to change track's main genre.

**Components**:
- UI: Blessed overlay/popup component
- Data: Genre statistics query (count by tag usage)
- Metadata: Genre update handler (Mutagen atomic write)

**Questions**:
- Should this also allow adding secondary genres, or only change primary?
    - Answer: Would be awesome to be able to select multiple genres, but have selections numbered so the first genre you click is 1, then 2, then 3, ect... if there is an existing genre it would be 1 and you need to click that to remove it and select a new 1. Selected genres will show at the top of the overlay and be removed from the genre list in order.
- Should popularity show absolute counts or percentages?
    - Answer: We don't even need to show popularity, it's just for sorting.

## 2. Genre Settings Page

**Context**: Settings/management view for library-wide genre cleanup

**Idea**: Dedicated page showing all genres with track counts. Inline editing of genre names triggers mass update across all affected tracks. Renaming to existing genre merges them automatically (e.g., "dubstep" → "Dubstep" merges both, removes "dubstep" from list).

**Components**:
- UI: Settings page with sortable genre list
- Data: Genre statistics with track counts
- Operations: Bulk genre rename/merge (atomic file operations for all affected tracks)
- Conflict handling: Auto-merge detection when renamed genre matches existing

**Behavior**:
- Show genre + count (e.g., "dubstep (15 tracks)")
- Edit inline → mass update all tracks
- Merge if target genre exists → combined count, old genre removed from list

## 3. SoundCloud + AI Metadata Enrichment

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

## 4. Android Browser Notification Shows Current Track Metadata

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

## 5. Keypad Shortcuts for Playlist-Builder Mode - 2026-02-15

Add numeric keypad shortcuts for common playlist-builder operations to speed up curation workflow.

**Context**: Blessed UI, playlist-builder keyboard event handlers (`ui/blessed/events/keys/builder.py`)

## 6. SoundCloud Reposts Sync and Playlist-Builder Integration - 2026-02-15

Auto-sync SoundCloud reposts (like `~/coding/soundcloud-discovery`) to keep an up-to-date list. Use playlist-builder to filter and curate monthly playlists (e.g., "Feb 26") from these reposts.

**Context**: SoundCloud provider, playlist-builder mode, cron job/sync system

**Components**:
- Cron job for periodic reposts sync
- SoundCloud track source in playlist-builder
- Filter/view for SoundCloud-only tracks
- Integration with existing playlist-builder UI

## 7. Fix Mobile Comparison Emoji Picker - 2026-02-17

Mobile comparison view: clicking emoji button stops the song, then emoji picker glitches (can't select emoji or close it). Likely interaction between swipe gestures and emoji picker popup.

**Context**: `web/frontend/src/components/ComparisonView.tsx`, `web/frontend/src/components/EmojiPicker.tsx`, `web/frontend/src/hooks/useSwipeGesture.ts`

## 8. True Shuffle with Rolling 100-Track Window - 2026-02-18

Implement proper shuffle that maintains a rolling window of ~100 tracks to avoid repeating recently played songs. Current shuffle likely picks randomly each time without history awareness.

**Context**: `domain/playback/` shuffle logic, playerStore, queue management
