# SoundCloud Bucket Sync (Auto-Push + Manual Sync Button)

## Overview
When tracks are assigned to a bucket linked to a SoundCloud-backed playlist, automatically push changes to SoundCloud in the background. Also provides a per-bucket manual sync button for bidirectional pull+push reconciliation. Merges and supersedes the merry-honking-meteor plan.

## Task Sequence
1. [01-sc-push-worker.md](./01-sc-push-worker.md) - Background daemon thread with queue for async SC API calls
2. [02-hook-auto-push.md](./02-hook-auto-push.md) - Hook enqueue calls into existing bucket sync functions
3. [03-surface-sc-id.md](./03-surface-sc-id.md) - Add `soundcloud_playlist_id` to bucket API response (backend + frontend)
4. [04-manual-sync-endpoint.md](./04-manual-sync-endpoint.md) - Bidirectional pull-then-push endpoint for manual sync
5. [05-frontend-sync-button.md](./05-frontend-sync-button.md) - RefreshCw button UI, hook mutation, toast feedback

## Dependency Graph
```
01 (worker) ──→ 02 (hook auto-push)
03 (surface SC ID) ──→ 04 (sync endpoint) ──→ 05 (frontend button)
```
Tasks 01-02 and 03 can run in parallel. Task 04 depends on 03. Task 05 depends on 03+04.

## Success Criteria
1. Link a bucket to a SC-linked playlist → logs show `SC push: synced N tracks`
2. Assign a track with `soundcloud_id` → logs show single track push to SC
3. Assign a local-only track (no `soundcloud_id`) → silently skipped
4. Unassign a track → logs show removal from SC
5. RefreshCw button appears only on SC-linked buckets
6. Click sync → toast shows pull/push counts
7. Add track on SC directly → click sync → track pulled into local playlist
8. Verify sync button spinner during operation

## Dependencies
- SoundCloud authentication must be active (`get_web_provider_state()` returns non-None)
- Bucket-playlist linking (snoopy-toasting-fox) must be implemented (it is)
- Existing SC API functions: `add_track_to_playlist`, `remove_track_from_playlist`, `reorder_playlist`, `get_playlist_tracks`
- No new database migrations required

## Supersedes
This plan replaces **merry-honking-meteor** (all 4 tasks absorbed).
