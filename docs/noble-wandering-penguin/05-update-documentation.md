# Update Documentation

## Files to Modify
- `CLAUDE.md` (modify)

## Implementation Details

Update the project documentation to reflect the new `--web` flag and web mode workflow.

### Changes to CLAUDE.md

#### Location: Development Workflow Section

Find the **Commands** subsection (currently around line 60-70) and update it:

**Current:**
```markdown
**Commands**:
- Primary: `music-minion`
- Dev mode: `music-minion --dev` (hot-reload)
- IPC: `music-minion-cli play|skip|love|...`
- Locate opus: `music-minion locate-opus /path/to/folder [--apply]`
- Web UI backend: `uv run uvicorn web.backend.main:app --reload`
- Web UI frontend: `cd web/frontend && npm install && npm run dev`
```

**Updated:**
```markdown
**Commands**:
- Primary: `music-minion`
- Dev mode: `music-minion --dev` (hot-reload)
- Web mode: `music-minion --web` (blessed UI + web backend + frontend)
- IPC: `music-minion-cli play|skip|love|...`
- Locate opus: `music-minion locate-opus /path/to/folder [--apply]`
```

#### Rationale

The `--web` flag replaces the need to manually run uvicorn and vite in separate terminals. The old commands are no longer the recommended workflow, so they're removed from the primary command list.

**Optional:** Add a note in the Development Workflow section explaining the simplified workflow:

```markdown
**Web Development Workflow**:
The `--web` flag starts all three services in one command:
- Blessed CLI UI (with IPC server for hotkeys)
- FastAPI backend (http://0.0.0.0:8000)
- Vite frontend (http://localhost:5173)

Logs are captured to `/tmp/music-minion-{uvicorn,vite}.log` to keep the terminal clean. All services stop gracefully when you quit the blessed UI.
```

## Acceptance Criteria

✅ `--web` flag documented in Commands section
✅ Old manual uvicorn/vite commands removed (no longer primary workflow)
✅ Documentation is clear and concise
✅ Optional: Web workflow explanation added for clarity

## Dependencies
- Tasks 01-03: Core implementation must be complete and working
