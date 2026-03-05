# Human Steps Required for Migration

## PRE-MIGRATION (Do These First)

### 1. Stop piserver Docker
```bash
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'
```

### 2. Stop local music-minion processes
If you have any music-minion processes running:
- Exit the blessed CLI (quit command or Ctrl+C)
- Stop the web backend if running separately
- Stop any IPC client processes

Verify nothing is running:
```bash
ps aux | grep music-minion
```

## AUTOMATED MIGRATION (Claude will do these)

- Database backup already created at `~/.local/share/music-minion/music_minion.db.bak`
- Dry-run verification completed successfully (72 tracks to migrate)
- Will run actual migration
- Will run verification queries

## POST-MIGRATION (Do These After)

### 1. Wait for Syncthing propagation
Monitor both databases until their MD5 hashes match (30-60 seconds for ~27MB database):

```bash
watch -n5 "echo 'Local:' && md5sum ~/.local/share/music-minion/music_minion.db && echo 'Pi:' && ssh piserver 'md5sum ~/.local/share/music-minion/music_minion.db'"
```

Wait until the hashes match, then press Ctrl+C.

### 2. Restart piserver Docker
```bash
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose up -d'
```

### 3. Functional Testing
Once piserver is back up:

1. Play "Overthinker (SHIX Flip)" by INZO - verify audio plays correctly
2. Check that waveform loads (may take a moment on first play to regenerate)
3. Verify playlist membership is preserved (check a playlist that contained one of the migrated tracks)
4. Check that ratings are intact (verify a rated track still has its rating)

## Migration Details

- 72 tracks will be migrated from `source='soundcloud'` with `local_path` to new `source='local'` records
- All foreign key relationships will be updated (playlists, ratings, notes, etc.)
- Original SoundCloud tracks will have `local_path` cleared but remain in database with `soundcloud_id`
- Transaction is atomic - either all 72 succeed or none (rollback on error)

## Rollback Plan

If something goes wrong:
```bash
# Stop everything again
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'

# Restore backup
cp ~/.local/share/music-minion/music_minion.db.bak ~/.local/share/music-minion/music_minion.db

# Wait for Syncthing to propagate backup to piserver
# Then restart piserver Docker
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose up -d'
```

## Ready to Proceed?

Confirm that you have:
- [ ] Stopped piserver Docker
- [ ] Stopped all local music-minion processes
- [ ] Verified nothing is running

Then Claude can run the migration.
