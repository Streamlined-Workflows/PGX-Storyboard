#!/usr/bin/env bash
# Pull the latest version from GitHub and restart the storyboard with its current settings.
set -e
cd "$(dirname "$0")"
git pull --ff-only
./run.sh
