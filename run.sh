#!/usr/bin/env bash
# Start (or restart) the storyboard as a background service on the PGX.
set -e
cd "$(dirname "$0")"
docker rm -f storyboard >/dev/null 2>&1 || true
# --gpus all gives the container nvidia-smi, which the System status page reads GPU load from.
docker run -d --name storyboard --restart unless-stopped --network host --gpus all \
  -v "$PWD":/app -w /app -e PORT=8190 python:3.12-slim python app.py >/dev/null

# Song analysis service for Full Assist (lyrics, beats). The first build takes a few minutes.
echo "Building the song analysis service (the first time takes a few minutes)..."
docker build -q -t storyboard-assist assist-service >/dev/null
docker rm -f storyboard-assist >/dev/null 2>&1 || true
docker run -d --name storyboard-assist --restart unless-stopped --network host \
  -v storyboard-assist-cache:/root/.cache storyboard-assist >/dev/null

echo "Storyboard is running. Open http://$(hostname).local:8190 in your browser."
