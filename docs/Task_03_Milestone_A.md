# Task 03, Milestone A: Audio Architecture and Data Model

Status: findings and design for review. The running application is unchanged.
What was added: this document, and an unconnected `audio/` package holding the proposed data
model with 11 tests. Milestone B does not start until this is approved.

---

## 1. Architecture assessment

### What exists today

| Capability | Where | Reusable for Task 03? |
|---|---|---|
| Audio upload | Browser sends the file to ComfyUI's input folder; the project lists it in `project["audio"]` as `{id, name, filename}` | The list becomes the first entries in the new asset library. The storage place does not suit an audio library (see 1.2) |
| Sound from a video file | Browser decodes an uploaded mp4 and re-encodes its sound as WAV before upload | Yes. The same browser decoding gives Audio Lab its playback |
| Song analysis | `assist-service/` container: ffmpeg converts to mono 22 kHz, librosa finds tempo, beats, downbeats, sections and energy | Yes. Tempo and beats feed the Audio Lab beat grid |
| Transcription | Same container: faster-whisper `large-v3-turbo`, word timing | Yes. Later: transcript-linked editing, subtitle alignment |
| ffmpeg | Only inside the `assist-service` container. The main app container has none | Yes. This container is the natural home for waveform data, rendering and export |
| Audio in video | `workflows._segment_audio`: ComfyUI loads the song and trims it to the segment; InfiniteTalk uses it to drive singing | Yes, unchanged. Later it takes an Audio Lab mix in place of the raw song |
| Preview | The storyboard plays picked clips against the song in the browser | Replaced by Audio Lab's transport for projects that use it |
| Language model | Ollama through `assist.chat()` with JSON schemas | Yes: outlines, scripts, splitting prose from dialogue, suggesting sounds for a scene |
| Job tracking | Identity Studio's tracker waits for an idle ComfyUI queue and survives restarts | Yes, for sound effects and music generated through ComfyUI |
| Project configuration | `config.py`, project schema 2, with a `tts` role reserved | Extended: an Audio Production type and five audio roles |
| Lore | Shared background text | Yes: fictional podcasts and narration draw on it until the Story Bible exists |

### What does not exist

- **No audio generation of any kind.** No text-to-speech, sound-effect or music model is installed or
  catalogued. I cannot see the PGX from here, so "installed" means "known to this repository".
- **No audio editing**, timeline, mixer, waveform display or export.
- **No audio asset records.** A project's audio is a file name and a display name; there is no
  length, sample rate, origin or approval state.
- **No finished-file export** of any kind, audio or video.

### 1.2 Constraints that shape the design

1. **Audio files live in ComfyUI's input folder**, which the app can write to but cannot list,
   measure or delete from. An audio library needs its own storage that the app owns.
2. **The app container has no audio tools.** Rendering and waveform data must be made where ffmpeg
   is, which means the two containers must share a folder.
3. **Browser saves replace whole lists** in the project file (`merge_project`). A timeline that is
   edited many times a minute, with undo, should not travel through that path.
4. **Memory is shared** between the CPU and GPU. Speech models are small; sound-effect and music
   models loaded in ComfyUI compete with video models. The tab-based memory release gets an
   Audio Lab entry.
5. **No sign-in.** Voice profiles and any future voice cloning need a consent record that means
   something; today anyone on the network is "the user".

---

## 2. Multi-track timeline schema

Implemented and tested in `audio/schemas.py` (`clean_timeline`, `clean_track`, `clean_clip`).

```json
{
  "schema": 1,
  "project_id": "…",
  "sample_rate": 48000,
  "revision": 17,
  "tempo": {"bpm": 120, "first_beat": 2400, "beats_per_bar": 4},
  "markers": [{"id": "…", "at": 96000, "name": "Chapter 2", "kind": "chapter"}],
  "master": {"volume_db": 0, "effects": []},
  "tracks": [{
    "id": "…", "name": "Host", "kind": "dialogue", "color": "#22c55e",
    "volume_db": 0, "pan": 0, "mute": false, "solo": false, "locked": false, "output": "master",
    "effects": [{"id": "…", "type": "eq", "on": true, "params": {"low_db": -3}}],
    "clips": [{
      "id": "…", "asset_id": "…",
      "start": 96000, "offset": 0, "length": 240000,
      "gain_db": 0, "fade_in": 480, "fade_out": 2400,
      "speed": 1, "pitch": 0, "reverse": false,
      "muted": false, "locked": false, "label": "",
      "effects": [],
      "link": {"kind": "segment", "id": "s1"}
    }]
  }]
}
```

Design decisions:

- **Time is whole samples** at the timeline's rate, not seconds. `start` is where a clip sits,
  `offset` is how far into its asset it begins, `length` is how much plays. Two clips meant to
  meet exactly do, and an export is identical every time. Fractions are refused, not rounded.
- **The sample rate is fixed when the timeline is made** (48 kHz by default), because changing it
  would move every clip. Assets at other rates are converted at render time.
- **Every edit is an instruction.** Trim, split, gain, fades, speed, pitch, reverse and effects
  are numbers on the clip. Splitting makes two clips pointing at one asset. Nothing touches the file.
- **Effects are an ordered chain** on a clip, a track or the master. Three types to start: EQ,
  compressor, reverb. Unknown types are dropped and out-of-range values take the default.
- **Solo wins over mute.**
- **`link`** ties a clip to what it belongs to: a storyboard segment, a script line, or a narration
  section. That is how a regenerated line replaces the right clip, and how audio follows a
  storyboard segment that moves.
- **`tempo`** carries the song analysis result so the grid can snap to beats. Empty for speech projects.
- **`revision`** rises by one on every save, so two browser tabs cannot silently overwrite each other.
- **Track kinds** are the seven in the task. **`output`** is always `master` for now; buses come later.
- Limits: 64 tracks, 2,000 clips per track, six hours.

**Where it is stored:** its own file, `data/audio/timelines/<project id>.json`, with its own API
and atomic writes. Not inside the project file (constraint 3). Undo and redo are kept in the browser
for the session; the server keeps the last 20 saved revisions for recovery.

---

## 3. Shared audio asset schema

Implemented and tested in `audio/schemas.py` (`clean_asset`).

```json
{
  "schema": 1,
  "id": "…", "name": "Rain on a wooden roof",
  "kind": "ambience",
  "origin": "generated",
  "approval": "draft",
  "file": {"name": "original.wav", "format": "wav", "sample_rate": 48000, "channels": 2,
           "length": 480000, "bytes": 1920044, "sha256": "…"},
  "parent_id": null,
  "generation": {"role": "sfx", "model": "…", "settings": {}, "source_text": "…", "seed": 12345},
  "speaker": "", "voice_profile_id": null,
  "category": "Weather", "tags": ["rain", "loop"],
  "projects": ["…"],
  "created": 0, "updated": 0
}
```

- **One library for everything**: uploads, generated speech, generated effects, music, sound taken
  from video. Stored as `data/audio/assets/<id>/asset.json` beside `original.<ext>` and a cached
  `peaks.bin` for the waveform.
- **Assets belong to the library, not to a project.** `projects` lists who uses one, so the same
  effect serves many projects with one file on disk. `sha256` catches a second upload of the same file.
- **The file's facts cannot be edited from a browser**: format, rate, channels and length are set
  by the server when it reads the file. `origin` never changes after creation.
- **Versions are new assets** with `parent_id` pointing at what they came from. A regenerated line
  is a new asset; the old one stays until the person removes it.
- **`approval`** is `draft`, `approved` or `rejected`, and is separate from any timeline. This keeps
  the three things the task asks to keep apart: generated assets, approved assets, arrangements.
- **`generation`** records the role, model, settings, source text and seed, so any generated sound
  can be made again or traced.
- The project's existing `audio` list is kept and read as before. Each entry gains an `asset_id`
  the first time Audio Lab opens that project; nothing is moved or deleted.

**Voice profiles** (`data/audio/voices/<id>.json`): name, the model and voice it uses, language,
default rate and expressiveness, and a `source` of `preset`, `designed` or `cloned`. A cloned
profile additionally requires a stored consent statement (who the voice belongs to, that they
agreed, date). Cloning is off until that exists and is not in the first speech milestone.

---

## 4. Audio model integration plan

### Roles

Five roles are added to the registry from Task 02; the single `tts` role reserved there is split.

| Role | Used by | Notes |
|---|---|---|
| Narration TTS | Narrator Studio | Long-form, one voice at a time |
| Conversational TTS | Podcast Studio, dialogue | Several speakers, turn-taking |
| Sound Effects Generation | Sound Effects Studio | Text to short audio |
| Audio Enhancement | Any speech clip | Denoise, restore |
| Music Generation | Reserved | Not built in this task |

One model may hold several roles. Each registered model declares its inputs, outputs, languages,
which voice controls it honours (rate, pitch, emotion, pauses, pronunciation), its longest single
generation, its licence, and whether a working adapter exists. The interface shows only the
controls the chosen model declares, and a model without a working adapter is never selectable.

### Where each kind of model runs

| Kind | Runtime | Why |
|---|---|---|
| Speech (both TTS roles) | A new `audio-service` container, beside `assist-service` | Speech models are Python libraries, not ComfyUI graphs. A container keeps them off the app and lets the small ones run on the CPU |
| Sound effects, music | ComfyUI | ComfyUI can run text-to-audio models with its standard nodes, the app already drives it, and the existing job tracker already queues politely behind renders |
| Enhancement | `audio-service` | CPU-friendly filters first (ffmpeg); a model later |
| Rendering, export, waveform data | `assist-service` (it has ffmpeg, librosa, soundfile) | No new dependency |

### Candidate models, to be confirmed at install time

I have not installed or run any of these. They are starting points from current public
comparisons; each needs its licence read and a test on the PGX's ARM processor before it is adopted.

| Role | Candidate | Why it is a candidate | Check before adopting |
|---|---|---|---|
| Narration TTS | Kokoro-82M | Small, reported to run on a CPU, Apache 2.0 licence reported | Voice range; ARM build |
| Conversational TTS | VibeVoice, Dia | Built for long multi-speaker dialogue from a tagged script | VibeVoice is reported as research-use only, which matters if output is ever sold. Dia's licence and hardware need |
| Either TTS role | Qwen3-TTS, Chatterbox | Widely recommended; Qwen3-TTS reported Apache 2.0 | Both centre on voice cloning; we would use preset or designed voices only until the consent rule exists |
| Sound effects | Stable Audio Open 1.0 | Runs in ComfyUI with standard nodes, about 2.3 GB | Stability's licence terms; length limit per generation |
| Music (reserved) | ACE-Step 1.5 | Native ComfyUI support | Out of scope here |

### Rules carried into every adapter

- **No silent downloads.** A model appears as "not installed" with its size and licence; installing
  is an explicit action, as with the existing AI Models panel.
- **No real-voice cloning or impersonation** without the consent record in section 3.
- **Script generation never invents real quotations, interviews or sourced claims as fact.** The
  script prompt says so, and reference documents are the only allowed source of factual statements.
- **Sound suggestions are proposals.** Assisted Storyboard may suggest sounds for a scene; nothing
  is generated until approved.

---

## 5. Implementation dependency map

```
A  Architecture and data model  (this milestone)
│
B  Audio Lab foundation ──────────────┐   needs: asset storage, timeline API, waveform data
│                                     │
C  Mixing and export ─────────────────┤   needs: B, ffmpeg rendering in assist-service
│                                     │
├── D  Narrator Studio                │   needs: C, audio-service, model registry (Task 02 M2)
│    │
│    └── E  Podcast Studio            │   needs: D (shares voices and line generation)
│
├── F  Sound Effects Studio           │   needs: C, model registry, shared job tracker (Task 02 M6)
│
└── G  Storyboard integration ────────┘   needs: C, and Task 02 M8 (final video assembly)

H  Review                                 after G
```

How this meets Task 02:

| Task 03 milestone | Depends on Task 02 |
|---|---|
| B, C | Nothing. They can be built now |
| D, E, F | Milestone 2 (model registry and selection). F also benefits from Milestone 6 (one job tracker) |
| Audio Production as a project type | Milestone 1 (done): one more video type and its subtypes in `config.py` |
| Audio-only projects not needing a storyboard | Milestone 3 (intake without a song) covers the same ground from the video side |
| Fictional podcasts using the Story Bible | Milestone 5. Until then they use Lore |
| G: audio in the final video | Milestone 8 |

**Converting an audio project to video** needs no copying: the project keeps its id, and Milestone 1
already keeps every type's settings when the type changes. The timeline and assets are keyed by
project id and asset id, so they come along untouched.

---

## 6. Module and file structure

```
audio/                          one Python package, the pattern Identity Studio uses
  schemas.py                    assets, timelines, effects (written, tested)
  storage.py                    data/audio/: assets, timelines, voices; atomic writes; trash
  api.py                        every route under /api/audio/
  render.py                     turns a timeline into an ffmpeg job description
  models.py                     audio roles, capabilities, adapters
  tests/

static/audio/
  audio-lab.js / .css           timeline, transport, tracks, waveforms
  mixer.js                      channel strips and meters
  engine.js                     Web Audio playback graph
  narrator.js, podcast.js, sfx.js      the three studios (later milestones)

assist-service/service.py       gains: /probe, /peaks, /render      (ffmpeg, soundfile)
audio-service/                  new container for speech models     (Milestone D)

data/audio/
  assets/<id>/asset.json, original.<ext>, peaks.bin
  timelines/<project id>.json   plus the last 20 revisions
  voices/<id>.json
  exports/<project id>/         rendered files
```

The host touches the module in the same few places as Identity Studio: `app.py` hands
`/api/audio/` requests over, `index.html` gains an "Audio Lab" sidebar entry and an empty
container, and `run.sh` mounts `data/audio` into `assist-service`.

**Playback and export are two engines on purpose.** The browser's Web Audio plays the timeline
live for editing. The server renders exports with ffmpeg from the same instructions, so an export
does not depend on the browser or the machine it ran on. Gain, pan, fades and trims will match
exactly; EQ, compression and reverb will sound close but not identical between the two, and the
interface will say that the export is the reference.

---

## 7. Testing strategy

| Layer | How | State |
|---|---|---|
| Data model | Unit tests on `clean_asset`, `clean_timeline`: browser cannot change file facts, time stays whole samples, fades cannot cross, solo and mute, effect chains, stability | 11 tests written, passing |
| Storage | Temporary folder: atomic writes, an interrupted write leaves the old file, trash on delete, revision conflicts, bad ids | With Milestone B |
| API | Handler called directly with dictionaries, as Identity Studio's is | With Milestone B |
| Rendering | Build the ffmpeg job from a timeline and check it as data. Then real renders of generated tones: a clip placed at sample N starts at sample N in the output; two half-level tones sum correctly; a fade reaches zero | With Milestone C. Needs ffmpeg, so these run inside `assist-service` or are skipped where ffmpeg is absent |
| Waveform data | Peaks of a known signal; cache reused when the file is unchanged | With Milestone B |
| Browser | Headless run: import, drag, trim, split, undo, reload and find the same arrangement | With Milestone B |
| Generation | Each adapter against a stand-in, then one real generation per installed model on the PGX | Milestones D to F |
| Existing features | The 99 tests from Task 02 keep passing; `./run-tests.sh` now also runs `audio/tests` (110 in total) | Passing |

Listening quality cannot be tested automatically. Each generation milestone ends with a short
list of things for you to listen to.

---

## 8. Milestone checklist

**A. Architecture and data model**
- [x] Audit existing audio functionality
- [x] Shared audio asset schema and timeline schema, as tested code
- [x] Model roles, capabilities and where each runs
- [x] Tests established
- [x] Integration and dependency map
- [ ] Review and the decisions below

**B. Audio Lab foundation**
- [ ] `data/audio` storage and `/api/audio/` routes; mount shared with `assist-service`
- [ ] `/probe` and `/peaks` in `assist-service`
- [ ] Audio Lab sidebar tab; import; existing project audio appears as assets
- [ ] Timeline with tracks: add, delete, rename, duplicate, reorder
- [ ] Clips: drag, trim, split, duplicate, delete, multi-select; snap to grid and markers
- [ ] Waveforms from cached peaks
- [ ] Play, pause, stop, seek, zoom, scroll; beat grid for music projects
- [ ] Undo and redo; saved and restored

**C. Mixing and export**
- [ ] Mixer: faders, pan, mute, solo, meters, master, clipping warning
- [ ] Clip gain, fades, speed, pitch, reverse; EQ, compressor, reverb chains
- [ ] `/render` in `assist-service`; WAV, MP3, FLAC; full mix, stems, ranges
- [ ] Timing verified by measurement

**D. Narrator Studio**, **E. Podcast Studio**, **F. Sound Effects Studio**, **G. Storyboard
integration**, **H. Review**: as set out in the task, each planned in detail when reached.

---

## 9. Risks

1. **This is a second large programme on top of Task 02**, which is at Milestone 1 of 8 and waiting
   for approval. The two share the model registry, the job tracker and final assembly. Running
   them in step matters more than speed in either.
2. **A browser timeline editor is the biggest single piece of interface work in the application so
   far.** Many clips, zooming waveforms and drift-free playback are where such editors usually
   struggle. Milestone B should prove responsiveness early, with a deliberately large test project.
3. **Preview and export will not be bit-identical** for EQ, compression and reverb (section 6).
4. **Speech model licences.** Some of the best conversational models are reported as research-use
   only. Fine for internal work; a real constraint if podcasts are ever sold.
5. **ARM.** The PGX's processor is ARM. Python speech libraries sometimes ship no ARM build; each
   candidate needs a real install test before the design depends on it.
6. **Voices.** Without sign-in there is no meaningful "authorised user" for voice cloning. Cloning
   stays out until both consent records and sign-in exist.
7. **Disk.** Uncompressed audio is large (about 10 MB a minute at 48 kHz stereo). Generated
   alternatives multiply it. The library needs the same lock and clean-up tools Identity Studio has.
8. **Pitch and speed** in the browser preview are limited (changing speed changes pitch unless a
   separate algorithm is used). Independent pitch shift may be export-only at first.

---

## 10. Decisions needed before Milestone B

1. **Order of work.** Audio Lab B and C depend on nothing in Task 02 and could start now. Or
   finish Task 02 Milestone 2 (model selection) first, since D, E and F need it. Which first?
2. **Storage.** A separate library under `data/audio/` shared by all projects, with timelines in
   their own files, as proposed?
3. **Sample rate.** 48 kHz for every timeline (the video standard), with other rates converted
   at render?
4. **A new `audio-service` container** for speech models, and sound effects through ComfyUI?
5. **Voice cloning** left out until consent records and sign-in exist?
