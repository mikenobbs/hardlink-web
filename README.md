<div align="center">
  
hardlink-web
  
</div>

<div align="center">
  
  [![GitHub Release](https://img.shields.io/github/v/release/mikenobbs/hardlonk-web?include_prereleases&display_name=release&style=flat)](https://github.com/mikenobbs/hardlink-web/releases)
  [![GitHub Repo stars](https://img.shields.io/github/stars/mikenobbs/hardlink-web?style=flat)](https://github.com/mikenobbs/hardlink-web/stargazers)
  [![GitHub watchers](https://img.shields.io/github/watchers/mikenobbs/hardlink-web)](https://github.com/mikenobbs/hardlink-web/watchers)
    
</div>

A browser-based UI for creating hardlinks between files on a mergerfs media server.

Built for home media setups where you want to hardlink files from a downloads folder into an organised library without copying data. Designed to run as a Docker container alongside your media stack.

-----

## Features

- Browse your media directories and pick source and destination folders
- Select files to hardlink, with optional per-file renaming
- Flatten or preserve folder structure at the destination
- Conflict handling: add a suffix, skip, or overwrite
- Clean filenames option (dots and underscores replaced with spaces)
- Create and rename folders from the browse view
- mergerfs-aware: resolves the correct branch path automatically so hardlinks always land on the same underlying disk
- Optional basic auth
- Rolling 7-day logs

-----

## Requirements

- Docker
- A mergerfs pool (or any single filesystem — mergerfs mode can be disabled in config)

-----

## Setup

### 1. Pull the image

```bash
docker pull mikenobbs/hardlink-web
```

### 2. Run the container

```bash
docker run -d \
  --name hardlink-web \
  -p 8088:8088 \
  -v /path/to/your/media:/data \
  -v /path/to/raw/disks:/path/to/raw/disks \
  -v /path/to/config:/config \
  mikenobbs/hardlink-web
```

- `/data` — your mergerfs pool or media root. This is what the app browses.
- `/path/to/raw/disks:/path/to/raw/disks` — your raw disks. Required for mergerfs so the app can resolve the correct branch path. The container path must match the host path exactly, since mergerfs reports the basepath directly and the app uses it as-is. If your disks are at `/mnt/raw/disk1`, `/mnt/raw/disk2` etc, mounting the parent `/mnt/raw:/mnt/raw` catches them all in one line.
- `/config` — persistent config and logs. Copy `config/config.yml` here before first run.

### 3. Open the app

```
http://your-server-ip:8088
```

-----

## docker-compose example

```yaml
services:
  hardlink-web:
    image: mikenobbs/hardlink-web
    container_name: hardlink-web
    ports:
      - "8088:8088"
    volumes:
      - /path/to/your/media:/data
      - /path/to/raw/disks:/path/to/raw/disks
      - /path/to/config:/config
    restart: unless-stopped
```

-----

## Configuration

Edit `/config/config.yml`:

```yaml
auth:
  enabled: false       # Set to true to require a username and password
  username: admin
  password: admin

mergerfs:
  enabled: true        # Set to false if not using mergerfs

ownership:
  uid: 1000            # UID to assign to created files and folders
  gid: 1000            # GID to assign to created files and folders
```

Changes to config require a container restart.

-----

## Notes

- Hardlinks only work within the same underlying filesystem. If you get a cross-device error, the source and destination are on different drives in your pool.
- Auth uses HTTP Basic. If exposing outside your local network, put it behind a reverse proxy with HTTPS.
- Logs are written to `/config/logs/` and automatically cleaned up after 7 days.
- App was coded with the assistance of AI.
