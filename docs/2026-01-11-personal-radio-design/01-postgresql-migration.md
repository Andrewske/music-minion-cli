# PostgreSQL Migration

## Files to Modify/Create
- `src/music_minion/core/database.py` (major refactor)
- `src/music_minion/core/config.py` (modify - add DATABASE_URL support)
- `pyproject.toml` (modify - add psycopg dependency)
- `migration_scripts/sqlite_to_postgres.py` (new - one-time migration script)
- `.env.example` (modify - add DATABASE_URL example)

## Implementation Details

Migrate music-minion from SQLite to PostgreSQL to enable Desktop CLI and Raspberry Pi to share ratings, ELO comparisons, and radio schedules.

### Database Connection Layer

1. **Add PostgreSQL dependency:**
   ```toml
   # pyproject.toml
   dependencies = [
       # ... existing deps
       "psycopg[binary,pool]>=3.1.0",  # PostgreSQL adapter with connection pooling
   ]
   ```

2. **Environment variable support:**
   ```python
   # src/music_minion/core/config.py
   def get_database_url() -> str:
       """Get database URL from environment or default to SQLite."""
       return os.getenv("DATABASE_URL", f"sqlite:///{get_data_dir() / 'music_minion.db'}")
   ```

3. **Abstract database connection:**
   ```python
   # src/music_minion/core/database.py
   from urllib.parse import urlparse

   def get_db_connection():
       db_url = get_database_url()
       parsed = urlparse(db_url)

       if parsed.scheme == "postgresql":
           # PostgreSQL connection with pooling
           import psycopg
           from psycopg_pool import ConnectionPool

           # Initialize pool if not exists (singleton pattern)
           if not hasattr(get_db_connection, '_pg_pool'):
               get_db_connection._pg_pool = ConnectionPool(
                   db_url,
                   min_size=2,
                   max_size=10,
                   timeout=30.0
               )

           with get_db_connection._pg_pool.connection() as conn:
               yield conn
       else:
           # SQLite connection (existing code)
           conn = sqlite3.connect(...)
           try:
               yield conn
           finally:
               conn.close()
   ```

### Schema Conversion

Key differences between SQLite and PostgreSQL:

| SQLite | PostgreSQL | Notes |
|--------|-----------|-------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | Auto-increment syntax |
| `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` | `TIMESTAMP DEFAULT NOW()` | Current time function |
| `datetime(...)` functions | `EXTRACT(...)` or `DATE_TRUNC(...)` | Date manipulation |
| `?` placeholders | `%s` or `%(name)s` | Parameter binding |

Create PostgreSQL schema script matching existing SQLite schema (v26).

### Query Adaptation

1. **Parameter placeholders:**
   - SQLite: `SELECT * FROM tracks WHERE id = ?`
   - PostgreSQL: `SELECT * FROM tracks WHERE id = %s`

2. **Date functions:**
   - SQLite: `datetime('now')`
   - PostgreSQL: `NOW()` or `CURRENT_TIMESTAMP`

3. **Row factory:**
   - SQLite: `conn.row_factory = sqlite3.Row`
   - PostgreSQL: Returns dict-like rows by default with `psycopg.rows.dict_row`

### Migration Script

Create one-time script to migrate existing SQLite data to PostgreSQL:

```python
# migration_scripts/sqlite_to_postgres.py
import sqlite3
import psycopg
from pathlib import Path

def migrate_sqlite_to_postgres(sqlite_path: Path, postgres_url: str):
    """Migrate all data from SQLite to PostgreSQL."""

    # Connect to both databases
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg.connect(postgres_url)

    # Get all tables
    tables = get_tables_in_order()  # Respect foreign key order

    for table in tables:
        print(f"Migrating {table}...")
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()

        if rows:
            # Build INSERT statement
            columns = list(rows[0].keys())
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

            # Batch insert
            with pg_conn.cursor() as cur:
                for row in rows:
                    cur.execute(insert_sql, tuple(row))

        pg_conn.commit()
        print(f"✓ Migrated {len(rows)} rows from {table}")

    sqlite_conn.close()
    pg_conn.close()
```

## Acceptance Criteria

- [ ] `DATABASE_URL` environment variable switches between SQLite and PostgreSQL
- [ ] All 2729 lines of `database.py` audited for SQLite-specific syntax
- [ ] PostgreSQL schema script creates all tables matching SQLite v26 schema
- [ ] Migration script successfully transfers all data from SQLite to PostgreSQL
- [ ] Test suite passes with both SQLite (no env var) and PostgreSQL (with DATABASE_URL)
- [ ] Desktop and Pi instances can connect to same hosted PostgreSQL instance
- [ ] Ratings/ELO changes on Desktop visible immediately on Pi and vice versa

## Dependencies

None - this is the foundation task that must complete before radio implementation.

## Testing Strategy

1. **Local PostgreSQL via Docker:**
   ```bash
   docker run --name postgres-test -e POSTGRES_PASSWORD=test -p 5432:5432 -d postgres:16
   export DATABASE_URL="postgresql://postgres:test@localhost:5432/music_minion"
   ```

2. **Run migration script:**
   ```bash
   uv run python migration_scripts/sqlite_to_postgres.py
   ```

3. **Verify data integrity:**
   - Check row counts match: `SELECT COUNT(*) FROM tracks`
   - Verify foreign keys intact
   - Test complex queries (ELO ratings, playlist filters)

4. **Test bidirectional sync:**
   - Add rating on Desktop
   - Query from Pi (or second local instance with same DATABASE_URL)
   - Verify rating appears immediately

## Performance Considerations

- Use connection pooling (min 2, max 10 connections) to avoid connection overhead
- Batch writes where possible (existing `executemany()` pattern)
- Index creation matches SQLite indexes for query performance
- Network latency acceptable for music curation tool (not real-time playback critical)
