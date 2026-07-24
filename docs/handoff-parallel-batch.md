# Handoff: Agent-Ready Parallel Batch

Context for a **fresh session** to fan out the next batch of agent-ready Palace tickets. All 7 tickets were triaged + specced on 2026-06-22/23. No prior conversation context needed.

## Tickets in this batch

| # | Title | Size | Primary files | Notes |
|---|-------|------|---------------|-------|
| #23 | EAS `appVersionSource` fix | XS | `mobile/eas.json` | One-liner: `"remote"` → `"local"`. Isolated. |
| #50 | Drop `affects_global` column | S | `src/music_minion/core/database.py`, `src/music_minion/domain/rating/database.py` (+ `tests/domain/rating/test_database.py`) | Column in `playlist_comparison_history`, always False post-migration. **Shares core/database.py with #51.** |
| #51 | Discovery `status` enum drift | S | `src/music_minion/core/database.py` (discovery_tracks table), discovery domain writers | Central constant/Enum + CHECK constraint. **Shares core/database.py with #50.** |
| #37 | AI prompt: exclude year/BPM/key tags | S | `src/music_minion/domain/ai/client.py`, `domain/ai/prompt_manager.py` | Prompt-string edit + small reject-list post-filter. |
| #38 | Sync delete `source='ai'` from COMMENT | S | `src/music_minion/domain/library/metadata.py`, `src/music_minion/domain/sync/engine.py` | Ownership rules: only strip `source='ai'`. Atomic mutagen write. |
| #44 | SC push worker bounded retry | S | `src/music_minion/domain/library/providers/soundcloud/api.py` (+ find the bg push/repost worker thread that calls it) | Single retry after ~30s, then drop. Bg thread must wrap try/except. |
| #29 | Command-bar cursor left/right | S | `src/music_minion/ui/blessed/state.py` (`cursor_pos` field exists), `ui/blessed/events/keys/` | Source plan: `docs/archive/command-bar-cursor-movement-plan.md`. Disambiguate arrows: seek vs text-edit context. |

**Full spec per ticket** (acceptance criteria + agent context): `palace issue-get music-minion-cli <N>`.

## Parallelization plan

**Conflict: #50 and #51 both edit `core/database.py` schema.** Do NOT run concurrently.

- **Wave 1 (parallel, disjoint files):** #23, #37, #38, #44, #29, **#50**
- **Wave 2:** **#51** — start only after #50 is committed (rebase on its schema change).

Possible soft overlap: #37 (`domain/ai/`) and #38 (`domain/library/metadata.py`) are both metadata-adjacent but different files — fine to parallelize; tell each its scope.

Per agent: implement → run `uv run pytest <relevant>` + `uv run ruff check <changed files>` → **do NOT git commit** (main thread reviews diffs, then commits one-per-ticket).

## Operational facts (this repo)

- **Palace CLI works without prompts** — `Bash(palace:*)` allow rule is in `.claude/settings.local.json`. Call **bare** `palace ...` (no wrapping function / no `cd` prefix, or the allow rule won't match).
  - Mark in-progress/done: `palace issue-set-labels music-minion-cli <N> "[ids]"` (custom PUT cmd; replaces full label set). IDs: agent-ready=12, in-progress=13, enhancement=6, soundcloud=4, size:small=15.
  - Close: `palace issue-comment ... && palace issue-close music-minion-cli <N>`. "Closes #N" in commits does NOT auto-close (GitHub mirror only, not Forgejo).
- **Commits:** on `main` (direct, matches history). Use `rtk git ...`. End message with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. One commit per ticket.
- **Conventions (CLAUDE.md):** functional/immutable, type hints, funcs ≤20 lines, `loguru` not `print`, atomic mutagen writes (temp + `os.replace`), data ownership (only remove `source` you own), bg threads must wrap try/except.
- **Build gate is GREEN** (#54 fixed 2026-06-23): `cd web/frontend && npm run build` exits 0.
- **Deploy** (manual, builds locally): `./scripts/deploy-to-pi.sh`. No autodeploy (#15 closed won't-do). Deploy is outward — confirm with Kevin first.

## Known pre-existing noise — do NOT blame your change / do NOT commit

- **Untracked, leave alone:** `scripts/test_*.py`, `scripts/move_sc_playlist_tracks.py`, `docs/*-progress.md`, `docs/mobile-app-completion-plan.md` — these are #14 (SC track-matching) WIP, not yours.
- **Pre-existing test failures** (verify baseline via `git stash` before attributing): `tests/.../test_youtube`, `radio/test_scheduler` (7 errors, `Station.source_filter` fixture), `web/backend/tests` collection errors, frontend vitest (`react-dom`/`useEffect` null).
- Frontend has repo-wide React-19 type quirks already handled by `web/frontend/src/jsx.d.ts`; `tsc -b` is green — don't reintroduce `: JSX.Element` issues.

## Suggested order
1. #23 (2-min, clears a mobile ticket)
2. Wave 1 fan-out (#37/#38/#44/#29/#50)
3. #51 after #50 lands
4. Review diffs → commit per ticket → push → optionally deploy + close tickets
