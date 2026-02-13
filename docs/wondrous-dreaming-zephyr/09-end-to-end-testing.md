# End-to-End Integration Testing

## Files to Test
All previously implemented components working together

## Testing Scenarios

### 1. Database Verification

```bash
# Check schema version
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM schema_version"
# Expected: version = 31

# Check initial emoji seeding
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT COUNT(*) FROM emoji_metadata"
# Expected: 50

# Verify tables exist
sqlite3 ~/.local/share/music-minion/music_minion.db ".tables"
# Expected: track_emojis and emoji_metadata present

# Check indexes
sqlite3 ~/.local/share/music-minion/music_minion.db ".indexes"
# Expected: All 4 emoji-related indexes present
```

### 2. Backend API Testing

```bash
# Start backend
uv run music-minion --web

# Test top emojis endpoint
curl http://localhost:8642/api/emojis/top?limit=10
# Expected: JSON array of 10 emoji objects

# Test search endpoint
curl "http://localhost:8642/api/emojis/search?q=fire"
# Expected: 🔥 and related emojis

# Test all emojis
curl http://localhost:8642/api/emojis/all
# Expected: All 50 seeded emojis

# Test adding emoji to track (get track ID from now-playing first)
TRACK_ID=$(curl -s http://localhost:8642/api/radio/now-playing | jq '.track.id')
curl -X POST http://localhost:8642/api/emojis/tracks/$TRACK_ID/emojis \
  -H "Content-Type: application/json" \
  -d '{"emoji_unicode": "🔥"}'
# Expected: {"success": true}

# Verify emoji in now-playing
curl http://localhost:8642/api/radio/now-playing | jq '.track.emojis'
# Expected: ["🔥"]

# Test removing emoji
curl -X DELETE "http://localhost:8642/api/emojis/tracks/$TRACK_ID/emojis/%F0%9F%94%A5"
# Expected: {"success": true}
```

### 3. Frontend UI Testing

**RadioPlayer Integration:**
1. Open http://localhost:5173
2. RadioPlayer shows current track
3. Emoji reactions section visible below track info
4. "+ Add" button present
5. Click "+ Add" → picker modal opens
6. Click "🔥" emoji → modal closes, badge appears
7. Click "🔥" badge → badge disappears
8. Add multiple emojis → all show as badges
9. Badges wrap to multiple rows if many emojis

**Emoji Picker:**
1. Open picker from RadioPlayer
2. "Most Used" section shows top 50 emojis in grid
3. "All Emojis" section shows full grid below
4. Type "fire" in search → results filter to fire-related emojis
5. Top 50 section hides during search
6. Clear search → both sections visible again
7. Hover over emoji → tooltip shows name
8. Click emoji → picker closes and emoji added

**Emoji Settings Page:**
1. Click "Emojis" in navigation
2. Settings page shows table of all emojis
3. Table has columns: Emoji, Default Name, Custom Name, Uses, Actions
4. Click "Edit" on 🔥 → input appears
5. Type "banger" → click "Save" → custom name persists
6. Reload page → custom name still shows
7. Click "Cancel" during edit → changes discarded

**Search with Custom Names:**
1. In settings, set custom name "banger" for 🔥
2. Go back to RadioPlayer
3. Open emoji picker
4. Search "banger" → 🔥 appears in results
5. Search "fire" → 🔥 still appears (default name)

### 4. Adaptive Top 50 Testing

```bash
# Add emoji 🎯 to 5 different tracks
for i in {1..5}; do
  # You'll need to manually play different tracks and add 🎯 to each
  # Or use API with different track IDs
  curl -X POST http://localhost:8642/api/emojis/tracks/$TRACK_ID/emojis \
    -H "Content-Type: application/json" \
    -d '{"emoji_unicode": "🎯"}'
done

# Check use_count
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT emoji_unicode, use_count FROM emoji_metadata ORDER BY use_count DESC LIMIT 5"
# Expected: 🎯 has use_count = 5

# Open emoji picker
# Expected: 🎯 appears at top of "Most Used" section
```

### 5. Persistence Testing

1. Add emoji to track A
2. Navigate to different track B
3. Navigate back to track A
4. Verify emoji still shows on track A

### 6. Error Handling

**Duplicate Add:**
- Add "🔥" to track
- Add "🔥" again to same track
- Verify: Badge doesn't duplicate, use_count doesn't double-increment

**Empty Custom Name:**
- In settings, clear custom name (empty string)
- Save
- Verify: Custom name shows "None" (italic gray)

**Non-existent Track:**
```bash
curl -X POST http://localhost:8642/api/emojis/tracks/99999/emojis \
  -H "Content-Type: application/json" \
  -d '{"emoji_unicode": "🔥"}'
# Expected: Error response (track not found or foreign key constraint)
```

## Acceptance Criteria
- [ ] All database checks pass
- [ ] All backend API tests pass
- [ ] RadioPlayer shows and hides emojis correctly
- [ ] Emoji picker opens, searches, and selects emojis
- [ ] Settings page allows editing custom names
- [ ] Custom names appear in search results
- [ ] Top 50 adapts based on usage
- [ ] Emojis persist across track changes
- [ ] No duplicate emojis on single track
- [ ] No console errors in browser
- [ ] No backend errors in logs

## Dependencies
- All previous tasks (01-07) must be complete
