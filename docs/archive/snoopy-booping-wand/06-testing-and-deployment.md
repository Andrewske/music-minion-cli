# Testing and Deployment

## Files to Modify/Create
- None (verification task)

## Implementation Details

### Part 1: Local End-to-End Testing

**Setup:**
```bash
# Terminal 1: Backend
cd web/backend && uv run uvicorn main:app --reload --port 8642

# Terminal 2: Frontend
cd web/frontend && npm run dev
```

**Manual Test Checklist:**

| # | Test | Expected |
|---|------|----------|
| 1 | Open http://localhost:5173 in two browser windows | Both load |
| 2 | Check console in both windows | "Connected to sync WebSocket" |
| 3 | Start comparison session in window 1 | Session starts |
| 4 | Check window 2 | Shows same comparison pair |
| 5 | Click Track B in window 1 | Window 2 shows Track B selected |
| 6 | Mark winner in window 2 | Window 1 advances to next pair |
| 7 | Close window 1, keep window 2 open | Window 2 continues working |
| 8 | Reopen window 1 | Syncs to current state |
| 9 | Disconnect network briefly | Reconnects automatically |

**Fix any issues found, then commit:**
```bash
git add -A
git commit -m "fix(sync): end-to-end testing fixes"
```

### Part 2: Deploy to Pi

```bash
./scripts/deploy-to-pi.sh
```

### Part 3: Production Testing

**Setup:**
- Laptop: Open https://music.piserver:8443
- Phone: Open https://music.piserver:8443
- Desktop CLI: Configure `remote_server = "https://music.piserver:8443"` in config.toml

**Production Test Checklist:**

| # | Test | Expected |
|---|------|----------|
| 1 | Both devices show same comparison pair | Synced |
| 2 | Mark winner on phone | Laptop advances instantly (<500ms) |
| 3 | Select Track B on laptop | Phone shows Track B |
| 4 | CLI: `music-minion web-winner` | Both devices advance |
| 5 | CLI: `music-minion web-play1` | Both devices select Track A |
| 6 | Phone loses connection briefly | Reconnects and resyncs |
| 7 | Radio track changes (if available) | Both devices update |

### Part 4: Final Commit

```bash
git add -A
git commit -m "feat(sync): complete live sync implementation"
```

## Acceptance Criteria

All checklist items pass on:
1. Local development environment
2. Production Pi server with real devices

## Dependencies

- All previous tasks (01-05) complete

## Verification Summary

| Test | Expected Result |
|------|-----------------|
| Two browsers, mark winner | Both advance instantly |
| Track selection syncs | <500ms delay |
| CLI remote command | Triggers broadcast to all clients |
| Disconnect/reconnect | State resyncs on reconnect |
| Radio track change | All clients update |
