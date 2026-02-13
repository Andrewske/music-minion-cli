# Create FilterItem Component

## Files to Create
- `web/frontend/src/components/builder/FilterItem.tsx` (new)

## Implementation Details

Create a display component for individual filters showing field, operator, and value in a compact badge format with edit/delete buttons.

### Component Interface
```tsx
interface FilterItemProps {
  filter: Filter;
  onEdit: () => void;
  onDelete: () => void;
  disabled?: boolean;
}
```

### Visual Design
Display format: `[genre] contains "dubstep"  [✏️] [×]`

### Implementation Structure
```tsx
import type { Filter } from '../../api/builder';
import { getOperatorSymbol } from './filterUtils';

function FilterItem({ filter, onEdit, onDelete, disabled }: FilterItemProps) {
  const operatorSymbol = getOperatorSymbol(filter.operator);
  const isNumeric = ['year', 'bpm'].includes(filter.field);

  return (
    <div className="flex items-center justify-between bg-slate-800 rounded-lg p-2 group">
      <div className="flex items-center gap-2 text-sm">
        <span className="px-2 py-0.5 bg-blue-600 rounded text-xs font-medium">
          {filter.field}
        </span>
        <span className="text-gray-400">{operatorSymbol}</span>
        <span className="text-white">
          {isNumeric ? filter.value : `"${filter.value}"`}
        </span>
      </div>

      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          disabled={disabled}
          className="p-1 hover:bg-slate-700 rounded text-gray-400 hover:text-blue-400"
          title="Edit filter"
        >
          ✏️
        </button>
        <button
          onClick={onDelete}
          disabled={disabled}
          className="p-1 hover:bg-slate-700 rounded text-gray-400 hover:text-red-400"
          title="Delete filter"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default FilterItem;
```

### Key Features
- **Badge display**: Field name in blue badge, operator as symbol, value with quotes (if text)
- **Hover interactions**: Edit/delete buttons appear on hover (opacity transition)
- **Disabled state**: Buttons disabled during mutations
- **Type-aware formatting**: Numeric values without quotes, text values with quotes

## Acceptance Criteria

- [ ] Component renders filter badge correctly
- [ ] Operator symbols displayed using `getOperatorSymbol()` helper
- [ ] Numeric values displayed without quotes
- [ ] Text values displayed with quotes
- [ ] Edit/delete buttons appear on hover
- [ ] Buttons disabled when `disabled` prop is true
- [ ] Proper TypeScript typing for all props
- [ ] Import Filter type from `../../api/builder`

## Dependencies

- Task 01 (filterUtils.ts) - requires `getOperatorSymbol()` function
- Filter type from `web/frontend/src/api/builder.ts` (already exists)
