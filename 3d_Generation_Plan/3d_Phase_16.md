# Phase 16: 3D Viewport and Editing Controls

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 16.1 Purpose and boundary

Provide one viewport contract across 3D Generation stages. Changing stage shall not create separate asset copies, inconsistent navigation, or independent selections. The viewport owns inspection and interaction. Generation, repair, painting, and validation remain actions of their respective stages. Full scene construction and precision mesh modeling belong outside this viewport.

The canonical geometry is FBX with right-handed coordinates, +Y up, +Z forward, and centimeters. The display may use optimized transient representations, but reading or inspecting them shall not change canonical files, measured geometric vertices, or export coordinates. Geometry and texture revision IDs govern selection validity.

## 16.2 Workspace behavior

| Workspace element | Required behavior |
| --- | --- |
| Camera and navigation | Orbit around selection or a picked surface, pan, dolly, zoom, frame selected/all, reset, and use perspective/orthographic projection. Use labeled front, rear, left, right, top, and bottom views consistent with the asset axes. Switch projection without changing the current viewing angle. Front is a separate explicit action. |
| Scene interaction | Pick components, surfaces, pivots, and enabled reference points as supported by the stage. Hierarchy and viewport selection stay synchronized by stable identity. Support additive and subtractive selection, isolate, hide, and selection lock. Stage tools declare whether they act on selection or require a designated target. |
| Display modes | Support shaded material, solid preview palette, unlit map, and wireframe inspection where applicable. Grid, axes, ground plane, boundaries, UV seams, normals, and reference points are optional overlays and never production changes. |
| Compare | Follow Phase 07: Source Only, Side by Side, Overlay, and Deviation Heatmap for compatible geometry review. Phase 09/10 editing workspace retains 3D View and synchronized Split View, not a standalone UV-only or texture-only viewport. |
| Defect and review layers | Highlight confirmed localizable defects red, with a separate scale and legend for uncertain scores or deviation. Keep production material, selection, paint mask, landmarks, and defect overlays visually and semantically separate. |
| Transform editing | Expose local/world gizmos, transform fields and optional snapping for supported asset/component transforms, pivots, and reference points. Display applicable unit values and distinguish pivot edit from object movement. |

Viewport framing, display mode and split layout are session state. Start a new session with default framing, display and split, and reopen assets at the default tool without an active component selection under Phase 23. Persist explicitly saved production work, including paint layers and transforms, independently. Changing selection or camera shall never submit a job. Selecting a hidden object via the hierarchy shall explicitly show its hidden state and allow reveal without implicitly changing assembly inclusion. A viewport-active stage shall intercept pointer actions only in its applicable tool mode, so camera gestures cannot paint surfaces or move geometry by accident.

## 16.3 Requirements

| ID | Requirement |
| --- | --- |
| VP-001 | Keep active project, asset, assembly, component, geometry revision, UV channel, and tool mode explicit. Reconcile selection by stable ID on stage change. Invalidate stale face, vertex, or UV selections when revisions diverge. |
| VP-002 | Separate camera, overlays, object visibility and palette from production geometry, material and named assembly data. Showing/hiding or isolating a component shall not change budget counts or export membership. |
| VP-003 | Support both camera projections and named views. Switching either way shall preserve the current viewing angle, with projection-appropriate framing as a technical interpretation. The separate named Front command changes the viewing angle only when invoked. No camera switch shall modify asset transforms. |
| VP-004 | Synchronize accepted stage tools with the hierarchy and applicable Split View. Show target scope and locked state before write actions. Default to visible surfaces. Offer explicit through-selection with a preview of affected hidden surfaces before applying. Canceling the preview leaves the previous selection unchanged. A hidden-surface preview does not implicitly show or activate other components. |
| VP-005 | Show one inspection-only display representation if no valid texture is loaded. Preview palette colors shall not create generated textures or become production assignments unless the user invokes a supported assignment action. |
| VP-006 | Use canonical world transform conversion for display and respect parent-relative transforms. Display orientation and origin of active asset/component grips and pivots; persist only explicit production edits. |
| VP-007 | Signal incompatible comparisons. Exact vertex displacement requires verified correspondence or declared distance algorithm. Closest-surface comparison shall disclose units, direction, scale and known limitations. Never present a viewport heatmap as a verified anatomical match. |
| VP-008 | No automatic repair. Provide stage-specific repair actions when available, preview candidates, preserve source artifacts, and distinguish candidate comparison from activation or approval. |
| VP-009 | A representative dense or textured asset shall remain navigable within the Phase 25 qualification target. Automatically use a simplified display temporarily while navigating under resource pressure, visibly indicate when it is active, and restore full detail when navigation ends. This never changes stored geometry, measurement inputs, or export output. During generation locks, leave supported lightweight editing and read-only inspection available. Phase 20 governs deferred heavy processing. |
| VP-010 | Keyboard shortcuts shall be discoverable, avoid firing while typing into fields, and include controls for camera framing, canceling a gesture, and switching tools. Nonvisual defect lists shall remain accessible where an overlay exists. |

## 16.4 Inputs, outputs, and ownership

**Inputs:** Validated asset manifest, canonical FBX or verified display derivative, applicable PNG maps/materials, active assembly and revisions, optional masks and landmarks, spatial references, validation findings, and stage capability declarations.  
**Outputs:** Session-only view-state settings, revision-bound selection, optional review screenshots, explicit transform or stage-edit requests, and a stage-independent event indicating the selected target.

The viewport shall own picking, coordinate conversion, overlays, transform interactions, camera synchronization, session-state reset, and automatic display quality indication. Providers are not needed for any viewport or deterministic inspection behavior. If a generator or validator returns marked deviations, the adapter shall declare revision, coordinate space, and region mapping. Director shall reject incompatible overlay data rather than guessing where to draw it.

## 16.5 Validation assertions

| ID | Test | Expected result |
| --- | --- | --- |
| VP-A01 | Use a fixture with labeled axes and asymmetric corners. | All named views and measurements follow the agreed axes and unit display without mirrored geometry. |
| VP-A02 | Start with an oblique perspective view, switch to orthographic, orbit, then switch back. Invoke Front separately. | Each projection switch preserves the active viewing angle at that point. Only the Front command points the camera frontward. Asset and transform hashes remain unchanged. |
| VP-A03 | Select a surface, switch stages, then replace source topology. | Compatible identity survives stage change. The stale surface selection cannot target the new revision. |
| VP-A04 | Hide a material component and toggle wireframe. | Display changes only; assembly membership, artifact hashes, and geometry statistics remain unchanged. |
| VP-A05 | Resolve one known defect and add a paint overlay. | The defect remains identifiable by red highlight and list entry; paint and selection use distinct visual treatments. |
| VP-A06 | Edit a pivot on a rotated child component, then cancel a second edit. | Intended parent-relative coordinates persist once; canceled interaction and unrelated component transforms remain unchanged. |
| VP-A07 | Force resource pressure on the dense fixture, orbit in Split View and stop navigation. | The reduced detail indicator appears during navigation and full detail returns after it stops. The saved mesh, metrics, and exported bytes are unchanged. |
| VP-A08 | Attempt deviation comparison for incompatible transforms and no declared alignment. | The viewport reports incompatibility; it does not display an apparently valid map. |
| VP-A09 | Set a custom frame and split, save a paint layer, then open a new session. | Session framing, mode, and split reset. The editable paint layer and all approved assets persist. |
| VP-A10 | Select with a hidden back face, then opt into through-selection. | Default excludes hidden surfaces. Opt-in previews affected hidden areas; cancel preserves selection and only confirmation applies the preview. |

## 16.6 MVP acceptance

A user can inspect, select, measure, compare, and explicitly transform assets and components from the same viewport across supported stages. Inspection cues distinguish display state from production edits. Validate representative props and modular characters, including a dense fixture, intentional overlaps, and affected/canceled transforms. Projection switches, session reset, through-selection preview and pressure-driven detail restoration must also pass on the qualified desktop clients and fixtures. Exact tuning and interaction budgets are qualified under Phase 25.

## 16.7 Approved decisions and boundaries

- **Q16-01:** Preserve the current viewing angle when switching projection. Front is a separate action.
- **Q16-02:** Reset framing, display mode and split layout when a new session starts. Durable edits are unaffected.
- **Q16-03:** Visible-surface selection by default, with explicit through-selection and a preview of affected hidden surfaces.
- **Q16-04:** Automatically simplify display during navigation under pressure, indicate the change, and restore full detail afterward. Production files, metrics and exports stay intact.
