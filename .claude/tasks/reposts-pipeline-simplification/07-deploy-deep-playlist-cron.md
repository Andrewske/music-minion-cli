---
task: 07-deploy-deep-playlist-cron
status: pending
depends: [06-add-tests]
files:
  - path: scripts/cron-discovery-sync.sh
    action: create
---

# Deploy, Seed Deep Playlist, Install Cron, Verify

## Context

Operational close-out. Push to Pi, create the second SC playlist + DB row, install nightly cron, run end-to-end verification. Source-only change here is the new shell script.

## Files to Modify/Create

- `scripts/cron-discovery-sync.sh` (create) — invokes `/api/discovery/sync` POST with lock + timeout
- DB row in `playlists` (operational, on Pi)
- SC playlist (operational, via SC web UI / API)
- Pi crontab entry (operational)

## Implementation Details

1. **Create `scripts/cron-discovery-sync.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Single-run lock so overlapping cron firings can't race playlist_tracks DELETE/INSERT.
# 1800s timeout caps any stuck connection.
exec flock -n /tmp/discovery-sync.lock \
    curl --max-time 1800 -sk -X POST \
        https://localhost:8443/api/discovery/sync \
        -H 'content-type: application/json' \
        -d '{"dry_run": false}'
```

`chmod +x scripts/cron-discovery-sync.sh`. Commit. Localhost (not public hostname) keeps the request entirely on the Pi — no DNS, no extra TLS roundtrip.

2. **Deploy to Pi:**

```bash
rtk uv run pytest tests/test_feed_sync.py -q   # final gate
rtk git push origin main
./scripts/deploy-to-pi.sh
```

3. **Seed deep SC playlist + DB row** (on Pi, manual one-shot):

   - Create empty SC playlist via SC web UI; capture playlist id.
   - Insert DB row:
     ```bash
     ssh piserver "sqlite3 ~/.local/share/music-minion/music_minion.db \
       \"INSERT INTO playlists (name, soundcloud_playlist_id, discovery_source) \
         VALUES ('reposts (deep)', '<new-sc-playlist-id>', 'soundcloud_reposts_deep');\""
     ```

4. **Install cron:**

```bash
ssh piserver 'crontab -l | { cat; echo "0 6 * * * /home/pi/music-minion/scripts/cron-discovery-sync.sh >> /var/log/discovery-sync.log 2>&1"; } | crontab -'
```

## Verification

Run full plan §"Verification" suite (A through F):

```bash
# A. Sync produces 100 tracks
rtk proxy curl -sk -X POST https://music.piserver:8443/api/discovery/sync -d '{"dry_run":false}'
sleep 30
rtk proxy curl -sk "https://music.piserver:8443/api/playlists/26/tracks?limit=200" \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)['tracks']))"
# expect 100

# B. Multi-reposter tracks rank first
rtk proxy curl -sk "https://music.piserver:8443/api/playlists/26/tracks?limit=10" \
  | python3 -c "import sys,json; \
                ts=json.load(sys.stdin)['tracks']; \
                print([(len(t.get('reposters',[])), t['title'][:40]) for t in ts])"
# expect descending reposter counts in roughly top slots

# C. No owned tracks (cross-playlist + love)
ssh piserver 'sqlite3 ~/.local/share/music-minion/music_minion.db "
  SELECT COUNT(*) FROM playlist_tracks pt
  WHERE pt.playlist_id = 26
    AND (
      pt.track_id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id != 26)
      OR pt.track_id IN (SELECT track_id FROM ratings WHERE rating_type=\"love\")
    );
"'
# expect 0

# D. Per-artist cap honored (counts every reposter, not just primary)
rtk proxy curl -sk "https://music.piserver:8443/api/playlists/26/tracks?limit=200" \
  | python3 -c "from collections import Counter; import sys,json; \
                ts=json.load(sys.stdin)['tracks']; \
                c=Counter(); \
                [c.update([r['slug']]) for t in ts for r in t.get('reposters',[])]; \
                print('max per artist:', max(c.values()), 'over limit:', sum(1 for v in c.values() if v>5))"
# expect max <= 5, over limit = 0

# E. Deep + mixes playlists exist, populated
rtk proxy curl -sk "https://music.piserver:8443/api/playlists/<deep_id>/tracks?limit=200"
rtk proxy curl -sk "https://music.piserver:8443/api/playlists/<mixes_id>/tracks?limit=50"

# F. Cron fires nightly + lock works (manual: invoke twice in quick succession; second should exit immediately)
ssh piserver '/home/pi/music-minion/scripts/cron-discovery-sync.sh & /home/pi/music-minion/scripts/cron-discovery-sync.sh; echo "exit=$?"'
ssh piserver 'tail /var/log/discovery-sync.log'

# G. Errors persisted as JSON (sanity)
ssh piserver 'sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT errors FROM discovery_sync_log WHERE errors IS NOT NULL ORDER BY started_at DESC LIMIT 5;"'
```

Also add TODO entries (per plan §TODOs):
- TODO E: Drop `tracks_fetched`/`artists_checked`/`tracks_new`/`tracks_skipped` columns from `discovery_sync_log` once new metrics in use ≥1 week.
- TODO F: Decide if `_fetch_all_reposts` should be inlined into `sync_followings_reposts` once it's the only caller.

(TODO D — DB-only mixes — collapsed into this PR.)

Append to `docs/incomplete-items.md` or wherever project tracks TODOs.

Expect: all checks pass; if A returns < 100 with no kept session, investigate before signing off.
