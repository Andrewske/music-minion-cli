#!/bin/bash
set -e

echo "🎵 Personal Radio Deployment"
echo "============================"

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your settings, then run this script again."
    exit 1
fi

# Load environment
source .env

echo "Domain: ${DOMAIN}"
echo "Music path: ${MUSIC_PATH}"
echo ""

# Check music directory exists
if [ ! -d "${MUSIC_PATH}" ]; then
    echo "❌ Music directory not found: ${MUSIC_PATH}"
    echo "   Please upload your music files first."
    exit 1
fi

# Build and start
echo "🔨 Building containers..."
docker compose -f docker-compose.prod.yml build

echo "🚀 Starting services..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Services:"
echo "  - Frontend: https://${DOMAIN}"
echo "  - Stream:   https://${DOMAIN}/stream"
echo "  - API:      https://${DOMAIN}/api/radio/now-playing"
echo ""
echo "Logs: docker compose -f docker-compose.prod.yml logs -f"
echo "Stop: docker compose -f docker-compose.prod.yml down"
