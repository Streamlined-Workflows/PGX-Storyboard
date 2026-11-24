# SWIFT Director

**Your story. Your vision. Directed by you, Built by AI.**

SWIFT Director is a browser studio for making music videos with AI models that run on your own machine. You bring the song and the characters and direct every shot; the models on a local ComfyUI server (built for an NVIDIA DGX Spark class machine) do the rendering. Nothing is sent to an outside service.

It has two ways of working. **Storyboard** is the hands-on workspace: split the song into segments and set each shot yourself. **Assisted Storyboard** has the AI listen to the song, propose the cuts, a story, a cast and the key frames for you to approve or change.

Load a song, split it into 5 to 15 second segments, give each one a begin shot, a prompt and a number of runs, and render the clips on your own server.

## Start it

On the server (the machine that runs ComfyUI):

```
git clone https://github.com/Streamlined-Workflows/SWIFT_Director ~/SWIFT_Director
~/SWIFT_Director/run.sh
```

Then open `http://<server-name>.local:8190` from any computer on the same network.

It runs as a Docker container named `swift-director` that starts on boot (with `swift-director-assist` beside it for song analysis). It expects ComfyUI on the same machine at port 8188.

## Update it

```
~/SWIFT_Director/update.sh
```

## What each part does

| File | Purpose |
|---|---|
| `app.py` | Web server (Python standard library only). Stores projects, forwards uploads and media to ComfyUI, queues renders, reports system load. |
| `workflows.py` | Builds the ComfyUI job for each segment. |
| `assist.py` | Assisted Storyboard: cut points, lyric matching and story prompts for the language model. |
| `assist-service/` | Song analysis container (lyrics and beats). Built and started by `run.sh`. |
| `static/index.html` | The page. |

## Sidebar

| Tab | What it holds |
|---|---|
| Storyboard | The song, timeline and segments of the open project |
| Projects | Every saved project. Open, rename, duplicate or delete one; each keeps its own timeline, assets and clips |
| Assets | The open project's actors, photos and audio. An actor is one character with a name, a description and any number of views (stills); photos are loose reference stills |
| Library | Every video rendered in the open project, with download links |
| Audio Lab | A multi-track audio timeline for the open project: import sounds, arrange, trim and split clips, mix with effects, and export a finished file |
| Lore | Long background text about a setting (world, factions, people, technology, look). Each entry can be tagged to any number of storyboards |
| Identity Studio | A separate workspace for logos and app identities. See [Identity Studio](#identity-studio) |
| System status | Ping test, and CPU, GPU, memory and disk meters for the server. Under the meters, a list of what is using memory and the GPU: the models Ollama and ComfyUI have loaded, and the largest programs on the server |

Each actor panel has two buttons. **Describe from images** sends up to four of the actor's views to the language model (it must be vision-capable) and writes the description. **Generate views from description** queues a close-up, a waist-up and a full-body still with FLUX.2 [dev] and the 8-step turbo LoRA, using up to three existing views as references so the new stills match; finished stills are copied into ComfyUI's input folder and added to the actor.

Assets and Library each have an **All / Project** toggle. All also lists what other projects hold: actors, photos and audio can be added to the open project (a copy that points at the same image and audio files), and clips can be watched, downloaded, or their project opened.

Projects are stored as `data/projects/<id>.json`. Deleted projects are moved to `data/trash/`. The GPU meter reads `nvidia-smi`, which is why `run.sh` starts the container with `--gpus all`. The list of largest programs reads the server's process list, which is why `run.sh` also uses `--pid host`; without it the container can see only itself.

## Assisted Storyboard

A guided pass that turns a song into a planned storyboard. Each step waits for approval.

| Step | What it does | Runs on |
|---|---|---|
| Listen | Tempo, beats, bar lines and sections (librosa); lyrics with timestamps (faster-whisper, CPU). Lyrics can be corrected line by line, or pasted and matched to the timing. | `assist-service/` container, port 8191, local only |
| Split | Picks cut points on bar lines so every segment is 5 to 15 s, favouring section changes and lyric phrase starts and avoiding cuts through a sung line. The language model names the segments and may merge neighbours. | `assist.py` + Ollama |
| Story | Writes a title, logline, visual style and one beat per segment. Approving copies each beat into its segment's empty prompt. | Ollama |
| Cast, Shots | Not built yet. | |

The language model is reached through Ollama on the server (`OLLAMA_URL`, default `http://127.0.0.1:11434`; `OLLAMA_MODEL`, default `qwen3.6:35b`). It is unloaded when a render is queued so its memory goes back to the video models.

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

## Assisted Storyboard: cast and shots

After a story is approved, step 4 (Cast) lets you tick which actors appear and what each plays, or ask the language model to recommend characters (each can be added as an actor with its description). Step 5 (Shots) writes the opening frame and one end frame per segment from that segment's lyrics, length, energy and story beat; the descriptions are editable. Generating the images runs FLUX.2 with one picture of each cast member in frame as a reference, then sets the opening frame as segment 1's begin shot and each end frame as its segment's end shot (they are also added to Photos).

## How a segment begins

- **New angle**: the segment has its own begin shot and starts on it.
- **Continue**: the begin shot is empty. The segment starts from the previous segment's end shot if it has one; otherwise from the last frame of the clip picked on the previous segment. Until a clip is picked there, renders of this segment are created "on hold" and start by themselves once you pick. Every clip saves its final frame for this.
- Singing segments cannot have an end shot (the lip sync engine only takes a start image).

In Assisted Storyboard > Shots the language model also decides, for every segment after the first, whether it **continues** the previous shot or cuts to a **new scene** (place, subject or time changes, or the music turns sharply), with a one-line reason. New scenes get their own begin-frame description and image; continuing segments have their begin shot cleared. Each decision can be flipped by hand. **Render all** skips segments that would have to wait for a pick and lists them.

## Fixing part of a picture

Click a picture (Assets, Library > Images, Assisted Storyboard key frames) to open the viewer, then **Fix an area**: paint over the problem, describe what should be there, and Generate fix. FLUX.2 repaints only the painted area (`workflows.build_fix`: noise-masked sampling with the original as reference, then pasted back through the mask). The result is saved as a new picture; the original is kept.

**Hugging Face key.** If the server has no key, Check for updates first asks for a read-only Hugging Face token. It is verified with Hugging Face, then stored in `data/hf_token` (owner-only, never committed, never sent back to the browser). Skip checks everything else; models that need access show a yellow triangle and are not attempted. A key saved by `hf auth login` on the server is used automatically.

## Project configuration

Assisted Storyboard opens with the **Project Configuration Center**: six collapsible sections of
settings stored with the project (`config` in the project file, schema 2) and restored when it is
reopened. `config.py` owns the choices, the defaults and the checking of anything a browser sends;
`static/config/` draws it.

Each setting is tagged **In use** or **Stored**. Two are in use today: the music-video subtype
shapes the story concept, and Storyboard Detail sets how much each key frame description says.
The rest are saved for the update that will act on them, including the project rating, which is
a label for filtering rules to be applied against later. The model roles show what performs each
job today; choosing between models is the next milestone.

Switching the video type never deletes the other types' settings. Projects from before the
configuration existed open with defaults that reproduce their old behaviour, and their files are
not rewritten until they are next saved. **Use these settings for new projects** saves the
current configuration to `data/defaults.json`.

Tests: `./run-tests.sh` (Python only; no ComfyUI, Ollama or network).

## Memory

The CPU and GPU share one pool of memory on this machine, and ComfyUI keeps its last models
loaded while idle. SWIFT Director gives memory back in three ways:

- **On opening a tab.** A few seconds after a tab is opened, the model servers it does not use
  are unloaded: Storyboard and Identity Studio keep ComfyUI; Assisted Storyboard and Assets keep
  both; Projects, Library and Lore keep neither. System status changes nothing.
- **Before the language model writes**, ComfyUI is asked to release its models; and before
  ComfyUI renders or draws, the language model is unloaded.
- **Free memory** on System status unloads everything.

ComfyUI is only ever asked while its queue is empty, and the language model is never unloaded in
the middle of an answer. The cost is time: the next job reloads its model.

## Scene assets, props and world assets

Three kinds of asset sit beside actors in the Assets tab. Each has a name, a one-line context
(what it is and whose), a description, and any number of pictures, which can be uploaded or
generated from the description.

| Kind | Stored | Example |
|---|---|---|
| Scene asset | In the storyboard (`things`) | The one ship this video follows |
| Prop | In the storyboard (`things`) | A sidearm, a console, a drum kit, a stage |
| World asset, world prop | With a lore entry (`assets` in `data/lore/<id>.json`) | Thirty ships with their factions |

A world is a lore entry: every storyboard tagged with that lore sees its world assets.

When shots are planned, the language model is given each asset's name and context line only and
names the ones visible in each frame ("Assets and props" under the frame). When a frame's picture
is made, the cast takes FLUX.2's four reference slots first and assets fill what is left, in the
order scene assets, props, world assets; so a frame with nobody in it can show up to four. An
asset that does not fit, or has no picture yet, is described in words in the prompt instead.

**Fix an area** has a "Use:" list of assets and props that have a picture. Choosing one adds its
first picture as an extra reference for the repaint, which is how a prop is swapped into a shot
that is otherwise right.

## Audio Lab

A multi-track timeline for arranging a project's audio. It is a separate module (`audio/` and
`static/audio/`) with its own storage under `data/audio/` and its own routes under `/api/audio/`.

- **Sounds** are kept once in a shared library and never changed. A clip on the timeline points
  at a sound and carries instructions: where it sits, where in the sound it starts, how long it plays.
- **Time is counted in whole samples** at 48 kHz, so clips that should meet exactly do.
- **Waveforms** are drawn from peak data the server makes once per sound.
- **Each project's timeline is its own file**, saved atomically with the last 20 versions kept.
  A save from a second window is detected, not silently overwritten.

- **Clips** carry a level, fades, speed, pitch, reverse and a chain of effects. **Tracks** and the
  **master** carry volume and effects; tracks also balance, mute and solo. The effects are EQ,
  compressor and reverb.
- **The mixer** shows a meter per track and for the mix, and marks when the mix goes over full level.
- **Export** writes a new file with ffmpeg from the saved timeline: the full mix, each track as its
  own file (a zip), or part of the timeline; WAV, FLAC or MP3; 48 or 44.1 kHz. Nothing is
  normalised or limited: the loudest point is measured and reported. Exports run in the background
  on the processor and are kept under `data/audio/exports/`.
- **Playback in the browser is a preview.** The export is the finished result.

See `docs/Task_03_Milestone_C.md` for how the export is checked. The application's container
includes ffmpeg for this (`Dockerfile`).

## Speech service

`speech-service/` is a third container (port 8192, local only) holding the software for two speech
generation models: Qwen3-TTS (Apache 2.0) and Ming-3.0-tts (MIT). `run.sh` builds it last and carries
on if the build fails. Model files are not in the image; each is downloaded from System status, AI
Models, Speech generation, into the Docker volume `swift-director-speech-models`.

One model is loaded at a time, each in its own process, so unloading always returns the memory. A
model is released when another tab is opened, by Free memory, or after five idle minutes. **Test
voice** speaks one line so a model can be heard; it is refused while a render is running or waiting.
See `docs/Task_02_Milestone_2_Audio.md`.

## Lore

Lore entries are stored on their own in `data/lore/<id>.json` and belong to no single project; a
storyboard lists the entries it uses. When Assisted Storyboard writes the story concept, recommends
the cast or plans the shots, the tagged entries are added to the request as background, with the
instruction to stay consistent with them and not to try to show all of it. Up to 12,000
characters per storyboard are sent, in the order tagged, so the most important text should come
first. Deleting an entry moves it to `data/trash/`.

In the story concept (step 3) every line of "What we see" can be edited, and locked. A locked line
cannot be edited, and **Write another** keeps locked lines word for word and writes the rest of
the story around them. Editing a line of an approved story also updates the approved copy, and
the segment's video prompt if that prompt was still the copied line.

## Identity Studio

A workspace for logos and app identities, opened from the sidebar. It is a separate module
(`identity_studio/` and `static/identity/`) with its own projects under `data/identity/`, and it
does not touch storyboard projects. Today it manages identity projects and their briefs; it does
not generate anything yet. Details: [identity_studio/README.md](identity_studio/README.md).

## SWIFT branding

The UI uses the SWIFT theme: `static/swift-tokens.css` (a vendored copy of the SWIFT tokens; do not edit the values, copy again from the source), the official wordmark and drop in `static/brand/` (unchanged), and Montserrat served locally from `static/fonts/` (SIL Open Font License). `static/index.html` defines no colours of its own: its variables map onto `--swift-*` tokens, and the "SWIFT skin" block at the end of its stylesheet applies them.

## Internal Design Notes:

Branding, themes, logos, shared components and UI standards for this app come from
[SWIFT_UI_and_Branding](https://github.com/Streamlined-Workflows/SWIFT_UI_and_Branding). Nothing about the SWIFT look is defined in this repository.
