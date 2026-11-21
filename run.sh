#!/usr/bin/env bash
# Start (or restart) the storyboard as a background service on the PGX.
set -e
cd "$(dirname "$0")"
docker rm -f storyboard >/dev/null 2>&1 || true
docker run -d --name storyboard --restart unless-stopped --network host \
  -v "$PWD":/app -w /app -e PORT=8190 python:3.12-slim python app.py >/dev/null
echo "Storyboard is running. Open http://$(hostname).local:8190 in your browser."
