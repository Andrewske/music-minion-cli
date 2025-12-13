# Document Expected WebSocket Browser Console Error

## Files to Modify
- `web/frontend/src/hooks/useIPCWebSocket.ts` (modify - lines 151-154)

## Implementation Details

### Problem
Browser console error "WebSocket connection to 'ws://localhost:8765/' failed: WebSocket is closed before the connection is established" appears during startup and confuses developers.

### Solution
Add explanatory comment in `onerror` handler to clarify this is **expected behavior** that cannot be suppressed via JavaScript.

### Root Cause Analysis
This error happens due to a startup race condition:
1. Frontend loads and immediately tries to connect to `ws://localhost:8765`
2. Backend WebSocket server might not be ready yet (race condition)
3. Browser logs connection failure (this is browser behavior, not suppressible)
4. The `onerror` handler already silently ignores it (correct)
5. Reconnection logic kicks in with exponential backoff (correct)

**This is NOT a bug** - it's expected behavior during startup that's already handled correctly.

### Changes to useIPCWebSocket.ts

**Lines 151-154** - Enhance comment to explain browser behavior:

```typescript
// Before:
ws.onerror = () => {
  // WebSocket connection failed - this is expected if backend isn't running
  // Silently ignore - reconnection logic will handle it
};

// After:
ws.onerror = () => {
  // WebSocket connection failed - expected if backend isn't ready yet
  //
  // NOTE: Browser will log "WebSocket connection to 'ws://localhost:8765/' failed"
  // to the console during startup race condition. This CANNOT be suppressed via
  // JavaScript - it's normal browser behavior. The reconnection logic below
  // handles it automatically with exponential backoff.
  //
  // Reconnection logic will handle it automatically
};
```

### Rationale
Documents that:
1. The browser console error is **expected** during startup
2. It **cannot be suppressed** via JavaScript (browser limitation)
3. The code **already handles it correctly** with reconnection logic
4. Future developers won't waste time trying to "fix" this non-issue

## Acceptance Criteria

- [ ] Comment updated in `useIPCWebSocket.ts`
- [ ] Comment explains browser console error is expected
- [ ] Comment clarifies error cannot be suppressed via JS
- [ ] Start `music-minion --web`, open browser console
- [ ] Verify error appears once during startup
- [ ] Verify connection succeeds after brief delay
- [ ] Verify reconnection works after backend restart

## Dependencies
None - documentation-only change

## Verification Commands

```bash
# Verify comment updated
rg -A10 "ws.onerror" web/frontend/src/hooks/useIPCWebSocket.ts

# Test WebSocket connection behavior
music-minion --web

# In browser:
# 1. Open DevTools Console
# 2. Navigate to http://localhost:5173
# 3. Observe "Connected to IPC WebSocket" message
# 4. May see brief "WebSocket connection failed" during initial load (expected)
# 5. Connection should establish within 1-2 seconds

# Test reconnection:
# 1. While running, quit music-minion (Ctrl-C)
# 2. Observe browser console shows connection attempts with backoff
# 3. Restart music-minion --web
# 4. Verify reconnection succeeds
```

## Reference
This addresses the user's original question about the console error. The answer is: **working as intended, no fix needed, just documentation**.
