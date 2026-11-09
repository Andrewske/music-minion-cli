# Stories page (artist-by-artist repost triage)

A SoundCloud "Discover / latest from people you follow" clone. Walk followed
artists one at a time, play each artist's reposts + uploads from the last 7
days, rate them, and drop artists from the list once all their tracks are heard.
Desktop web + phone web (responsive). Mobile Expo app: out of scope.

## Product rules (decided with Kevin, 2026-11-08)

- Scope: artists with `discovery_artists.is_following = 1`. Content = their
  reposts (`discovery_track_reposters`, event_type 'repost' AND 'upload') plus
  their own uploads (`sc_artist_uploads`), last 7 days (rolling).
- Artist sort: most recent activity timestamp (repost/upload time) across the
  artist's window tracks, newest first.
- Track order within an artist: Jev score (`sc_track_predictions.probability`,
  latest row per soundcloud_id) desc, unscored last, then activity time desc.
- **Listened** = ANY of:
  1. played >= 5 seconds on this page (explicit `listened` write),
  2. a current verdict in `sc_track_decisions` (keep / not_quite / nope, any surface),
  3. already in library: a `tracks` row with that `soundcloud_id` that has a
     local file or is in any playlist,
  4. played in MM before: a `radio_history` row joined via `tracks.soundcloud_id`.
- Listened is global per track: a track heard via artist A shows listened under artist B.
- Listened tracks render greyed but stay visible; clicking plays them. They are
  never auto-queued.
- Artists with zero unheard tracks are not returned. Client side: when the user
  leaves an artist whose tracks are all heard, it disappears from the list.
  Artists reappear only once they repost/upload something unheard.
- Controls: Like (= keep: SC like + monthly playlist, existing behaviour),
  Not quite, Skip (= nope + advance; track stays in list), Previous
  (track, then artist — may return to an artist already dropped from the list).
  Bail out of an artist by clicking another artist in the list. No next-artist button.
- Playback: full track from the start; click waveform to seek. Track ends with
  no verdict -> advance to next unheard track (listened, no verdict). When the
  artist has no unheard tracks left -> first unheard track of the next artist.
- Verdicts go through the existing `POST /api/feed/{soundcloud_id}/rate` with
  `surface: "stories"`.
- Tracks flagged "not for feed" (`sc_track_flags`) are excluded.

## Data gotcha

`discovery_track_reposters.reposted_at` has mixed formats: `2026/11/09 07:08:08 +0000`
(exact) and NULL/empty (approximate; use `seen_at`). `sc_artist_uploads.uploaded_at`
is ISO (`2026-11-08T23:24:11+00:00`). Normalize before comparing; never compare raw strings.
Volume check (2026-11-08 snapshot): ~2,660 reposts from 240 artists in 7 days.

## API contract

### `GET /api/stories?days=7`

```json
{
  "generated_at": "2026-11-08T20:00:00Z",
  "artists": [
    {
      "discovery_artist_id": 12,
      "display_name": "MIRR.IMG",
      "slug": "mirr-img",
      "avatar_url": "https://...",
      "latest_activity_at": "2026-11-08T02:00:00Z",
      "unheard_count": 3,
      "tracks": [
        {
          "soundcloud_id": "123456",
          "title": "Na ostri noze (Techno Remix)",
          "artist_name": "3Nightz",
          "artwork_url": "https://...",
          "permalink_url": "https://soundcloud.com/...",
          "duration_ms": 245000,
          "kind": "repost",
          "activity_at": "2026-11-08T02:00:00Z",
          "local_track_id": 9876,
          "score": 0.71,
          "decision": "keep",
          "listened": true
        }
      ]
    }
  ]
}
```

- `kind`: `"repost" | "upload"`. `decision`: `"keep" | "not_quite" | "nope" | null`.
- Timestamps: ISO 8601 UTC with `Z`.
- `local_track_id` may be null (not materialized yet; materialize via the
  existing `POST /api/feed/materialize` before playing, as FeedPage does).
- A track reposted twice by the same artist in the window appears once.

### `POST /api/stories/{soundcloud_id}/listened`

Body `{"surface": "stories"}` (optional). Idempotent upsert into new table
`sc_track_listens(soundcloud_id TEXT PRIMARY KEY, first_listened_at TIMESTAMP, surface TEXT)`.
Returns `{"soundcloud_id": "...", "listened": true}`.

## Files

- Backend: `web/backend/queries/stories.py`, `web/backend/routers/stories.py`,
  register in `web/backend/main.py`, migration v70 in `src/music_minion/core/database.py`.
- Frontend: `web/frontend/src/routes/stories.tsx`, `web/frontend/src/api/stories.ts`,
  `web/frontend/src/components/stories/*`, sidebar nav entry.
