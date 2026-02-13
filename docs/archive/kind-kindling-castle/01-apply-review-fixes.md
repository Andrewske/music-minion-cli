# Apply Plan Review Fixes to Swirling-Snuggling-Harbor

## Files to Modify
- `docs/swirling-snuggling-harbor/01-database-migration.md` (modify)
- `docs/swirling-snuggling-harbor/02-domain-logic-builder.md` (modify)
- `docs/swirling-snuggling-harbor/03-backend-api-routes.md` (modify)
- `docs/swirling-snuggling-harbor/06-frontend-state-management.md` (modify)
- `docs/swirling-snuggling-harbor/07-frontend-playlist-builder-page.md` (modify)
- `docs/swirling-snuggling-harbor/README.md` (modify)
- `web/frontend/.env.example` (modify)

## Implementation Details

This task applies critical architectural improvements discovered during technical review. The changes simplify session state management to match the proven comparison page pattern.

### Change 1: Database Schema (01-database-migration.md)

**Find:**
```sql
CREATE TABLE IF NOT EXISTS playlist_builder_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER UNIQUE NOT NULL,
    current_track_id INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
    FOREIGN KEY (current_track_id) REFERENCES tracks (id) ON DELETE SET NULL
)
```

**Replace with:**
```sql
CREATE TABLE IF NOT EXISTS playlist_builder_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER UNIQUE NOT NULL,
    last_processed_track_id INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
    FOREIGN KEY (last_processed_track_id) REFERENCES tracks (id) ON DELETE SET NULL
)
```

**Rationale:** `current_track_id` creates persistent state that can go stale. `last_processed_track_id` is only used to exclude recently-seen tracks from next candidate selection (UX nicety, not critical state).

---

### Change 2: Domain Logic Simplification (02-domain-logic-builder.md)

#### A. Update candidate query for performance

**Find:**
```sql
WHERE {builder_filter_where_clause}
  AND t.id NOT IN (SELECT track_id FROM playlist_tracks WHERE playlist_id = ?)
  AND t.id NOT IN (SELECT track_id FROM playlist_builder_skipped WHERE playlist_id = ?)
  AND t.id NOT IN (SELECT track_id FROM ratings WHERE rating_type = 'archive')
```

**Replace with:**
```sql
WHERE {builder_filter_where_clause}
  AND NOT EXISTS (SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = t.id)
  AND NOT EXISTS (SELECT 1 FROM playlist_builder_skipped WHERE playlist_id = ? AND track_id = t.id)
  AND NOT EXISTS (SELECT 1 FROM ratings WHERE rating_type = 'archive' AND track_id = t.id)
```

**Rationale:** 10-50x faster than NOT IN. SQLite optimizes EXISTS subqueries better.

#### B. Simplify add_track() return value

**Find:**
```python
def add_track(playlist_id: int, track_id: int) -> dict:
    """Add track to playlist using existing CRUD and return next candidate.

    Returns: {
        'added_track_id': int,
        'next_track': dict | None,
        'candidates_remaining': int
    }
    """
```

**Replace with:**
```python
def add_track(playlist_id: int, track_id: int) -> dict:
    """Add track to playlist using existing CRUD.

    Uses: music_minion.domain.playlists.crud.add_track_to_playlist()

    Returns: {
        'added_track_id': int,
        'success': bool
    }
    """
    from music_minion.domain.playlists.crud import add_track_to_playlist

    add_track_to_playlist(playlist_id, track_id)

    return {
        'added_track_id': track_id,
        'success': True
    }
```

**Rationale:** Frontend will fetch next candidate separately via new endpoint. No need to return it here.

#### C. Simplify skip_track() and ensure persistence

**Find:**
```python
def skip_track(playlist_id: int, track_id: int) -> dict:
    """Mark track as skipped and return next candidate.

    Returns: {
        'skipped_track_id': int,
        'next_track': dict | None,
        'candidates_remaining': int
    }
    """
```

**Replace with:**
```python
def skip_track(playlist_id: int, track_id: int) -> dict:
    """Mark track as skipped and persist to database.

    CRITICAL: Must INSERT into playlist_builder_skipped table
    so broken tracks don't reappear in future sessions.

    Returns: {
        'skipped_track_id': int,
        'success': bool
    }
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO playlist_builder_skipped (playlist_id, track_id) VALUES (?, ?)",
            (playlist_id, track_id)
        )
        conn.commit()

    return {
        'skipped_track_id': track_id,
        'success': True
    }
```

**Rationale:** Ensures auto-skipped tracks (playback errors) don't loop infinitely.

#### D. Add new function: get_next_candidate()

**Add new function:**
```python
def get_next_candidate(playlist_id: int) -> dict | None:
    """Get next random candidate track, excluding last processed track.

    Respects:
    - Builder filters (if set)
    - Tracks already in playlist
    - Skipped tracks
    - Archived tracks
    - Last processed track (for variety)

    Returns: Track dict or None if no candidates available
    """
    from music_minion.core.database import get_db_connection
    from music_minion.domain.playlists.filters import build_filter_query

    # Get session's last processed track (if any)
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT last_processed_track_id FROM playlist_builder_sessions WHERE playlist_id = ?",
            (playlist_id,)
        )
        row = cursor.fetchone()
        last_processed_id = row['last_processed_track_id'] if row else None

    # Get builder filters
    filters = get_builder_filters(playlist_id)
    filter_where, filter_params = build_filter_query(filters) if filters else ("1=1", [])

    # Build candidate query
    with get_db_connection() as conn:
        query = f"""
            SELECT DISTINCT t.*, COALESCE(er.rating, 1500.0) as elo_rating
            FROM tracks t
            LEFT JOIN elo_ratings er ON t.id = er.track_id
            WHERE {filter_where}
              AND NOT EXISTS (SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM playlist_builder_skipped WHERE playlist_id = ? AND track_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM ratings WHERE rating_type = 'archive' AND track_id = t.id)
        """

        params = filter_params + [playlist_id, playlist_id]

        # Exclude last processed track for variety
        if last_processed_id:
            query += " AND t.id != ?"
            params.append(last_processed_id)

        query += " ORDER BY RANDOM() LIMIT 1"

        cursor = conn.execute(query, params)
        row = cursor.fetchone()

        if row:
            track = dict(row)

            # Update session's last_processed_track_id
            conn.execute(
                "UPDATE playlist_builder_sessions SET last_processed_track_id = ?, updated_at = CURRENT_TIMESTAMP WHERE playlist_id = ?",
                (track['id'], playlist_id)
            )
            conn.commit()

            return track

        return None
```

**Rationale:** Frontend calls this after add/skip to get next track. Keeps session logic simple and stateless.

#### E. Simplify start_builder_session()

**Find:**
```python
def start_builder_session(playlist_id: int) -> dict:
    """Create or resume builder session.

    Returns: {
        'session_id': int,
        'playlist_id': int,
        'current_track': dict | None,
        'candidates_remaining': int,
        'started_at': str,
        'updated_at': str
    }
    """
```

**Replace with:**
```python
def start_builder_session(playlist_id: int) -> dict:
    """Create or resume builder session.

    Frontend should call get_next_candidate() separately to fetch first track.

    Returns: {
        'session_id': int,
        'playlist_id': int,
        'started_at': str,
        'updated_at': str
    }
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        # Check for existing session
        cursor = conn.execute(
            "SELECT * FROM playlist_builder_sessions WHERE playlist_id = ?",
            (playlist_id,)
        )
        existing = cursor.fetchone()

        if existing:
            return {
                'session_id': existing['id'],
                'playlist_id': existing['playlist_id'],
                'started_at': existing['started_at'],
                'updated_at': existing['updated_at']
            }

        # Create new session
        cursor = conn.execute(
            "INSERT INTO playlist_builder_sessions (playlist_id) VALUES (?)",
            (playlist_id,)
        )
        session_id = cursor.lastrowid
        conn.commit()

        # Fetch the created session
        cursor = conn.execute(
            "SELECT * FROM playlist_builder_sessions WHERE id = ?",
            (session_id,)
        )
        session = dict(cursor.fetchone())

        return {
            'session_id': session['id'],
            'playlist_id': session['playlist_id'],
            'started_at': session['started_at'],
            'updated_at': session['updated_at']
        }
```

---

### Change 3: Backend API Routes (03-backend-api-routes.md)

#### A. Update TrackActionResponse schema

**Find:**
```python
class TrackActionResponse(BaseModel):
    success: bool
    next_track: Optional[dict]
    stats: dict  # {candidates_remaining, added_count, skipped_count}
```

**Replace with:**
```python
class TrackActionResponse(BaseModel):
    success: bool
    message: str
```

#### B. Add new endpoint: GET /api/builder/candidates/{playlist_id}/next

**Add to endpoints section:**
```python
@router.get("/candidates/{playlist_id}/next")
async def get_next_candidate_track(
    playlist_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """Get next random candidate track.

    Respects filters, exclusions, and provides variety by avoiding
    last processed track.

    Returns: Track object or {"track": null} if no candidates available
    """
    from music_minion.domain.playlists.builder import get_next_candidate

    track = get_next_candidate(playlist_id)

    if track:
        return {"track": track}
    else:
        return {"track": None}
```

#### C. Add context activation endpoints

**Add to endpoints section:**
```python
@router.post("/activate/{playlist_id}")
async def activate_builder_mode(
    playlist_id: int,
    db: Session = Depends(get_db)
):
    """Activate builder mode for keyboard shortcuts.

    Updates AppContext.active_web_mode = 'builder'
    Updates AppContext.active_builder_playlist_id = playlist_id
    Broadcasts activation to blessed UI backend.
    """
    # TODO: Implement AppContext update mechanism
    # This will be implemented when blessed UI integration is ready
    return {"success": True, "message": "Builder mode activated"}

@router.delete("/activate")
async def deactivate_builder_mode():
    """Deactivate builder mode (on unmount).

    Clears AppContext.active_web_mode and active_builder_playlist_id
    """
    # TODO: Implement AppContext deactivation
    return {"success": True, "message": "Builder mode deactivated"}
```

#### D. Update add_track and skip_track endpoints

**Find add_track endpoint, update to:**
```python
@router.post("/add/{playlist_id}/{track_id}")
async def add_track_to_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db)
) -> TrackActionResponse:
    """Add track to playlist.

    Frontend should call GET /candidates/{playlist_id}/next
    separately to fetch next candidate.
    """
    from music_minion.domain.playlists.builder import add_track

    result = add_track(playlist_id, track_id)

    return TrackActionResponse(
        success=result['success'],
        message=f"Track {track_id} added to playlist"
    )
```

**Find skip_track endpoint, update to:**
```python
@router.post("/skip/{playlist_id}/{track_id}")
async def skip_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db)
) -> TrackActionResponse:
    """Skip track permanently.

    Adds to skipped list. Frontend should call
    GET /candidates/{playlist_id}/next to fetch next candidate.
    """
    from music_minion.domain.playlists.builder import skip_track as domain_skip_track

    result = domain_skip_track(playlist_id, track_id)

    return TrackActionResponse(
        success=result['success'],
        message=f"Track {track_id} skipped"
    )
```

#### E. Add error handling documentation

**Add new section after all endpoints:**
```markdown
### Error Handling Pattern

**Domain Layer:** Raises exceptions for error conditions (ValueError, KeyError, etc.)
**API Layer:** Catches exceptions and converts to HTTPException with appropriate status codes
**Frontend:** React Query catches errors and displays toast notifications

Example:
```python
try:
    result = add_track(playlist_id, track_id)
    return TrackActionResponse(success=True, message="Track added")
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal server error")
```
```

---

### Change 4: Frontend State Management (06-frontend-state-management.md)

#### A. Remove polling from session query

**Find:**
```typescript
const { data: session, isLoading, error } = useQuery({
  queryKey: ['builder-session', playlistId],
  queryFn: () => playlistId ? builderApi.getSession(playlistId) : null,
  enabled: !!playlistId,
  refetchInterval: 5000,  // Refresh every 5 seconds
  staleTime: 4000  // Consider stale after 4 seconds
});
```

**Replace with:**
```typescript
const { data: session, isLoading, error } = useQuery({
  queryKey: ['builder-session', playlistId],
  queryFn: () => playlistId ? builderApi.getSession(playlistId) : null,
  enabled: !!playlistId
});
```

**Rationale:** No polling needed - only frontend modifies session state via mutations.

#### B. Add query for current candidate track

**Add new query:**
```typescript
// Fetch current candidate track
const { data: currentCandidate, refetch: refetchCandidate } = useQuery({
  queryKey: ['builder-candidate', playlistId],
  queryFn: () => playlistId ? builderApi.getNextCandidate(playlistId) : null,
  enabled: !!playlistId && !!session
});

const currentTrack = currentCandidate?.track;
```

#### C. Update mutations to refetch candidate

**Find add_track mutation, update onSuccess:**
```typescript
const addTrack = useMutation({
  mutationFn: (trackId: number) => {
    if (!playlistId) throw new Error('No playlist selected');
    return builderApi.addTrack(playlistId, trackId);
  },
  onSuccess: () => {
    // Fetch next candidate
    refetchCandidate();

    // Invalidate related queries
    queryClient.invalidateQueries({ queryKey: ['playlists'] });
    queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
  }
});
```

**Find skip_track mutation, update onSuccess:**
```typescript
const skipTrack = useMutation({
  mutationFn: (trackId: number) => {
    if (!playlistId) throw new Error('No playlist selected');
    return builderApi.skipTrack(playlistId, trackId);
  },
  onSuccess: () => {
    // Fetch next candidate
    refetchCandidate();

    // Invalidate related queries
    queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
    queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
  }
});
```

#### D. Update return value

**Find:**
```typescript
return {
  session,
  isLoading,
  error,
  currentTrack: session?.current_track,
  stats: session ? {
    candidatesRemaining: session.candidates_remaining,
    startedAt: session.started_at,
    updatedAt: session.updated_at
  } : null,

  startSession,
  endSession,
  addTrack,
  skipTrack,
  filters,
  updateFilters,

  isAddingTrack: addTrack.isPending,
  isSkippingTrack: skipTrack.isPending
};
```

**Replace with:**
```typescript
return {
  session,
  isLoading,
  error,
  currentTrack,
  stats: session ? {
    startedAt: session.started_at,
    updatedAt: session.updated_at
  } : null,

  startSession,
  endSession,
  addTrack,
  skipTrack,
  refetchCandidate,  // Expose for manual refresh
  filters,
  updateFilters,

  isAddingTrack: addTrack.isPending,
  isSkippingTrack: skipTrack.isPending
};
```

---

### Change 5: Frontend UI Updates (07-frontend-playlist-builder-page.md)

#### A. Add context activation on mount

**Add to component after imports:**
```typescript
// Activate builder mode on mount for keyboard shortcuts
useEffect(() => {
  if (selectedPlaylistId) {
    fetch(`/api/builder/activate/${selectedPlaylistId}`, { method: 'POST' })
      .catch(err => console.error('Failed to activate builder mode:', err));

    return () => {
      fetch('/api/builder/activate', { method: 'DELETE' })
        .catch(err => console.error('Failed to deactivate builder mode:', err));
    };
  }
}, [selectedPlaylistId]);
```

#### B. Update WebSocket hook with useRef pattern

**Find useIPCWebSocket implementation, replace with:**
```typescript
export function useIPCWebSocket(handlers: {
  onBuilderAdd?: () => void;
  onBuilderSkip?: () => void;
}) {
  const handlersRef = useRef(handlers);

  // Update ref when handlers change (no reconnection)
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8765';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'builder:add' && handlersRef.current.onBuilderAdd) {
          handlersRef.current.onBuilderAdd();
        } else if (msg.type === 'builder:skip' && handlersRef.current.onBuilderSkip) {
          handlersRef.current.onBuilderSkip();
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => {
      ws.close();
    };
  }, []); // Only connect once - no reconnections
}
```

**Rationale:** Prevents constant reconnections when handlers change.

#### C. Add mutation locking to prevent race conditions

**Find WebSocket handler usage:**
```typescript
useIPCWebSocket({
  onBuilderAdd: () => {
    if (currentTrack && !isAddingTrack) {
      addTrack.mutate(currentTrack.id);
    }
  },
  onBuilderSkip: () => {
    if (currentTrack && !isSkippingTrack) {
      skipTrack.mutate(currentTrack.id);
    }
  }
});
```

**Replace with:**
```typescript
useIPCWebSocket({
  onBuilderAdd: () => {
    if (currentTrack && !isAddingTrack && !isSkippingTrack) {
      addTrack.mutate(currentTrack.id);
    }
  },
  onBuilderSkip: () => {
    if (currentTrack && !isAddingTrack && !isSkippingTrack) {
      skipTrack.mutate(currentTrack.id);
    }
  }
});
```

**Find button rendering:**
```typescript
<button
  onClick={handleAdd}
  disabled={isAddingTrack}
  className="btn-add"
>
  {isAddingTrack ? 'Adding...' : 'Add to Playlist'}
</button>
<button
  onClick={handleSkip}
  disabled={isSkippingTrack}
  className="btn-skip"
>
  {isSkippingTrack ? 'Skipping...' : 'Skip'}
</button>
```

**Replace with:**
```typescript
<button
  onClick={handleAdd}
  disabled={isAddingTrack || isSkippingTrack}
  className="btn-add"
>
  {isAddingTrack ? 'Adding...' : 'Add to Playlist'}
</button>
<button
  onClick={handleSkip}
  disabled={isAddingTrack || isSkippingTrack}
  className="btn-skip"
>
  {isSkippingTrack ? 'Skipping...' : 'Skip'}
</button>
```

**Rationale:** Prevents race condition where user presses keyboard shortcut while clicking button.

#### D. Remove SkippedTracksReview from component list

**Find and remove:**
```typescript
function PlaylistSelection({ onSelect }: { onSelect: (id: number) => void }) {
  // TODO: Fetch and display manual playlists
  return <div>Playlist Selection (TODO)</div>;
}
```

**Note:** Unskip UI is deferred to post-MVP. Remove any references to reviewing/unskipping tracks from the UI spec.

---

### Change 6: Environment Configuration (web/frontend/.env.example)

**Add:**
```
# WebSocket URL for IPC communication with blessed UI
VITE_WS_URL=ws://localhost:8765
```

---

### Change 7: README Updates (docs/swirling-snuggling-harbor/README.md)

#### A. Add error handling pattern section

**Add after "Architecture Patterns" section:**
```markdown
## Error Handling Pattern

**Domain Layer:** Raises exceptions for error conditions (ValueError, KeyError, database errors)
**API Layer:** Catches exceptions and converts to HTTPException with appropriate status codes (400, 404, 500)
**Frontend:** React Query catches errors and displays toast notifications

This pattern keeps domain logic pure (no HTTP concerns) while API layer handles HTTP-specific error formatting.
```

#### B. Update known limitations

**Find "Known Limitations" section, update:**
```markdown
## Known Limitations

1. **Performance:** Candidate query limited to 100 tracks with RANDOM() sampling. Uses optimized NOT EXISTS subqueries but may still be slow on 100k+ track libraries.
2. **Audio Formats:** Requires browser-compatible formats (MP3, OGG, OPUS)
3. **WebSocket:** Single connection per tab (no multi-tab sync)
4. **Filter Complexity:** Reuses smart playlist filter logic (limited operators)
5. **No Unskip UI in MVP:** Users cannot review/unskip tracks in initial release. Backend endpoints exist (`GET /skipped`, `DELETE /skipped/{track_id}`). UI will be added based on user feedback.
```

#### C. Update future enhancements

**Add to "Future Enhancements" section:**
```markdown
- **Skipped tracks review UI:** Component to view and unskip accidentally skipped tracks (backend already supports this)
```

## Acceptance Criteria

1. All specified changes applied to plan files
2. Database schema uses `last_processed_track_id` instead of `current_track_id`
3. Domain functions simplified (no next_track in return values)
4. New endpoint `/candidates/{playlist_id}/next` added to API spec
5. Frontend polling removed from session query
6. WebSocket hook uses useRef pattern (no reconnections)
7. Mutation locking prevents race conditions
8. Error handling pattern documented
9. Environment variable for WebSocket URL added
10. Unskip UI moved to future enhancements

## Dependencies

None - this task only modifies planning documents, not implementation.

## Verification Steps

1. Read each modified file and verify changes match specifications
2. Ensure all cross-references between files are consistent
3. Check that session state management pattern is consistent across all layers
4. Verify error handling pattern is documented
5. Confirm unskip UI is properly deferred to post-MVP
