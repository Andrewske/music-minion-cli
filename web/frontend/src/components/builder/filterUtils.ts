// Filter utilities for playlist builder
// Pure functions for validation, formatting, and constants

export const TEXT_OPERATORS = ['contains', 'starts_with', 'ends_with', 'equals', 'not_equals'] as const;
export const NUMERIC_OPERATORS = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'] as const;
export const NUMERIC_FIELDS = ['year', 'bpm'] as const;
export const TEXT_FIELDS = ['title', 'artist', 'album', 'genre', 'key'] as const;

export type TextOperator = typeof TEXT_OPERATORS[number];
export type NumericOperator = typeof NUMERIC_OPERATORS[number];
export type NumericField = typeof NUMERIC_FIELDS[number];
export type TextField = typeof TEXT_FIELDS[number];
export type FilterField = NumericField | TextField;
export type FilterOperator = TextOperator | NumericOperator;

/**
 * Validates a filter configuration
 * @param field - The field to filter on
 * @param operator - The comparison operator
 * @param value - The value to compare against
 * @returns Error message if invalid, null if valid
 */
export function validateFilter(field: string, operator: string, value: string): string | null {
  // Required fields check
  if (!field || !operator || !value) {
    return "All fields are required";
  }

  // Numeric field validation
  if (NUMERIC_FIELDS.includes(field as NumericField)) {
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
  const isNumericField = NUMERIC_FIELDS.includes(field as NumericField);
  const isNumericOperator = NUMERIC_OPERATORS.includes(operator as NumericOperator);
  const isTextOperator = TEXT_OPERATORS.includes(operator as TextOperator);

  if (isNumericField && !isNumericOperator) {
    return `Operator '${operator}' is not valid for numeric field '${field}'`;
  }
  if (!isNumericField && !isTextOperator) {
    return `Operator '${operator}' is not valid for text field '${field}'`;
  }

  return null;
}

/**
 * Gets the display symbol for a filter operator
 * @param operator - The operator to get symbol for
 * @returns Display symbol or the operator name if not found
 */
export function getOperatorSymbol(operator: string): string {
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

/**
 * Gets appropriate placeholder text for filter value input
 * @param field - The field being filtered
 * @param operator - The operator being used
 * @returns Placeholder text for the input field
 */
export function getPlaceholder(field: string, operator: string): string {
  if (field === 'year') {
    return operator === 'equals' ? '2025' : '2020';
  }
  if (field === 'bpm') {
    return operator === 'equals' ? '140' : '120';
  }
  if (operator === 'contains') {
    return 'search term...';
  }
  if (operator === 'starts_with') {
    return 'prefix...';
  }
  if (operator === 'ends_with') {
    return 'suffix...';
  }
  return 'value...';
}