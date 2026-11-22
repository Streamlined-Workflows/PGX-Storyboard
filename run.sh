#!/usr/bin/env bash
# Start (or restart) SWIFT Director as a background service on this machine.
set -e
cd "$(dirname "$0")"
# Containers from before the rename to SWIFT Director; remove them so they do not hold the ports.
docker rm -f storyboard storyboard-assist >/dev/null 2>&1 || true
docker rm -f swift-director >/dev/null 2>&1 || true
# The AI Models panel checks and updates the files in ComfyUI's models folder, using your Hugging Face sign-in.
MODELS_DIR="${COMFY_MODELS:-$HOME/dgx-spark-playbooks/nvidia/playbook-comfyui/models}"
mkdir -p "$HOME/.cache/huggingface"
[ -d "$MODELS_DIR" ] || echo "Note: $MODELS_DIR not found, so the AI Models panel will show every file as missing."
# --gpus all gives the container nvidia-smi, which the System status page reads GPU load from.
# --pid host lets System status list which programs on this machine are using memory and the GPU.
docker run -d --name swift-director --restart unless-stopped --network host --gpus all --pid host \
  -v "$PWD":/app -v "$MODELS_DIR":/models -v "$HOME/.cache/huggingface":/hf:ro \
  -w /app -e PORT=8190 python:3.12-slim python app.py >/dev/null

# Song analysis service for Assisted Storyboard (lyrics, beats). The first build takes a few minutes.
echo "Building the song analysis service (the first time takes a few minutes)..."
docker build -q -t swift-director-assist assist-service >/dev/null
docker rm -f swift-director-assist >/dev/null 2>&1 || true
# The cache volume keeps its earlier name so the speech model is not downloaded again.
docker run -d --name swift-director-assist --restart unless-stopped --network host \
  -v storyboard-assist-cache:/root/.cache swift-director-assist >/dev/null

echo "SWIFT Director is running. Open http://$(hostname).local:8190 in your browser."
