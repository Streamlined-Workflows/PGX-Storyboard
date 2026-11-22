# Song analysis for the storyboard: faster-whisper (lyrics) and librosa (beats), CPU only.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir faster-whisper librosa soundfile
WORKDIR /srv
COPY service.py .
CMD ["python", "service.py"]
