#!/bin/sh
set -e

mkdir -p /config/logs

if [ ! -f /config/config.yml ]; then
    echo "No config found, copying default config..."
    cp /app/config.yml /config/config.yml
fi

exec gunicorn --bind 0.0.0.0:8088 --workers 2 app:app
