# Playlist Organizer: Multiple Sessions (new / reload)

Origin: `docs/ideas.md` #13 (2026-03-05). Also closes the TODOS item "Investigate stuck `active` `bucket_sessions`".

## Goal

Per playlist in the organizer:
- **New session**: all tracks go back to unassigned, zero buckets. The previous session is kept, not destroyed.
- **Reload session**: pick an older session from a dropdown and get its buckets and assignments back.
- Rename and delete sessions.

## What exists today

Most of the plumbing is already there. Sessions are a real table; the app just only ever shows one.

| Piece | State |
|---|---|
| `bucket_sessions (id, playlist_id, created_at, status)` | exists. `status` is `active` / `applied` / `discarded` |
| Partial unique index `idx_active_session_playlist` | one `active` session per playlist |
| `buckets.session_id`, `bucket_tracks` | already scoped per session, so many sessions per playlist works at the data level |
| `POST /api/buckets/sessions` | get-or-create the single active session |
| Reset button (`RotateCcw`, `PlaylistOrganizer.tsx:587`) | calls **finalize**: marks session `applied`, page refetches, a fresh empty session is created. So "new session" half-works already, but the old one can never be reopened |
| `finalize_session` | does NOT delete buckets or `bucket_tracks`. Old sessions are intact in the DB |
| `discard_session` | strips bucket emojis from tracks, marks `discarded`. Rows stay |

Live DB (pi, 2026-11-10): 10 `active`, 3 `applied`, 0 `discarded` sessions. The 3 applied sessions still hold 6 buckets / 24 track assignments, so they become reloadable for free once the UI exists.

### Gotchas found while reading the code

1. **Reset triggers discovery side effects.** `finalize_session_endpoint` runs `_update_discovery_feedback`: on discovery playlists it marks tracks liked/dismissed, **likes tracks on SoundCloud**, and deletes dismissed tracks from `tracks`. A "new session" must not do this. That needs a separate, quiet "park" transition.
2. **Resume reconciliation deletes data.** `get_or_create_session` hard-deletes `bucket_tracks` whose track left the playlist. Fine for one live session. For a session parked for weeks it's lossy: discovery sync clears and refills discovery playlists, so reloading would come back to empty buckets. (It also skips the emoji cleanup and linked-playlist unsync that `unassign_track` does.)
3. **Player queue.** `queue_manager.py:902/983` falls back to playlist context when the organizer session isn't active. Switching sessions mid-playback silently drops organizer context. Acceptable, but worth a toast or a rebuild.
4. **`discovery_sync.py:61`** reads "the active session". This stays correct as long as "active" means "currently loaded".
5. **Dead code**: `localStorage organizer-session-${playlistId}` gets written and removed but is never read. Delete it.
6. **Mobile** (`mobile/app/(main)/organizer/*`) calls `createOrResumeSession` too. Keeping that endpoint's behavior unchanged means mobile keeps working untouched.

## Design

### Status model

Keep `active` meaning "the session currently loaded for this playlist" (the unique index already enforces one). Add `parked`.

```
            new / activate other              activate
  active ─────────────────────────▶ parked ───────────▶ active
    │  finalize (discovery feedback)                       ▲
    ├────────────────────────────▶ applied ───activate─────┘
    │  discard
    └────────────────────────────▶ discarded   (hidden, terminal)
```

`applied` sessions can be reopened too: that's the user asking to revisit finished work. `discarded` stays hidden.

With this model, 10 active sessions across 10 playlists is normal, not "stuck". The TODOS item becomes a non-issue; delete it when this ships.

### Schema (v71)

```sql
ALTER TABLE bucket_sessions ADD COLUMN name TEXT;
ALTER TABLE bucket_sessions ADD COLUMN last_opened_at TIMESTAMP;
UPDATE bucket_sessions SET last_opened_at = created_at;
CREATE INDEX idx_bucket_sessions_playlist_status ON bucket_sessions(playlist_id, status);
```

`name` is nullable. The UI falls back to `"Session · Nov 10"` built from `created_at`. No CHECK constraint on `status` today, so `parked` needs no table rebuild.

### Backend: `web/backend/queries/buckets.py`

New pure-ish query functions (each one transaction):

- `list_sessions(playlist_id) -> list[dict]`: non-discarded sessions, newest `last_opened_at` first, with `bucket_count`, `assigned_count` (counting only tracks still in the playlist), `name`, `status`, `created_at`.
- `_park_active_session(conn, playlist_id) -> None`: `UPDATE ... SET status='parked' WHERE playlist_id=? AND status='active'`. No side effects.
- `create_new_session(playlist_id, name: str | None) -> dict`: park, insert new active, return `get_session_with_data`.
- `activate_session(session_id) -> dict | None`: look up playlist, park the current active, set target `active` + `last_opened_at = now`. Order matters: park first or the partial unique index rejects the update. Reject `discarded` (404).
- `rename_session(session_id, name) -> bool`.

Change the reconciliation (gotcha 2): stop deleting in `get_or_create_session`. Filter at read time in `get_session_with_data` instead: join `bucket_tracks` against `playlist_tracks` for the session's playlist. Tracks that leave and come back reappear in their bucket, and parked sessions survive discovery refills. Cost: stale `bucket_tracks` rows pile up. They're tiny and cascade-delete with the session.

`apply_session` already only touches tracks in `playlist_tracks`, so it needs no change.

### Backend: `web/backend/routers/buckets.py`

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/sessions?playlist_id=` | | `list[SessionSummary]` |
| POST | `/sessions/new` | `{playlist_id, name?}` | `SessionResponse` |
| POST | `/sessions/{id}/activate` | | `SessionResponse` |
| PATCH | `/sessions/{id}` | `{name}` | `{renamed: true}` |
| DELETE | `/sessions/{id}` | | existing discard, unchanged |
| POST | `/sessions` | | unchanged (get-or-create active) |

Route order: register `/sessions/new` before `/sessions/{session_id}` routes. `SessionResponse` gains `name`, `created_at`.

### Shared API: `shared/src/api/buckets.ts`

- `BucketSession.status` adds `'parked'`; add `name: string | null`, `created_at: string`.
- New `SessionSummary` type plus `listSessions`, `createNewSession`, `activateSession`, `renameSession`.

### Frontend hook: `web/frontend/src/hooks/usePlaylistOrganizer.ts`

- Keep `queryKey = ['organizer','session',playlistId]` for the loaded session (still backed by `createOrResumeSession`).
- Add `sessionsQueryKey = ['organizer','sessions',playlistId]` for the list (fetched lazily when the dropdown opens).
- `newSession(name?)` / `switchSession(id)` mutations: `setQueryData(queryKey, returnedSession)` (no refetch flash), invalidate the list.
- `renameSession`, `deleteSession` (deleting the loaded one: invalidate `queryKey`, and the get-or-create endpoint makes a fresh one).
- Existing mutations keep keying off `session.id`, so they follow the switch automatically.

### Frontend UI: `web/frontend/src/pages/PlaylistOrganizer.tsx`

New component `components/organizer/SessionSwitcher.tsx` (Radix/shadcn `DropdownMenu`), placed under the playlist name where the "N unassigned" subtitle sits:

```
Reposts                                   [Apply Order]
▾ Dubstep split · Nov 3  ·  212 unassigned
  ┌──────────────────────────────────────┐
  │ ✓ Dubstep split    4 buckets · 88    │  ← current, click name to rename
  │   Session · Oct 20 3 buckets · 41  🗑 │
  │   Vibes (done)     2 buckets · 12  🗑 │  ← applied sessions marked
  │ ──────────────────────────────────── │
  │ + New session                        │
  │ ✔ Finish session                     │  ← old finalize, discovery playlists get a warning line
  └──────────────────────────────────────┘
```

- Remove the standalone `RotateCcw` reset button. Its meaning was ambiguous and it fired SC likes.
- Delete asks for confirmation (it strips bucket emojis).
- Switching while organizer playback is active: show a toast "Playback switched to playlist order" (gotcha 3), or rebuild the queue with the new session id if that's cheap in `PlayerBar`/`playerStore`.
- Remove the dead localStorage writes.

## Decisions (resolved 2026-11-10)

1. **Bucket emojis when parking:** leave them on the tracks. Only delete (discard) strips them.
2. **Linked playlists on switch:** leave as is. A parked session's buckets stay linked.
   **Plus pull-on-link:** when a bucket gets linked to playlist P (any session, typically a new session reusing a playlist an older session linked), offer to pull in the tracks that are in P *and* in the playlist being organized *and* currently unassigned in this session. The user picks "Assign N tracks" or "Keep unassigned" (so they can still sort them into other buckets).
3. **New session from these buckets:** later improvement, not in this PR.
4. **Mobile session switcher:** out of scope, tracked as a GitHub issue.

## API contract (both agents build against this)

Session JSON (`SessionResponse`) gains two fields:
```json
{ "id": "...", "playlist_id": 1, "status": "active", "name": null,
  "created_at": "2026-11-10 12:00:00", "buckets": [...], "unassigned_track_ids": [...] }
```
`status` is one of `active | parked | applied | discarded`.

`SessionSummary`:
```json
{ "id": "...", "playlist_id": 1, "name": "Dubstep split" | null, "status": "active",
  "created_at": "...", "last_opened_at": "...", "bucket_count": 4, "assigned_count": 88 }
```

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/buckets/sessions?playlist_id=1` | | `SessionSummary[]` (non-discarded, `last_opened_at` desc) |
| POST | `/api/buckets/sessions/new` | `{playlist_id, name?: string\|null}` | `SessionResponse` (old active becomes `parked`) |
| POST | `/api/buckets/sessions/{id}/activate` | | `SessionResponse`; 404 if missing or discarded |
| PATCH | `/api/buckets/sessions/{id}` | `{name: string\|null}` | `{renamed: true}`; 404 if missing |
| POST | `/api/buckets/{bucket_id}/link` | `{playlist_id}` (unchanged) | `{linked: bool, pullable_track_ids: number[]}` (empty list when unlinking) |
| POST | `/api/buckets/{bucket_id}/pull-linked` | | `{assigned: number}`: assigns the current pullable set to the bucket (emojis applied as in normal assign) |

`pullable_track_ids` = tracks in the linked playlist ∩ the session's playlist that are in no bucket of this session, ordered by position in the session's playlist. Computed after the link-time push of existing bucket tracks.

## Tasks

1. Migration v71 + `SCHEMA_VERSION` bump (`src/music_minion/core/database.py`).
2. Query functions + read-time reconciliation (`web/backend/queries/buckets.py`).
3. Endpoints + schemas (`web/backend/routers/buckets.py`).
4. Backend tests: new file `web/backend/tests/test_bucket_sessions.py` (there are no bucket query tests today). Cover: new parks old; activate swaps and respects the unique index; activate applied session works; discarded can't be activated; list excludes discarded and orders by `last_opened_at`; tracks removed from the playlist are hidden but return when re-added; `get_or_create_session` unchanged for mobile; parking does NOT call discovery feedback.
5. Shared API types/functions (`shared/src/api/buckets.ts`).
6. Hook mutations (`web/frontend/src/hooks/usePlaylistOrganizer.ts`) + vitest for cache behavior on switch.
7. `SessionSwitcher` component + wire into `PlaylistOrganizer.tsx`, remove reset button and dead localStorage.
8. Remove the stuck-sessions item from `TODOS.md`, mark idea #13 done.
9. Pull-on-link: backend `pullable_track_ids` + `pull-linked` (with tests); frontend prompt after linking in `BucketEditDialog` / page ("N tracks from <P> are already in this playlist: Assign / Keep unassigned").

Size: roughly 1 to 1.5 days by hand, a couple of hours with an agent. Backend tasks 1-4 are independent of 5-7 once the API shape above is agreed.

## Deploy notes

- Migration runs on the pi (DB owner) on container start. Additive only, no data rewrite besides backfilling `last_opened_at`.
- Test against a snapshot first: `scripts/pull-db-snapshot.sh`, then `MUSIC_MINION_DB_PATH=<snapshot> uv run music-minion --web`. The 3 existing `applied` sessions make good reload fixtures.
