#!/usr/bin/env bash
# Pull the latest version from GitHub and restart SWIFT Director with its current settings.
set -e
cd "$(dirname "$0")"
git pull --ff-only
./run.sh
