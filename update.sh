#!/usr/bin/env bash
# Pull the latest version from GitHub and restart the storyboard.
set -e
cd "$(dirname "$0")"
git pull --ff-only
docker restart storyboard >/dev/null
echo "Updated. Refresh http://$(hostname).local:8190 in your browser."
