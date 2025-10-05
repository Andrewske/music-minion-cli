# Playlist Analytics Feature Plan

## Overview
Add `playlist analyze <name>` command to show comprehensive statistics about a playlist's content - useful for set planning, curation, and understanding playlist composition.

## Analytics Categories

### 1. **Basic Statistics**
- Total tracks
- Total duration (formatted as HH:MM:SS)
- Average track length
- Year range (oldest to newest)

### 2. **Artist Analysis**
- Top 10 artists by track count
- Total unique artists
- Artist diversity metric (tracks per artist ratio)

### 3. **Genre Analysis**
- Top genres from `tracks.genre`
- Genre distribution percentages

### 4. **Tag Analysis**
- Top 10 tags overall
- Breakdown by source (AI vs user vs file)
- Tag frequency distribution
- Most confident AI tags

### 5. **DJ-Focused Musical Characteristics**
- **BPM Analysis**:
  - Min/Max/Average/Median BPM
  - BPM distribution: <100, 100-120, 120-140, 140-160, 160+
  - Identifies mixing opportunities
- **Key Distribution**:
  - Most common keys
  - Harmonic mixing suggestions (compatible keys)
- **Energy Analysis**: Tags like "high-energy", "chill", "melodic"

### 6. **Year/Era Distribution**
- Decade breakdown (70s, 80s, 90s, 00s, 10s, 20s)
- Recent (2020+) vs classic ratio

### 7. **Rating Analysis**
- Tracks with ratings
- Love/like/skip counts
- Archived tracks (quality check)
- Most loved tracks in playlist

### 8. **Quality Metrics**
- Tracks missing BPM (%)
- Tracks missing key (%)
- Tracks missing year (%)
- Tracks without tags (%)
- Completeness score

### 9. **Temporal Info** (if applicable)
- When playlist was created
- Last modified
- Most recently added tracks

## Implementation Structure

### New File: `src/music_minion/domain/playlists/analytics.py`
```python
def get_playlist_analytics(playlist_id: int) -> Dict[str, Any]
def analyze_artists(tracks: List[Dict]) -> Dict
def analyze_genres(tracks: List[Dict]) -> Dict
def analyze_tags(track_ids: List[int]) -> Dict
def analyze_bpm(tracks: List[Dict]) -> Dict
def analyze_keys(tracks: List[Dict]) -> Dict
def analyze_years(tracks: List[Dict]) -> Dict
def analyze_ratings(track_ids: List[int]) -> Dict
def analyze_completeness(tracks: List[Dict]) -> Dict
```

### Updated: `src/music_minion/commands/playlist.py`
```python
def handle_playlist_analyze_command(ctx: AppContext, args: List[str])
```

### Router Update: `src/music_minion/router.py`
Add routing for "playlist analyze"

## Display Format Options

**Option A: Full Report (default)**
- All sections with tables and charts
- ~50-100 lines output
- Rich formatting with colors/emojis

**Option B: Compact Mode** (`playlist analyze <name> --compact`)
- Key metrics only
- ~20-30 lines
- Quick overview

**Option C: Specific Section** (`playlist analyze <name> --section=bpm`)
- Deep dive into one category
- Useful for targeted analysis

## Benefits for NYE 2025 Use Case
1. **Set Planning**: Duration analysis helps plan set length
2. **Energy Flow**: BPM/tag distribution shows energy progression
3. **Harmonic Mixing**: Key analysis enables smooth transitions
4. **Track Selection**: Identify most loved tracks for peak moments
5. **Quality Check**: Find missing metadata before exporting to Serato
6. **Genre Balance**: Ensure variety or consistency as desired

## Technical Approach
- SQL queries for performance (avoid loading all track data)
- Reuse existing patterns from `get_library_analytics()`
- Use Rich library for formatted output
- Pure functions following functional architecture
- Handle both manual and smart playlists

## Example Output
```
📊 Playlist Analytics: "NYE 2025"
═══════════════════════════════════════

📈 BASIC STATS
  Tracks: 127
  Duration: 8h 34m 12s
  Avg Length: 4m 3s
  Year Range: 2018-2025

🎤 TOP ARTISTS (10 of 42)
  1. Excision - 12 tracks (9%)
  2. Subtronics - 8 tracks (6%)
  ...

🎵 GENRE DISTRIBUTION
  Dubstep: 65 (51%)
  Drum & Bass: 32 (25%)
  ...

⚡ BPM ANALYSIS
  Range: 138-174 BPM
  Average: 148 BPM
  Distribution:
    140-150: 45 tracks (35%)
    150-160: 62 tracks (49%)
    ...

🔑 KEY DISTRIBUTION
  Most Common: A minor (18), G major (14)
  Harmonic Pairs: 42 compatible transitions

#️⃣ TOP TAGS (AI)
  high-energy (87), heavy-bass (65), ...

✅ QUALITY SCORE: 92%
  Missing BPM: 3 tracks (2%)
  Missing Key: 8 tracks (6%)
  ...
```

## Implementation Steps
1. Create `analytics.py` with data gathering functions
2. Add command handler in `playlist.py`
3. Update router for "playlist analyze" command
4. Add comprehensive tests
5. Document in CLAUDE.md
6. Update command autocomplete

## Estimated Effort
3-4 hours for complete implementation with tests

## Additional Ideas to Consider

### Export Analytics
- `playlist analyze <name> --export=json` - Export raw data for external analysis
- `playlist analyze <name> --export=csv` - Export for spreadsheet analysis

### Comparison Mode
- `playlist compare <name1> <name2>` - Compare two playlists side-by-side
- Shows differences in BPM, keys, genres, tags
- Useful for creating complementary sets

### Visual Enhancements
- ASCII bar charts for distributions
- Color coding (green for complete metadata, yellow/red for missing)
- Progress bars for percentages

### Smart Suggestions
- "Consider adding more tracks in key of X for better mixing"
- "BPM range too wide - might be difficult to mix"
- "Low energy variety - consider adding more chill tracks"
- "Missing metadata warnings for Serato export"

### Integration with Existing Features
- Link to `playlist show` for detailed track viewer
- Integrate with AI review to improve tag coverage
- Auto-run after playlist import to assess quality
