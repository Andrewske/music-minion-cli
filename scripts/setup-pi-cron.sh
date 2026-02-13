#!/bin/bash
# Setup cron job for daily 3am sync on Pi server

CRON_ENTRY="0 3 * * * curl -s -X POST http://localhost:8642/api/sync >> /home/kevin/music-minion/logs/cron-sync.log 2>&1"
CRON_FILE="/tmp/music-minion-cron"

# Ensure logs directory exists
mkdir -p /home/kevin/music-minion/logs

# Get existing crontab (ignore error if empty)
crontab -l 2>/dev/null > "$CRON_FILE" || true

# Check if entry already exists
if grep -q "curl.*api/sync" "$CRON_FILE"; then
    echo "Cron job already exists, skipping..."
else
    echo "$CRON_ENTRY" >> "$CRON_FILE"
    crontab "$CRON_FILE"
    echo "Added cron job: daily sync at 3am"
fi

rm -f "$CRON_FILE"

echo ""
echo "Current crontab:"
crontab -l
