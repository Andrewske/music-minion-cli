#!/bin/bash
set -e

# Music Minion Pi Deployment Script
# Builds frontend, syncs to Pi, rebuilds Docker containers

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Building frontend..."
cd web/frontend && npm run build && cd ../..

echo "Syncing to Pi..."
rsync -avz --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude 'web/frontend/node_modules' \
  --exclude '*.log' \
  --exclude '.session.json' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  --exclude '*.pyc' \
  ./ piserver:~/music-minion/

echo "Rebuilding containers on Pi..."
ssh piserver "cd ~/music-minion/docker/pi-deployment && docker compose up -d --build"

echo ""
echo "Done! Access at: https://music.piserver:8443"
echo ""
echo "Commands:"
echo "  Logs:     ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose logs -f'"
echo "  Restart:  ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose restart'"
echo "  Stop:     ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'"
