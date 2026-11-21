# PGX Storyboard

A browser storyboard for making music videos on a local ComfyUI server (built for a Lenovo ThinkStation PGX / DGX Spark).

Load a song, split it into 5 to 15 second segments, give each one a begin shot, a prompt and a number of runs, and render the clips on the PGX.

## Start it

On the PGX:

```
git clone https://github.com/Streamlined-Workflows/PGX-Storyboard ~/PGX-Storyboard
~/PGX-Storyboard/run.sh
```

Then open `http://thinkstationpgx-0e76.local:8190` from any computer on the same network.

It runs as a Docker container named `storyboard` that starts on boot. It expects ComfyUI on the same machine at port 8188.

## Update it

```
~/PGX-Storyboard/update.sh
```

## What each part does

| File | Purpose |
|---|---|
| `app.py` | Web server (Python standard library only). Stores the project in `data/project.json`, forwards uploads and media to ComfyUI, queues renders. |
| `workflows.py` | Builds the ComfyUI job for each segment. |
| `static/index.html` | The page. |

## Timing, progress and batch renders

- Segments run back to back. Each has its own 5 to 15 second length slider; changing one shifts the segments after it.
- A segment with no begin shot starts from the end shot of the segment before it.
- Clips show a live progress bar read from ComfyUI's websocket (port 8188 must be reachable from the browser).
- **Render all segments** queues every segment's listed runs for an unattended batch. The page can be closed while it runs.

## Shot types

| Type | Engine | Frame rate | Long segments |
|---|---|---|---|
| Story | Wan 2.1 image-to-video with the lightx2v 4-step LoRA | 16 fps | Chained: each 5 s pass starts from the last frame of the one before |
| Singing | Wan 2.1 InfiniteTalk, driven by that slice of the song | 25 fps | Chained: each pass continues from the previous frames |

## Models it expects in ComfyUI

`diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`, `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`, `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `vae/Wan2_1_VAE_bf16.safetensors`, `clip_vision/clip_vision_h.safetensors`, `model_patches/wan2.1_infiniteTalk_single_fp16.safetensors`, `audio_encoders/wav2vec2-chinese-base_fp16.safetensors`.

File names are set at the top of `workflows.py`.

## Not built yet

- End shots do not drive the video yet (needs a start-and-end-frame model). Today an end shot is used as the next segment's begin shot when that segment has none.
- Generating new actor stills from a character reference.
- Upscaling and final assembly of picked clips into one video.

## Security

There is no login. Keep ports 8190 and 8188 on your home network only; do not forward them from your router.
