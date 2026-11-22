# SWIFT Identity Studio

A workspace inside SWIFT Director for designing logos and app identities. It is built as a
separate module so it can later be lifted into its own app without untangling it from the
storyboard code.

**Status: Phase 1 (architectural foundation).** Identity projects and their briefs work.
Nothing is generated, uploaded or exported yet.

## Architecture

| Part | Where | What it owns |
|---|---|---|
| Schemas | `identity_studio/schemas.py` | The shape of an identity project, the allowed styles, layouts, backgrounds and platforms, and validation of anything a browser sends |
| Storage | `identity_studio/storage.py` | Reading and writing projects on disk, safe ids, duplicate, trash |
| API | `identity_studio/api.py` | Every route under `/api/identity/` |
| Tests | `identity_studio/tests/` | Unit tests for the three parts above |
| Frontend | `static/identity/identity-studio.js` and `.css` | The workspace page. Classes all start with `ids-`, colours are SWIFT tokens only |

The host touches the module in exactly four places:

1. `app.py` imports `identity_studio.api` and passes any `/api/identity/` request to `handle()`.
2. `app.py` serves `.js` files from `static/` (it already served `.css`, `.svg` and `.woff2`).
3. `static/index.html` has one sidebar button, one empty container (`#v-identity`) and the two tags that load the module's files.
4. `show('identity')` calls `IdentityStudio.show()`.

The module imports nothing from `app.py`, `assist.py`, `workflows.py` or `models.py`, and never
reads or writes `data/projects/`.

## Features in Phase 1

- List, create, open, duplicate and delete identity projects.
- Per project: name, notes, and a brief (application name, tagline, purpose, what the logo
  should show, style, style notes, layout, background, colours, target platforms, concepts per round).
- The brief saves as you type.
- Delete moves the project to a trash folder; nothing is erased.

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `<repo>/data` | The same variable SWIFT Director uses. Identity Studio keeps to the `identity/` folder inside it |

No other settings exist yet.

## Dependencies

Python standard library only, and no browser libraries. Later phases will need an imaging
library (Pillow) for resizing and icon sets and an SVG rasteriser for exports; neither is in the
server image today, and adding them is a decision to make at that phase, not something done here.

## Storage

```
data/identity/
  projects/<id>.json      one file per identity project
  assets/<id>/            that project's files (empty until references and concepts exist)
  trash/                  deleted projects, with the time of deletion in the name
```

Project ids are 8 to 32 lowercase hex characters and are checked on every request, so an id can
never point outside these folders. Files are written to a temporary name and then swapped in, so
a crash cannot leave a half-written project. Each file carries a `schema` number so later phases
can upgrade older projects.

A project file holds: `schema`, `id`, `name`, `description`, `created`, `updated`,
`brand_profile_id`, `settings` (the brief), `references`, `concepts`, `approved_concept_id`,
`exports`. The last five are reserved for later phases and stay empty for now.

## API

| Method | Route | Body | Returns |
|---|---|---|---|
| GET | `/api/identity/info` | | Module version, option lists, and which features are ready |
| GET | `/api/identity/projects` | | `{projects: [summary…]}` |
| GET | `/api/identity/project?id=…` | | The full project |
| POST | `/api/identity/projects` | `{name, description?}` | The new project |
| PUT | `/api/identity/project?id=…` | `{name?, description?, settings?}` | The saved project |
| POST | `/api/identity/projects/duplicate` | `{id}` | The copy |
| POST | `/api/identity/projects/delete` | `{id}` | Confirmation |

Errors come back as `{"error": "…"}` with status 400 (bad input) or 404 (unknown route).
Only `name`, `description` and `settings` can be changed through the API; unknown settings are
dropped and invalid values fall back to the current ones.

## Generation integration (not built)

Phase 1 sends nothing to ComfyUI. When generation is added it has to respect three facts about
the host:

- SWIFT Director tracks image jobs against storyboard projects. Identity Studio needs its own
  job tracking, or that tracking needs to be made general first.
- "Stop all renders" clears the whole ComfyUI queue, so it would also stop identity jobs, and an
  identity job must never interrupt a running video render.
- The stills model in use, FLUX.2 [dev], carries a non-commercial licence. Whether logos made
  with it may be used commercially needs deciding before Phase 2.

## Export (not built)

No export exists yet. `exports` in the project file is reserved for it.

## Known limitations

- No concept generation, reference images, brand profiles, approval, export or publishing.
- No sign-in, the same as the rest of SWIFT Director. Do not expose the port to the internet.
- Two browser tabs editing the same brief: the last save wins.
- The trash folder is never emptied automatically.

## Roadmap

Phase 1 (this one) is the foundation: module boundary, storage, API, project management.
Still to come, in the order the development prompt sets out: concept generation through ComfyUI
with its own job tracking, reference images and brand profiles (with safe handling of uploaded
SVG files), refinement and approval, export of icon sets, and explicit publishing.

## Running the tests

```
python3 -m unittest discover -s identity_studio/tests -t .
```

## Notes for reuse

- `Store(data_dir)` takes its folder as an argument and `api.use_store()` swaps it, so a
  standalone app or a test can point the module anywhere.
- `api.handle(method, path, query, payload)` takes and returns plain dictionaries and knows
  nothing about the web server, so it can sit behind any server.
- The frontend needs only an element to draw in and the `--swift-*` tokens.
- Nothing in the module names SWIFT's own logo or products; the brief is data.
