# Integrate FilterPanel with PlaylistBuilder

## Files to Modify
- `web/frontend/src/pages/PlaylistBuilder.tsx` (modify lines 150-157, 228-235)

## Implementation Details

Replace the placeholder FilterPanel with the fully functional component.

### Step 1: Add Import

At the top of the file, add:
```tsx
import FilterPanel from '../components/builder/FilterPanel';
```

### Step 2: Remove Placeholder Function

**Remove lines 228-235:**
```tsx
// DELETE THIS:
function FilterPanel(_props: { filters: any[]; onUpdate: (filters: any[]) => void }) {
  return (
    <div className="text-gray-400">
      <p className="text-sm">Filter UI coming soon</p>
      <p className="text-xs mt-2">Genre, BPM, Year, Key</p>
    </div>
  );
}
```

### Step 3: Update FilterPanel Usage

**Update lines 150-157:**

Replace:
```tsx
<aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
  <h3 className="text-lg font-semibold mb-4">Filters</h3>
  <FilterPanel
    filters={filters || []}
    onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
  />
</aside>
```

With:
```tsx
<aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
  <FilterPanel
    filters={filters || []}
    onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
    isUpdating={updateFilters.isPending}
  />
</aside>
```

**Key changes:**
1. Remove standalone `<h3>Filters</h3>` header (FilterPanel has its own header)
2. Add `isUpdating={updateFilters.isPending}` prop to enable loading states

### Complete Integration Context

The FilterPanel component will now be fully wired into the existing React Query hooks from `useBuilderSession`:

```tsx
const {
  session,
  addTrack,
  skipTrack,
  filters,           // ← filters state
  updateFilters,     // ← mutation for updating filters
  startSession,
  isAddingTrack,
  isSkippingTrack
} = useBuilderSession(playlistId);
```

When `updateFilters.mutate(newFilters)` is called:
1. Backend API called: `PUT /api/builder/filters/{playlistId}`
2. On success, React Query invalidates:
   - `['builder-filters', playlistId]` → UI shows new filters
   - `['builder-session', playlistId]` → Session stats update
   - `['builder-candidates', playlistId]` → New candidate fetched
3. PlaylistBuilder auto-fetches next candidate matching filters
4. User sees new track immediately

## Acceptance Criteria

- [ ] Import statement added correctly
- [ ] Placeholder FilterPanel function removed
- [ ] FilterPanel usage updated with all three props
- [ ] Header duplication eliminated (FilterPanel has its own)
- [ ] No TypeScript errors
- [ ] No visual regressions in sidebar layout
- [ ] Filters sidebar renders with new FilterPanel component
- [ ] Filter operations trigger candidate refresh
- [ ] Loading states work correctly (buttons disabled during mutation)

## Testing Checklist

1. **Visual Check:**
   - [ ] Sidebar renders without layout issues
   - [ ] "Filters" header appears once (in FilterPanel, not duplicate)
   - [ ] Empty state shows when no filters

2. **Functional Check:**
   - [ ] Click "+ Add Filter" opens editor
   - [ ] Add filter → candidate updates
   - [ ] Edit filter → candidate updates
   - [ ] Delete filter → candidate updates
   - [ ] Clear all → candidate updates
   - [ ] Toggle AND/OR → candidate updates

3. **Loading States:**
   - [ ] Buttons disable during filter mutation
   - [ ] No race conditions with rapid filter changes

## Dependencies

- Task 05 (FilterPanel.tsx) - must be completed first
- Existing hooks in `web/frontend/src/hooks/useBuilderSession.ts` (no changes needed)
- Existing API in `web/frontend/src/api/builder.ts` (no changes needed)
