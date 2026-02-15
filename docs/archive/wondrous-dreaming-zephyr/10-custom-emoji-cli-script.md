# Custom Emoji CLI Script

## Overview

Add custom emoji images (PNG, JPEG, GIF) via offline CLI script. Images are processed (resized, optimized), stored locally, and added to database. Frontend displays custom emojis as images alongside Unicode emojis.

**Key Decision:** Web upload removed from plan. Use CLI script for adding custom emojis (simpler, no blocking issues, perfect for personal project).

## Files to Create
- `scripts/add-custom-emoji.py` (new - CLI script)
- `scripts/bulk-tag-emoji.py` (new - bulk tagging script)
- `web/backend/services/emoji_processor.py` (new - shared image processing)

## Files to Modify
- `web/backend/routers/emojis.py` (add delete endpoint only)
- `web/backend/main.py` (mount static files)
- `web/frontend/src/components/EmojiSettings.tsx` (display grid + delete)
- `web/frontend/src/components/EmojiReactions.tsx` (render custom as images)
- `web/frontend/src/components/EmojiPicker.tsx` (render custom as images)

**Note:** Schema changes (type, file_path columns, custom_emojis directory) are included in v31 migration (Task 01).

## Implementation Details

### Step 1: Image Processing Service

Create `web/backend/services/emoji_processor.py`:

```python
"""Image processing for custom emojis. Shared by CLI script and backend."""
import uuid
import io
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageSequence
from music_minion.core.config import get_data_dir

MAX_SIZE = 128  # Max width/height in pixels
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB (prevents blocking)
MAX_FRAMES = 20  # Max GIF frames (prevents blocking)
ALLOWED_FORMATS = {'PNG', 'JPEG', 'GIF'}

def get_custom_emojis_dir() -> Path:
    """Get the custom emojis directory, creating if needed."""
    custom_dir = get_data_dir() / "custom_emojis"
    custom_dir.mkdir(exist_ok=True)
    return custom_dir

def process_emoji_image(file_content: bytes, original_filename: str) -> Tuple[str, Path]:
    """
    Process uploaded emoji image: validate, resize, save.

    Returns:
        Tuple of (emoji_id, file_path)
        emoji_id: UUID string (type column distinguishes custom from unicode)
        file_path: filename of saved file

    Raises:
        ValueError: If file too large, wrong format, or too many frames
    """
    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Open image
    img = Image.open(io.BytesIO(file_content))

    # Validate format
    if img.format not in ALLOWED_FORMATS:
        raise ValueError(f"Unsupported format: {img.format}. Allowed: {ALLOWED_FORMATS}")

    # Generate unique filename
    file_ext = img.format.lower()
    emoji_id = str(uuid.uuid4())  # Just UUID, no "custom:" prefix
    filename = f"{emoji_id}.{file_ext}"

    # Resize image
    output_path = get_custom_emojis_dir() / filename

    if img.format == 'GIF' and getattr(img, 'is_animated', False):
        # Check frame count
        frame_count = getattr(img, 'n_frames', 1)
        if frame_count > MAX_FRAMES:
            raise ValueError(f"Too many frames ({frame_count}). Max: {MAX_FRAMES}")

        # Preserve GIF animation
        frames = []
        durations = []

        for frame in ImageSequence.Iterator(img):
            # Resize frame preserving aspect ratio
            frame = frame.copy()
            frame.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            frames.append(frame)
            durations.append(frame.info.get('duration', 100))

        # Save animated GIF
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True
        )
    else:
        # Resize static image
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
        img.save(output_path, optimize=True)

    return emoji_id, filename

def delete_emoji_file(file_path: str) -> None:
    """Delete a custom emoji file."""
    full_path = get_custom_emojis_dir() / file_path
    if full_path.exists():
        full_path.unlink()
```

### Step 3: CLI Script for Adding Custom Emojis

Create `scripts/add-custom-emoji.py`:

```python
#!/usr/bin/env python3
"""
Add custom emoji to Music Minion.

Usage:
    uv run scripts/add-custom-emoji.py --image path/to/emoji.png --name "my emoji"
    uv run scripts/add-custom-emoji.py --image ~/Downloads/cool.gif --name "cool"
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.backend.services.emoji_processor import process_emoji_image
from music_minion.core.database import get_db_connection

def main():
    parser = argparse.ArgumentParser(description='Add custom emoji to Music Minion')
    parser.add_argument('--image', required=True, help='Path to image file (PNG, JPEG, GIF)')
    parser.add_argument('--name', required=True, help='Name for the emoji')
    args = parser.parse_args()

    # Read image file
    image_path = Path(args.image).expanduser()
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    try:
        with open(image_path, 'rb') as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading image: {e}")
        sys.exit(1)

    # Process image
    try:
        emoji_id, filename = process_emoji_image(file_content, image_path.name)
    except ValueError as e:
        print(f"Error processing image: {e}")
        sys.exit(1)

    # Insert into database
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO emoji_metadata (emoji_id, type, file_path, default_name, use_count)
                VALUES (?, 'custom', ?, ?, 0)
                """,
                (emoji_id, filename, args.name.strip())
            )
            conn.commit()
    except Exception as e:
        print(f"Error inserting into database: {e}")
        # Clean up file if database insert failed
        from web.backend.services.emoji_processor import delete_emoji_file
        delete_emoji_file(filename)
        sys.exit(1)

    print(f"✅ Custom emoji added successfully!")
    print(f"   ID: {emoji_id}")
    print(f"   Name: {args.name}")
    print(f"   File: {filename}")

if __name__ == '__main__':
    main()
```

### Step 4: CLI Script for Bulk Tagging

Create `scripts/bulk-tag-emoji.py`:

```python
#!/usr/bin/env python3
"""
Bulk tag tracks with emoji.

Usage:
    # Tag all tracks in a playlist
    uv run scripts/bulk-tag-emoji.py --playlist "Workout Mix" --emoji "🔥"

    # Tag tracks by path pattern
    uv run scripts/bulk-tag-emoji.py --path-pattern "*/EDM/*" --emoji "⚡"

    # Tag specific track IDs
    uv run scripts/bulk-tag-emoji.py --track-ids 1,2,3,4 --emoji "💎"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music_minion.core.database import get_db_connection, normalize_emoji_id

def main():
    parser = argparse.ArgumentParser(description='Bulk tag tracks with emoji')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--playlist', help='Playlist name')
    group.add_argument('--path-pattern', help='File path pattern (e.g., "*/EDM/*")')
    group.add_argument('--track-ids', help='Comma-separated track IDs')
    parser.add_argument('--emoji', required=True, help='Emoji to add (Unicode or custom:uuid)')
    args = parser.parse_args()

    emoji_id = normalize_emoji_id(args.emoji)

    with get_db_connection() as conn:
        # Get track IDs based on selection method
        if args.playlist:
            cursor = conn.execute(
                """
                SELECT t.id FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                JOIN playlists p ON pt.playlist_id = p.id
                WHERE p.name = ?
                """,
                (args.playlist,)
            )
        elif args.path_pattern:
            cursor = conn.execute(
                "SELECT id FROM tracks WHERE local_path GLOB ?",
                (args.path_pattern,)
            )
        else:  # track_ids
            track_ids = [int(x.strip()) for x in args.track_ids.split(',')]
            placeholders = ','.join('?' * len(track_ids))
            cursor = conn.execute(
                f"SELECT id FROM tracks WHERE id IN ({placeholders})",
                track_ids
            )

        track_ids = [row['id'] for row in cursor.fetchall()]

        if not track_ids:
            print("No tracks found matching criteria")
            sys.exit(0)

        print(f"Found {len(track_ids)} tracks. Adding emoji '{args.emoji}'...")

        # Use IMMEDIATE transaction for atomicity
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Auto-create emoji metadata if missing (same behavior as web UI)
            cursor = conn.execute(
                "SELECT type FROM emoji_metadata WHERE emoji_id = ?",
                (emoji_id,)
            )
            row = cursor.fetchone()
            if not row:
                # Check if it looks like a custom emoji UUID
                if len(emoji_id) == 36 and emoji_id.count('-') == 4:
                    print(f"Error: Custom emoji '{emoji_id}' not found in database")
                    print("Add custom emojis first with add-custom-emoji.py")
                    sys.exit(1)

                # Auto-create for Unicode emojis
                import emoji
                try:
                    name = emoji.demojize(emoji_id).strip(':').replace('_', ' ')
                except Exception:
                    name = emoji_id

                conn.execute(
                    "INSERT INTO emoji_metadata (emoji_id, type, default_name, use_count) VALUES (?, 'unicode', ?, 0)",
                    (emoji_id, name)
                )
                print(f"Auto-created metadata for emoji '{emoji_id}' ({name})")

            # Bulk insert (INSERT OR IGNORE to skip duplicates)
            added = 0
            for track_id in track_ids:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
                    (track_id, emoji_id)
                )
                if cursor.rowcount > 0:
                    added += 1

            # Increment use_count once per actually added association
            if added > 0:
                conn.execute(
                    """
                    UPDATE emoji_metadata
                    SET use_count = use_count + ?, last_used = CURRENT_TIMESTAMP
                    WHERE emoji_id = ?
                    """,
                    (added, emoji_id)
                )

            conn.commit()
            print(f"✅ Added emoji to {added} tracks ({len(track_ids) - added} already had it)")

        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
```

### Step 5: Backend Delete Endpoint

Update `web/backend/routers/emojis.py` (add delete endpoint only):

```python
@router.delete("/emojis/custom/{emoji_id}")
async def delete_custom_emoji(emoji_id: str, db=Depends(get_db)) -> dict:
    """Delete a custom emoji and its file."""
    from ..services.emoji_processor import delete_emoji_file

    # Get emoji info and verify it's a custom emoji
    cursor = db.execute(
        "SELECT type, file_path FROM emoji_metadata WHERE emoji_id = ?",
        (emoji_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(404, "Emoji not found")

    if row['type'] != 'custom':
        raise HTTPException(400, "Only custom emojis can be deleted via this endpoint")

    file_path = row['file_path']

    # Delete database record (CASCADE will remove track_emojis entries)
    db.execute("DELETE FROM emoji_metadata WHERE emoji_id = ?", (emoji_id,))
    db.commit()

    # Delete file
    try:
        delete_emoji_file(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete custom emoji file {file_path}: {e}")

    return {'deleted': True}
```

### Step 6: Serve Custom Emoji Files

Update `web/backend/main.py`:

```python
from fastapi.staticfiles import StaticFiles
from music_minion.core.config import get_data_dir

# After creating app, before routers
custom_emojis_dir = get_data_dir() / "custom_emojis"
custom_emojis_dir.mkdir(exist_ok=True)

app.mount(
    "/custom_emojis",
    StaticFiles(directory=str(custom_emojis_dir)),
    name="custom_emojis"
)
```

### Step 7: Frontend - Display Custom Emojis

Update `web/frontend/src/components/EmojiSettings.tsx` to show custom emojis with delete:

```tsx
{/* Custom Emojis Grid */}
<div className="mt-6">
  <h3 className="text-lg font-semibold text-white mb-3">
    Your Custom Emojis
  </h3>
  <p className="text-sm text-slate-400 mb-4">
    To add custom emojis, use the CLI script:{' '}
    <code className="bg-slate-800 px-2 py-1 rounded">
      uv run scripts/add-custom-emoji.py --image path/to/emoji.png --name "my emoji"
    </code>
  </p>
  <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
    {emojis.filter(e => e.type === 'custom').map((emoji) => (
      <div
        key={emoji.emoji_id}
        className="relative bg-slate-800 rounded-lg p-3 group"
      >
        <img
          src={`/custom_emojis/${emoji.file_path}`}
          alt={emoji.default_name}
          className="w-full h-16 object-contain"
        />
        <p className="text-xs text-slate-400 text-center mt-2 truncate">
          {emoji.custom_name || emoji.default_name}
        </p>

        {/* Delete button */}
        <button
          onClick={() => handleDeleteCustom(emoji.emoji_id)}
          className="absolute top-1 right-1 bg-red-600 hover:bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          aria-label="Delete"
        >
          ×
        </button>
      </div>
    ))}
  </div>
</div>
```

### Step 8: Rendering Custom Emojis as Images

Create helper component `web/frontend/src/components/EmojiDisplay.tsx`:

```tsx
interface EmojiDisplayProps {
  emojiId: string;  // unicode string or "custom:uuid"
  emojiData?: { type: string; file_path?: string };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function EmojiDisplay({
  emojiId,
  emojiData,
  className = '',
  size = 'md'
}: EmojiDisplayProps): JSX.Element {
  const sizeClasses = {
    sm: 'w-4 h-4 text-base',
    md: 'w-8 h-8 text-3xl',
    lg: 'w-12 h-12 text-5xl'
  };

  // Check if custom emoji via type field
  const isCustom = emojiData?.type === 'custom';

  if (isCustom && emojiData?.file_path) {
    return (
      <img
        src={`/custom_emojis/${emojiData.file_path}`}
        alt={emojiId}
        className={`${sizeClasses[size].split(' text-')[0]} object-contain ${className}`}
        onError={(e) => {
          // Fallback if image fails to load
          e.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  // Unicode emoji
  return <span className={`${sizeClasses[size]} ${className}`}>{emojiId}</span>;
}
```

Use in EmojiReactions and EmojiPicker:
```tsx
// Instead of: {emoji.emoji_id}
// Use:
<EmojiDisplay
  emojiId={emoji.emoji_id}
  emojiData={emoji}
  size="md"
/>
```

## Dependencies

- **Python**: `Pillow` for image processing (`uv add pillow`)
- Task 01 (database migration to v31)
- All previous tasks (requires working emoji system)

## Acceptance Criteria

### Backend
- [ ] Migration to v32 completes successfully
- [ ] custom_emojis/ directory created in ~/.local/share/music-minion/
- [ ] CLI script accepts PNG, JPEG, GIF files
- [ ] Images resized to max 128x128px
- [ ] Animated GIFs preserve animation (up to 20 frames)
- [ ] File size limit enforced (1MB)
- [ ] Custom emojis served at /custom_emojis/{filename}
- [ ] Delete endpoint removes both database record and file

### CLI Scripts
- [ ] add-custom-emoji.py successfully adds custom emoji
- [ ] bulk-tag-emoji.py tags multiple tracks with single emoji
- [ ] Scripts provide clear success/error messages
- [ ] File size and frame count limits enforced
- [ ] Database transaction rollback on error (cleanup temp files)

### Frontend
- [ ] Settings page shows custom emoji grid with CLI instructions
- [ ] Delete button on hover with confirmation
- [ ] Custom emojis render as images in picker
- [ ] Custom emojis render as images in track badges
- [ ] Image error fallback handles missing files
- [ ] EmojiDisplay component handles both Unicode and custom

### Integration
- [ ] Add custom emoji via CLI → appears in picker immediately (after page refresh)
- [ ] Add custom emoji to track → shows as image badge
- [ ] Custom emoji syncs via Syncthing to other devices
- [ ] Search works for custom emoji names
- [ ] Top 50/Recent sections include custom emojis
- [ ] Bulk tagging script tags entire playlists correctly

## Testing

```bash
# Add custom emoji
uv run scripts/add-custom-emoji.py --image ~/Downloads/fire.png --name "custom fire"

# Verify file exists
ls ~/.local/share/music-minion/custom_emojis/

# Check database
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT * FROM emoji_metadata WHERE type='custom'"

# Bulk tag playlist
uv run scripts/bulk-tag-emoji.py --playlist "Favorites" --emoji "🔥"

# Delete custom emoji (via web UI)
curl -X DELETE "http://localhost:8642/api/emojis/custom/custom%3Auuid"
```

## Notes

**File Storage:**
- Files stored in `~/.local/share/music-minion/custom_emojis/`
- Automatically syncs via Syncthing (same as database)
- UUID filenames prevent conflicts

**Emoji Identification:**
- Unicode: emoji_id is the actual emoji character ("🔥"), type='unicode'
- Custom: emoji_id is a UUID, type='custom', file_path has the filename
- Backend and frontend both use the `type` field to discriminate
- No "custom:" prefix needed - type column is the source of truth

**Image Processing:**
- Max 128x128px (aspect ratio preserved)
- Supports static and animated images (up to 20 frames)
- GIF animation preserved using ImageSequence
- Optimized on save for smaller file size
- 1MB file size limit prevents CLI blocking

**Limitations:**
- Max file size: 1MB (prevents slow processing)
- Max GIF frames: 20 (prevents slow processing)
- Formats: PNG, JPEG, GIF only
- No web upload (use CLI script)
- Delete requires confirmation (prevents accidents)

**No Storage Limits:**
- Personal project, single user
- Trust user won't abuse storage
- Document in script help that custom emojis consume disk space
