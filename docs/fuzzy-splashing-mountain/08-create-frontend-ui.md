# Create Frontend UI for YouTube Import

## Files to Create
- `web/frontend/src/components/YouTube/ImportVideoForm.tsx` (new)
- `web/frontend/src/components/YouTube/ImportPlaylistForm.tsx` (new)
- `web/frontend/src/components/YouTube/YouTubeImport.tsx` (new - parent component)

## Files to Modify
- TBD - depends on existing routing/navigation structure

## Implementation Details

Create React components for YouTube import functionality in the web UI.

### Component Structure

#### `YouTubeImport.tsx` (Parent Component)

Container component with tabs/toggle for single video vs. playlist import.

**Features**:
- Tab/toggle UI to switch between import modes
- Renders `ImportVideoForm` or `ImportPlaylistForm` based on selection
- Handles shared state (loading, errors, success messages)

#### `ImportVideoForm.tsx`

Form for importing a single YouTube video with metadata.

**Fields**:
- **YouTube URL** (required)
  - Text input with validation (YouTube URL format)
  - Placeholder: "https://youtube.com/watch?v=..."
- **Artist** (optional)
  - Text input
- **Title** (optional)
  - Text input
- **Album** (optional)
  - Text input

**Features**:
- Submit button: "Import Video"
- Loading state with polling (disable form, show spinner)
- Success message: "✓ Imported: {artist} - {title}"
- Error handling: Display error message from API
- Clear form after successful import

**API Integration (with polling)**:
```typescript
// 1. Start import job
const startResponse = await fetch('/youtube/import', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url, artist, title, album })
});
const { job_id } = await startResponse.json();

// 2. Poll for completion
const pollJob = async (jobId: string): Promise<JobResult> => {
  while (true) {
    const statusResponse = await fetch(`/youtube/import/${jobId}`);
    const status = await statusResponse.json();

    if (status.status === 'completed') {
      return status.result;
    } else if (status.status === 'failed') {
      throw new Error(status.error);
    }

    await new Promise(resolve => setTimeout(resolve, 1000)); // Poll every 1s
  }
};

const result = await pollJob(job_id);
```

#### `ImportPlaylistForm.tsx`

Form for bulk importing a YouTube playlist.

**Fields**:
- **Playlist ID or URL** (required)
  - Text input with validation
  - Placeholder: "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf or full URL"
  - Auto-extract ID from URL if pasted

**Features**:
- **Preview before import**: Fetch playlist info to show title and video count
- Submit button: "Import Playlist"
- Loading state with polling
- Success message: "✓ Imported {count} tracks ({skipped} duplicates skipped)"
- Display failures if any: "{N} videos failed to download"
- List of imported track IDs (optional: link to tracks)

**API Integration (with preview and polling)**:
```typescript
// 1. Fetch playlist preview (on URL/ID input blur)
const fetchPreview = async (playlistId: string) => {
  const response = await fetch(`/youtube/playlist/${playlistId}`);
  if (!response.ok) throw new Error('Invalid playlist');
  return await response.json(); // { title, video_count, videos }
};

// Show preview to user before they click import
const preview = await fetchPreview(playlistId);
setPlaylistPreview({
  title: preview.title,
  videoCount: preview.video_count
});

// 2. Start import job (on submit)
const startResponse = await fetch('/youtube/import-playlist', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ playlist_id: playlistId })
});
const { job_id } = await startResponse.json();

// 3. Poll for completion (same pattern as single video)
const result = await pollJob(job_id);
// result: { imported_count, skipped_count, failed_count, failures, track_ids }
```

### Track Display Enhancement

Enhance existing track display components to show YouTube source:

**Badge/Icon**:
- Add YouTube icon/badge to tracks with `youtube_id`
- Color: Red (YouTube brand color)
- Icon: YouTube logo or "YT" text

**Link to Original Video**:
- Clickable link: `https://youtube.com/watch?v={youtube_id}`
- Opens in new tab
- Tooltip: "View on YouTube"

### Styling

Use existing design system/component library (shadcn/ui if available):
- Form inputs with labels
- Primary button for submit
- Loading spinners
- Success/error alerts
- Tabs/toggle for mode selection

## Acceptance Criteria

- [ ] Single video import form accepts URL and optional metadata
- [ ] Form submits to POST /youtube/import and polls for completion
- [ ] Loading state with spinner during polling
- [ ] Success message displays imported track info
- [ ] Error messages displayed clearly (including specific errors like age-restricted)
- [ ] Playlist import form accepts playlist ID/URL
- [ ] Playlist ID auto-extracted from URL
- [ ] **Playlist preview fetched before import** (shows title, video count)
- [ ] Import statistics shown after completion (imported, skipped, failed)
- [ ] Track display shows YouTube badge/icon
- [ ] Link to original video works (opens YouTube)
- [ ] Forms reset after successful import
- [ ] Validation prevents invalid inputs

## Dependencies

- Task 07 (Web API endpoints) must be complete

## Notes

**Exact file paths TBD** - depends on existing frontend structure. Adapt component organization to match existing patterns in the codebase.

**Optional Enhancements**:
- Thumbnail preview for videos (from YouTube API)
- Cancel in-progress imports (would need API support)
