# SWIFT Identity Studio

A workspace inside SWIFT Director for designing logos and app identities. It is built as a
separate module so it can later be lifted into its own app without untangling it from the
storyboard code.

**Status: Phase 1 (architectural foundation) plus job tracking.** Identity projects and their
briefs work, reference images can be added and switched on or off, concepts can be generated,
looked at closely and fixed by area. Nothing is exported yet.

## Architecture

| Part | Where | What it owns |
|---|---|---|
| Schemas | `identity_studio/schemas.py` | The shape of an identity project, the allowed styles, layouts, backgrounds and platforms, and validation of anything a browser sends |
| Storage | `identity_studio/storage.py` | Reading and writing projects on disk, safe ids, duplicate, trash |
| References | `identity_studio/references.py` | Checking uploaded images, and rebuilding SVG files so they are safe to keep and show |
| Tools | `identity_studio/tools.py` | The models and tools only Identity Studio uses, with whether each is installed. System status shows them in their own section |
| Generation | `identity_studio/generate.py` | Turning the brief and enabled references into concept jobs, fixing an area, and bringing finished pictures into the project |
| Jobs | `identity_studio/jobs.py` | Identity Studio's own job list and its rules for sharing ComfyUI with video renders |
| API | `identity_studio/api.py` | Every route under `/api/identity/` |
| Tests | `identity_studio/tests/` | Unit tests for the three parts above |
| Frontend | `static/identity/identity-studio.js` and `.css` | The workspace page. Classes all start with `ids-`, colours are SWIFT tokens only |

The host touches the module in seven places:

1. `app.py` imports `identity_studio.api` and passes any `/api/identity/` request to `handle()`.
2. `app.py` serves `.js` files from `static/` (it already served `.css`, `.svg` and `.woff2`).
3. `static/index.html` has one sidebar button, one empty container (`#v-identity`) and the two tags that load the module's files.
4. `show('identity')` calls `IdentityStudio.show()`.
5. `app.py` calls `identity_api.start()` once at start-up, so jobs left waiting by a restart carry on.
6. `app.py` calls `identity_api.configure(build_image=…, build_fix=…, before=…)`, handing over the
   storyboard's FLUX.2 graph builders. The module keeps no copy of model names or sampler settings.
7. The picture viewer's `openViewer(src, name, fixer)` takes an optional third argument, so the
   module can reuse the same zoom, pan and "Fix an area" tools with its own fix handler.

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
| `COMFY_URL` | `http://127.0.0.1:8188` | The same ComfyUI the storyboard uses |

## Dependencies

Python standard library only, and no browser libraries. Later phases will need an imaging
library (Pillow) for resizing and icon sets and an SVG rasteriser for exports; neither is in the
server image today, and adding them is a decision to make at that phase, not something done here.

## Storage

```
data/identity/
  projects/<id>.json      one file per identity project
  assets/<id>/references/ that project's reference images, named by our own ids
                          (<ref>.flat.png is the white-backed PNG the image model is given)
  assets/<id>/concepts/   finished concept pictures, copied out of ComfyUI's output folder
  trash/                  deleted projects, with the time of deletion in the name
  jobs.json               identity jobs: waiting, in ComfyUI, and the last 200 finished
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
| POST | `/api/identity/projects/delete` | `{id}` | Confirmation. The project's jobs are cancelled |
| GET | `/api/identity/models` | | Identity Studio's own models and tools, and whether each is installed |
| GET | `/api/identity/queue` | | Whether ComfyUI is reachable, how many other jobs it holds, how many identity jobs are in play |
| GET | `/api/identity/jobs?project=…` | | `{jobs: […]}`, without their graphs |
| POST | `/api/identity/jobs/cancel` | `{id}` | The job, cancelled |
| POST | `/api/identity/jobs/retry` | `{id}` | The job, waiting again |

| POST | `/api/identity/references?project=…&name=…` | The image file itself | The reference's record |
| GET | `/api/identity/reference?project=…&id=…` | | The stored image |
| PUT | `/api/identity/reference?project=…&id=…` | `{use?, note?, name?}` | The reference's record |
| POST | `/api/identity/references/remove` | `{project, id}` | Confirmation. The file goes to the trash folder |

| POST | `/api/identity/reference/flat?project=…&id=…` | A PNG | Stores the flattened copy the page made |
| POST | `/api/identity/concepts/generate` | `{project, direction?}` | `{queued, concepts, notes}` |
| GET | `/api/identity/concept?project=…&id=…` | | A finished concept's picture |
| POST | `/api/identity/concepts/fix?project=…&id=…&prompt=…` | The painted mask (PNG) | `{queued, concepts}` |
| POST | `/api/identity/concepts/remove` | `{project, id}` | Confirmation. The picture goes to the trash folder |

`PUT …/reference` also takes `{enabled}`. No route accepts a ComfyUI graph from the browser. Jobs are created by module code only.

Errors come back as `{"error": "…"}` with status 400 (bad input) or 404 (unknown route).
Only `name`, `description` and `settings` can be changed through the API; unknown settings are
dropped and invalid values fall back to the current ones.

## Reference images

A project can hold up to 24 references: PNG, JPEG or WebP up to 20 MB each, and SVG up to 2 MB.
Each has a use and a note:

- **Insert as it is** (`insert`): the reference's own pixels are placed in the centre of the picture
  and everything else is drawn around them. The default for an SVG or a PNG with transparency.
- **Follow closely (redrawn)** (`keep exactly`), **Style guide**, **Inspiration**: the reference is
  given to the image model as guidance, and the model redraws it.

Uploads are treated as untrusted:

- The file type is decided from the file's first bytes, never its name, and the name on disk is
  the module's own id.
- An SVG is rebuilt from an allow-list of drawing elements. Scripts, event handlers,
  `foreignObject`, embedded images, links, references to anything outside the file, and styles
  that import or load anything are removed. Files that define their own XML entities are refused.
  What is stored is the rebuilt file, and the page says how many parts were removed.
- The page shows references only inside `<img>`, and the server sends them with
  `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox` and `nosniff`.

The checker is not a full image decoder: a file that starts like a PNG but is corrupt is stored
and simply fails to display. The one place the module uses fixed colours is the grey checkerboard
behind a reference, so transparent marks stay visible.

## Sharing ComfyUI with video renders

Identity Studio keeps its own job list (`jobs.py`) and follows four rules, each covered by a test:

1. A job is handed to ComfyUI only when ComfyUI has nothing running and nothing waiting. Until
   then it waits in `jobs.json`, and the page says how many jobs are ahead of it.
2. Only one identity job is in ComfyUI at a time, so a render queued meanwhile goes ahead of the
   next identity job.
3. Stopping an identity job removes that job from the queue. It is interrupted only if it is the
   job ComfyUI is running at that moment. A running render is never interrupted.
4. The host's "Stop all renders" still clears the whole ComfyUI queue, identity jobs included. A
   job lost that way is marked stopped and waits for Retry; it does not restart by itself.

Jobs use the client id `identity-studio`, so storyboard progress bars never show identity work.
The storyboard's own job tracking is untouched.

One gap remains: if a render is queued in the instant between the idle check and the hand-over,
the identity job sits in front of it. It delays that render by one still image and interrupts nothing.

## Generation

**Generate concepts** queues one job per concept ("concepts per round" in the brief), each with
its own seed, through the job tracker above. The prompt is built from the brief, an optional
direction for the round, and the enabled references. Icon-only concepts are 1024 × 1024; icon and
text are 1536 × 768. When a job finishes, its picture is copied into the project's own folder.

References and the image model:

- Up to four enabled references are sent. More than four enabled: the first four are used and the page says so.
- FLUX.2 cannot read SVG or transparency, so the page draws each reference onto white and stores
  that PNG; generation uses it. An SVG whose flat copy has not been made yet is refused with a message.
- A reference is guidance. "Keep exactly" asks for a faithful copy, but the model redraws the
  mark, so its shape must be checked in each concept. Exact placement of the uploaded vector
  belongs to a later composition step.
- Concepts are drawn on plain white (or black for a dark background). Transparency comes with export.
- Lettering from the model is often misspelled.

**Insert as it is** works differently from the other uses. The page places the reference at 46%
of the picture's shorter side, centred, on a blank canvas, and makes a mask that is black over the
mark. The storyboard's inpainting graph then draws everything except the mark and pastes the
original canvas back through the mask, so the mark's pixels are exactly the upload's. One
reference is inserted per round, and the other enabled references sit that round out. A reference
with no transparency is inserted as its whole rectangle. A small raster is enlarged and looks
soft; the page warns when that happens.

**Fix an area** uses the storyboard's inpainting graph: paint over the part to change, describe
it, and a new concept is added. The original is kept.

Licence: concepts are made with FLUX.2 [dev], which is licensed for non-commercial use. That is
accepted because these are internal concept and placeholder marks; final artwork for any product
that is sold will come from hired artists. The page says this under the concepts.

## Export (not built)

No export exists yet. `exports` in the project file is reserved for it.

Planned for export: tracing an approved concept into an SVG with VTracer (the `vtracer` Python
package, which has a build for the server's ARM processor and Python 3.12). It is listed under
System status as not installed; the server image does not include it yet. A traced SVG scales cleanly but is
an approximation of the picture (many small curves, lettering as shapes rather than type). It
suits flat marks with a few solid colours and suits gradients, glows and fine texture badly.

## Known limitations

- No brand profiles, approval, export or publishing.
- Generation and fixing are tested against a stand-in for ComfyUI, not yet on the real server.
- No sign-in, the same as the rest of SWIFT Director. Do not expose the port to the internet.
- Two browser tabs editing the same brief: the last save wins.
- The trash folder is never emptied automatically.

## Roadmap

Phase 1 (this one) is the foundation: module boundary, storage, API, project management.
Job tracking, reference images, concept generation and fixing an area are also in. Still to
come, in the order the development prompt sets out: brand profiles, approval, export of icon sets, and explicit publishing.

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
