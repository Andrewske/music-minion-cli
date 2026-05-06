# Waveform Refresh: Per-Track + Bulk Purge

## Overview
SoundCloud waveform data cached in `~/.local/share/music-minion/waveforms/{track_id}.json` is frequently wrong — some completely off, some partially wrong. Once cached, waveforms are never re-fetched. This plan adds per-track refresh (button on WaveformPlayer) and bulk purge of all SoundCloud waveforms (lazy re-fetch on next view).

## Task Sequence
1. [01-backend-waveform-endpoints.md](./01-backend-waveform-endpoints.md) - DELETE + POST endpoints for single and bulk waveform cache invalidation
2. [02-frontend-waveform-refresh.md](./02-frontend-waveform-refresh.md) - API functions, useWavesurfer refresh callback + isRefreshing state, refresh button on WaveformPlayer, bulk purge in SoundCloud settings

## Success Criteria
1. Click refresh on a bad waveform → it re-fetches from SoundCloud and displays new data
2. Bulk purge deletes only `"source": "soundcloud"` cache files, preserves locally-generated ones
3. Visiting a purged track lazy-loads a fresh waveform on view

## Dependencies
- SoundCloud OAuth token must be valid for re-fetching waveforms
- `"source": "soundcloud"` field already present in SC waveform cache files (written by `fetch_soundcloud_waveform()`)
