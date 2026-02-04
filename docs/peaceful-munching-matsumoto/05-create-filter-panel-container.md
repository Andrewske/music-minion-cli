# Create FilterPanel Container Component

## Files to Create
- `web/frontend/src/components/builder/FilterPanel.tsx` (new)

## Implementation Details

Create the main container component that orchestrates the filter UI, managing state and coordinating between FilterItem, ConjunctionToggle, and FilterEditor.

### Component Interface
```tsx
interface FilterPanelProps {
  filters: Filter[];
  onUpdate: (filters: Filter[]) => void;
  isUpdating: boolean;
}
```

### State Management
```tsx
const [isEditing, setIsEditing] = useState(false);
const [editingIndex, setEditingIndex] = useState<number | null>(null);
const [editingFilter, setEditingFilter] = useState<Filter | undefined>(undefined);
const [toastMessage, setToastMessage] = useState<string | null>(null);
```

### Event Handlers

**Add Mode:**
```tsx
const startAdding = () => {
  setIsEditing(true);
  setEditingIndex(null);
  setEditingFilter(undefined);
};
```

**Edit Mode:**
```tsx
const startEditing = (index: number) => {
  setIsEditing(true);
  setEditingIndex(index);
  setEditingFilter(filters[index]);
};
```

**Cancel:**
```tsx
const handleCancel = () => {
  setIsEditing(false);
  setEditingIndex(null);
  setEditingFilter(undefined);
};
```

**Save:**
```tsx
const handleSave = async (filter: Filter) => {
  try {
    const updatedFilters = editingIndex !== null
      ? filters.map((f, i) => i === editingIndex ? filter : f)
      : [...filters, filter];

    await onUpdate(updatedFilters);
    setIsEditing(false);
    setEditingIndex(null);
    setEditingFilter(undefined);
  } catch (error) {
    setToastMessage(`❌ Failed to save filter: ${error.message}`);
    setTimeout(() => setToastMessage(null), 5000);
  }
};
```

**Delete:**
```tsx
const handleDelete = async (index: number) => {
  try {
    const updatedFilters = filters.filter((_, i) => i !== index);
    await onUpdate(updatedFilters);
  } catch (error) {
    setToastMessage(`❌ Failed to delete filter: ${error.message}`);
    setTimeout(() => setToastMessage(null), 5000);
  }
};
```

**Toggle Conjunction:**
```tsx
const toggleConjunction = async (index: number) => {
  try {
    const updatedFilters = filters.map((f, i) =>
      i === index
        ? { ...f, conjunction: f.conjunction === 'AND' ? 'OR' : 'AND' }
        : f
    );
    await onUpdate(updatedFilters);
  } catch (error) {
    setToastMessage(`❌ Failed to toggle conjunction: ${error.message}`);
    setTimeout(() => setToastMessage(null), 5000);
  }
};
```

**Clear All:**
```tsx
const handleClearAll = async () => {
  if (!confirm('Clear all filters? This will reset the candidate pool.')) {
    return;
  }
  try {
    await onUpdate([]);
  } catch (error) {
    setToastMessage(`❌ Failed to clear filters: ${error.message}`);
    setTimeout(() => setToastMessage(null), 5000);
  }
};
```

### Render Structure

**Header:**
```tsx
<div className="flex justify-between items-center mb-4">
  <h3 className="text-lg font-semibold">Filters</h3>
  {filters.length > 0 && (
    <button
      onClick={handleClearAll}
      className="text-xs text-red-400 hover:text-red-300"
    >
      Clear All
    </button>
  )}
</div>
```

**Filter List:**
```tsx
<div className="space-y-2 mb-4">
  {filters.map((filter, idx) => (
    <Fragment key={idx}>
      {idx > 0 && (
        <ConjunctionToggle
          conjunction={filter.conjunction}
          onChange={() => toggleConjunction(idx)}
          disabled={isUpdating}
        />
      )}
      <FilterItem
        filter={filter}
        onEdit={() => startEditing(idx)}
        onDelete={() => handleDelete(idx)}
        disabled={isUpdating}
      />
    </Fragment>
  ))}
</div>
```

**Editor or Add Button:**
```tsx
{isEditing ? (
  <FilterEditor
    initialFilter={editingFilter}
    editingIndex={editingIndex}
    onSave={handleSave}
    onCancel={handleCancel}
  />
) : (
  <button
    onClick={startAdding}
    disabled={isUpdating}
    className="w-full py-2 border-2 border-dashed border-slate-700 rounded-lg hover:border-blue-500 text-sm text-gray-400 hover:text-blue-400 disabled:opacity-50"
  >
    + Add Filter
  </button>
)}
```

**Empty State:**
```tsx
{filters.length === 0 && !isEditing && (
  <div className="text-center py-8 text-gray-500">
    <p className="text-sm mb-3">No filters active</p>
    <p className="text-xs">All tracks are candidates</p>
  </div>
)}
```

**Toast Notification:**
```tsx
{toastMessage && (
  <div className="fixed top-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 max-w-sm">
    {toastMessage}
  </div>
)}
```

## Acceptance Criteria

- [ ] Component accepts filters, onUpdate, and isUpdating props
- [ ] Header shows "Clear All" button only when filters exist
- [ ] Filter list renders all filters with ConjunctionToggle between them
- [ ] First filter has no ConjunctionToggle (index 0)
- [ ] Edit/delete operations update filters correctly
- [ ] Add operation appends new filter
- [ ] Clear all shows confirmation dialog
- [ ] Empty state displays when no filters
- [ ] Editor mode replaces add button
- [ ] Cancel returns to normal mode
- [ ] Toast notifications appear for errors
- [ ] All interactions disabled when isUpdating is true
- [ ] Proper TypeScript typing throughout
- [ ] Fragment used for list rendering (no unnecessary wrapper divs)

## Dependencies

- Task 02 (FilterItem.tsx)
- Task 03 (ConjunctionToggle.tsx)
- Task 04 (FilterEditor.tsx)
- Filter type from `web/frontend/src/api/builder.ts` (already exists)
