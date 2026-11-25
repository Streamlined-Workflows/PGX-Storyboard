# Phase 11: Material Extraction and Generation

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 11.1 Purpose and boundaries

Create, extract, edit, assign, and reuse surface materials independently of mesh, UV, and texture generation. A material defines how a surface responds to light. A Phase 10 texture map supplies image data. A texture set ties coordinated maps to a particular surface layout. An assignment binds a material to a stable slot on a component. The same definition may be reused, while a map baked for one UV revision must not be treated as portable to another.

Inherited requirements: local-only processing, independently runnable stages, canonical PNG maps and Positive Y tangent normals, one common resolution per texture set, independent component texture sets, explicit repair, and no new shared atlases, hybrid layouts, or UDIMs in MVP. This phase does not select providers or revise approved format, retention, or texture rules. MVP materials use portable metallic-roughness PBR and UV-based mapping. The Phase 10 image projection workflow remains available for producing textures. Live triplanar material mapping, refraction, clearcoat, and skin scattering are outside MVP.

## 11.2 Inputs and outputs

| Direction | Data | Contract |
|---|---|---|
| Input | Optional target asset, component, material slot, geometry and UV revisions | Required for asset-bound assignment. A standalone material needs no mesh. |
| Input | Image crop, mask, multi-view evidence, text prompt, existing maps, or imported material description | Input needs depend on the selected method. Report unused references and missing channels. |
| Input | Target surface type, UV channel, tiling or scale intent, property locks, lighting policy | Optional where applicable. Mapping uses a compatible UV channel. Normal conventions and channel color spaces cannot silently change. |
| Output | Material definition and optional compatible map or texture-set references | Uses stable IDs and immutable artifact references. A constant-only result may carry no maps. |
| Output | Optional component/slot assignment, compatibility report, and preview settings | Assignment is reviewable separately from the definition. Preview lighting is not a production material property. |
| Output | Optional face-to-slot binding derivative | Preserves the original geometry and references its exact revision and face selection. |

## 11.3 Workflows

1. **Author from constants or maps:** create a material using values, existing textures, or both. Show how mapped values combine with scalar factors and when a channel is unused.
2. **Extract from reference:** choose a swatch or crop, identify excluded pixels or occlusion, inspect proposed base color and surface properties under neutral lighting, then explicitly retain the candidate. Single-image roughness, normal, metallic, or height inferred from appearance are estimates, not physically measured values. Do not interpret shadows or highlights as material detail without flagging uncertainty.
3. **Generate from intent:** select prompt and optional image input, define material use and finish, and request one candidate. Use deterministic derivation where suitable. Optional coordinated maps follow Phase 10, including color spaces, common resolution, and lock preservation.
4. **Import or derive:** map supported imported slots and inputs to a new local material artifact. Preserve original data separately when conversion is incomplete. Variant creation and property edits follow copy-on-edit, with an explicit shared-update alternative.
5. **Assign and inspect:** choose one or more compatible slots, preview on the selected asset and a standard swatch, inspect unmapped features or missing maps, and commit the assignment only by explicit action. Opening the library or previewing a candidate does not assign it. If no suitable slot exists, deliberately select faces and preview a new slot assignment as a nondestructive derivative. Do not cut, split, or modify the original mesh.
6. **Start from a preset:** browse the offline starter set or load a user-saved reusable preset. Selecting a starter or saving a preset does not automatically assign the material or enroll project artifacts in the Phase 17 library.

## 11.4 Functional requirements and controls

| ID | Requirement |
|---|---|
| MAT-001 | Support a portable, documented metallic-roughness material definition with base color, metallic, roughness, optional emissive and normal inputs, and supported Phase 10 map bindings. Support opaque rendering, alpha cutouts, and basic blended transparency. Store normalized units, ranges, and declared defaults. |
| MAT-002 | Support explicit per-component, per-slot bindings, including more than one material on a component. Preserve unaffected slots, and display slot identity and geometry/UV revision before apply. Provide a deliberate face selection action for a new slot with reviewable face membership. |
| MAT-003 | Support swatch crop, source masking, visible evidence inspection, and optional prompt guidance. Record provenance per channel, covering imported, manually authored, derived, and estimated values and maps. |
| MAT-004 | Present 3D and synchronized Split View inspection with neutral lighting, alternate lighting, and individual channel inspection. Feedback about preview fidelity shall not be recorded as a material defect unless validation establishes one. |
| MAT-005 | Offer property locks, variant creation, non-destructive preview, review, and revert of an uncommitted preview. Generation affects requested and unlocked channels only. |
| MAT-006 | Use UV-based material mapping. Separate portable UV-based bindings from source-specific baked textures. Keep Phase 10 texture projection distinct from viewport material mapping. Explicitly flag slot, UV channel, or source revision incompatibilities. No automatic UV repair, map bake, or creation of per-map resolution overrides. |
| MAT-007 | On shared material or shared texture edits, list all affected assets. Default to Create Independent Material or equivalent independent edit, and apply a shared change only after explicit confirmation. |
| MAT-008 | Create a single material candidate per generation request and lock repeat or conflicting submissions in the active material workflow. The server may hold separately eligible requests under Phase 21. Review acceptance does not automatically approve pending dependencies. At approval, explain dependency reasons and obtain confirmation before retaining them together. |
| MAT-009 | Validate required fields, channel metadata, supported shader features, missing maps, and texture binding compatibility. Show confirmed defects in red and offer explicitly initiated Safe or Advanced repair where applicable. Preserve compatible originals. |
| MAT-010 | Keep material and assignment data separate from the canonical FBX. The asset manifest pins the applicable artifacts. Export identifies features an external target cannot preserve, instead of silently dropping them. |
| MAT-011 | Bundle a small rights-cleared starter material set that works offline and support user-saved presets. Respect pinned material revisions and explicit library inclusion and updates under Phase 17. |
| MAT-012 | Validate the source geometry revision and face identifiers before accepting a new slot binding. Preserve topology, vertex ordering, and source geometry checksum. If export must materialize a binding in FBX, write a separate output and revalidate that topology remains unchanged. |

User controls include source and crop, production method, properties and locks, texture bindings, tiling/scale when supported, preview lighting and object, component, slot or explicit face target, offline starter and user preset controls, candidate inspection, independent or shared edit, and approval.

## 11.5 Provider constraints and application responsibilities

| ID | Provider constraint | SWIFT responsibility |
|---|---|---|
| MPC-001 | Declare inputs consumed, channel types returned, supported material models, native texture dimensions, and whether properties are inferred. | Resolve valid sources, adapt outputs to canonical textures without hiding unsupported data, and validate reported capabilities. |
| MPC-002 | Emit a separate local candidate without overwriting the source image, asset, material, or maps. | Own IDs, slot mapping, locks, dependency closure, retention, and atomic assignment. |
| MPC-003 | Return available map metadata and explicit partial failures. | Verify channel semantics, dimensions, normals, and referenced artifacts independently. Fail closed where a required input is missing. |
| MPC-004 | Disclose any repeatability and lighting-neutralization limits. | Expose provenance and comparison controls, and pin versions for any evaluated claim. Use controlled fixtures rather than assuming that a plausible swatch proves physical accuracy. |

## 11.6 Validation assertions and acceptance

| ID | Test | Pass condition |
|---|---|---|
| MVA-001 | Assign constant-only material | A compatible slot renders without generating placeholder maps. Other slots and FBX checksums are unchanged. |
| MVA-002 | Extract a crop with asymmetric detail and visible glare | Evidence is retained, unsupported or estimated fields are labeled, and source image and crop selection remain traceable while retained. |
| MVA-003 | Bind UV-dependent maps from a mismatched revision | The assignment is blocked or marked unresolved before apply. No bake, destructive rewrite, or silent remap occurs. |
| MVA-004 | Change one material used by three assets | The impact modal lists all three. Default independent edit changes one binding. Confirmed shared update changes only the listed usage. |
| MVA-005 | Apply a mismatched texture set or attempt modification of a locked map | Incompatibility is visible and only requested, unlocked canonical maps may change after explicit action. Source file hashes match. |
| MVA-006 | Turn a preview capability off in an export target | The preflight identifies the exact unsupported property and adaptation outcome. A required unsupported property prevents a successful export claim. |
| MVA-007 | Cancel or fail a coordinated map candidate | No material is assigned, no source changes, and any validated partial artifacts appear for review under normal lifecycle rules. |
| MVA-008 | Create a slot from selected faces on a fixture with two existing slots | Only the selected faces use the new slot in the derivative. Original FBX checksum, vertex order, and unselected slot memberships match the baseline. |
| MVA-009 | Open the starter set offline and save a user preset | Both are accessible without external calls. Preview does not mutate a project assignment or automatically enroll project assets. |
| MVA-010 | Render solid, cutout, and blended fixtures and attempt an unsupported shader mode | Each supported alpha mode renders as intended. Advanced effects or live triplanar mapping are not silently accepted, and Phase 10 image-projected maps still assign through UVs. |

Phase 11 passes when an operator can create a portable material without a mesh, review a local extracted or generated candidate, bind a compatible revision or create a nondestructive face-level slot, and verify cross-project reuse and shared-edit isolation. Offline starter materials and user-saved presets must both be usable. Provider quality limits and target export exceptions must be documented rather than concealed.

## 11.7 MVP boundary and decision trace

**Decisions applied:** Q11-01 portable PBR and basic alpha, Q11-02 UV-based material mapping, Q11-03 nondestructive face-level slot creation, Q11-04 offline starter materials and user presets.
