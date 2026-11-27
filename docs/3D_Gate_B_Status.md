# 3D Generation: Gate B status

Gate B is the "first working demo" in `3d_Generation_Plan/3d_Phase_26.md`. Its exit test is: *from approved references
or imported FBX, review a candidate, reopen it, confirm a pending export and validate package reimport.*

The **imported FBX** half of that path is built and passes in automated tests and in a browser run. The **from approved
references** half (generating geometry) is not built, because no geometry model is installed or chosen.

Nothing here has been run on the PGX yet, and no real-world FBX (Blender, Character Creator, iClone) has been tried.

## Built

| Plan phase | What exists | Where |
| --- | --- | --- |
| 4 Asset definition | Asset records with stable ids, classification from the shared registry, status, quality, target count, dimensions, tags; duplicate; delete; `AssetManifest.json` | `studio3d/assets.py` |
| 5 Reference hand-off | Attach pictures sent from Reference Generation by id (no copies), roles and directions, live state (approved, pending, gone) | `assets.py`, `app.py` hooks |
| 6 Geometry (import only) | Binary FBX reader: counts, bounds, axes and units, parts, rigging carried, seven kinds of fault; pending candidates; select; budget shown against target | `studio3d/fbx.py` |
| 14 Character preparation (inspect only) | Roles, profile, stated pose, height, ground, centring, axes, base-mesh faults, two confirmations, hand-off record | `studio3d/character.py` |
| 16 Viewport | FBX display, named views, perspective/orthographic, frame, shading, colour by part, fault marking, hide/isolate/select, per-axis grids | `static/studio3d/viewport.js` |
| 18 Export and reimport | SWIFT ZIP with manifest, checksums and compatibility report; read-back check; pending confirmation; validated reimport as a new editable asset | `studio3d/package.py` |
| 19-21 Providers, queue, locks | Capability table, provider registry, one-at-a-time ledger kept on disk, lock scopes, cancel, force-stop confirmation, retry, interrupted-on-restart | `studio3d/jobs.py` |
| 22 Lifecycle and storage | Content-addressed store, 10-day expiry, approve with dependency confirmation, deny deletes, free-space floor, orphan sweep, hourly cleanup and Clean Up Now | `studio3d/store.py`, `assets.py` |
| 23 Workspace | Header, nine tabs, parts tree, inspector, job list, the two inherited confirmation dialogs | `static/studio3d/studio3d.js` |
| 24 Local security | Same-origin check on changes, size limits before reading, path and checksum checks on packages, external picture addresses in FBX never fetched, no outbound calls | `app.py`, `package.py`, `viewport.js` |

## Not built

- **Any provider that makes or changes geometry**: generation from references, optimisation, segmentation, FBX
  conversion or normalising, UVs, texture generation and baking, pose conversion, weight transfer, landmarks. The tabs
  exist and say "Not available yet" with the reason.
- **Writing FBX.** The studio stores and exports files byte for byte. A file in other axes or units is reported, not converted.
- Phases 7 to 13, 15 and 17 (optimisation, components as separate files, UVs, textures, materials, surface editing,
  landmarks, assembly) beyond the read-only facts shown on their tabs.
- Components are the model nodes the file already has. They cannot be split, joined or exported one by one.
- Materials and textures inside an FBX are counted but not read or shown; the view's colours are only for looking.
- ASCII FBX, and any format other than FBX.
- Logins or per-user permissions (the plan relies on Tailscale).

## Decisions taken without asking, to change if you disagree

1. **An imported FBX is pending** (10 days) unless "Approve on import" is ticked. The plan could be read as "imports are
   yours, so approved"; pending was chosen because Gate B's test exports a pending item.
2. **No FBX library.** The reader is plain Python and reads binary FBX only. This keeps the server dependency-free, at
   the cost of no conversion and no ASCII.
3. **The 3D view uses three.js's own FBX loader**, so what you see can differ from what the reader measured for unusual
   files (pivots, pre-rotations). The inspector says when its size figure is approximate.
4. **Reimport always makes a new asset**, even when the original is still here.
5. **Exports are kept for a day** in `data/studio3d/exports/` and then removed; the download is the copy that lasts.
6. The old placeholder cube view and its **Reset view** button were replaced by this workspace; the **3/4** button does the same job.

## How it was checked

- `./run-tests.sh`: `studio3d/tests/` covers the reader, storage, lifecycle, queue, export, reimport, character checks
  and the routes. The FBX files are small ones written by the tests themselves.
- A browser run (Chrome, software WebGL) against the real server: import, parts list, hide/isolate, lock, views and lens,
  character checks, each unavailable tab, export cancelled then confirmed, download, reimport, approve, a second
  candidate with faults marked, deny, reload, and a phone-width layout. No request left the machine.

- The reader measured a made-up mesh of 202,500 control points (8 MB) in 1.5 seconds in the test sandbox. Real files have
  not been timed.

## To try on the PGX

1. Import a real character FBX from Blender or Character Creator. Does it draw, and do the counts match the source tool?
2. Import a large file (hundreds of MB). How long does the read take, and does the page stay usable?
3. Export, then import the ZIP. Do the names, roles and locks come back?
4. Open the exported FBX in the tool it came from. It should be identical, since it is the same bytes.
