# SWIFT Director's converter: Blender, run without a window, behind a small local service (see service.py).
# Blender comes from Ubuntu's own packages so the same file builds on the PGX (ARM64) and on an ordinary PC.
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends blender python3 python3-numpy && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY service.py glb_to_fbx.py ./
RUN useradd --system --home /tmp converter
USER converter
CMD ["python3", "service.py"]
