# Artists Page (Luminous Curating Heron)

Top-level **Artists** page in the web UI for cross-source artist stats, following hygiene, and feed-noise triage. Artist is the unit; sources (local, SoundCloud, Spotify-later) are facets.

## Goal

Give Kevin a single view to:
1. Browse every artist present in his data (library tracks, SC follows, reposters in feed)
2. See aggregated stats per artist (library count, repost count, repost hit rate, feed noise, rank, follow status)
3. Cleanly unfollow SC artists who create noise but aren't in his top 200
4. Toggle which stats are visible (card layout, stat-chips customizable)

## Non-goals (v1)

- Spotify integration (schema-ready, feature-deferred)
- Bulk-unfollow UI
- Feed noise trends/charts (just current 7/30d averages)
- Following *new* artists from the page

---

## Architecture

### Identity & matching

Artists live in a new `artists` table keyed by internal ID, with per-source facets (`artist_sources`):

```
artists
  id INTEGER PK
  canonical_name TEXT
  created_at, updated_at

artist_sources
  id INTEGER PK
  artist_id FK -> artists.id
  source TEXT  -- 'local' | 'soundcloud' | 'spotify'
  source_id TEXT  -- SC user id, Spotify id, or NULL for local-only
  source_name TEXT  -- name as it appears on that source
  avatar_url TEXT NULL
  follower_count INTEGER NULL
  is_following BOOLEAN  -- only meaningful for SC/Spotify
  raw_json TEXT NULL  -- dump for later expansion
  last_synced_at TIMESTAMP
  UNIQUE(source, source_id)
  UNIQUE(source, source_name) WHERE source_id IS NULL  -- local-only
```

**Matching strategy:**
- On SC sync / library scan, normalize name (lowercase, strip punctuation, unicode-fold)
- Look up existing `artist_sources` by normalized name; if found, attach to same `artist_id`
- Else create new `artists` row + `artist_sources` row
- **Manual override table**:

```
artist_match_overrides
  id INTEGER PK
  artist_id FK -> artists.id  -- target
  source TEXT
  source_id TEXT NULL
  source_name TEXT  -- the variant being pinned
  action TEXT  -- 'merge' | 'split'
  created_at
```

Name variants (e.g. local tag "Deadmau5" vs SC "deadmau5") get pinned here, taking precedence over auto-match.

### Feed event log

Raw events, no pre-aggregation, derive stats at query time:

```
sc_feed_events
  id INTEGER PK
  artist_source_id FK -> artist_sources.id  -- the reposter
  track_sc_id TEXT  -- SC track id (not necessarily in local library)
  track_title TEXT
  seen_at TIMESTAMP  -- when our cron saw it
  reposted_at TIMESTAMP  -- when SC says it was reposted
  INDEX (artist_source_id, seen_at)
  INDEX (track_sc_id)
```

**Cascade rule**: when a SC artist is unfollowed via our UI, delete their `sc_feed_events` rows. Matching `artists` row stays (may still have library tracks by them).

### Feed-sync daemon

Modeled after `web/backend/sc_push_worker.py` — daemon thread in FastAPI backend.

```
web/backend/sc_feed_worker.py
  - on startup: spawn daemon thread
  - loop: check sc_feed_sync_state.last_run_at
    - if > 24h ago (or never): run fetch
    - else: sleep until next 24h boundary
  - fetch: page through SC stream endpoint, filter repost items,
    upsert artist_sources for any new reposters, insert feed events
  - log to loguru; errors caught & logged, thread survives
```

```
sc_feed_sync_state
  id INTEGER PK (single row)
  last_run_at TIMESTAMP
  last_run_status TEXT  -- 'ok' | 'error'
  last_error TEXT NULL
  events_added_last_run INTEGER
```

Manual trigger endpoint `POST /api/soundcloud/feed-sync` drains same work (shared function), useful for dev + forcing updates.

### Stats derivation

All computed at query time via SQL (no materialized stats):

| Stat | Query shape |
|------|-------------|
| Library track count | `COUNT tracks WHERE artist matches any of this artist's sources` |
| Reposts in library | `COUNT tracks WHERE reposter_artist_id matches` (uses existing repost tracking) |
| Repost hit rate | `COUNT reposts IN (monthly playlists ∪ likes)` / `COUNT reposts` |
| Feed noise (7d/30d avg) | `COUNT sc_feed_events WHERE artist_source_id = X AND seen_at > now - N days` / N |
| Last loved at | `MAX loved_at FROM loves JOIN tracks WHERE artist matches` |
| Avg ELO | `AVG elo FROM tracks WHERE artist matches` |
| Rank / top-200 | Join against existing rank table |
| SC follow status | `artist_sources.is_following` (synced via SC API) |

One endpoint returns denormalized rows; frontend filters/sorts client-side for v1 (artist count is bounded — hundreds to low thousands).

---

## SoundCloud API additions

New functions in `src/music_minion/domain/library/providers/soundcloud/api.py`:

- `get_followings(state) -> list[ArtistDict]` — paginate `/me/followings`
- `unfollow_user(state, user_id) -> bool` — `DELETE /me/followings/{id}`
- `get_stream(state, since: datetime | None) -> list[StreamItem]` — paginate `/me/activities` (or stream endpoint), filter to repost type

Reference for endpoints: SC OpenAPI spec (see memory `reference_soundcloud_api.md`).

---

## Backend API

New router `web/backend/routers/artists.py`:

```
GET  /api/artists                  -> list all artists with aggregated stats
GET  /api/artists/{id}             -> single artist detail (recent feed events, top tracks)
POST /api/artists/{id}/unfollow    -> unfollow on SC (uses sc_push_worker for async push)
POST /api/artists/match-override   -> pin/unpin a match override
POST /api/soundcloud/feed-sync     -> manual trigger for feed-sync worker
GET  /api/soundcloud/feed-sync/status -> last_run_at, status, events_added
POST /api/soundcloud/followings-sync -> pull current SC followings into artist_sources
```

Query payload for `/api/artists`:
```
?sources=local,soundcloud   # filter
?only_following=true         # SC-follows view
?min_feed_noise=0.5          # noise threshold
?columns=library,reposts,hit_rate,noise  # which stats to compute (micro-opt)
```

---

## Frontend

New route `web/frontend/src/routes/artists.tsx`:

- Card-based layout (avatar, name, source badges, stat chips)
- Stat-chip menu: toggle which chips appear on every card (persisted to localStorage)
- Sort/filter bar: by noise, by library count, by hit rate, by follow status, by rank
- Search by name (client-side, artist list is bounded)
- Click card → artist detail drawer (recent reposts, top tracks in library, match override UI)

Stat chips (v1 set):
- In top 200 (badge pill — only renders if true)
- Rank #NN
- Library: N tracks
- Reposts: N
- Hit rate: NN%
- Feed: N.N/day
- Last loved: relative time
- Avg ELO: NNNN
- Followers: NNk

Actions per card:
- Unfollow (SC) — confirm dialog
- Fix match (opens merge/split UI)
- Open on SC (external link)

Sidebar entry "Artists" in `Sidebar.tsx` between Playlists and Filters.

---

## Task breakdown

Each task = one commit, aim for independently-shippable slices.

1. **Schema + migrations** — `artists`, `artist_sources`, `artist_match_overrides`, `sc_feed_events`, `sc_feed_sync_state` tables + migration
2. **Artist matching logic** — normalize/match function, upsert on library scan + SC sync, override table lookup
3. **Backfill artists from existing data** — one-time migration: iterate tracks & existing SC data, populate `artists` + `artist_sources`
4. **SC API: followings + unfollow** — `get_followings`, `unfollow_user`, wire into sync to populate `is_following`
5. **SC API: stream/feed** — `get_stream`, filter to reposts
6. **Feed-sync daemon worker** — `sc_feed_worker.py` mirroring push worker pattern, startup hook, manual trigger endpoint
7. **Stats queries** — SQL for all v1 stats, single query endpoint that joins everything
8. **Artists API router** — list/detail/unfollow/match-override endpoints
9. **Frontend: Artists route + cards** — basic layout, all stats as chips, no customization yet
10. **Frontend: chip toggle menu** — localStorage persistence, per-user stat visibility
11. **Frontend: sort/filter/search bar**
12. **Frontend: artist detail drawer** — recent reposts, match-override UI
13. **Frontend: unfollow action** — optimistic update, confirm dialog, error rollback
14. **Sidebar nav entry**

Phase 1 = tasks 1-9 (usable page). Phase 2 = 10-14 (polish).

---

## Risks & open questions

- **SC rate limits on stream endpoint** — unknown how deep we can page daily. First feed-sync run may need to be conservative (just last 48h), then daily incremental. Add backoff.
- **Artist name collisions** — two different real artists sharing a name (e.g. "Mike"). Match override table handles this post-hoc; won't pre-solve. Could worsen stats for collision cases until user fixes.
- **Repost hit rate definition** — "in monthly playlists or likes" needs a concrete query; monthly playlists are identified how? (needs confirmation during task 7)
- **Backfill performance** — library scan across all tracks to populate `artist_sources` may take time on first run. One-shot migration script, run once, done.
- **Avatar URLs** — SC avatar URLs may change / expire. Cache them in `artist_sources`, re-sync on followings-sync.

## Files likely touched

- `src/music_minion/core/database.py` — schema migrations
- `src/music_minion/domain/library/providers/soundcloud/api.py` — new endpoints
- `web/backend/sc_feed_worker.py` — NEW
- `web/backend/routers/artists.py` — NEW
- `web/backend/routers/soundcloud.py` — feed-sync + followings-sync endpoints
- `web/backend/queries/artists.py` — NEW
- `shared/src/api/artists.ts` — NEW
- `web/frontend/src/routes/artists.tsx` — NEW
- `web/frontend/src/components/artists/` — NEW (cards, chips, drawer, filters)
- `web/frontend/src/components/sidebar/Sidebar.tsx` — add nav entry
