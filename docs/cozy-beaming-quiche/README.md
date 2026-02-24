# Fix Database Locking During SoundCloud Playlist Import

## Overview
Fix "database is locked" error during SoundCloud playlist import in the web UI. The root cause is `create_playlist_from_matches` mixing the FastAPI-injected database connection with CRUD functions that open their own connections, creating lock contention.

## Task Sequence
1. [01-refactor-playlist-creation.md](./01-refactor-playlist-creation.md) - Replace mixed connections with single connection + batch operations

## Success Criteria
1. Import a SoundCloud playlist with 20+ tracks via web UI while CLI is running
2. No "database is locked" error
3. Playlist created with correct track count
4. All tracks have soundcloud_id populated

## Dependencies
- None - single file change to existing endpoint
