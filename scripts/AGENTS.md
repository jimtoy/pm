# Scripts

Start/stop scripts for the Docker container, one pair per platform:

- `start.sh` / `stop.sh` — Mac and Linux (bash)
- `start.ps1` / `stop.ps1` — Windows (PowerShell)

All four just wrap `docker compose up --build -d` / `docker compose down` from the repo root, so behavior stays identical across platforms — update `docker-compose.yml` rather than duplicating logic in each script.

`start` prints the local URL (`http://localhost:8000`) once the container is up.
