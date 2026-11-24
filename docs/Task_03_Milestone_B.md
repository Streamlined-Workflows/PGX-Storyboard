# Task 03, Milestone B: Audio Lab Foundation

Status: built on `main`, for review. Milestone C does not start until this is approved.

Decisions this followed (24 November): Task 03 goes ahead of Task 02 Milestone 2; a separate
audio library under `data/audio/` shared by all projects; 48 kHz for every timeline; a new
container for speech models and sound effects through ComfyUI (both later milestones); and voice
cloning is to be built when speech arrives, not held back, since access to the server is limited
to its owner. Each cloned voice will still carry a note of whose voice it is and that they agreed.

## What was built

**Audio library** (`audio/storage.py`, `audio/media.py`)
- Each sound is stored once under `data/audio/assets/<id>/`: `asset.json`, `original.<ext>`
  exactly as it arrived, and `peaks.bin`, the cached waveform data.
- The server reads every file itself to record its format, sample rate, channels and length.
  Anything that is not sound is refused and leaves nothing behind.
- The same file added twice is stored once and shared between projects.
- Taking a sound out of a project moves it to `data/audio/trash/` once no project uses it.
- WAV, FLAC, MP3, OGG, Opus, AAC, M4A and the sound from an MP4 are accepted.

**Timeline storage**
- One file per project, `data/audio/timelines/<project id>.json`, apart from the project file.
- Every save writes to a temporary file and swaps it in, so an interrupted save leaves the previous
  version intact. The last 20 saved versions are kept beside it.
- Each save carries the revision it was based on. If another window has saved since, the save is
  refused and the page offers to load the latest version.

**Audio Lab tab** (`static/audio/`)
- Sounds in this project: import, add to a track, drag onto a track, take out of the project.
  A project's earlier audio uploads (its song) are brought in automatically the first time.
- Tracks: add, delete, rename, set the type (the seven in the task), duplicate, move up and down,
  mute, solo, lock, volume and pan.
- Clips: drag to move, drag between tracks, drag either edge to trim, split at the playhead,
  duplicate, delete, shift-click to select several and move them together.
- Snap: off, grid, beats, or markers and clip edges. Beats uses the song's tempo from Assisted
  Storyboard when the project has one.
- Waveforms drawn from the cached peak data.
- Play, pause, stop, seek by clicking the ruler or a lane, zoom (buttons or Ctrl and scroll),
  scrolling in both directions, a playhead that follows playback.
- Markers: add at the playhead, click to go there, double-click to rename, right-click to remove.
- Undo and redo, up to 100 steps, for every change.
- Keys: Space, S, M, Delete, Ctrl+Z, Ctrl+Y, Ctrl+D, Home, End.
- Saved automatically and restored when the project is reopened.

**Server**
- `app.py` hands `/api/audio/` requests to the module, the same way it does for Identity Studio.
- The application's container now includes ffmpeg (`Dockerfile`, built by `run.sh`).
- Opening Audio Lab releases the AI models from memory, since it needs none.

## A change from the Milestone A plan

Milestone A proposed doing audio file work in the song analysis container, because that was the
only place ffmpeg existed. Building it showed a simpler route: give the application's own
container ffmpeg. That removes a shared folder and a second service from every import, and
exporting in Milestone C will use the same tools in the same place. The song analysis container is
unchanged.

## Tests

`./run-tests.sh`: 124 tests, all passing. New here: 14 for the library, timeline storage and API,
using real audio files in a temporary folder (facts recorded, waveform data correct for a known
tone, duplicates stored once, non-audio refused, originals never changed, stale saves refused,
history kept, damaged files reported, ids that cannot reach outside the library).

Checked in a headless browser with real audio and ffmpeg: the project's song was brought in;
WAV and MP3 imported and a non-audio file refused; a clip was moved (snapping to the grid),
trimmed, prevented from trimming past the end of its sound, split, duplicated, deleted, restored
by undo and redo, and moved to another track; tracks were renamed, retyped, soloed, duplicated
and reordered; playback advanced in step with the clock (0.95 to 1.01 seconds measured over one second) and survived an edit made while playing;
the arrangement came back identical after a reload; and a save from a second window was detected
and resolved. The storyboard, Assisted Storyboard, Assets, Library, System status and Identity
Studio checks still pass.

## Not verified

- Nothing here has run on the PGX. The first update there builds the new container, which needs
  the internet once to fetch ffmpeg.
- I confirmed playback by its clock and scheduling, not by listening. How it sounds is yours to judge.
- Very long sounds and timelines with hundreds of clips have not been load-tested.

## Known limits

- **Playback decodes a sound in the browser the first time it is needed**, so the first Play of a
  long song pauses briefly. Waveforms do not need this; they come from the cached data.
- **No mixer panel, meters, clip gain, fades, speed, pitch, reverse or effects yet.** The data
  model holds them; the controls are Milestone C.
- **No export.** Milestone C.
- **Waveforms of very long clips at high zoom are drawn at reduced sharpness** (the picture is
  capped at 8,192 pixels wide and stretched).
- **Undo history is per visit.** It is not kept after the page is reloaded; the saved versions on
  the server are the recovery route.
- **Markers are plain markers.** Chapter markers arrive with Podcast Studio.
- **Touch screens:** not tested. The interface is built for a mouse and keyboard.

## Recommended next step

Milestone C, mixing and export: the mixer panel with meters, clip gain and fades, the EQ,
compressor and reverb chains, and rendering a full mix, stems or a range to WAV, MP3 or FLAC, with
the timing of the output measured against the timeline.
