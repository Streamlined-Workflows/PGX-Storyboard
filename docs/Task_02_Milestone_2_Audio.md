# Task 02, Milestone 2 (audio part): Speech Models and the Speech Service

Status: built on `main`, for review. **Nothing in it has run on the PGX yet**, and no real speech
model has been loaded anywhere. The first update on the server is the real test.

Decisions this followed (24 November): the two speech models are Qwen3-TTS and Ming-3.0-tts; go
ahead with a new speech container and a model registry before Narrator Studio. Assumed, since not
answered: English first, and podcasts built line by line on the Audio Lab timeline.

## What was built

**A speech container** (`speech-service/`, port 8192, reachable from the server itself only)
- Holds both models' software. No model files are in it.
- Built from the makers' published code, pinned to exact versions, not from anyone's ready-made image.
- The base image, PyTorch versions and Qwen library version are the combination published as working
  on this machine class, including a report that names the ThinkStation PGX.
- The two models need different versions of the same libraries, so each has its own Python environment.
- If Ming's software fails to install, the container still builds and Qwen3-TTS still works. The
  reason is kept and shown under System status.

**How it uses memory**
- One model is loaded at a time. Asking for another unloads the first.
- Each loaded model is its own process. Unloading ends the process, which is the certain way to give
  graphics memory back.
- A model is unloaded when you open another tab (after the usual few seconds), by Free memory, and
  by itself after five idle minutes. System status is the exception, as for the other models:
  looking at memory does not change it.
- The memory a model actually takes is measured when it loads and shown beside it.

**The model list** (System status, AI Models, new group "Speech generation")
- Four entries: Qwen3-TTS copy a voice, design a voice, built-in speakers; and Ming-3.0-tts.
- Each shows its maker, licence, what it is for here, download size (read from Hugging Face when
  you press Check for updates), size on disk, and measured memory.
- **Download** fetches that one model. Nothing is downloaded until it is pressed.
- **Check for updates** compares the installed version with the one published today.
- **Test voice** speaks one fixed line and plays it on the page. For a model that copies voices,
  **Test with a recording…** takes a short clip from your computer; the clip is used for that one
  test and removed from the server straight after.
- A test is refused while a render is running or waiting, so it cannot slow one down.

**Licences recorded**
| Model | Maker | Licence |
|---|---|---|
| Qwen3-TTS 1.7B (three variants) | Alibaba | Apache 2.0, commercial use allowed |
| Ming-3.0-tts 0.5B | Ant Group | MIT, commercial use allowed |

## Checked here

169 automated tests pass (`./run-tests.sh`). The 15 new ones run the real service code with a
stand-in for the model (it answers the same way and writes a tone):

- nothing is downloaded before Download is pressed, including when speech is asked for first
- a failed download says why and is not marked installed
- one model at a time; unloading ends its process
- a recording for copying is converted to a plain WAV for the model and not kept afterwards
- refused: unknown model, a mode the model does not have, empty or over-long text, no description,
  no recording, a recording that is not sound
- a model that will not load, or stops mid-sentence, reports the reason and holds no memory
- Ming failing to build is reported while Qwen3-TTS keeps working
- no graphics card: says so instead of trying
- the model list follows install, update available, and the speech service being absent
- changing tabs and Free memory release the voice model; System status does not

In a browser against the stand-in service: the four rows with licences, check, download with
progress, Test voice playing sound, the copy test with a recording, the Ming build failure shown in
its row, and release after a tab change. All earlier checks still pass.

## Not verified, in order of risk

1. **Ming-3.0-tts on this hardware.** Its makers tested it with PyTorch 2.6 on x86. Here it gets
   PyTorch 2.12 on ARM because that is what the graphics card needs. It may fail to install, fail to
   load, or load and sound wrong. One known mismatch is already worked around (how it reads sound
   files). If it does not work after one round of fixes, the recommendation is to drop it.
2. **The container build.** Never run. It downloads several GB and should take 10 to 20 minutes the
   first time. The pinned versions come from a published recipe, not from a build I watched.
3. **Qwen3-TTS loading and speaking.** The calls follow the library's code at the pinned version,
   but have not been executed.
4. **Memory figures.** None are claimed. A public report for this machine class puts the three Qwen
   variants at roughly 1 to 2 GB each; the page will show what is measured on your server.
5. **How either model sounds.**

## Limits

- Only the test line can be spoken so far. Narrator Studio (Task 03 Milestone D) is where scripts,
  saved voices and the "whose voice, and they agreed" record arrive.
- The rest of Task 02 Milestone 2 (choosing models per project, licences for the existing image and
  video models) is not part of this.
- The speech service listens on the server itself only. It has no login, like ComfyUI, and must
  not be exposed.
- Model files live in a Docker volume named `swift-director-speech-models`.

## What to do on the PGX

1. Run the update. Watch for "The speech service is running." or a line starting "PROBLEM".
2. Open System status, press **Check for updates**. The Speech generation group should show four
   models as not downloaded, with sizes. If Ming's row shows a build problem, send that text.
3. Press **Download** on "Qwen3-TTS 1.7B: design a voice", then **Test voice**.
4. If that speaks, do the same for the others, Ming last.

## Recommended next step

Fix whatever the first build shows, then Task 03 Milestone D, Narrator Studio.
