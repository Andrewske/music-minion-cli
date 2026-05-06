---
task: 03-extend-sync-log-telemetry
status: pending
depends: []
files:
  - path: web/backend/queries/discovery.py
    action: modify
---

# Extend `discovery_sync_log` with Funnel Telemetry + Errors

## Context

Decision #14 — track candidates_returned, deep_candidates_returned, kept_count per sync run so we can see funnel shape. Plus persist `errors` (JSON-encoded) so cron failures are queryable from SQL, not only `/var/log/discovery-sync.log`. Schema migration via `ALTER TABLE` (idempotent), called lazily from `log_sync_run` so prod auto-heals on first call. `log_sync_run` signature changes; Step 4 (`run_discovery_sync` rewrite) calls it with the new fields.

## Files to Modify/Create

- `web/backend/queries/discovery.py` (modify) — schema migration + extend `log_sync_run`

## Implementation Details

1. **Schema migration helper.** Add idempotent `ALTER TABLE` runner. Wrap each ALTER in try/except for `sqlite3.OperationalError` (column already exists) so reruns are safe:

```python
def _ensure_sync_log_columns(conn) -> None:
    for col in (
        "candidates_returned INTEGER DEFAULT 0",
        "deep_candidates_returned INTEGER DEFAULT 0",
        "kept_count INTEGER DEFAULT 0",
        "errors TEXT",
    ):
        try:
            conn.execute(f"ALTER TABLE discovery_sync_log ADD COLUMN {col}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
```

2. **Lazy invocation.** Call `_ensure_sync_log_columns(conn)` as the first statement inside `log_sync_run` (before INSERT). Self-healing on first call after deploy; no separate migration step needed. Avoids the "did we wire it into init?" question.

3. **Extend `log_sync_run` signature.** Add new kwargs, drop unused `tracks_skipped` only if confidently unused (grep first). Keep legacy params (`artists_checked`, `tracks_fetched`, `mixes_added`, `dry_run`, `duration_seconds`) for back-compat (callers still pass these or rely on defaults):

```python
def log_sync_run(
    started_at: datetime,
    candidates_returned: int = 0,
    deep_candidates_returned: int = 0,
    kept: int = 0,
    tracks_added: int = 0,
    mixes_added: int = 0,
    errors: list[str] | None = None,
    # legacy kept as no-op defaults until TODO E drops the columns
    artists_checked: int = 0,
    tracks_fetched: int = 0,
    tracks_skipped: int = 0,
    dry_run: bool = False,
    duration_seconds: float = 0.0,
) -> int:
    """Log a sync run to discovery_sync_log. Returns the log entry ID."""
    started_iso = started_at.isoformat()
    errors_json = json.dumps(errors) if errors else None
    with get_db_connection() as conn:
        _ensure_sync_log_columns(conn)
        cursor = conn.execute(
            """
            INSERT INTO discovery_sync_log
                (started_at, completed_at,
                 artists_checked, tracks_fetched, tracks_added, mixes_added,
                 tracks_skipped, dry_run, duration_seconds,
                 candidates_returned, deep_candidates_returned, kept_count, errors)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_iso,
                artists_checked,
                tracks_fetched,
                tracks_added,
                mixes_added,
                tracks_skipped,
                dry_run,
                duration_seconds,
                candidates_returned,
                deep_candidates_returned,
                kept,
                errors_json,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
```

4. **Backwards compat.** Existing call sites that still pass `tracks_fetched=...` etc. continue to work. New call site (Step 4) passes the new kwargs.

`import json` and `import sqlite3` at top of file if not already present.

## Verification

```bash
# Migration is idempotent
uv run python -c "
import sqlite3
from pathlib import Path
db = Path.home() / '.local/share/music-minion/music_minion.db'
con = sqlite3.connect(db)
from web.backend.queries.discovery import _ensure_sync_log_columns
_ensure_sync_log_columns(con)
_ensure_sync_log_columns(con)  # second call must not raise
cols = [r[1] for r in con.execute('PRAGMA table_info(discovery_sync_log)').fetchall()]
assert all(c in cols for c in ['candidates_returned','deep_candidates_returned','kept_count','errors']), cols
print('cols OK:', cols)
"

# Signature check
uv run python -c "
import inspect
from web.backend.queries.discovery import log_sync_run
params = inspect.signature(log_sync_run).parameters
for k in ['candidates_returned','deep_candidates_returned','kept','errors']:
    assert k in params, f'missing {k}'
print('sig OK')
"

# log_sync_run with errors persists JSON
uv run python -c "
from datetime import datetime, timezone
from web.backend.queries.discovery import log_sync_run, get_last_sync
log_sync_run(datetime.now(timezone.utc), errors=['boom', 'crash'], dry_run=True)
last = get_last_sync()
print('errors col:', last.get('errors'))
"

# Lint
rtk uv run ruff check web/backend/queries/discovery.py
```

Expect: idempotent migration, all four new columns/params present, errors round-trip as JSON, lint clean.
