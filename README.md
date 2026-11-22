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
| `app.py` | Web server (Python standard library only). Stores projects, forwards uploads and media to ComfyUI, queues renders, reports system load. |
| `workflows.py` | Builds the ComfyUI job for each segment. |
| `assist.py` | Full assist: cut points, lyric matching and story prompts for the language model. |
| `assist-service/` | Song analysis container (lyrics and beats). Built and started by `run.sh`. |
| `static/index.html` | The page. |

## Sidebar

| Tab | What it holds |
|---|---|
| Storyboard | The song, timeline and segments of the open project |
| Projects | Every saved project. Open, rename, duplicate or delete one; each keeps its own timeline, assets and clips |
| Assets | The open project's actors, photos and audio. An actor is one character with a name, a description and any number of views (stills); photos are loose reference stills |
| Library | Every video rendered in the open project, with download links |
| System status | Ping test, and CPU, GPU, memory and disk meters for the PGX |

Each actor panel has two buttons. **Describe from images** sends up to four of the actor's views to the language model (it must be vision-capable) and writes the description. **Generate views from description** queues a close-up, a waist-up and a full-body still with FLUX.2 [dev] and the 8-step turbo LoRA, using up to three existing views as references so the new stills match; finished stills are copied into ComfyUI's input folder and added to the actor.

Assets and Library each have an **All / Project** toggle. All also lists what other projects hold: actors, photos and audio can be added to the open project (a copy that points at the same image and audio files), and clips can be watched, downloaded, or their project opened.

Projects are stored as `data/projects/<id>.json`. Deleted projects are moved to `data/trash/`. The GPU meter reads `nvidia-smi`, which is why `run.sh` starts the container with `--gpus all`.

## Full assist

A guided pass that turns a song into a planned storyboard. Each step waits for approval.

| Step | What it does | Runs on |
|---|---|---|
| Listen | Tempo, beats, bar lines and sections (librosa); lyrics with timestamps (faster-whisper, CPU). Lyrics can be corrected line by line, or pasted and matched to the timing. | `assist-service/` container, port 8191, local only |
| Split | Picks cut points on bar lines so every segment is 5 to 15 s, favouring section changes and lyric phrase starts and avoiding cuts through a sung line. The language model names the segments and may merge neighbours. | `assist.py` + Ollama |
| Story | Writes a title, logline, visual style and one beat per segment. Approving copies each beat into its segment's empty prompt. | Ollama |
| Cast, Shots | Not built yet. | |

The language model is reached through Ollama on the PGX (`OLLAMA_URL`, default `http://127.0.0.1:11434`; `OLLAMA_MODEL`, default `qwen3.6:35b`). It is unloaded when a render is queued so its memory goes back to the video models.

## Timing, progress and batch renders

- Segments run back to back. Each has its own 5 to 15 second length slider; changing one shifts the segments after it.
- A segment with no begin shot starts from the end shot of the segment before it.
- Clips show a live progress bar read from ComfyUI's websocket (port 8188 must be reachable from the browser).
- Picking a clip puts it on the timeline strip, and playing the song shows the picked clips in the preview, in sync.
- **Render all segments** queues every segment's listed runs for an unattended batch. The page can be closed while it runs.

## Shot types

| Type | Engine | Frame rate | Long segments |
|---|---|---|---|
| Story | Wan 2.1 image-to-video with the lightx2v 4-step LoRA | 16 fps | Chained: each 5 s pass starts from the last frame of the one before |
| Singing | Wan 2.1 InfiniteTalk, driven by that slice of the song | 25 fps | Chained: each pass continues from the previous frames |
| Story with an end shot | Wan 2.2 first-and-last-frame video (high-noise and low-noise models, 4-step LoRAs) | 16 fps | Chained: only the final pass is steered to the end shot |

## Models it expects in ComfyUI

`diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`, `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`, `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `vae/Wan2_1_VAE_bf16.safetensors`, `clip_vision/clip_vision_h.safetensors`, `model_patches/wan2.1_infiniteTalk_single_fp16.safetensors`, `audio_encoders/wav2vec2-chinese-base_fp16.safetensors`.

For story segments that have an end shot, also: `diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`, `diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`, `loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`, `loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`, `vae/wan_2.1_vae.safetensors` (all from `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`).

File names are set at the top of `workflows.py`.

## Not built yet

- Singing segments cannot be steered to an end shot (the lip-sync model takes a begin shot only).
- Generating new actor stills from a character reference.
- Upscaling and final assembly of picked clips into one video.

## Security

There is no login. Keep ports 8190 and 8188 on your home network only; do not forward them from your router.

## Audio patch for NVIDIA's ComfyUI container

NVIDIA's ComfyUI image for DGX Spark ships a placeholder in place of `torchaudio`, so any node that processes audio fails. `patch-comfy-audio.sh` copies two small pure-PyTorch files from `comfy-patches/` into the container (`resample` and `MelSpectrogram`, checked against the real library) and restarts ComfyUI. Run it again if the container is ever rebuilt.

## AI models panel

System status > AI models lists every model the storyboard uses, with what it does here. **Check for updates** compares each one with the version published today:

- Files in ComfyUI's models folder are compared by SHA-256 with the same file on Hugging Face. The first check reads every file once (several minutes); results are cached in `data/model_hashes.json`, so later checks are quick.
- The Ollama model is compared with the Ollama library; the speech model with its Hugging Face repo.

**Update** downloads the new file beside the old one, verifies it, then swaps it in and asks ComfyUI to unload the old copy. `run.sh` mounts the models folder (`COMFY_MODELS` overrides the path) and `~/.cache/huggingface` (read-only, for the token saved by `hf auth login`, needed for FLUX.2 and LTX-2.5). The list lives in `models.py`.

## Full assist: cast and shots

After a story is approved, step 4 (Cast) lets you tick which actors appear and what each plays, or ask the language model to recommend characters (each can be added as an actor with its description). Step 5 (Shots) writes the opening frame and one end frame per segment from that segment's lyrics, length, energy and story beat; the descriptions are editable. Generating the images runs FLUX.2 with one picture of each cast member in frame as a reference, then sets the opening frame as segment 1's begin shot and each end frame as its segment's end shot (they are also added to Photos).

## How a segment begins

- **New angle**: the segment has its own begin shot and starts on it.
- **Continue**: the begin shot is empty. The segment starts from the previous segment's end shot if it has one; otherwise from the last frame of the clip picked on the previous segment. Until a clip is picked there, renders of this segment are created "on hold" and start by themselves once you pick. Every clip saves its final frame for this.
- Singing segments cannot have an end shot (the lip sync engine only takes a start image).
