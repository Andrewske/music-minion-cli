# Create Filter Utilities Module

## Files to Create
- `web/frontend/src/components/builder/filterUtils.ts` (new)

## Implementation Details

Create a utilities module containing validation logic, helper functions, and constants for filter operations.

### Required Functions

**1. validateFilter(field, operator, value): string | null**
```tsx
function validateFilter(field: string, operator: string, value: string): string | null {
  // Required fields check
  if (!field || !operator || !value) {
    return "All fields are required";
  }

  // Numeric field validation
  if (['year', 'bpm'].includes(field)) {
    const num = parseFloat(value);
    if (isNaN(num)) {
      return `${field} must be a number`;
    }
    if (field === 'year' && !Number.isInteger(num)) {
      return "Year must be a whole number";
    }
    if (num < 0) {
      return `${field} cannot be negative`;
    }
  }

  // Empty string check for text fields
  if (value.trim() === '') {
    return "Value cannot be empty";
  }

  // Operator compatibility (defensive check)
  const isNumericField = ['year', 'bpm'].includes(field);
  const isNumericOperator = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'].includes(operator);
  const isTextOperator = ['contains', 'equals', 'not_equals', 'starts_with', 'ends_with'].includes(operator);

  if (isNumericField && !isNumericOperator) {
    return `Operator '${operator}' is not valid for numeric field '${field}'`;
  }
  if (!isNumericField && !isTextOperator) {
    return `Operator '${operator}' is not valid for text field '${field}'`;
  }

  return null;
}
```

**2. getOperatorSymbol(operator): string**
```tsx
function getOperatorSymbol(operator: string): string {
  const symbols: Record<string, string> = {
    contains: '~',
    equals: '=',
    not_equals: '≠',
    starts_with: 'starts with',
    ends_with: 'ends with',
    gt: '>',
    gte: '≥',
    lt: '<',
    lte: '≤',
  };
  return symbols[operator] || operator;
}
```

**3. getPlaceholder(field, operator): string**
```tsx
function getPlaceholder(field: string, operator: string): string {
  if (field === 'year') return operator === 'equals' ? '2025' : '2020';
  if (field === 'bpm') return operator === 'equals' ? '140' : '120';
  if (operator === 'contains') return 'search term...';
  if (operator === 'starts_with') return 'prefix...';
  if (operator === 'ends_with') return 'suffix...';
  return 'value...';
}
```

### Required Constants

Export these constants for use in other components:
```tsx
export const TEXT_OPERATORS = ['contains', 'starts_with', 'ends_with', 'equals', 'not_equals'];
export const NUMERIC_OPERATORS = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'];
export const NUMERIC_FIELDS = ['year', 'bpm'];
export const TEXT_FIELDS = ['title', 'artist', 'album', 'genre', 'key'];
```

## Acceptance Criteria

- [ ] All three functions exported and properly typed
- [ ] Constants exported for reuse
- [ ] Validation covers all edge cases:
  - Empty field/operator/value
  - Non-numeric values for numeric fields
  - Decimal year (should fail)
  - Decimal BPM (should pass)
  - Negative numbers (should fail)
  - Incompatible operator for field type
- [ ] No external dependencies (pure utility module)
- [ ] TypeScript compiles without errors

## Dependencies

None - this is a foundational module that other components will depend on.
