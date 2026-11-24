# Task 03, Milestone C: Mixing and Export

Status: built on `main`, for review. Milestone D (Narrator Studio) does not start until this is
approved.

## What was built

**Export** (`audio/render.py`, `audio/exports.py`)
- The saved timeline is turned into one ffmpeg job and written as a new file. Original sounds are
  only read.
- What can be exported: the full mix, each audible track as its own file (stems, delivered as one
  zip), or part of the timeline between two times.
- File types: WAV and FLAC at 16 or 24 bit, MP3 at 128, 192, 256 or 320 kbps. Sample rate 48 kHz
  or 44.1 kHz.
- Everything is placed by whole samples at the timeline's rate. The export is resampled, if 44.1
  kHz was asked for, only at the very end.
- Order of work. Clip: the part used, reverse, speed and pitch, level, fades, the clip's effects,
  then its place on the timeline. Track: its clips added together, the track's effects, volume,
  balance. Mix: the tracks added together, master effects, master volume.
- Stems carry the track's own effects, volume and balance but not the master stage, and every stem
  runs the full length so they line up when loaded elsewhere.
- **Nothing is normalised or limited.** The loudest point is measured before the file is written
  and shown with each export. If the mix goes over full level the export still finishes, and says
  by how many dB so the master can be lowered by that much.
- Exports run one at a time in the background, on the processor. They do not use the graphics
  card and do not wait for or interrupt video renders.
- Each export has a record (what was asked, progress, length, size, loudest point, any problem).
  The last 30 per project are kept under `data/audio/exports/<project id>/`. An export cut short
  by a server restart is marked stopped, not left looking busy.

**Effects** (three, on a clip, a track or the whole mix, up to 8 in a chain, in the order listed)
- EQ: low, middle and high, each with a level and a frequency.
- Compressor: where it starts working, strength, how fast it reacts and lets go, level added back.
- Reverb: room size, how long it dies away, amount. The room is a sound file the server makes once
  per setting from a fixed recipe, so it is identical on every machine. The browser's preview loads
  the same file. An export with reverb runs on past the last clip until the room has died away.

**Mixer panel** (`static/audio/audio-mix.js`)
- One strip per track: level meter, volume fader, balance, mute, solo, effects. A master strip with
  left and right meters, master volume and master effects.
- An **Over** light that comes on when the mix goes past full level during playback and stays on
  until clicked, with the loudest level reached shown beside it.
- Faders, balance, mute and solo are heard at once while playing.

**Clip settings** (shown when clips are selected)
- Name, level, fade in, fade out, speed, pitch, reverse, mute, lock, effects. With several clips
  selected, a change applies to all of them.
- Changing the speed keeps the same stretch of sound and changes how long the clip lasts.
- Trimming and splitting take speed and reverse into account.
- Dragging a slider is one Undo step however far it moves.

**Playback** was rebuilt to follow the same chain as the export: clip level, fades and effects,
then track effects, volume and balance, then master effects and volume.

## How it was checked

154 automated tests pass (`./run-tests.sh`): 51 application, 48 Identity Studio, 55 audio. The 30
new ones make real exports and measure the files:

| Checked | Result measured |
|---|---|
| A clip placed at sample 12,345 | Silence before it, sound from exactly that sample, file exactly as long as the timeline |
| Starting partway into a sound, WAV and FLAC | The first sample out is the one asked for, including when the file is jumped into 3 s in |
| A 44.1 kHz sound on the 48 kHz timeline | Placed correctly, full level within a few samples |
| Two overlapping sounds | They add (0.25 + 0.25 = 0.5); nothing is turned down to make room |
| Clip level, track volume, master volume | Each applies; three halvings give one eighth |
| Fades | Straight line from silence and to silence, right at the midpoint |
| Mute, solo, muted clips, balance | As set; solo wins over mute; balance lowers only the other side |
| Reverse, speed, pitch | Backwards from the right sample; twice the sound in the same length at the same note; an octave up at the same length |
| EQ and compressor | +12 dB where aimed and none elsewhere; loud sound lowered, make-up level restores exactly 12 dB |
| Reverb | Used exactly as made: no delay, no change of level, amount splits dry and room as set; export runs on by the decay time |
| Range, 44.1 kHz, 24-bit, FLAC, MP3 | Exact lengths (MP3 within its usual padding) |
| Stems | One file per audible track, named and numbered, all the same length, without the master stage |
| Over full level | Reported as +3.5 dB over; the file is not altered to hide it |
| Same timeline twice | Byte-for-byte identical files |
| Missing sound, restart mid-export | Fails with the reason and leaves no partial file; marked stopped |

The same 30 tests were run against ffmpeg 6.1 and ffmpeg 7.0, because the version inside the
application's container depends on when its image was built. Both pass.

In a browser against a test server: clip settings, effect chains (add, reorder, switch off,
remove), mixer faders and balance, meters moving during playback, the Over light, playback running
through a reverb's tail and stopping, export of a full mix, stems and a range, download, removing
an export, and the arrangement coming back after a reload. The downloaded full mix was read back
and matched the expected length to the sample. All earlier Audio Lab and whole-application checks
still pass.

## Differences from the plan

- **Rendering runs in the application's container, not `assist-service`.** Milestone B put ffmpeg
  in the application's container for waveforms, so the export uses it there and no second service
  is involved.
- **A one-channel sound plays at full level on both sides.** ffmpeg's default would have lowered it
  by 3 dB; the export was made to match what the browser plays.

## Known limits

- **Nobody has listened to it.** Every check above is a measurement or a meter. How the effects
  sound, and whether the preview is close enough to the export, needs ears on the server.
- **Preview and export are not identical.** The export is the finished result. In the preview a
  speed change is heard like a tape, with the pitch moving too, and a pitch change is not heard at
  all; the clip panel says so when either is used. The preview's compressor is the browser's own
  and only approximates the export's. EQ and reverb are built to match but were not compared by
  measurement.
- **Speed and pitch are tested on steady tones.** Their quality on voices and music was not judged.
- **No loudness target yet** (for example the level podcast services ask for). The loudest point
  is measured; average loudness and an optional, explicit "match this loudness" step belong with
  Podcast Studio.
- **No crossfade tool, volume automation or ducking.** Overlapping clips with fades give a manual
  crossfade. Ducking music under speech belongs with Narrator and Podcast Studio.
- **MP3, OGG and M4A sounds are read from their start for every clip that uses them**, since they
  cannot be jumped into at an exact sample. A long MP3 cut into very many clips will export slowly;
  WAV and FLAC do not have this cost.
- **Exports are kept on the server** until removed (30 per project). Download saves a copy to the
  computer the browser is on.
- **Touch screens** were not tested, in this milestone or the last. The Milestone B note that
  dragging works on touch was not checked and should be read as unknown.
- **Not yet run on the server itself.** The first update since Milestone B builds the
  application's container image, which needs the internet once.

## Recommended next step

Milestone D, Narrator Studio, depends on choosing and installing a speech model, which is Task 02
Milestone 2 (model selection). The order that avoids rework: approve this, then Task 02 Milestone 2
limited to what audio needs (a registry of models with their licences and memory use, and the new
container for speech), then Milestone D.
