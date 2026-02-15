# Create EmojiPicker Component (using emoji-mart)

## Files to Create
- `web/frontend/src/components/EmojiPicker.tsx` (new)

## Files to Modify
- `web/frontend/package.json` (add emoji-mart dependencies)

## Implementation Details

### Step 1: Install emoji-mart

```bash
cd web/frontend
npm install @emoji-mart/react @emoji-mart/data
```

### Step 2: Create EmojiPicker Wrapper Component

Create `web/frontend/src/components/EmojiPicker.tsx`:

```tsx
import { useEffect, useRef } from 'react';
import Picker from '@emoji-mart/react';
import data from '@emoji-mart/data';
import { useQuery } from '@tanstack/react-query';

interface EmojiPickerProps {
  onSelect: (emojiId: string) => void;
  onClose: () => void;
}

interface EmojiMartEmoji {
  id: string;
  name: string;
  native?: string;  // Unicode emoji character
  src?: string;     // Custom emoji image URL
}

/**
 * Emoji picker using emoji-mart with custom emoji support.
 * Wraps emoji-mart in a modal overlay with backdrop click to close.
 */
export function EmojiPicker({ onSelect, onClose }: EmojiPickerProps): JSX.Element {
  const pickerRef = useRef<HTMLDivElement>(null);

  // Fetch custom emojis from backend in emoji-mart format
  const { data: customEmojis } = useQuery({
    queryKey: ['emojis', 'custom-for-picker'],
    queryFn: async () => {
      const res = await fetch('/api/emojis/custom-picker');
      if (!res.ok) return [];
      return res.json();
    },
  });

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleEmojiSelect = (emoji: EmojiMartEmoji) => {
    // For Unicode emojis, use the native character as ID
    // For custom emojis, use the id (UUID)
    const emojiId = emoji.native ?? emoji.id;
    onSelect(emojiId);
    onClose();
  };

  // Build custom category for emoji-mart
  const customCategory = customEmojis?.length
    ? [
        {
          id: 'custom',
          name: 'Custom',
          emojis: customEmojis,
        },
      ]
    : [];

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        ref={pickerRef}
        onClick={(e) => e.stopPropagation()}
        className="rounded-lg overflow-hidden"
      >
        <Picker
          data={data}
          custom={customCategory}
          onEmojiSelect={handleEmojiSelect}
          theme="dark"
          skinTonePosition="search"
          previewPosition="none"
          navPosition="top"
          perLine={10}
          emojiSize={32}
          emojiButtonSize={42}
          maxFrequentRows={2}
        />
      </div>
    </div>
  );
}
```

### Step 3: Add Backend Endpoint for Custom Emojis (emoji-mart format)

Update `web/backend/routers/emojis.py` to add:

```python
@router.get("/emojis/custom-picker")
async def get_custom_emojis_for_picker(db=Depends(get_db)) -> list[dict]:
    """Get custom emojis in emoji-mart format."""
    cursor = db.execute(
        """
        SELECT emoji_id, custom_name, default_name, file_path
        FROM emoji_metadata
        WHERE type = 'custom'
        ORDER BY use_count DESC
        """
    )

    return [
        {
            'id': row['emoji_id'],
            'name': row['custom_name'] or row['default_name'],
            'keywords': [row['default_name'].lower()],
            'skins': [{'src': f'/custom_emojis/{row["file_path"]}'}],
        }
        for row in cursor.fetchall()
    ]
```

### Step 4: Theme Customization (Optional)

emoji-mart supports CSS variable theming. Add to your global CSS if needed:

```css
/* Match emoji-mart to your dark theme */
em-emoji-picker {
  --em-rgb-background: 15, 23, 42;  /* slate-900 */
  --em-rgb-input: 30, 41, 59;       /* slate-800 */
  --em-rgb-color: 248, 250, 252;    /* slate-50 */
}
```

## What emoji-mart Provides (no custom code needed)

- ✅ Full Unicode emoji database (3600+)
- ✅ Categories (Smileys, People, Nature, Food, Activities, Travel, Objects, Symbols, Flags)
- ✅ Search with fuzzy matching
- ✅ Keyboard navigation (arrow keys, Enter, Tab)
- ✅ Skin tone selector
- ✅ Frequently used (auto-tracked by emoji-mart)
- ✅ Custom emoji categories
- ✅ Accessible (ARIA labels, screen reader support)
- ✅ Virtualized rendering (fast with thousands of emojis)

## What Your Backend Still Handles

- use_count tracking (your `/api/emojis/tracks/{id}/emojis` endpoint)
- Custom emoji storage and serving
- Emoji-to-track associations
- Custom names for emojis (via Settings page)

## Acceptance Criteria

- [ ] `npm install @emoji-mart/react @emoji-mart/data` completes successfully
- [ ] Picker opens in modal overlay with dark theme
- [ ] Clicking backdrop closes picker
- [ ] Escape key closes picker
- [ ] Selecting emoji calls `onSelect` with correct ID (Unicode char or UUID)
- [ ] Custom emojis appear in "Custom" category (if any exist)
- [ ] Search works across all emojis including custom
- [ ] Keyboard navigation works (arrow keys, Enter to select)

## Dependencies

- Task 02 (emoji router) - for custom emoji endpoint
- Task 04 (frontend setup) - for react-query

## Notes

**Why emoji-mart over custom implementation:**
- Eliminates ~300 lines of custom picker code
- Battle-tested keyboard navigation and accessibility
- Handles emoji rendering edge cases (ZWJ sequences, skin tones, flags)
- Built-in "frequently used" tracking
- Custom emoji support is first-class

**Syncing "frequently used" with backend:**
emoji-mart tracks frequent emojis in localStorage. Your backend tracks use_count separately. These are complementary:
- emoji-mart's frequent = what you selected recently in the picker
- Backend's use_count = lifetime usage across all contexts

Both are valid; no need to sync them.
