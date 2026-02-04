# Create FilterEditor Component

## Files to Create
- `web/frontend/src/components/builder/FilterEditor.tsx` (new)

## Implementation Details

Create a three-step wizard component for adding/editing filters with progressive disclosure based on field type.

### Component Interface
```tsx
interface FilterEditorProps {
  initialFilter?: Filter;
  editingIndex: number | null;
  onSave: (filter: Filter) => void;
  onCancel: () => void;
}
```

### State Management
```tsx
const [field, setField] = useState(initialFilter?.field || '');
const [operator, setOperator] = useState(initialFilter?.operator || '');
const [value, setValue] = useState(initialFilter?.value || '');
const [validationError, setValidationError] = useState<string | null>(null);
```

### Three-Step Wizard Flow

**Step 1: Field Selection**
```tsx
<div className="bg-slate-800 rounded-lg p-3">
  <label className="text-xs text-gray-400 block mb-2">Field</label>
  <select value={field} onChange={(e) => setField(e.target.value)} className="w-full bg-slate-700 rounded px-3 py-2 text-white">
    <option value="">Choose field...</option>
    <option value="title">Title</option>
    <option value="artist">Artist</option>
    <option value="album">Album</option>
    <option value="genre">Genre</option>
    <option value="year">Year</option>
    <option value="bpm">BPM</option>
    <option value="key">Key</option>
  </select>
</div>
```

**Step 2: Operator Selection (Conditional)**

For text fields (title, artist, album, genre, key):
```tsx
{field && ['title', 'artist', 'album', 'genre', 'key'].includes(field) && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label className="text-xs text-gray-400 block mb-2">Condition</label>
    <select value={operator} onChange={(e) => setOperator(e.target.value)} className="w-full bg-slate-700 rounded px-3 py-2 text-white">
      <option value="">Choose condition...</option>
      <option value="contains">contains (~)</option>
      <option value="equals">equals (=)</option>
      <option value="not_equals">not equals (≠)</option>
      <option value="starts_with">starts with</option>
      <option value="ends_with">ends with</option>
    </select>
  </div>
)}
```

For numeric fields (year, bpm):
```tsx
{field && ['year', 'bpm'].includes(field) && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label className="text-xs text-gray-400 block mb-2">Condition</label>
    <select value={operator} onChange={(e) => setOperator(e.target.value)} className="w-full bg-slate-700 rounded px-3 py-2 text-white">
      <option value="">Choose condition...</option>
      <option value="equals">equals (=)</option>
      <option value="not_equals">not equals (≠)</option>
      <option value="gt">greater than (>)</option>
      <option value="gte">greater or equal (≥)</option>
      <option value="lt">less than (<)</option>
      <option value="lte">less or equal (≤)</option>
    </select>
  </div>
)}
```

**Step 3: Value Input (Conditional)**

Genre dropdown (field=genre, operator=equals):
```tsx
{field === 'genre' && operator === 'equals' && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label className="text-xs text-gray-400 block mb-2">Genre</label>
    <select value={value} onChange={(e) => setValue(e.target.value)} className="w-full bg-slate-700 rounded px-3 py-2 text-white">
      <option value="">Choose genre...</option>
      {uniqueGenres.map(({ name, count }) => (
        <option key={name} value={name}>{name} ({count} tracks)</option>
      ))}
    </select>
  </div>
)}
```

Text/number input (all other cases):
```tsx
{field && operator && !(field === 'genre' && operator === 'equals') && (
  <div className="bg-slate-800 rounded-lg p-3 mt-2">
    <label className="text-xs text-gray-400 block mb-2">Value</label>
    <input
      type={['year', 'bpm'].includes(field) ? 'number' : 'text'}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder={getPlaceholder(field, operator)}
      className="w-full bg-slate-700 rounded px-3 py-2 text-white"
    />
  </div>
)}
```

### Genre Extraction (useMemo)
```tsx
const { data: candidates } = useQuery({
  queryKey: ['builder-candidates', playlistId],
  // Use existing query from parent context
});

const uniqueGenres = useMemo(() => {
  if (!candidates) return [];
  const genreMap = new Map<string, number>();
  candidates.forEach(track => {
    if (track.genre) {
      genreMap.set(track.genre, (genreMap.get(track.genre) || 0) + 1);
    }
  });
  return Array.from(genreMap.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name));
}, [candidates]);
```

### Auto-Clear Incompatible Operator (useEffect)
```tsx
useEffect(() => {
  if (field && operator) {
    const isNumericField = ['year', 'bpm'].includes(field);
    const isNumericOperator = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'].includes(operator);
    const isTextOperator = ['contains', 'equals', 'not_equals', 'starts_with', 'ends_with'].includes(operator);

    if (isNumericField && !isNumericOperator) {
      setOperator(''); // Clear incompatible operator
    } else if (!isNumericField && !isTextOperator) {
      setOperator('');
    }
  }
}, [field]);
```

### Save Handler with Validation
```tsx
const handleSave = () => {
  const error = validateFilter(field, operator, value);
  if (error) {
    setValidationError(error);
    return;
  }

  onSave({
    field,
    operator,
    value,
    conjunction: initialFilter?.conjunction || 'AND'
  });
};

const isValid = field && operator && value && !validateFilter(field, operator, value);
```

### Action Buttons
```tsx
<div className="flex gap-2 mt-3">
  <button
    onClick={handleSave}
    disabled={!isValid}
    className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors"
  >
    {editingIndex !== null ? 'Update' : 'Add Filter'}
  </button>
  <button
    onClick={onCancel}
    className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium transition-colors"
  >
    Cancel
  </button>
</div>
```

### Validation Error Display
```tsx
{validationError && (
  <div className="mt-2 p-2 bg-red-900/50 border border-red-700 rounded text-xs text-red-300">
    {validationError}
  </div>
)}
```

## Acceptance Criteria

- [ ] Three-step wizard renders correctly
- [ ] Field selection shows all 7 fields
- [ ] Operator selection conditional on field type (text vs numeric)
- [ ] Value input conditional on field/operator combination
- [ ] Genre dropdown appears for genre+equals, shows track counts
- [ ] Text/number input appears for all other cases
- [ ] Auto-clear operator when field type changes
- [ ] Validation prevents invalid filter submission
- [ ] Validation errors displayed clearly
- [ ] Add/Update button label changes based on edit mode
- [ ] Save handler calls onSave with complete filter object
- [ ] Cancel handler calls onCancel
- [ ] Proper TypeScript typing throughout

## Dependencies

- Task 01 (filterUtils.ts) - requires `validateFilter()` and `getPlaceholder()`
- Filter type from `web/frontend/src/api/builder.ts` (already exists)
- React Query `useQuery` hook (already available)
