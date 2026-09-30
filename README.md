# Bleeparr 2.0

**Bleeparr 2.0** is a profanity-cleaning tool for TV shows that integrates with Sonarr.

## Features
- Web GUI styled like Sonarr
- Sonarr API integration
- Auto-clean new episodes or batch process
- SQLite settings
- Dry run mode
- Dockerized

## Quick Start
```bash
git clone https://github.com/davidpeele/bleeparr.git
cd bleeparr
docker compose up --build
```
Then visit [http://localhost:5050](http://localhost:5050)

## Dev Structure
- FastAPI backend in `backend/`
- React frontend in `frontend/`
- SQLite DB
- Dockerized with frontend + backend combined

## Stretch Goals
- Discord/email/webhook notifications
- Radarr/Plex/Jellyfin integration
- Post-processing hook support
- LXC template for Proxmox
