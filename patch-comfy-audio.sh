#!/usr/bin/env bash
# Install the audio functions ComfyUI needs into NVIDIA's ComfyUI container.
# The NGC image ships a placeholder torchaudio; these two files supply resample() and
# MelSpectrogram, the only pieces the lip-sync and LTX audio nodes call.
# Restarts ComfyUI, so do not run it while a render is in progress.
set -e
cd "$(dirname "$0")"
DEST=$(docker exec comfyui python -c "import torchaudio, os; print(os.path.dirname(torchaudio.__file__))")
docker cp comfy-patches/functional.py "comfyui:$DEST/functional.py"
docker cp comfy-patches/transforms.py "comfyui:$DEST/transforms.py"
docker restart comfyui >/dev/null
echo "Audio patch installed. ComfyUI is restarting; give it about 30 seconds."
