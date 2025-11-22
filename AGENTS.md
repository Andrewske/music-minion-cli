# AGENTS
1. Env setup: run `uv sync --dev`, then `uv pip install -e .` for editable CLI.
2. Always execute Python via `uv run`; no direct python invocations.
3. Primary command: `uv run music-minion --dev` for hot-reload UI and blessed checks.
4. Run full tests with `uv run pytest`; single test via `uv run pytest path/to/test.py::test_case`.
5. Lint with `uv run ruff check src`; format using `uv run ruff format src`.
6. Imports must be absolute (e.g., `from music_minion.core import database`); only relative inside __init__.
7. Enforce functional style: pure functions, explicit AppContext passing, ≤20 lines and ≤3 nesting levels.
8. Use dataclasses/NamedTuple only for shared structure; avoid classes elsewhere.
9. Type every parameter and return; forbid implicit Any, unknown, or non-null assertions.
10. Naming: snake_case modules, camelCase vars/functions, PascalCase dataclasses/enums.
11. Treat state as immutable; prefer dataclasses.replace/new dicts over in-place mutation.
12. User-facing logs go through `music_minion.core.output.log`; background threads use `loguru.logger`; never print.
13. Errors must add context (provider, playlist, file) and call `logger.exception` inside except blocks.
14. Database code uses `with get_db_connection() as conn:`, batches via executemany, single commit per batch.
15. Provider modules implement pure protocols (`authenticate`, `sync_library`, `get_stream_url`) with immutable ProviderState.
16. Rendering obeys blessed three-tier redraw (full on track/resize, input for typing, partial for clocks).
17. File metadata writes must be atomic: copy to temp, edit via Mutagen, then `os.replace`.
18. Never delete data without checking `source`; only remove records owned by this tool.
19. Save new patterns to `ai-learnings.md`, note gaps in README/CLAUDE, and there are no Cursor/Copilot rule files.
