# Live Sync for Music Minion Web

## Overview

Enable real-time state synchronization between multiple devices viewing music.piserver. When you mark a comparison winner on your phone, your laptop immediately shows the next pair. CLI commands from your desktop can control the Pi server remotely.

**Architecture:** WebSocket broadcast from FastAPI backend. No rooms needed (single user). CLI commands POST to remote server when configured.

**Tech Stack:** FastAPI WebSocket, Zustand, TypeScript, Python

## Task Sequence

1. [01-backend-websocket-core.md](./01-backend-websocket-core.md) - Stateful SyncManager + WebSocket endpoint in `live.py`
2. [02-backend-broadcast-integration.md](./02-backend-broadcast-integration.md) - Add broadcasts to comparison verdict + radio track start
3. [03-frontend-sync-hook.md](./03-frontend-sync-hook.md) - useSyncWebSocket hook + root layout integration
4. [04-track-selection-sync.md](./04-track-selection-sync.md) - Track selection endpoint + frontend integration
5. [05-cli-remote-commands.md](./05-cli-remote-commands.md) - Config option + CLI remote POST support
6. [06-testing-and-deployment.md](./06-testing-and-deployment.md) - E2E testing + Pi deployment

## Success Criteria

| Test | Expected Result |
|------|-----------------|
| Two browsers, mark winner | Both advance instantly (<500ms) |
| Track selection syncs | Both devices show same track selected |
| CLI remote command | Triggers broadcast to all connected clients |
| Disconnect/reconnect | State resyncs automatically on reconnect |
| Radio track change | All clients update via WebSocket |

## Execution Instructions

1. Execute tasks in numerical order (01 → 06)
2. Each task file contains:
   - Files to modify/create
   - Implementation details with code
   - Acceptance criteria
   - Dependencies
3. Verify acceptance criteria before moving to next task
4. Commit after each task as specified

## Dependencies

- FastAPI with WebSocket support (already in stack)
- Zustand stores (already exist: comparisonStore, radioStore)
- Existing IPC WebSocket pattern to adapt (`useIPCWebSocket.ts`)

## Key Files

**Backend:**
- `web/backend/sync_manager.py` (new - stateful connection manager)
- `web/backend/routers/live.py` (new - WebSocket endpoint, separate from filesystem sync.py)
- `web/backend/routers/comparisons.py` (modify - add broadcast + track selection)
- `web/backend/routers/radio.py` (modify - add broadcast on track start)
- `web/backend/main.py` (modify - register live router)

**Frontend:**
- `web/frontend/src/hooks/useSyncWebSocket.ts` (new)
- `web/frontend/src/routes/__root.tsx` (modify)
- `web/frontend/src/api/comparisons.ts` (modify)

**CLI:**
- `src/music_minion/cli/web_commands.py` (modify)
- `config.toml` (add `[web] remote_server`)

## Related Docs

- Design: `docs/plans/2026-02-12-live-sync-design.md`
- Implementation: `docs/plans/2026-02-12-live-sync-implementation.md`
