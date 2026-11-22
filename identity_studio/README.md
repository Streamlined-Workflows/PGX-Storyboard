# SWIFT Identity Studio

A workspace inside SWIFT Director for designing logos and app identities. It is built as a
separate module so it can later be lifted into its own app without untangling it from the
storyboard code.

**Status: Phase 1 (architectural foundation) plus job tracking.** Identity projects and their
briefs work, reference images can be added, and the module can queue ComfyUI jobs politely.
Nothing builds a job yet, so nothing is generated or exported.

## Architecture

| Part | Where | What it owns |
|---|---|---|
| Schemas | `identity_studio/schemas.py` | The shape of an identity project, the allowed styles, layouts, backgrounds and platforms, and validation of anything a browser sends |
| Storage | `identity_studio/storage.py` | Reading and writing projects on disk, safe ids, duplicate, trash |
| References | `identity_studio/references.py` | Checking uploaded images, and rebuilding SVG files so they are safe to keep and show |
| Jobs | `identity_studio/jobs.py` | Identity Studio's own job list and its rules for sharing ComfyUI with video renders |
| API | `identity_studio/api.py` | Every route under `/api/identity/` |
| Tests | `identity_studio/tests/` | Unit tests for the three parts above |
| Frontend | `static/identity/identity-studio.js` and `.css` | The workspace page. Classes all start with `ids-`, colours are SWIFT tokens only |

The host touches the module in exactly five places:

1. `app.py` imports `identity_studio.api` and passes any `/api/identity/` request to `handle()`.
2. `app.py` serves `.js` files from `static/` (it already served `.css`, `.svg` and `.woff2`).
3. `static/index.html` has one sidebar button, one empty container (`#v-identity`) and the two tags that load the module's files.
4. `show('identity')` calls `IdentityStudio.show()`.
5. `app.py` calls `identity_api.start()` once at start-up, so jobs left waiting by a restart carry on.

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
| GET | `/api/identity/queue` | | Whether ComfyUI is reachable, how many other jobs it holds, how many identity jobs are in play |
| GET | `/api/identity/jobs?project=…` | | `{jobs: […]}`, without their graphs |
| POST | `/api/identity/jobs/cancel` | `{id}` | The job, cancelled |
| POST | `/api/identity/jobs/retry` | `{id}` | The job, waiting again |

| POST | `/api/identity/references?project=…&name=…` | The image file itself | The reference's record |
| GET | `/api/identity/reference?project=…&id=…` | | The stored image |
| PUT | `/api/identity/reference?project=…&id=…` | `{use?, note?, name?}` | The reference's record |
| POST | `/api/identity/references/remove` | `{project, id}` | Confirmation. The file goes to the trash folder |

No route accepts a ComfyUI graph from the browser. Jobs are created by module code only.

Errors come back as `{"error": "…"}` with status 400 (bad input) or 404 (unknown route).
Only `name`, `description` and `settings` can be changed through the API; unknown settings are
dropped and invalid values fall back to the current ones.

## Reference images

A project can hold up to 24 references: PNG, JPEG or WebP up to 20 MB each, and SVG up to 2 MB.
Each has a use ("keep exactly", "style guide" or "inspiration") and a note. Nothing reads them
yet; concept generation and the composition step will.

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

## Generation (not built)

Nothing builds a job yet. Decided for when it does: concepts will be made with FLUX.2 [dev], whose
licence is non-commercial. That is accepted because these are internal concept and placeholder
marks; final artwork for any product that is sold will come from hired artists. The page should
say this next to generated concepts.

## Export (not built)

No export exists yet. `exports` in the project file is reserved for it.

Planned for export: tracing an approved concept into an SVG. A traced SVG scales cleanly but is
an approximation of the picture (many small curves, lettering as shapes rather than type). It
suits flat marks with a few solid colours and suits gradients, glows and fine texture badly.

## Known limitations

- No concept generation, brand profiles, approval, export or publishing. References are stored but not yet used.
- No sign-in, the same as the rest of SWIFT Director. Do not expose the port to the internet.
- Two browser tabs editing the same brief: the last save wins.
- The trash folder is never emptied automatically.

## Roadmap

Phase 1 (this one) is the foundation: module boundary, storage, API, project management.
Job tracking and reference images are also in. Still to come, in the order the development
prompt sets out: concept generation through ComfyUI, brand profiles, refinement and approval, export of icon sets, and explicit publishing.

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
