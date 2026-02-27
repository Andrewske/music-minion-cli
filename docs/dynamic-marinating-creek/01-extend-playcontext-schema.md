---
task: 01-extend-playcontext-schema
status: pending
depends: [00-database-migration]
files:
  - path: web/backend/schemas.py
    action: modify
---

# Extend PlayContext Schema for Organizer Context

## Context
Add support for a new "organizer" playback context that references bucket sessions. This enables the queue system to differentiate between standard playlist playback and organizer-specific playback that filters to only unassigned tracks.

## Files to Modify/Create
- web/backend/schemas.py (modify)

## Implementation Details

**Line 221** - Modify PlayContext type Literal:
```python
# Change from:
type: Literal["playlist", "track", "builder", "search", "comparison"]

# To:
type: Literal["playlist", "track", "builder", "search", "comparison", "organizer"]
```

**Line 227** - Add session_id field (after shuffle):
```python
shuffle: bool = True
session_id: Optional[str] = None  # NEW: for organizer context
```

**After session_id field** - Add Pydantic field validator for organizer context:
```python
from pydantic import field_validator

@field_validator('session_id', mode='after')
@classmethod
def validate_organizer_session_id(cls, v: Optional[str], info) -> Optional[str]:
    """Validate that organizer contexts include session_id."""
    if info.data.get('type') == 'organizer' and not v:
        raise ValueError('session_id is required when type is "organizer"')
    return v
```

Note: Using `@field_validator` instead of `@model_validator` provides clearer JSON path errors ("context.session_id is required") vs generic model validation errors.

This allows the PlayContext to carry the bucket session ID, which will be used to resolve unassigned tracks dynamically. The validator ensures schema-level validation rather than endpoint-level checks.

## Verification
- Run type checker: `uv run mypy web/backend/schemas.py`
- Verify no type errors introduced
- Confirm PlayContext now accepts `type: "organizer"`
