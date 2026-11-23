# Task 02, Milestone 0: Architecture and Compatibility

Status: findings for review. Nothing in the running application was changed for this milestone.
What was added: this document, a regression test suite (`tests/`), and `run-tests.sh`.

Milestone 1 does not start until this is approved.

---

## 1. Current architecture

SWIFT Director is one small Python web server with a single-page browser interface, sitting in
front of three services on the PGX.

| Piece | Where | What it does |
|---|---|---|
| Web server | `app.py` (1,251 lines, Python standard library only) | Serves the page, stores projects, talks to ComfyUI and Ollama, 48 routes |
| Language-model requests | `assist.py` | Every prompt sent to Ollama: cuts, story, cast, shots, picture prompts |
| ComfyUI graphs | `workflows.py` | Builds the graph for each engine; holds the model file names |
| Model updates | `models.py` | The AI Models panel: 23 catalogued models, version checks, downloads, Hugging Face key |
| Lore | `lore.py` | Background text and world assets, shared across storyboards |
| Memory report | `usage.py` | What is using memory and the GPU; Free memory |
| Song analysis | `assist-service/` (own container, port 8191) | faster-whisper transcription, librosa beats and sections, ffmpeg |
| Identity Studio | `identity_studio/` + `static/identity/` | Separate module with its own storage, API, job tracker and tests |
| Interface | `static/index.html` (1,863 lines, plain JavaScript) | Every view except Identity Studio |

Services it depends on: ComfyUI (port 8188, in Docker), Ollama (port 11434, `qwen3.6:35b`), and
the song analysis container. The app runs in a `python:3.12-slim` container with no extra
packages, started by `run.sh`; `update.sh` pulls `main` and restarts it.

Storage is JSON files under `data/`, outside the container image:

```
data/projects/<id>.json     one storyboard
data/lore/<id>.json         one lore entry and its world assets
data/identity/…             Identity Studio
data/trash/                 anything deleted
data/hf_token               Hugging Face key (mode 0600)
```

Pictures, clips and audio live in ComfyUI's input and output folders; projects hold file names.

### The ten areas the task asks about

| # | Area | Where it lives today |
|---|---|---|
| 1 | Project management and persistence | `app.py`: `empty_project`, `normalize`, `load_project`, `save_project`, `merge_project`, `list_projects`; duplicate, delete to trash |
| 2 | Segments and timeline | `project["segments"]`: start, end, type (story or singing), begin and end picture, prompt, runs, chosen clip, results. The timeline is the song |
| 3 | Assisted Storyboard | `assist_*` functions in `app.py`, state in `project["assist"]`: analysis, lines, split, story draft and approved story, cast, shots |
| 4 | Song analysis | `assist-service/service.py`: tempo, beats, downbeats, sections, energy, transcription. Browser extracts audio from mp4 |
| 5 | Ollama | `assist.chat()` with JSON schemas, one retry with a larger context. One model, set by `OLLAMA_MODEL` |
| 6 | ComfyUI | `workflows.py`: Wan 2.1 image-to-video (story), InfiniteTalk (singing), Wan 2.2 first-and-last-frame (end shots), FLUX.2 [dev] stills and inpainting |
| 7 | Character and asset libraries | Actors, photos, audio, scene assets, props (per storyboard); world assets (per lore entry); All/Project toggle |
| 8 | Model management | `models.py` `CATALOG`: hash comparison with Hugging Face, Ollama registry check, downloads, key handling |
| 9 | Image editing, key frames, queues | Viewer with zoom, pan and Fix an area; key frames per segment with locks; hold-and-release for continuing shots; Render all |
| 10 | Branding and interface | SWIFT tokens (`static/swift-tokens.css`), Montserrat, logo; collapsible sidebar |

---

## 2. What exists, what is partial, what is missing

| Task 02 part | State | Detail |
|---|---|---|
| 2. Configuration panel | Missing | Assisted Storyboard opens with a status panel only. Per-project settings are just `{width, height}` |
| 3. Model roles and selection | Missing | Model file names are fixed in `workflows.MODELS`; the language model is fixed by an environment variable. The catalogue exists only for update checks |
| 3.4 Memory management | Partial | The language model is unloaded before renders; Free memory exists; nothing schedules around memory |
| 4. Production settings | Missing | Clips are 832 × 480 at 16 fps (story) or 25 fps (singing). No aspect ratio, export size or style settings |
| 5. Intake without a song | Missing | Analysis, segmentation, story and shots all require an analysed song. Clips take their audio from the song |
| 6. Production Collections | Missing | Lore is the nearest thing: text and assets shared by tagging |
| 7. Story Bible | Partial | Lore holds free text; there is no split between confirmed facts and suggestions |
| 8. Collection → Project → Scene → Shot → Generation | Partial | Project → Segment → Result exists. No Scene level. Shot plans live in `assist.shots`, keyed by segment |
| 9. Approval settings | Partial | Story approval, locks on story lines and key frames, a picked clip per segment. No general approval states or settings |
| 10. Electron | Missing | Browser only. No sign-in. The page connects straight to ComfyUI's websocket for progress |
| 11. Final assembly | Missing | The storyboard previews picked clips against the song in the browser. Nothing exports a finished video |
| Tests | Was missing | The core had none. Now 21 core tests plus 48 Identity Studio tests |
| Schema version | Missing | Project files carry no version number. Identity Studio's do |

Features that exist but are unverified on the real server: the Wan 2.2 end-shot engine (models
probably not downloaded), the AI Models check against live Hugging Face and Ollama, and the
prop reference in Fix an area. LTX-2.5 is installed for testing with no workflow behind it.
No text-to-speech model is installed.

---

## 3. Compatibility and regression requirements

These hold for every later milestone. Each is covered by a test unless marked.

1. **Every existing project opens.** A project with only a name and segments still loads, and
   gains missing fields in memory without losing anything it had.
2. **Unknown fields survive.** A field this version does not know is kept through load and save,
   so an older copy of the app never strips data written by a newer one.
3. **The browser cannot overwrite server-owned data.** Render results, `assist`, `lore` and
   `generated` are untouched by a browser save.
4. **Segment rules stay.** A singing segment never has an end shot; runs are 1 to 8; a segment
   needs a begin picture and a positive length.
5. **Each engine still builds a fully wired graph** that saves a video and its last frame.
6. **Every model a graph loads is in the update catalogue.**
7. **Stills take four references; a fix changes only the painted area.**
8. **Story rules stay.** One line per segment; locked lines cannot be edited and survive a
   rewrite; an approved story follows edits; a prompt the person rewrote is never overwritten.
9. **Shot rules stay.** The first segment always opens a scene; continue or new scene per
   segment; only known cast and asset names are accepted.
10. **Asset ranking stays:** cast, then scene assets, props, world assets.
11. **Lore:** tagging, the 12,000-character budget, world assets surviving text edits, trash on delete.
12. **Cuts** cover the whole song back to back.
13. **Identity Studio** stays independent: its 48 tests pass and it reads no storyboard data.
14. **Deleting never erases** (trash folder), except Clean up storage, which says so. *(Not yet tested for storyboard projects.)*
15. **Locked or approved work is never regenerated silently.** *(Locked key frames: tested in the browser earlier, not yet in the suite.)*
16. **Branding:** SWIFT tokens only, the slogan, and the name Assisted Storyboard. *(Checked by eye.)*

Run everything with `./run-tests.sh`. It needs Python only.

Gaps in coverage to close during Milestone 1, before the code they protect is touched: render
queueing and hold-and-release (`render_segment`, `release_waiting`), `refresh_statuses`, key-frame
locks in `assist_shot_images`, and project duplicate and delete.

---

## 4. Proposed project schema

Additive. A project file gains a version number and one new block; nothing existing moves.

```json
{
  "schema": 2,
  "id": "…", "name": "…", "created": 0, "updated": 0,
  "settings": {"width": 832, "height": 480},
  "segments": [], "actors": [], "things": [], "photos": [], "audio": [], "lore": [],
  "assist": {}, "image_jobs": [], "generated": [],

  "config": {
    "identity": {
      "rating": "PG-13",
      "video_type": "music_video",
      "story":      {"type": "short_story", "subtype": "narrative", "in_between_purpose": null},
      "music":      {"type": "single", "subtype": "reenactment"},
      "commercial": {"type": "product_ad", "audience": "", "message": "", "call_to_action": "", "runtime": null}
    },
    "models": {
      "analysis": "auto", "prompting": "auto", "image": "auto", "image_lora": "auto",
      "singing_video": "auto", "story_video": "auto", "begin_end_video": "auto", "stt": "auto", "tts": "auto"
    },
    "production": {
      "aspect": "16:9", "custom_aspect": null, "export_resolution": "1080p", "target_fps": 24, "platform": "general",
      "visual_direction": "cinematic", "visual_notes": "", "visual_references": [],
      "storyboard_detail": "standard",
      "continuity": {"character": true, "environment": true, "costume": true, "style": true, "narrative": true},
      "environment": "local"
    },
    "workflow": {
      "approve_each_scene": false, "approve_each_shot": false,
      "approve_before_assets": false, "approve_before_render": true,
      "auto_progress": false, "keep_alternatives": true, "keep_history": true, "auto_model_recommendations": true
    }
  },

  "intake": {"kind": "song", "text": "", "brief": {}},
  "collection_id": null
}
```

Rules:

- **Version.** Files without `schema` are version 1. `normalize()` fills `config` with defaults in
  memory; the file is rewritten only when the project is next saved. No bulk migration.
- **All three type blocks are always kept.** Switching video type changes which block is shown,
  never deletes the others. This meets "preserve unrelated settings".
- **Defaults** for music-video projects reproduce today's behaviour exactly.
- **Stable keys, readable labels.** Values are lower-case keys (`music_video`); the interface shows
  the labels from the task ("Music Video").
- **`settings.width/height` stay** as the generation size. `production.export_resolution` is the
  size wanted at export. The two are different on purpose.
- **Defaults for new projects** go in `data/defaults.json`, same shape as `config`.
- **Later milestones add** `scenes` (a list; segments gain `scene_id`), per-segment approval state,
  and `data/collections/<id>.json`. Reserved now, not written.

Model assignments are stored as `"auto"` or `"<provider>:<identifier>"`, for example
`"ollama:qwen3.6:35b"` or `"comfyui:flux2_dev_fp8mixed.safetensors"`.

---

## 5. Milestone checklist

**Milestone 0: Architecture and Compatibility (this document)**
- [x] Inspect the repository after Task 01
- [x] Document the current architecture
- [x] Identify existing capabilities and incomplete features
- [x] Establish compatibility and regression requirements, with a test suite
- [x] Propose the expanded project schema
- [x] Identify risks and conflicts
- [ ] Jeremy's review and the decisions in section 7

**Milestone 1: Assisted Storyboard Configuration**
- [ ] Add `schema` and `config` to `normalize()` with tests for old and new files
- [ ] Close the test gaps listed in section 3
- [ ] Project Configuration Center at the top of Assisted Storyboard, six collapsible sections, as a separate script and stylesheet (the pattern Identity Studio uses)
- [ ] Project Identity: rating, video type, and the conditional Story, Music Video and Commercial fields
- [ ] Production Settings and Workflow sections: stored and restored
- [ ] AI Model Configuration and Audio and Speech sections: show what is in use today, read-only, until Milestone 2 makes them functional
- [ ] Confirmation when a type change would invalidate approved work
- [ ] Defaults for new projects
- [ ] One place each setting takes effect in Milestone 1: rating and storyboard detail feed the story and shot prompts; music-video subtype feeds the story prompt. Everything else is stored and labelled "not used yet"

**Milestone 2: Model Selection.** Discovery from Ollama (`/api/tags`) and ComfyUI (`/object_info`); a table of model families the app has a working graph for; Auto and explicit choice passed into `assist.chat` and `workflows`; LoRA filtered by image model.

**Milestone 3: Generalized Intake.** Timeline no longer requires a song; story and commercial intake; silent or narrated clips.

**Milestone 4: Production Collections.** `data/collections/`, ordered projects, relationships.

**Milestone 5: Narrative and Storyboard Expansion.** Story Bible, scenes, approval states.

**Milestone 6: Production Orchestration.** One job tracker, retries, memory-aware scheduling.

**Milestone 7: Desktop Application.** Electron client and connection manager.

**Milestone 8: Final Assembly.** Export a playable video.

---

## 6. Risks and conflicts

**Conflicts between the task and how the application works today**

1. **Output settings the models cannot meet.** Generation is 832 × 480 at 16 or 25 fps. 1080p,
   4K and 60 fps need an upscaling and frame-interpolation step that is not installed. Milestone 1
   will store these as the wanted export and say plainly that generation size is separate.
2. **"Model selection must be functional."** Most roles have exactly one working implementation
   today, and text-to-speech has none. After Milestone 2 several dropdowns will honestly offer
   one choice, and TTS will read "not available". A discovered file is only selectable once a
   graph exists for its model family; adding a family (LTX-2.5, for example) is real work each time.
3. **Everything assumes a song.** The timeline, segment lengths, analysis, and clip audio all
   come from it. Milestone 3 is the largest change in the plan and touches rendering.
4. **Segment length is a model limit, not a creative choice.** Clips are a few seconds long
   because of the video models. "Flexible shot durations" for narrative scenes means chaining
   clips, which the continue-from-last-frame logic already does.
5. **Lore, Story Bible and Collections overlap.** Recommended shape: a Collection owns a Story
   Bible; today's lore entries become Story Bible sections by reference, not by copying; world
   assets stay attached to them. Lore keeps working unchanged until then.
6. **Two job trackers.** The storyboard polls per project; Identity Studio has its own tracker.
   Milestone 6 should make Identity Studio's tracker the shared one, since it already waits for an
   idle queue and survives restarts.
7. **Branch instruction versus how the server updates.** The task asks for a dedicated feature
   branch. The PGX updates from `main`, and work on a branch is invisible there, which caused
   confusion earlier today. See decision 1.

**Technical risks**

8. **Memory.** ComfyUI was holding about 105 GB of 122 GB while idle today. Model selection
   (Milestone 2) makes contention likelier well before orchestration (Milestone 6). A minimal
   guard, freeing ComfyUI before the language model loads and the reverse, should come forward
   into Milestone 2.
9. **One 1,863-line interface file.** New surfaces should be separate scripts, as Identity Studio
   is, so the existing views are not disturbed.
10. **No sign-in, and the browser talks to ComfyUI directly.** Fine on a home network; both must
    change before a desktop client connects from elsewhere (Milestone 7). Ports 8188 and 8190 must
    stay off the internet until then.
11. **No imaging or video tools in the app's container.** Final assembly needs ffmpeg, which
    today exists only in the song analysis container.
12. **Licences.** FLUX.2 [dev] is non-commercial, accepted for internal concept work. "Commercial"
    as a video type here means in-world advertisements, which does not change that; selling the
    product or its output would.

**Content rating**

13. The rating is a classification label for filtering down. It is stored with the project so
    that custom filtering rules can be applied against it later: a lower rating means stricter
    limits on what the assistant proposes and what passes review. It never widens what is allowed.
    In Milestone 1 it is stored, shown, and passed to the story and shot prompts as an upper
    bound on tone; the custom rules themselves are a later piece of work.

---

## 7. Decisions needed before Milestone 1

1. **Branch or main?** Work on `main` in small commits (visible on the PGX after each update), or
   on a feature branch merged at the end of each milestone (safer, but invisible until merged).
2. **Schema as proposed in section 4?** In particular: keeping all three type blocks, and
   `config` as one new block beside the existing fields.
3. **Milestone 1 scope:** are the three places settings take effect (rating, storyboard detail,
   music-video subtype in the prompts) the right first ones, with the rest stored for later?
4. **Bring the memory guard forward** from Milestone 6 to Milestone 2?
