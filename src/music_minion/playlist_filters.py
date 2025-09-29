"""Smart playlist filter management and evaluation.

This module handles filter rules for smart playlists, including:
- Adding/removing/updating filter rules
- Building SQL queries from filter rules
- Evaluating filters to get matching tracks
- Validating filter fields and operators
"""

from typing import List, Dict, Any, Tuple, Optional
from .database import get_db_connection


# Valid filter fields (must match tracks table columns)
VALID_FIELDS = {
    'title', 'artist', 'album', 'genre', 'year', 'bpm', 'key'
}

# Text operators for string fields
TEXT_OPERATORS = {
    'contains', 'starts_with', 'ends_with', 'equals', 'not_equals'
}

# Numeric operators for integer/float fields
NUMERIC_OPERATORS = {
    'equals', 'not_equals', 'gt', 'lt', 'gte', 'lte'
}

# Field type mapping
NUMERIC_FIELDS = {'year', 'bpm'}
TEXT_FIELDS = {'title', 'artist', 'album', 'genre', 'key'}

# Field name to column name mapping (for SQL safety)
FIELD_TO_COLUMN = {
    'title': 'title',
    'artist': 'artist',
    'album': 'album',
    'genre': 'genre',
    'year': 'year',
    'bpm': 'bpm',
    'key': 'key_signature'  # Note: database column is key_signature
}


def validate_filter(field: str, operator: str, value: str) -> None:
    """Validate filter field, operator, and value compatibility.

    Args:
        field: Field name to filter on
        operator: Filter operator
        value: Filter value

    Raises:
        ValueError: If field is invalid, operator incompatible with field type,
                   or value is invalid for numeric fields
    """
    if field not in VALID_FIELDS:
        raise ValueError(f"Invalid field: {field}. Must be one of {VALID_FIELDS}")

    # Check operator compatibility with field type
    if field in NUMERIC_FIELDS:
        if operator not in NUMERIC_OPERATORS:
            raise ValueError(
                f"Operator '{operator}' not valid for numeric field '{field}'. "
                f"Use one of: {NUMERIC_OPERATORS}"
            )
        # Validate that value is numeric
        try:
            if field == 'bpm':
                float(value)  # BPM can be float (e.g., 128.5)
            else:
                int(value)  # Year must be integer
        except ValueError:
            raise ValueError(
                f"Value '{value}' is not a valid number for numeric field '{field}'. "
                f"Expected a {'decimal' if field == 'bpm' else 'whole'} number."
            )
    elif field in TEXT_FIELDS:
        if operator not in TEXT_OPERATORS:
            raise ValueError(
                f"Operator '{operator}' not valid for text field '{field}'. "
                f"Use one of: {TEXT_OPERATORS}"
            )


def add_filter(
    playlist_id: int,
    field: str,
    operator: str,
    value: str,
    conjunction: str = 'AND'
) -> int:
    """Add a filter rule to a smart playlist.

    Args:
        playlist_id: ID of the playlist to add filter to
        field: Field name to filter on (title, artist, album, etc.)
        operator: Filter operator (contains, equals, gt, etc.)
        value: Filter value
        conjunction: How to combine with other filters ('AND' or 'OR')

    Returns:
        ID of the created filter

    Raises:
        ValueError: If validation fails or playlist doesn't exist/isn't smart
    """
    # Validate filter
    validate_filter(field, operator, value)

    if conjunction not in ('AND', 'OR'):
        raise ValueError(f"Conjunction must be 'AND' or 'OR', got: {conjunction}")

    # Verify playlist exists and is smart type
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT type FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Playlist {playlist_id} not found")

        if row['type'] != 'smart':
            raise ValueError(
                f"Cannot add filters to manual playlist. "
                f"Only smart playlists support filters."
            )

        # Insert filter
        cursor = conn.execute(
            """
            INSERT INTO playlist_filters (playlist_id, field, operator, value, conjunction)
            VALUES (?, ?, ?, ?, ?)
            """,
            (playlist_id, field, operator, value, conjunction)
        )
        conn.commit()
        return cursor.lastrowid


def remove_filter(filter_id: int) -> bool:
    """Remove a filter rule.

    Args:
        filter_id: ID of the filter to remove

    Returns:
        True if filter was removed, False if not found
    """
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM playlist_filters WHERE id = ?", (filter_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_filter(
    filter_id: int,
    field: Optional[str] = None,
    operator: Optional[str] = None,
    value: Optional[str] = None,
    conjunction: Optional[str] = None
) -> bool:
    """Update an existing filter rule.

    Args:
        filter_id: ID of the filter to update
        field: New field name (optional)
        operator: New operator (optional)
        value: New value (optional)
        conjunction: New conjunction (optional)

    Returns:
        True if filter was updated, False if not found

    Raises:
        ValueError: If validation fails
    """
    # Get current filter
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM playlist_filters WHERE id = ?", (filter_id,))
        row = cursor.fetchone()

        if not row:
            return False

        # Use current values if not provided
        new_field = field if field is not None else row['field']
        new_operator = operator if operator is not None else row['operator']
        new_value = value if value is not None else row['value']
        new_conjunction = conjunction if conjunction is not None else row['conjunction']

        # Validate new values
        validate_filter(new_field, new_operator, new_value)

        if new_conjunction not in ('AND', 'OR'):
            raise ValueError(f"Conjunction must be 'AND' or 'OR', got: {new_conjunction}")

        # Update filter
        cursor = conn.execute(
            """
            UPDATE playlist_filters
            SET field = ?, operator = ?, value = ?, conjunction = ?
            WHERE id = ?
            """,
            (new_field, new_operator, new_value, new_conjunction, filter_id)
        )
        conn.commit()
        return True


def get_playlist_filters(playlist_id: int) -> List[Dict[str, Any]]:
    """Get all filter rules for a playlist.

    Args:
        playlist_id: ID of the playlist

    Returns:
        List of filter dictionaries with keys: id, field, operator, value, conjunction
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, field, operator, value, conjunction
            FROM playlist_filters
            WHERE playlist_id = ?
            ORDER BY id
            """,
            (playlist_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def build_filter_query(filters: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """Build SQL WHERE clause from filter rules.

    Args:
        filters: List of filter dictionaries

    Returns:
        Tuple of (where_clause, parameters) for parameterized query

    Example:
        filters = [
            {'field': 'genre', 'operator': 'equals', 'value': 'dubstep', 'conjunction': 'AND'},
            {'field': 'year', 'operator': 'gte', 'value': '2025', 'conjunction': 'AND'}
        ]
        Returns: ("genre = ? AND year >= ?", ['dubstep', '2025'])
    """
    if not filters:
        return "", []

    where_parts = []
    params = []

    # Map operators to SQL
    operator_map = {
        'contains': 'LIKE',
        'starts_with': 'LIKE',
        'ends_with': 'LIKE',
        'equals': '=',
        'not_equals': '!=',
        'gt': '>',
        'lt': '<',
        'gte': '>=',
        'lte': '<='
    }

    for i, f in enumerate(filters):
        field = f['field']
        operator = f['operator']
        value = f['value']

        # Map field name to actual column name (SQL injection prevention)
        column_name = FIELD_TO_COLUMN.get(field)
        if not column_name:
            # This should never happen if validation works correctly
            raise ValueError(f"Invalid field '{field}' - not in field mapping")

        sql_op = operator_map.get(operator, '=')

        # Handle LIKE operators with wildcards
        if operator == 'contains':
            where_parts.append(f"{column_name} {sql_op} ?")
            params.append(f"%{value}%")
        elif operator == 'starts_with':
            where_parts.append(f"{column_name} {sql_op} ?")
            params.append(f"{value}%")
        elif operator == 'ends_with':
            where_parts.append(f"{column_name} {sql_op} ?")
            params.append(f"%{value}")
        else:
            # Direct comparison
            where_parts.append(f"{column_name} {sql_op} ?")
            params.append(value)

    # Join with conjunctions (default to AND for first filter)
    where_clause_parts = [where_parts[0]]
    for i in range(1, len(where_parts)):
        conjunction = filters[i - 1].get('conjunction', 'AND')
        where_clause_parts.append(f" {conjunction} {where_parts[i]}")

    where_clause = ''.join(where_clause_parts)
    return where_clause, params


def evaluate_filters(playlist_id: int) -> List[Dict[str, Any]]:
    """Evaluate smart playlist filters and return matching tracks.

    Args:
        playlist_id: ID of the smart playlist

    Returns:
        List of track dictionaries matching the filters
    """
    # Get filters for this playlist
    filters = get_playlist_filters(playlist_id)

    if not filters:
        # No filters means no tracks
        return []

    # Build WHERE clause
    where_clause, params = build_filter_query(filters)

    # Query tracks
    with get_db_connection() as conn:
        query = f"""
            SELECT *
            FROM tracks
            WHERE {where_clause}
            ORDER BY artist, album, title
        """
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]