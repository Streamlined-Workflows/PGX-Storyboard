# Task 02, Milestone 1: Assisted Storyboard Configuration

Status: built on `main`, for review. Milestone 2 does not start until this is approved.

Decisions this followed: work on `main`; one `config` block with all three type blocks always
kept; the rating is shown and stored but has no effect yet.

## What was built

- **Project schema 2.** Every project has `schema`, `config`, `intake` and `collection_id`. A
  version 1 file gets the defaults in memory when opened and is rewritten only when next saved.
  A file from a newer version keeps its number and any fields this version does not know.
- **`config.py`.** The choices for every field in the task, the defaults, and `clean()`, which
  takes only valid values from a browser and keeps the stored value otherwise.
- **Project Configuration Center** at the top of Assisted Storyboard (`static/config/`), six
  collapsible sections that remember which are open:
  1. Project Identity: rating, video type, and the Story, Music Video or Commercial fields for the chosen type, with In-between Purpose when the story subtype is In-between
  2. AI Model Configuration: the seven generation roles, what performs each today, all on Auto
  3. Video Generation: aspect ratio, output resolution, target FPS, platform, generation environment
  4. Audio and Speech: speech-to-text in use; text-to-speech "not installed"
  5. Production Settings: visual direction and notes, storyboard detail, five continuity switches
  6. Workflow and Approval Controls: eight switches
- **In use / Stored tags** on every setting, so nothing looks more functional than it is.
- **Confirmation** before changing video type when an approved story or planned shots exist,
  saying they are kept but may no longer fit.
- **Defaults for new projects** (`data/defaults.json`), set from any project's configuration.

## What takes effect now

| Setting | Effect |
|---|---|
| Music Video Subtype | Adds a "kind of video" instruction to the story concept request. Re-enactment of Events adds nothing, so it matches earlier behaviour |
| Storyboard Detail | Adds a "level of detail" instruction to the shot planning request. Standard adds nothing |

Everything else is stored only. The rating in particular is stored and shown; applying filtering
rules against it waits until every generation type, including text-to-speech, is laid out.

## Tests

`./run-tests.sh`: 45 core tests and 48 Identity Studio tests, all passing. New in this milestone:

- `tests/test_config.py` (11): defaults reproduce old behaviour, bad values keep what was stored,
  switching type keeps the other types' settings, every choice in the task is offered, guidance
  reaches the language model, version 1 files open without being rewritten, newer files keep
  their number and unknown fields, saved defaults apply to new projects only.
- `tests/test_render.py` (13), closing the gaps listed in Milestone 0: queueing runs, holding a
  continuing shot and releasing it from the picked clip's last frame, Render all skipping what
  would wait, results following ComfyUI, locked key frames and singing end shots being skipped,
  duplicate and delete.

Checked in a browser against stand-ins for ComfyUI and Ollama: all six sections, conditional
fields, the type-change confirmation (declined and accepted), saving and reloading, defaults for
a new project, and that the existing steps below the panel still work.

## Not verified

- Nothing in this milestone has run on the PGX.
- The two prompt additions have not been judged against the real language model.

## Known limits

- Story and Commercial can be selected and configured, but Assisted Storyboard still starts from
  a song. The panel says so. Song-free intake is Milestone 3.
- Output resolution, frame rate and aspect ratio describe the wanted export. Clips are still
  generated at 832 × 480. The panel says so.
- The model roles are read-only. Selection is Milestone 2.
- The workflow switches are stored; the approvals that already exist are unchanged.
- Assisted Storyboard already scrolls sideways on a phone-width screen because of its tables.
  The new panel fits, but the page around it does not. Not introduced here; worth fixing.

## Decision carried over

Bring a basic memory guard forward from Milestone 6 to Milestone 2? (Asked in Milestone 0,
not yet answered.)

## Recommended next step

Milestone 2, Model Selection: discovery from Ollama and ComfyUI, a table of the model families
the app has a working graph for, and Auto or explicit choice passed through to generation.
