#!/bin/sh
set -e

mkdir -p /config/logs

if [ ! -f /config/config.yml ]; then
    echo "No config found, copying default config..."
    cp /app/config.yml /config/config.yml
fi

exec python /app/app.py
