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
# The app's image is plain Python plus ffmpeg (for Audio Lab). It is built once and reused; the code itself is mounted.
echo "Preparing the SWIFT Director container (the first time takes a minute or two)..."
docker build -q -t swift-director-app -f Dockerfile . >/dev/null
# Optional: COMFY_INPUT is ComfyUI's input folder on this machine. When it is given, Reference Generation can delete the
# image file of a picture you deny or that expires; without it only SWIFT Director's own record of the picture is deleted.
INPUT_MOUNT=()
if [ -n "$COMFY_INPUT" ] && [ -d "$COMFY_INPUT" ]; then INPUT_MOUNT=(-v "$COMFY_INPUT":/comfy-input -e COMFY_INPUT_DIR=/comfy-input); fi
docker run -d --name swift-director --restart unless-stopped --network host --gpus all --pid host \
  -v "$PWD":/app -v "$MODELS_DIR":/models -v "$HOME/.cache/huggingface":/hf:ro "${INPUT_MOUNT[@]}" \
  -w /app -e PORT=8190 swift-director-app python app.py >/dev/null

# Song analysis service for Assisted Storyboard (lyrics, beats). The first build takes a few minutes.
echo "Building the song analysis service (the first time takes a few minutes)..."
docker build -q -t swift-director-assist assist-service >/dev/null
docker rm -f swift-director-assist >/dev/null 2>&1 || true
# The cache volume keeps its earlier name so the speech model is not downloaded again.
docker run -d --name swift-director-assist --restart unless-stopped --network host \
  -v storyboard-assist-cache:/root/.cache swift-director-assist >/dev/null

# Speech generation (Qwen3-TTS and Ming-3.0-tts). Built last and allowed to fail, so a problem here never stops the rest.
# The image holds the software only; model files are downloaded from System status, into the volume below, when you ask.
echo
echo "SWIFT Director itself is up. Now preparing the speech service."
echo "The first time, this downloads several GB of software and takes 10 to 20 minutes. Lines will scroll; that is normal."
if docker build -t swift-director-speech speech-service; then
  docker rm -f swift-director-speech >/dev/null 2>&1 || true
  docker run -d --name swift-director-speech --restart unless-stopped --network host --gpus all \
    -v swift-director-speech-models:/models -v "$HOME/.cache/huggingface":/hf:ro swift-director-speech >/dev/null \
    && echo "The speech service is running." \
    || echo "PROBLEM: the speech service was built but would not start. Everything else works. Send Claude the lines above."
else
  echo "PROBLEM: the speech service could not be built. Everything else works. Send Claude the last 30 lines above."
fi
# The converter: Blender, run without a window, turns GLB files into the studio's FBX. It listens on this computer only.
echo
echo "Now preparing the converter (Blender). The first time, this downloads about 1 GB of software."
if docker build -t swift-director-convert convert-service; then
  docker rm -f swift-director-convert >/dev/null 2>&1 || true
  docker run -d --name swift-director-convert --restart unless-stopped --network host --read-only --tmpfs /tmp:size=4g \
    --cap-drop ALL --security-opt no-new-privileges swift-director-convert >/dev/null \
    && echo "The converter is running." \
    || echo "PROBLEM: the converter was built but would not start. Everything else works. Send Claude the lines above."
else
  echo "PROBLEM: the converter could not be built. Everything else works; GLB files cannot be imported. Send Claude the last 30 lines above."
fi
echo
echo "SWIFT Director is running. Open http://$(hostname).local:8190 in your browser."
