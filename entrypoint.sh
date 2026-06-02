#!/bin/sh
set -e

mkdir -p /config/logs

if [ ! -f /config/config.yml ]; then
    echo "No config found, copying default config..."
    cp /app/config.yml /config/config.yml
fi

if [ ! -f /config/.secret_key ]; then
    echo "Generating secret key..."
    python -c "import secrets; open('/config/.secret_key', 'w').write(secrets.token_hex(32))"
fi

exec gunicorn --bind 0.0.0.0:8088 --workers 2 --chdir /app app:app
