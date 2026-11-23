#!/usr/bin/env bash
# Run every automated test. Needs only Python 3; no ComfyUI, Ollama or network.
set -e
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -t .
python3 -m unittest discover -s identity_studio/tests -t .
python3 -m unittest discover -s audio/tests -t .
