# Speech generation for SWIFT Director: Qwen3-TTS and Ming-3.0-tts, on the graphics card.
#
# Built for the ThinkStation PGX (NVIDIA GB10: ARM64, CUDA 13). The base image, the PyTorch versions and the
# faster-qwen3-tts commit are the combination published as working on this machine class
# (github.com/mARTin-B78/dgx-spark-faster-qwen3-tts). Change them together or not at all.
#
# The two models need different versions of the same libraries, so each has its own Python environment:
#   /opt/qwen   Qwen3-TTS, and the service itself
#   /opt/ming   Ming-3.0-tts
# No model weights are in this image. They are downloaded into the /models volume only when Install is pressed.
FROM nvidia/cuda:13.0.2-base-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev build-essential \
        ffmpeg git ca-certificates sox libsox-fmt-all libsndfile1 && rm -rf /var/lib/apt/lists/*

ARG TORCH=2.12.1
ARG TORCHAUDIO=2.11.0
ARG TORCH_INDEX=https://download.pytorch.org/whl/cu130

# ---- Qwen3-TTS ----
ARG FASTER_QWEN3_TTS_REF=7cdef7e40195108b51a808f2ce5c7d5f3e235a79
RUN python3.12 -m venv /opt/qwen && /opt/qwen/bin/pip install --upgrade pip \
 && /opt/qwen/bin/pip install torch==${TORCH} torchaudio==${TORCHAUDIO} --index-url ${TORCH_INDEX}
RUN git clone https://github.com/andimarafioti/faster-qwen3-tts.git /opt/src/faster-qwen3-tts \
 && cd /opt/src/faster-qwen3-tts && git checkout --detach ${FASTER_QWEN3_TTS_REF} \
 && /opt/qwen/bin/pip install . "qwen-tts==0.1.1" "huggingface-hub<1.0" soundfile

# ---- Ming-3.0-tts ----
# Its makers tested it on other hardware (PyTorch 2.6, CUDA 12.4, x86). Here it gets the PyTorch that works on this
# machine and their other pinned libraries. If any step fails the image still builds: the reason is kept in
# /opt/ming-build.log and shown under System status, and Qwen3-TTS is unaffected.
ARG MING_REF=c88c023ea6ccc08fd1e7a1d289cb6246c21deff1
RUN ( set -e; python3.12 -m venv /opt/ming; /opt/ming/bin/pip install --upgrade pip; \
      /opt/ming/bin/pip install torch==${TORCH} torchaudio==${TORCHAUDIO} --index-url ${TORCH_INDEX}; \
      /opt/ming/bin/pip install transformers==4.46.3 tokenizers accelerate==1.3.0 "huggingface_hub<1.0" numpy soundfile tqdm loguru \
          x_transformers==2.9.2 diffusers==0.33.0 onnxruntime inflect einops packaging; \
      git clone https://github.com/inclusionAI/Ming-3.0-tts.git /opt/src/ming; cd /opt/src/ming; git checkout --detach ${MING_REF}; \
      /opt/ming/bin/python -c "import torch, torchaudio, transformers, diffusers, onnxruntime, x_transformers" \
    ) > /opt/ming-build.log 2>&1 || touch /opt/ming.failed

WORKDIR /srv
COPY service.py worker.py ./
ENV MODELS_DIR=/models
CMD ["/opt/qwen/bin/python", "service.py"]
