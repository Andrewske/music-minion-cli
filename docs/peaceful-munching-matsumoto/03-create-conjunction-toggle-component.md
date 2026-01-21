# Create ConjunctionToggle Component

## Files to Create
- `web/frontend/src/components/builder/ConjunctionToggle.tsx` (new)

## Implementation Details

Create a simple toggle button component for switching between AND/OR conjunctions between filters.

### Component Interface
```tsx
interface ConjunctionToggleProps {
  conjunction: 'AND' | 'OR';
  onChange: () => void;
  disabled?: boolean;
}
```

### Visual Design
- AND: Gray pill (`bg-slate-700`) - default, most restrictive
- OR: Blue pill (`bg-blue-600`) - highlights less common case
- Centered between filters

### Implementation
```tsx
function ConjunctionToggle({ conjunction, onChange, disabled }: ConjunctionToggleProps) {
  return (
    <div className="flex justify-center py-1">
      <button
        onClick={onChange}
        disabled={disabled}
        className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
          conjunction === 'AND'
            ? 'bg-slate-700 hover:bg-slate-600 text-gray-300'
            : 'bg-blue-600 hover:bg-blue-700 text-white'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {conjunction}
      </button>
    </div>
  );
}

export default ConjunctionToggle;
```

### Behavior
- Click to toggle between AND/OR
- Visual distinction: gray (AND) vs blue (OR)
- Disabled during mutations (dimmed with cursor-not-allowed)
- Smooth color transition on toggle

## Acceptance Criteria

- [ ] Component renders centered conjunction pill
- [ ] AND displays as gray pill
- [ ] OR displays as blue pill
- [ ] Click triggers `onChange` callback
- [ ] Disabled state prevents clicks and dims button
- [ ] Smooth transitions between states
- [ ] Proper TypeScript typing for all props

## Dependencies

None - standalone component with no external dependencies.
