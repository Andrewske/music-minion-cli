# Create Emoji Settings Page

## Files to Create
- `web/frontend/src/components/EmojiSettings.tsx` (new)
- `web/frontend/src/routes/emoji-settings.tsx` (new)

## Files to Modify
- `web/frontend/src/routes/__root.tsx` (modify - add navigation)

## Implementation Details

### Create `EmojiSettings.tsx` Component

**State:**
```tsx
const [emojis, setEmojis] = useState<EmojiInfo[]>([]);
const [editingEmoji, setEditingEmoji] = useState<string | null>(null);
const [editValue, setEditValue] = useState('');
const [isLoading, setIsLoading] = useState(true);
const [isSaving, setIsSaving] = useState(false);  // NEW: saving state

interface EmojiInfo {
  emoji_unicode: string;
  custom_name: string | null;
  default_name: string;
  use_count: number;
}
```

**Data Loading:**
```tsx
useEffect(() => {
  async function loadEmojis(): Promise<void> {
    try {
      const res = await fetch('/api/emojis/all');
      const data = await res.json();
      setEmojis(data);
    } catch (err) {
      console.error('Failed to load emojis:', err);
    } finally {
      setIsLoading(false);
    }
  }

  loadEmojis();
}, []);
```

**Edit Handlers:**
```tsx
const handleEdit = (emoji: EmojiInfo): void => {
  setEditingEmoji(emoji.emoji_unicode);
  setEditValue(emoji.custom_name || '');
};

const handleSave = async (emojiUnicode: string): Promise<void> {
  try {
    await fetch(`/api/emojis/metadata/${encodeURIComponent(emojiUnicode)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ custom_name: editValue.trim() || null })
    });

    // Update local state
    setEmojis(prev => prev.map(e =>
      e.emoji_unicode === emojiUnicode
        ? { ...e, custom_name: editValue.trim() || null }
        : e
    ));

    setEditingEmoji(null);
  } catch (err) {
    console.error('Failed to update emoji:', err);
  }
};

const handleCancel = (): void => {
  setEditingEmoji(null);
  setEditValue('');
};
```

**UI Table:**
```tsx
<div className="max-w-4xl mx-auto p-6">
  <h1 className="text-2xl font-bold text-white mb-6">Emoji Settings</h1>

  <div className="bg-slate-900 rounded-lg overflow-hidden">
    <table className="w-full">
      <thead className="bg-slate-800">
        <tr>
          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">Emoji</th>
          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">Default Name</th>
          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">Custom Name</th>
          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">Uses</th>
          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">Actions</th>
        </tr>
      </thead>
      <tbody>
        {emojis.map((emoji) => (
          <tr key={emoji.emoji_unicode} className="border-t border-slate-800">
            <td className="px-4 py-3 text-2xl">{emoji.emoji_unicode}</td>
            <td className="px-4 py-3 text-sm text-slate-400">{emoji.default_name}</td>
            <td className="px-4 py-3">
              {editingEmoji === emoji.emoji_unicode ? (
                <input
                  type="text"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="w-full px-2 py-1 bg-slate-800 text-white rounded"
                  autoFocus
                />
              ) : (
                <span className="text-white">
                  {emoji.custom_name || <span className="text-slate-500 italic">None</span>}
                </span>
              )}
            </td>
            <td className="px-4 py-3 text-sm text-slate-400">{emoji.use_count}</td>
            <td className="px-4 py-3">
              {editingEmoji === emoji.emoji_unicode ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSave(emoji.emoji_unicode)}
                    className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-sm text-white"
                  >
                    Save
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm text-white"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleEdit(emoji)}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm text-white"
                >
                  Edit
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
</div>
```

### Create Route File: `emoji-settings.tsx`

```tsx
import { createFileRoute } from '@tanstack/react-router';
import { EmojiSettings } from '../components/EmojiSettings';

function EmojiSettingsPage(): JSX.Element {
  return <EmojiSettings />;
}

export const Route = createFileRoute('/emoji-settings')({
  component: EmojiSettingsPage,
});
```

### Update Navigation in `__root.tsx`

Find the navigation section and add:

```tsx
<NavButton to="/emoji-settings">Emojis</NavButton>
```

## Acceptance Criteria
- [ ] Navigate to `/emoji-settings` route without errors
- [ ] Page shows table of all emojis with columns: Emoji, Default Name, Custom Name, Uses, Actions
- [ ] Click "Edit" button → input field appears
- [ ] Type custom name → click "Save" → custom name persists
- [ ] Empty custom name → shows "None" in italic gray text
- [ ] Click "Cancel" → editing mode exits without saving
- [ ] Use count displays correctly for each emoji
- [ ] Navigation button "Emojis" appears in header
- [ ] Clicking nav button navigates to settings page

## Dependencies
- Task 02 (emoji router) - provides API endpoints
