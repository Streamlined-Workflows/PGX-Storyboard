# SWIFT Director's own container: Python, plus ffmpeg so Audio Lab can read audio files and draw their waveforms.
# The application code is not copied in; run.sh mounts the repository, so an update never needs a rebuild.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
