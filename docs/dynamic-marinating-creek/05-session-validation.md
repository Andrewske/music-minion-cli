---
task: 05-session-validation
status: pending
depends: [02-implement-queue-resolution]
files:
  - path: web/backend/routers/player.py
    action: modify
---

# Add Session Validation for Organizer Context

## Context
Validate that organizer playback contexts reference valid, active bucket sessions. This prevents playback errors when sessions are missing, inactive, or have been applied/discarded.

**Note:** Basic validation (session_id required for organizer) is handled by Pydantic validator in PlayContext schema (task 01). This task adds runtime validation for session existence and status.

## Files to Modify/Create
- web/backend/routers/player.py (modify)

## Implementation Details

**In the `play()` endpoint** - Add session validation after parsing request:

```python
# Validate organizer session exists and is active
if request.context.type == "organizer":
    from ..queries.buckets import get_session_with_data
    session = get_session_with_data(request.context.session_id)
    if not session:
        raise HTTPException(404, f"Organizer session {request.context.session_id} not found")
    if session["status"] != "active":
        raise HTTPException(400, f"Organizer session is {session['status']}, cannot play")
```

## Verification
- Test missing session_id: `POST /api/player/play` with `context.type: "organizer"` but no `session_id`
  - Expect: 400 Bad Request
- Test invalid session_id: Use non-existent session UUID
  - Expect: 404 Not Found
- Test inactive session: Apply a session, then try to play from it
  - Expect: 400 Bad Request with message about session status
- Test valid session: Create active session and play
  - Expect: 200 OK, playback starts
