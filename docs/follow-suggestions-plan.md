# Follow Suggestions Plan

Goal: a page that lists SoundCloud artists Kevin should follow, ranked by evidence from his own likes and keeps, with a one-click follow. Plus: keep followings in sync and get new follows into the tier list.

Research was done on the 2026-11-10 DB snapshot (`~/.local/share/music-minion/dev/music_minion.db`).

## Decisions (Kevin, 2026-11-11)

- **Labels and promo channels:** separate section, collapsed by default. They are often the accounts Kevin ends up unfollowing.
- **Big/mainstream artists:** rank lower, not hidden. The ranking should lean on how often the account posts or reposts and how recently Kevin liked one of their tracks, not on remixes of their old songs (the Daft Punk case).
- **Follow:** one at a time. No bulk follow.
- **Tiers:** newly followed artists start at tier C. Also surface recent follows that are still untiered. Semi-automatic tiering is a separate project.

## What the data says

| Data | Size | Has SC user id? |
|---|---|---|
| `sc_likes` | 6,994 liked tracks | No (keyed by track id only) |
| `tracks` rows for those likes | 6,854 distinct | No. `artist` is `metadata_artist` or uploader username |
| `discovery_tracks` (feed reposts) | 143k, 3,256 of them liked | Yes, `uploader_soundcloud_id` on 129k |
| `sc_artist_uploads` | 6.8k | Yes, `uploader_soundcloud_id` |
| `discovery_artists` | 1,967, 1,937 followed | Yes, `soundcloud_user_id` |
| `sc_track_decisions` keeps | ~1.3k current decisions | Joins to the above by track id |

Followed tiers: S 26, A 61, B 54, C 14, untiered 1,782 (stored as empty string, not NULL).

### Followings sync is stale

`sync_followings()` only runs from the manual endpoint in `web/backend/routers/soundcloud.py`. Newest `discovery_artists.created_at` is 2026-03-29 and `last_sc_sync_at` is NULL on every row. Anyone Kevin followed on SoundCloud since March is not in MM, so the feed worker never polls them, and the suggestions page would recommend accounts he already follows. This has to be fixed first.

There is also no follow date. Every row's `created_at` is the March bulk import, so "recently followed" can't be answered from current data.

### Signal 1: credits on liked tracks (name based)

Parsing `artist` / `title` / `remix_artist` with the existing `_parse_track_credits()` gives 5,357 distinct credited names across liked tracks. After matching against followed accounts: **459 unfollowed names with 3+ liked tracks, 156 with 5+.**

Top of the list: DirtySnatcha 21, Ganja White Night 17, PHRVA 17, John Summit 16, Eater 15, Space Laces 14, Ozztin 14, Inzo 12, GAWM 12, Brainrack 12, Sully 11, Nevve 11 (all feats), Myrias 11, Nitti Gritti 10, Habstrakt 10.

Problems found:
- **Name matching against follows is fragile.** SC display names carry decoration: "Wooli 🐘", "▶︎ Dirt Monkey ◀︎", "Eliminate*". Plain `display_name_normalized` matching listed all three as unfollowed. Matching on alphanumerics only, plus the slug with `music`/`official`/`dj` suffixes stripped, fixed them.
- **Duo names split.** "Chase & Status" shows as "chase" 14 and "status" 14, because `_split_credits` splits on `&`. Needs a duo guard: if both halves of a split always co-occur, treat the whole string as one name.
- **Label vs artist account.** Kevin follows "DirtySnatcha Records" but not the DirtySnatcha artist account. Names can't tell these apart.
- **Old remixes inflate classic artists.** Daft Punk, Eminem and Black Eyed Peas rank high mostly from other people's remixes of their songs. A primary credit on a track someone else remixed should count far less than an original.
- A name is not an account. To follow someone we need their SC user id, which this signal does not give.

### Signal 2: uploaders of liked or kept tracks (id based)

Liked or kept tracks that also appear in `discovery_tracks` carry the uploader's SC user id. **264 unfollowed uploaders with 2+ liked/kept tracks.**

Top: Monstercat 21, Hybrid Trap 20, DirtySnatcha 16 (the artist account, id 69528588), Bassrush 16, Phrva 15, Electrostep Network 13, DramaClubRecs 10, Ganja White Night 8, GAWM 8, Habstrakt 7, CRUCAST 7, bitbird 7, Acyan 6, Space Laces 6, Never Say Die 6.

This agrees with Signal 1 on the artists. It also surfaces labels and promo channels (Monstercat, Bassrush, Hybrid Trap, CRUCAST), which per the decisions above go in their own section.

Coverage gap: only 3,256 of 6,994 likes are in `discovery_tracks`. The rest need a backfill.

### Signal 3: connections (similar artists)

- **Co-credit graph (free, local).** `_connection_partners()` already powers the per-artist Connections tab. Run it across S/A/B tier artists and score each unfollowed partner by the tiers of the artists they work with.
- **Followings of your top artists (API).** `GET /users/{urn}/followings` for the 87 S+A artists. Score X by how many of them follow X, divided by a popularity term so that everyone-follows-Skrillex does not win. About 450 calls once, then weekly. The only signal that finds artists Kevin has never heard.

SoundCloud's `/tracks/{id}/related` is noisy and track-level; skip it.

## Plan

### Step 0: keep followings in sync

1. Run `sync_followings()` nightly in `web/backend/sc_feed_worker.py`, alongside the likes reconcile.
2. Add `discovery_artists.followed_at`. Set it when a row flips from not-followed to followed (or is inserted as followed). Leave it NULL for the March import.
3. Backfill estimate: `/me/followings` comes back newest first in practice. Record the position from the first sync as `follow_order` so the review list can show "most recent follows" even without real dates. Verify the order claim on the first run before relying on it.
4. New follows get tier C via `set_artist_tier()` (which recomputes rankings). This covers follows from the suggestions page and follows made directly on SoundCloud. Only rows with an empty tier are touched; a re-follow keeps its old tier.

### Step 1: account-level suggestions (the core page)

1. **Store uploader identity on likes.** Add `uploader_soundcloud_id`, `uploader_permalink`, `uploader_username` to `sc_likes`. Fill them in `_record_sc_likes()` from `track.user` in the `/me/likes/tracks` response, which the sync already fetches.
2. **Backfill** existing likes: copy from `discovery_tracks` / `sc_artist_uploads` where present, then `get_tracks_by_ids()` for the rest (~3,700 ids, batches of 50, ~75 calls). One-off script via `scripts/on-pi.sh`.
3. **Resolve credited names to accounts.** Cache table `sc_name_resolutions(name_key, soundcloud_user_id, confidence, resolved_at)`. Sources in order: (a) uploader ids from step 1 whose username/permalink key equals the name key, (b) `artist_match_resolved`, (c) SC `GET /users?q=` for names with 3+ credits, accepting only an alphanumeric-exact match and preferring the highest follower count. Unresolved names still show, with a "search on SC" link instead of a Follow button.
4. **Activity cache.** Table `sc_account_activity(soundcloud_user_id, followers, last_upload_at, last_repost_at, uploads_90d, reposts_90d, is_label, fetched_at)`. Filled for candidates only, using the existing `get_user_tracks()` and `get_user_reposts()` with one page each. Refresh weekly.
5. **Score** each account (pure functions in `web/backend/follow_suggestions.py`):

   ```
   evidence  = Σ over liked/kept tracks: role_weight × recency_weight
   score     = evidence × activity_factor × size_factor
   ```

   - `role_weight`: uploader 1.0, original primary 1.0, remixer 0.8, feat 0.5, primary on someone else's remix 0.2 (kills the Daft Punk effect), kept but not liked 0.5
   - `recency_weight`: `0.3 + 0.7 × 0.5^(age_months / 12)`. Recent likes count most, but old likes never drop below 0.3. NULL `liked_at` (backfilled rows) gets the 0.3 floor.
   - `activity_factor`: from posts + reposts in the last 90 days. Zero activity in 12 months drops the account to the bottom, it doesn't hide it.
   - `size_factor`: gentle penalty above ~500k followers (log scale). Ranks big names lower without hiding them.
   - The page shows the parts, not just the total.
6. **Label detection** for the separate section: name matches `records|recordings|music group|network|label|collective`, or most of the account's recent uploads credit other artists (`metadata_artist` differs from the account's username). Manual override per account, stored with the dismissals.
7. **Page:** "Suggestions" tab on `/artists` (`web/frontend/src/routes/artists.tsx`).
   - **Artists** section (main list). Row: avatar, name, score chips (`12 liked · last like 3 wk ago · posts 4/mo`), expandable list of the liked tracks, Follow button, Dismiss button.
   - **Labels & channels** section, collapsed by default.
   - **Recent follows, untiered**: follows with `followed_at` (or high `follow_order`) and an empty tier, with inline tier buttons. Also lists the 57 untiered follows that already have 3+ rated tracks, showing their keep rate so tiering is quick.
8. **Follow action:** `follow_user()` next to `unfollow_user()` in `soundcloud/api.py` (`PUT /me/followings/{urn}`). On success, upsert into `discovery_artists` with `followed_at = now`, tier C, so the feed worker picks them up on its next run. Dismiss writes to `follow_suggestion_dismissals` so the account never comes back.

### Step 2: co-credit connections

Add a "works with your top artists" score from the co-credit graph across S/A/B tiers. Reuses `_parse_track_credits` / `_connection_partners`. Shown as a chip: `collabs with 3 of your S-tier`.

### Step 3: followings-of-favorites

Weekly job in the feed worker: fetch followings for S+A artists into `sc_artist_followings(follower_id, followee_id, fetched_at)`, compute lift. Its own section on the page ("Your favorites follow"), since most of these will have zero liked tracks.

### Later, separate project: semi-automatic tiers

`upload_keep_rate` / `repost_keep_rate` and their rated counts already exist on `discovery_artists`. A tier suggester could propose promotions and demotions from keep rate, rated count and recent likes, with Kevin approving each one. Out of scope here. The "untiered with 3+ rated" list in step 1 is a cheap first taste of it.

## Settled follow-ups (Kevin, 2026-11-11)

1. Old likes always count. Recency decays toward a 0.3 floor, never to zero.
2. Dismissals are permanent. A dismissed account never comes back, whatever Kevin likes later.
3. Every new follow gets tier C, whether it was made on this page or directly on SoundCloud (the nightly sync in step 0 handles the second case).
