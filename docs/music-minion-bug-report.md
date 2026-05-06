# Bug: `context` dict/object mismatch in `queue_manager.py`

**Date**: 2026-03-15
**Severity**: High — breaks playback and device connectivity

## Summary

`queue_manager.py` accesses `context` using dot notation (e.g., `context.type`) but in some code paths `context` is passed as a plain `dict` instead of a typed object. This causes `AttributeError: 'dict' object has no attribute 'type'` and 500 errors on multiple player endpoints.

## Affected Endpoints

- `POST /api/player/toggle-shuffle` — crashes at `player.py:530` and `player.py:550`
- `POST /api/player/next` — crashes at `player.py:368`

## Root Cause

Two functions in `queue_manager.py` use attribute access on `context`:

1. **`_resolve_context_to_track_ids`** (line ~659): `context.type` fails when `context` is a dict
2. **`save_queue_state`** (line ~253): `context.type` same issue

The `context` value at runtime is a plain dict:
```python
{'type': 'organizer', 'track_ids': None, 'playlist_id': 381, 'builder_id': None, 'query': None, 'start_index': 0, 'shuffle': ...}
```

But the code expects an object with attributes:
```python
if context.type == "track":  # AttributeError
```

## Symptoms

1. Toggling shuffle returns 500
2. Skipping to next track returns 500
3. After repeated 500s, the WebSocket connection drops: `Device disconnected, starting grace period: <device_id>`
4. UI shows **"no device available to play"** because the device is now disconnected

## Suggested Fix

Either:

**A) Convert dict to object before use** — ensure callers wrap the dict in the expected model/dataclass before passing to these functions.

**B) Use dict access** — change attribute access to bracket notation:
```python
# Before
if context.type == "track":
context.type,

# After
if context["type"] == "track":
context["type"],
```

Option A is preferable if there's already a typed model (Pydantic, dataclass, etc.) for context — the bug is likely that serialization/deserialization lost the type somewhere upstream. Check where `context` is loaded from the database or received from the API to find where it becomes a raw dict.

## Relevant Log Excerpt

```
2026-03-15 19:24:50.667 | ERROR | web.backend.queue_manager:_resolve_context_to_track_ids:733 -
    Error resolving context to track IDs: 'dict' object has no attribute 'type'
2026-03-15 19:24:50.670 | WARNING | web.backend.queue_manager:rebuild_queue:179 -
    No available tracks for queue rebuild
INFO: 172.20.0.1:52604 - "POST /api/player/toggle-shuffle HTTP/1.1" 500 Internal Server Error
2026-03-15 19:23:14.443 | INFO | web.backend.routers.live:sync_websocket:45 -
    Device disconnected, starting grace period: 2b3cfcd9-d046-42d0-b6d4-2ed16ae10152
```
