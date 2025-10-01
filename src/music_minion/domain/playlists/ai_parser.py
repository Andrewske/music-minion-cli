"""AI-powered natural language parsing for smart playlist creation.

This module uses OpenAI to parse natural language descriptions into
structured filter rules for smart playlists.
"""

import json
import time
from typing import List, Dict, Any, Tuple, TypedDict

from ..ai import get_api_key, AIError
from .filters import (
    VALID_FIELDS, TEXT_OPERATORS, NUMERIC_OPERATORS,
    NUMERIC_FIELDS, TEXT_FIELDS, validate_filter
)


# Constants
CONJUNCTION_AND = "AND"
CONJUNCTION_OR = "OR"
DEFAULT_CONJUNCTION = CONJUNCTION_AND


# Operator display mapping for prettier output
OPERATOR_DISPLAY_MAP = {
    'gte': '>=',
    'lte': '<=',
    'gt': '>',
    'lt': '<',
    'starts_with': 'starts with',
    'ends_with': 'ends with',
    'not_equals': '!=',
}


class FilterDict(TypedDict):
    """Type definition for filter dictionary."""
    field: str
    operator: str
    value: str
    conjunction: str


def parse_natural_language_to_filters(description: str) -> Tuple[List[FilterDict], Dict[str, Any]]:
    """Parse natural language description into structured filter rules using AI.

    Args:
        description: Natural language description of desired playlist
                    (e.g., "all dubstep songs from albums ending with 25")

    Returns:
        Tuple of (filters_list, request_metadata) where filters_list contains
        filter dictionaries with keys: field, operator, value, conjunction

    Raises:
        AIError: If API key not found, API error, or invalid response format
    """
    api_key = get_api_key()
    if not api_key:
        raise AIError("No OpenAI API key found. Use 'ai setup <key>' to configure.")

    try:
        import openai
    except ImportError:
        raise AIError("OpenAI library not installed. Install with: pip install openai")

    # Build structured prompt with schema
    instruction = """Parse the user's playlist description into structured filter rules.

Available fields: title, artist, album, genre, year, bpm, key

Text operators (for title, artist, album, genre, key): contains, starts_with, ends_with, equals, not_equals
Numeric operators (for year, bpm): equals, not_equals, gt, lt, gte, lte

Return ONLY a valid JSON array of filter objects. Each filter must have:
- field: one of the available fields
- operator: appropriate operator for the field type
- value: the filter value as a string
- conjunction: "AND" or "OR" (how to combine with previous filter)

Example valid output:
[
  {"field": "genre", "operator": "equals", "value": "dubstep", "conjunction": "AND"},
  {"field": "album", "operator": "ends_with", "value": "25", "conjunction": "AND"}
]

IMPORTANT:
- Return ONLY the JSON array, no additional text
- Use actual operators from the list above (contains, starts_with, ends_with, equals, not_equals, gt, lt, gte, lte)
- For year comparisons, use numeric operators (gte, lte, gt, lt, equals, not_equals)
- For text matching, use text operators (contains, starts_with, ends_with, equals, not_equals)
- Values should be strings, even for numeric fields
- First filter's conjunction doesn't matter, but include it for consistency"""

    input_text = f"""Playlist description: "{description}"

Parse this into filter rules following the schema provided in the instructions."""

    # Prepare OpenAI client
    client = openai.OpenAI(api_key=api_key)

    start_time = time.time()

    try:
        # Make API request using Responses API
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=instruction,
            input=input_text
        )

        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)

        # Parse JSON response
        output_text = response.output_text.strip()

        # Try to parse as JSON
        try:
            filters = json.loads(output_text)
        except json.JSONDecodeError as e:
            raise AIError(f"AI returned invalid JSON: {e}\n\nResponse: {output_text}")

        # Validate structure
        if not isinstance(filters, list):
            raise AIError(f"AI response is not a list: {type(filters)}")

        if not filters:
            raise AIError("AI returned empty filter list")

        # Validate each filter has required keys
        for i, f in enumerate(filters):
            if not isinstance(f, dict):
                raise AIError(f"Filter {i+1} is not a dictionary: {type(f)}")

            required_keys = {'field', 'operator', 'value', 'conjunction'}
            missing_keys = required_keys - set(f.keys())
            if missing_keys:
                raise AIError(f"Filter {i+1} missing keys: {missing_keys}")

        # Build request metadata
        request_metadata = {
            'prompt_tokens': response.usage.input_tokens,
            'completion_tokens': response.usage.output_tokens,
            'response_time_ms': response_time_ms,
            'success': True
        }

        return filters, request_metadata

    except openai.APIError as e:
        raise AIError(f"OpenAI API error: {str(e)}")

    except Exception as e:
        raise AIError(f"Unexpected error: {str(e)}")


def format_filters_for_preview(filters: List[FilterDict]) -> str:
    """Format filter list as numbered display for preview.

    Args:
        filters: List of filter dictionaries

    Returns:
        Formatted string with numbered filters

    Example output:
        1. genre equals "dubstep"
        2. album ends_with "25" (AND)
        3. year >= 2025 (AND)
    """
    if not filters:
        return "No filters"

    lines = []
    for i, f in enumerate(filters, 1):
        field = f['field']
        operator = f['operator']
        value = f['value']
        conjunction = f.get('conjunction', DEFAULT_CONJUNCTION)

        # Format operator for display using mapping
        op_display = OPERATOR_DISPLAY_MAP.get(operator, operator.replace('_', ' '))

        # Format the line
        line = f"{i}. {field} {op_display} \"{value}\""

        # Add conjunction indicator for filters after the first
        if i > 1:
            line += f" ({conjunction})"

        lines.append(line)

    return "\n".join(lines)


def edit_filters_interactive(filters: List[FilterDict]) -> List[FilterDict]:
    """Interactive editor for filter list.

    Allows user to:
    - edit <n>: Edit a specific filter
    - remove <n>: Remove a filter
    - add: Add a new filter
    - done: Finish editing

    Args:
        filters: List of filter dictionaries to edit

    Returns:
        Modified list of filters
    """
    while True:
        print("\n" + "=" * 60)
        print("Current filters:")
        print(format_filters_for_preview(filters))
        print("\n" + "=" * 60)
        print("Commands: edit <n>, remove <n>, add, done")

        command = input("\nCommand: ").strip().lower()

        if command == 'done':
            break

        elif command == 'add':
            # Add new filter
            print("\nAdding new filter...")
            print("Available fields: " + ", ".join(sorted(VALID_FIELDS)))

            field = input("Field: ").strip().lower()
            if field not in VALID_FIELDS:
                print(f"❌ Invalid field. Must be one of: {', '.join(sorted(VALID_FIELDS))}")
                continue

            # Show valid operators
            if field in NUMERIC_FIELDS:
                print(f"Numeric operators: {', '.join(sorted(NUMERIC_OPERATORS))}")
                valid_ops = NUMERIC_OPERATORS
            else:
                print(f"Text operators: {', '.join(sorted(TEXT_OPERATORS))}")
                valid_ops = TEXT_OPERATORS

            operator = input("Operator: ").strip().lower()
            if operator not in valid_ops:
                print(f"❌ Invalid operator for {field}")
                continue

            value = input("Value: ").strip()
            if not value:
                print("❌ Value cannot be empty")
                continue

            # Ask for conjunction
            conjunction = 'AND'
            if filters:
                conj_input = input("Combine with previous filters using AND or OR? [AND]: ").strip().upper()
                if conj_input in ('AND', 'OR'):
                    conjunction = conj_input

            # Validate the filter
            try:
                validate_filter(field, operator, value)
                filters.append({
                    'field': field,
                    'operator': operator,
                    'value': value,
                    'conjunction': conjunction
                })
                print(f"✅ Added filter: {field} {operator} '{value}'")
            except ValueError as e:
                print(f"❌ Validation error: {e}")

        elif command.startswith('edit '):
            # Edit existing filter
            try:
                index = int(command.split()[1]) - 1
                if index < 0 or index >= len(filters):
                    print(f"❌ Invalid filter number. Must be 1-{len(filters)}")
                    continue
            except (ValueError, IndexError):
                print("❌ Invalid command. Use: edit <number>")
                continue

            current = filters[index]
            print(f"\nEditing filter {index + 1}: {current['field']} {current['operator']} \"{current['value']}\"")

            # Edit field
            field_input = input(f"Field [{current['field']}]: ").strip().lower()
            field = field_input if field_input else current['field']

            if field not in VALID_FIELDS:
                print(f"❌ Invalid field. Must be one of: {', '.join(sorted(VALID_FIELDS))}")
                continue

            # Show valid operators for the field
            if field in NUMERIC_FIELDS:
                print(f"Numeric operators: {', '.join(sorted(NUMERIC_OPERATORS))}")
                valid_ops = NUMERIC_OPERATORS
            else:
                print(f"Text operators: {', '.join(sorted(TEXT_OPERATORS))}")
                valid_ops = TEXT_OPERATORS

            # Edit operator
            operator_input = input(f"Operator [{current['operator']}]: ").strip().lower()
            operator = operator_input if operator_input else current['operator']

            if operator not in valid_ops:
                print(f"❌ Invalid operator for {field}")
                continue

            # Edit value
            value_input = input(f"Value [{current['value']}]: ").strip()
            value = value_input if value_input else current['value']

            # Edit conjunction (only if not first filter)
            conjunction = current.get('conjunction', 'AND')
            if index > 0:
                conj_input = input(f"Conjunction [{conjunction}]: ").strip().upper()
                if conj_input in ('AND', 'OR'):
                    conjunction = conj_input

            # Validate the updated filter
            try:
                validate_filter(field, operator, value)
                filters[index] = {
                    'field': field,
                    'operator': operator,
                    'value': value,
                    'conjunction': conjunction
                }
                print(f"✅ Updated filter {index + 1}")
            except ValueError as e:
                print(f"❌ Validation error: {e}")

        elif command.startswith('remove '):
            # Remove filter
            try:
                index = int(command.split()[1]) - 1
                if index < 0 or index >= len(filters):
                    print(f"❌ Invalid filter number. Must be 1-{len(filters)}")
                    continue
            except (ValueError, IndexError):
                print("❌ Invalid command. Use: remove <number>")
                continue

            removed = filters.pop(index)
            print(f"✅ Removed filter: {removed['field']} {removed['operator']} \"{removed['value']}\"")

            if not filters:
                print("⚠️  No filters remaining. Type 'add' to add filters or 'done' to exit.")

        else:
            print("❌ Unknown command. Use: edit <n>, remove <n>, add, or done")

    return filters