# Server Access & File Management

## SSH Access

```bash
ssh root@46.62.221.136
```

## File Locations

| Local Path | Server Path |
|------------|-------------|
| `docker/radio/` | `/root/docker/radio/` |
| `src/` | `/root/docker/radio/src/` |
| `web/frontend/` | `/root/docker/radio/web/frontend/` (source) |
| `web/backend/` | `/root/docker/radio/web/backend/` |
| Music files | `/root/music/` |

## Syncing Files

**Sync entire radio docker folder:**
```bash
rsync -avz --delete docker/radio/ root@46.62.221.136:/root/docker/radio/
```

**Sync just source code:**
```bash
rsync -avz --delete src/ root@46.62.221.136:/root/docker/radio/src/
```

**Sync single file:**
```bash
scp docker/radio/Caddyfile root@46.62.221.136:/root/docker/radio/Caddyfile
```

## Rebuilding Containers

After syncing files, rebuild and restart:

```bash
# SSH in first
ssh root@46.62.221.136
cd /root/docker/radio

# Rebuild backend (after changing src/ or web/backend/)
docker compose -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.prod.yml up -d backend

# Rebuild frontend (after changing web/frontend/)
docker compose -f docker-compose.prod.yml up --build frontend-builder
docker compose -f docker-compose.prod.yml restart caddy

# Restart liquidsoap (after changing radio.liq)
docker compose -f docker-compose.prod.yml restart liquidsoap

# Restart caddy (after changing Caddyfile)
docker compose -f docker-compose.prod.yml restart caddy

# Restart everything
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## Editing Files Directly on Server

```bash
ssh root@46.62.221.136

# Edit with nano
nano /root/docker/radio/Caddyfile

# Edit with vim
vim /root/docker/radio/liquidsoap/radio.liq

# View file
cat /root/docker/radio/.env
```

## Viewing Logs

```bash
# Backend logs
docker logs radio-backend -f

# Liquidsoap logs
docker logs radio-liquidsoap -f

# Caddy logs
docker logs radio-caddy -f

# All containers
docker compose -f docker-compose.prod.yml logs -f
```

## Quick Checks

```bash
# Container status
docker ps --filter 'name=radio'

# Test APIs
curl http://localhost:8080/api/radio/stations
curl http://localhost:8080/api/radio/now-playing

# Test stream
curl -I http://localhost:8080/stream
```

## Adding Music to Radio Library

Music files live at `/root/music/` on the server (mounted as `/home/kevin/Music/radio-library/` in containers).

**Copy music files to server:**
```bash
# Single file
scp "/path/to/song.opus" root@46.62.221.136:/root/music/

# Entire folder
rsync -avz --progress "/path/to/music/folder/" root@46.62.221.136:/root/music/
```

**After adding files, re-import to PostgreSQL:**
```bash
# From local machine (uses local SQLite as source)
cd /home/kevin/coding/music-minion-radio-impl/docker/radio
source <(ssh root@46.62.221.136 "grep DATABASE_URL /root/docker/radio/.env")
uv run python import_tracks.py
```

**Or scan directly on server:**
```bash
ssh root@46.62.221.136
cd /root/docker/radio
source .env
python import_tracks.py --scan /root/music
```

**Database access via Claude Code:** The postgres MCP server is configured for this database - use `mcp__postgres__*` tools to query directly.

**When local files change (e.g., added loudness metadata):**
```bash
uv run music-minion sync-radio
```

This command:
1. Rsyncs audio files from `~/Music/radio-library/` to server
2. Imports from local SQLite to PostgreSQL

**Note:** The "Radio Library" playlist (ID 368) is what the station plays from. To add new tracks to rotation:
1. Add them to your local Music Minion library
2. Add them to the "Radio Library" playlist locally
3. Re-run the import script to sync to PostgreSQL

## Environment Variables

Located in `/root/docker/radio/.env`:
```bash
# View on server
ssh root@46.62.221.136 "cat /root/docker/radio/.env"
```

Contains: `DOMAIN`, `MUSIC_PATH`, `DATABASE_URL` (CloudClusters PostgreSQL)
