# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 05: Reference Image and Multi-View Generation**  
**Version:** 1.0  
**Status:** Finalized for MVP; implementation details deferred  
**Application location:** SWIFT Director > Asset Generation > 3D Generation  
**Preceding documents:** `3d_Phase_1.md`, `3d_Phase_2.md`, `3d_Phase_3.md`, `3d_Phase_4.md`  
**Companion specification and development prerequisite:** `Reference_Generation_Design.md`, Version 1.0

## 5.1 Purpose and scope

This phase establishes how 3D Generation acquires, organizes, validates, and consumes visual reference imagery for local geometry reconstruction. The objective is to reduce unsupported inference about unseen surfaces and preserve asset identity, proportions, component placement, pose, and intended asymmetry across reconstruction inputs.

The studio shall support single-view and multi-view reconstruction inputs, with multi-view preferred wherever useful and supported. Reference completeness shall depend on the asset classification and intended structure rather than a universal six-view requirement.

3D Generation shall not duplicate image generation, reference sheet generation, sheet assembly, or sheet extraction functionality. Those operations belong to the existing Image Generation workspace and the separately specified Reference Generation workspace. This phase defines their integration and downstream geometry input contracts, not their internal interfaces. All operations remain local-only for MVP. No specific AI models or implementation libraries are selected.

## 5.2 Workspace responsibilities and navigation

```text
SWIFT Director
└── Asset Generation
    ├── Image Generation
    │   └── Individual concepts and visual refinements
    ├── Reference Generation (replaces Character Generation)
    │   ├── Sheet Generation
    │   │   ├── Simple
    │   │   └── Advanced
    │   └── Sheet Extraction (separately initiated)
    └── 3D Generation
        └── Reference import, selection, assignment, validation,
            provider preparation and geometry submission
```

| ID | Requirement |
|---|---|
| NAV-001 | 3D Generation shall import and select existing images and reference artifacts without embedding image synthesis controls. |
| NAV-002 | Requests to create individual concept imagery shall navigate to Image Generation. |
| NAV-003 | Requests to create coordinated reference sheets, regenerate reference rows or views, or extract sheets shall navigate to Reference Generation as applicable. |
| NAV-004 | Navigation shall preserve the originating asset ID, classification, subtype, intended reference role, direction or feature, configuration state, and component association where available. |
| NAV-005 | Users shall be able to assign selected generated or extracted artifacts to an existing or newly defined 3D asset. |
| NAV-006 | Returning to 3D Generation shall preserve existing asset progress and selected references unless the user explicitly changes them. |
| NAV-007 | Transfer shall use identifiable artifact references without unnecessary physical file duplication. |
| NAV-008 | Navigation, selection, transfer and assignment shall not implicitly approve pending artifacts or reset their retention deadline. |
| NAV-009 | Generation, assembly, transfer and import of a complete sheet shall not silently initiate sheet extraction. |
| NAV-010 | All inference, processing and storage shall occur locally; no cloud fallback shall be required. |

## 5.3 Reference roles and identity

| Role | Purpose |
|---|---|
| Primary | Visual identity anchor for the asset. |
| Directional | Subject or interior from an assigned viewing direction. |
| Detail | Close-up of a feature or surface. |
| Component | Isolated breakaway component or independently generated part. |
| Material | Surface appearance for subsequent material or texture workflows. |
| Style | Artistic presentation guidance. |
| Scale | Relative or explicitly specified physical dimensions. |
| Layout | Spatial arrangement, such as an interior floor plan. |
| Configuration variant | Alternate pose, expression, clothing state or mechanical configuration. |

An image may serve multiple roles. A primary reference need not be a front view; a three-quarter image may be preferable. A primary reference is optional when sufficient compatible directional references exist. Historical reference inputs do not automatically become required retention dependencies.

| ID | Requirement |
|---|---|
| REF-001 | Import PNG, JPEG and WebP reference imagery subject to provider compatibility. |
| REF-002 | Each reference shall identify its image artifact and applicable roles. |
| REF-003 | Users shall be able to assign, replace and remove reference associations independently. |
| REF-004 | An asset may designate one primary reference; replacing it shall not overwrite other references. |
| REF-005 | Changed reference assignments shall invalidate affected validation results and identify references requiring review. |
| REF-006 | References shall support asset-level and component-level assignments. |
| REF-007 | Users shall be able to select exactly which available references are submitted. |
| REF-008 | Reference images shall remain reusable across compatible assets without conflating their logical approval states. |
| REF-009 | Selection and locking shall remain distinct from permanent approval. |

## 5.4 Classification-specific reference profiles

The four parent classifications and eight asset types defined in Phase 03 remain authoritative. Classification is mandatory before geometry generation; subtype is optional, including Custom. The following defaults align with Section 3 of `Reference_Generation_Design.md`. They are recommendations, not mandatory image counts.

| Parent | Asset type | Recommended Base references | Detail and supplemental references |
|---|---|---|---|
| Actors | Humanoid | Front, right, rear, left in consistent A-pose or T-pose; optional clean base anatomy | Head front, sides and rear; hands, feet, eyes, teeth and tongue, head hair, facial hair, clothing, footwear, armor, accessories |
| Actors | Creature | Complete creature in a consistent anatomy-appropriate neutral pose; directions as applicable | Head, paws, claws, teeth, tail, wings, horns, fur, scales, equipment; expressions and poses kept distinct |
| Scene Assets | Scene Prop | Complete isolated object; directions appropriate to its structure | Materials, structural features, cavities, removable components |
| Scene Assets | Vehicle | Exterior front, right, rear, left, top and bottom as applicable | Hull, engines, glass, landing gear, wheels, tracks, doors, accessories |
| Props | Held Prop | Complete isolated object; relevant directional views | Grip surfaces, functional details, materials, removable components |
| Props | Interactive Prop | Complete object with explicitly distinguished configuration states | Moving parts, cavities, hinges, handles and attachment surfaces |
| World Assets | Vehicle Interior | Forward, rearward, left, right, ceiling and floor as applicable; optional layout | Fixtures, controls, furniture, doors and structural surfaces |
| World Assets | Scenery | Exterior or interior references according to the selected structural profile | Roof, walls, vegetation, foundations, architectural components and materials |

| ID | Requirement |
|---|---|
| RPF-001 | Reference completeness shall depend on asset type, subtype, component and structural characteristics. |
| RPF-002 | Single-view generation shall remain available where supported. |
| RPF-003 | A complete humanoid reference set need not contain top or bottom views. Top and bottom shall be recommended only when useful. |
| RPF-004 | Users may include or exclude views and supply supplemental imagery. |
| RPF-005 | Recommended completeness shall be distinguished from mandatory provider inputs. |
| RPF-006 | Exterior and interior generation shall remain separate for MVP. Vehicle is exterior-only; Vehicle Interior is interior-only; Scenery uses one structural profile at a time. |
| RPF-007 | Actor references shall preserve consistent anatomy and neutral pose across corresponding views. |
| RPF-008 | Interactive states, alternate clothing, poses and expressions shall be identified separately from directional views of a single configuration. |
| RPF-009 | Interior references may use perspective images from inside the space and supplemental floor plans; external orthographic views are not a substitute for interior spatial information. |

## 5.5 Direction and projection conventions

The standard directional slots are Front, Left, Right, Rear, Top and Bottom. Supplemental three-quarter, custom and non-directional feature references may also be used where supported. A row need not populate all six slots.

Phase 04 defines right-handed coordinates, Y-up, positive Z forward and centimeters as the canonical unit. Front and rear cameras correspond to positive and negative Z; top and bottom correspond to positive and negative Y. Left and right shall use an explicitly documented viewing convention. Coordinate-axis right (+X) must not be confused with an actor's anatomical right or the right side of an image. Provider adapters shall translate directional labels and camera conventions without silently mirroring asymmetric geometry. Interior-facing directions shall describe the direction the camera looks within the space, not the position of an exterior camera.

| Projection | Intended use |
|---|---|
| Orthographic | Preferred for exterior directional references. |
| Perspective | Interior references, spatial context and supplemental depth information. |
| Three-quarter | Primary identity and supplemental structural information. |

| ID | Requirement |
|---|---|
| DIR-001 | Maintain identifiable directions, roles and projection metadata. |
| DIR-002 | Support standard directions and supplemental views without imposing all six universally. |
| DIR-003 | Identify whether camera pose or calibration is supplied, estimated or unknown. |
| DIR-004 | Do not represent orthographic-looking generated images as verified calibrated projections without evidence. |
| DIR-005 | Preserve intentional asymmetry and avoid automatic mirroring of directional inputs. |
| DIR-006 | Distinguish exterior camera positions from interior viewing directions and configuration states. |

## 5.6 Reference Generation integration contract

The companion specification is authoritative for creation, extraction, controls and export of reference sheets. 3D Generation shall consume its outputs through shared artifact identities and the Phase 04 asset manifest architecture.

| Capability | Companion workflow and downstream behavior |
|---|---|
| Simple | Up to four source images; 1 to 10 complete coordinated sheet candidates. Complete sheet imagery is not automatically treated as extracted views. |
| Advanced | Independently manageable Base and Detail rows; up to six source inputs and six directional output slots per row, which are separate collections. |
| Row and view controls | Independent uploads, generation, regeneration, candidate selection, enabled state and locks. Locked selections are protected from replacement. |
| Row inheritance | References may come from other rows or existing assets. Changing the source does not automatically regenerate dependent rows. |
| Row classification | Optional classification/subtype override with a separate component role and association. |
| Layout | Base above Detail by default; variable row widths, image sizes and aspect ratios; deterministic Advanced assembly. |
| Specification panels | Optional Base panel and one per Detail row, with Label, Sub Label, custom fields and independent inclusion control. |
| Extraction | Explicitly initiated, automatic region detection with manual correction or manual cropping; supports nonuniform layouts. |
| Export | Sheet Only, Individual Views, Complete Reference Package, Component Reference Sheets. These are Reference Generation export profiles, not additional 3D geometry export modes. |

### Transfer and assignment requirements

| ID | Requirement |
|---|---|
| RGI-001 | 3D Generation shall accept selected individual reference artifacts and their semantic assignments. |
| RGI-002 | A complete sheet or complete row image may remain an identity or component reference; it shall not be misrepresented as separate directional files. |
| RGI-003 | If a provider requires separate views, users shall explicitly initiate extraction in Reference Generation or supply existing individual images. |
| RGI-004 | Missing views shall be generated explicitly through the appropriate workspace, never inferred by ordinary cropping. |
| RGI-005 | Transfer shall preserve row classification, component role, assigned direction, configuration state, native/output dimensions and relevant specification metadata. |
| RGI-006 | Locked selections shall remain protected in Reference Generation; locks do not grant permanent retention. |
| RGI-007 | A component sheet may be transferred as a component reference or its available individual views may be assigned independently. |
| RGI-008 | Disabled or unselected views shall not be silently included in the geometry input set. |
| RGI-009 | Generation counts, sheet assembly controls, row prompts and extraction controls shall remain in Reference Generation, not be duplicated in 3D Generation. |
| RGI-010 | Simple-to-Advanced conversion shall not trigger extraction or alter original imagery. |

## 5.7 Modular reference management

All eight asset types and three approved generation modes (Unified, Automatic Modular, Directed Modular) shall use the common reference architecture. A complete asset reference establishes identity and assembly relationships, while isolated component references clarify individual geometry. Unified mode does not require separate components; Automatic Modular may recommend components; Directed Modular permits explicit component assignments.

For humanoids, clean base anatomy and clothed references should represent the same underlying proportions and neutral pose. Clothing, head hair, facial hair, eyes, teeth and tongue, footwear and accessories may be represented independently. For vehicles, separate hull, engines, glass and landing gear references may guide modular construction. For interactive props, open and closed images shall be treated as different configurations rather than equivalent static views.

| ID | Requirement |
|---|---|
| MRF-001 | Components shall support independent reference sets. |
| MRF-002 | Complete asset references may be used as identity anchors for component preparation. |
| MRF-003 | Users shall be able to override component reference assignments without altering unrelated components. |
| MRF-004 | Preserve component ownership, intended scale, relative placement and configuration metadata. |
| MRF-005 | Row classification overrides shall be preserved when transferring separately classified attached assets. |
| MRF-006 | Missing or expired inherited references shall be clearly identified. |
| MRF-007 | Changing a source reference shall not automatically regenerate geometry or unrelated reference rows. |

## 5.8 Resolution and presentation

Reference resolution shall remain independent of final texture resolution. The approved target profiles are 512, 1024, 2048 and 4096; non-square aspect ratios are supported where appropriate. The 1024 general default is a configurable starting point, not a required native resolution. Sheet, row, individual view and extracted image resolutions are distinct.

| ID | Requirement |
|---|---|
| RPS-001 | Record actual pixel width and height, native dimensions and any resulting resized or upscaled dimensions. |
| RPS-002 | Validate image resolution, aspect ratio, format and transparency against provider capabilities. |
| RPS-003 | Prioritize complete visible silhouettes, controlled lighting and isolated subjects for geometry inputs. |
| RPS-004 | Preserve intentional detail crops and non-square source proportions. |
| RPS-005 | Support transparent or neutral backgrounds as appropriate. |
| RPS-006 | Avoid unrelated objects, annotations and presentation effects that obscure geometry in individual reconstruction references. |
| RPS-007 | Distinguish upscaled imagery from native visual detail; upscaling shall not be represented as new verified source detail. |

A 2048 by 2048 sheet with four equal cells yields at most 1024 by 1024 native pixels per cell before margins. Actual reference sheets may use unequal cells, so individual dimensions must be measured rather than inferred from the sheet size.

## 5.9 Reference preparation and preprocessing

3D Generation may perform local, provider-specific input preparation through adapters without duplicating the Reference Generation extraction workspace. Ordinary preparation shall not overwrite original images or invent visual information. User-directed visual refinement and missing-view synthesis belong to the appropriate image workspace.

| Operation | Purpose |
|---|---|
| Format conversion | Meet supported image format requirements. |
| Resizing and padding | Meet input dimensions without stretching the subject. |
| Orientation correction | Normalize image orientation without unintended mirroring. |
| Subject centering and cropping | Prepare existing individual images without cutting required geometry. |
| Alpha handling | Preserve or replace transparency according to provider requirements. |
| Optional segmentation or background removal | Isolate intended geometry when required and supported locally. |

| ID | Requirement |
|---|---|
| RPP-001 | Preserve original reference artifacts and create separate derivatives when needed. |
| RPP-002 | Preserve subject proportions and intended visible geometry. |
| RPP-003 | Disclose significant preprocessing changes and allow review. |
| RPP-004 | Record applicable processing parameters while associated artifacts remain retained. |
| RPP-005 | Validate prepared input before inference. |
| RPP-006 | Delete temporary preprocessing derivatives when no longer needed, subject to active-job and valid dependency protection. |
| RPP-007 | Do not silently crop a composite sheet into directional references; sheet extraction remains explicitly initiated in Reference Generation. |

## 5.10 Visual consistency validation

Visual validation shall flag discrepancies clearly without blocking a technically compatible generation request. This applies even to significant inconsistencies and uncertain assessments. Technical compatibility is separate and may prevent execution when a provider cannot consume the requested inputs.

| Validation category | Objective |
|---|---|
| Identity and silhouette | Same intended asset and defining features. |
| Structural proportions | Consistent relative dimensions and visible geometry. |
| Component count and placement | No unintended additions, omissions or displacement. |
| Anatomy and pose | Consistent limb counts, attachment locations and neutral pose. |
| Material and color | Compatible surface appearance and intended distribution. |
| Orientation and asymmetry | Correct direction and preservation of asymmetric features. |
| Isolation and projection | Appropriate subject boundaries and projection for the intended use. |
| Configuration state | Corresponding references depict compatible configurations. |
| Interior layout | Consistent visible spatial arrangement across interior perspectives. |

| Outcome | Behavior |
|---|---|
| Passed | Report findings; do not claim verified 3D accuracy solely from visual agreement. |
| Warning or significant inconsistency | Prominently identify affected images and discrepancy; allow generation. |
| Unable to validate | Report uncertainty and allow manual review and generation. |
| Technical incompatibility | Explain the unsupported format, missing mandatory input or other actual execution constraint; prevent incompatible execution until resolved. |

| ID | Requirement |
|---|---|
| RVL-001 | Support local visual consistency evaluation and user review. |
| RVL-002 | Report affected references, discrepancy category, description and uncertainty where applicable. |
| RVL-003 | Never automatically block generation solely because of visual inconsistency or inability to validate. |
| RVL-004 | Invalidate affected results when selected images or their relevant assignments change. |
| RVL-005 | Validation shall not approve, alter or permanently retain reference artifacts. |
| RVL-006 | Technical input compatibility shall be evaluated independently of visual findings. |
| RVL-007 | Quantitative visual consistency thresholds shall be determined in Phase 25. |

## 5.11 Geometry provider compatibility and submission

The available reference set shall remain independent of the subset a geometry provider can consume. True multi-view geometry generation requires the geometry pipeline to consume multiple compatible reference views; generating multiple images upstream does not by itself make a single-image reconstruction provider multi-view capable.

| ID | Requirement |
|---|---|
| RPC-001 | Providers shall declare minimum and maximum reference counts, supported directions or camera configurations, formats, resolutions, aspect ratios and projection requirements. |
| RPC-002 | Providers requiring calibration or ordered views shall declare those requirements. |
| RPC-003 | Automatic selection shall prioritize compatible multi-view reconstruction when sufficient relevant references exist. |
| RPC-004 | Advanced manual provider override shall remain available subject to compatibility validation. |
| RPC-005 | Show which selected inputs the provider will consume and which cannot be consumed. |
| RPC-006 | Obtain explicit user confirmation before proceeding with a reduced reference set. |
| RPC-007 | Do not silently discard references or represent unsupported directions as consumed. |
| RPC-008 | Reject only actual execution incompatibilities, not visual consistency warnings. |
| RPC-009 | Submit selected reference artifact IDs, applicable classification, component and configuration assignments, supported camera metadata and generation settings through the standardized provider adapter. |
| RPC-010 | Preserve the selected reference input set for the active job and prevent cleanup from invalidating its execution in accordance with Phase 04 safeguards. |
| RPC-011 | Sequential processing shall not require simultaneous residency of unrelated image and geometry models. |

## 5.12 Reference data and manifest integration

Reference metadata extends the JSON-based `AssetManifest.json` and shared artifact structure defined in Phase 04. Reference Generation project and row metadata remain owned by that workspace; 3D Generation references the applicable selected artifacts and semantic assignments rather than duplicating projects or binary images.

The following is an illustrative logical record, not a finalized serialization contract:

```json
{
  "referenceId": "reference-unique-id",
  "artifactId": "artifact-unique-id",
  "assetId": "asset-unique-id",
  "componentId": null,
  "sourceReferenceProjectId": "reference-project-id",
  "sourceRowId": "row-id",
  "roles": ["Primary", "Directional"],
  "direction": "Front",
  "projection": "Orthographic",
  "configurationState": "Default",
  "camera": {
    "position": null,
    "orientation": null,
    "focalLength": null,
    "orthographicScale": null,
    "calibrationStatus": "Unknown"
  },
  "image": {
    "format": "PNG",
    "nativeWidth": 1024,
    "nativeHeight": 1024,
    "width": 1024,
    "height": 1024,
    "upscaled": false,
    "hasAlpha": true
  },
  "selection": { "included": true },
  "validation": { "status": "Pending", "findings": [] }
}
```

| ID | Requirement |
|---|---|
| RDT-001 | Maintain unique reference and artifact identities and the associated asset and optional component. |
| RDT-002 | Preserve reference roles, source project/row associations where available, direction, projection and configuration state. |
| RDT-003 | Support optional camera metadata without presenting unknown values as measured facts. |
| RDT-004 | Record actual and native image dimensions and upscaling status. |
| RDT-005 | Keep input selection, visual validation and artifact approval independent. |
| RDT-006 | Resolve physical files through shared storage and portable export references. |
| RDT-007 | Distinguish required dependencies from historical generation inputs. |
| RDT-008 | Remove exclusive reference records and generation metadata when their associated artifacts are denied or expire, in accordance with Phase 04. |
| RDT-009 | Do not retain a permanent history of expired or rejected reference generations. |

## 5.13 Retention, approval and export

Phase 02 and Phase 04 govern all reference artifacts. New generated artifacts enter pending status; unapproved results expire ten days after successful generation. Denial or expiration deletes exclusive files, prompts, parameters, previews, metadata and history. Shared files remain only while required by another valid artifact. Temporary processing data shall be cleaned up when no longer needed.

Selecting, locking, transferring, validating or exporting an image shall not automatically approve it or extend its retention. When an asset requires pending dependencies to remain functional, the approval modal shall identify each required dependency and explain why it is needed, and ask the user to approve the item and dependencies together or cancel. Historical source images shall not be automatically retained solely because they were used in generation.

3D Generation shall retain its unified ZIP export architecture with canonical FBX geometry. Applicable available reference artifacts and portable metadata may accompany that export as defined by the asset package; separate reference export options belong to Reference Generation. Pending artifact export requires a modal explaining unapproved status, remaining retention, automatic local deletion and asking whether to continue. Export does not alter retention or affect an already downloaded copy.

## 5.14 Model constraints

The companion specification, Sections 13 and 14, establishes detailed constraints and assertions for reference sheet generation, independent row/view synthesis and extraction providers. Those requirements are not duplicated as 3D Generation features. The following constraints apply to the local providers and adapters participating in the reference-to-geometry handoff. A combination of providers may satisfy a capability through sequential execution.

| ID | Constraint |
|---|---|
| RMC-001 | Support local-only programmatic execution and independently accessible outputs. |
| RMC-002 | Declare supported asset classifications and image input capabilities. |
| RMC-003 | Declare supported reference counts, directions, image dimensions, aspect ratios, formats and any camera metadata requirements. |
| RMC-004 | For multi-view reconstruction, actually consume multiple compatible references, directly or through a documented local pipeline. |
| RMC-005 | Support intended identity, structural proportions, component placement, pose and asymmetry according to declared capabilities. |
| RMC-006 | Accept relevant component references or support subsequent component reconstruction stages where declared. |
| RMC-007 | Support interior perspective inputs where interior reconstruction capability is declared. |
| RMC-008 | Support independent execution and resource reclamation between stages. |
| RMC-009 | Do not require permanent retention of unnecessary native intermediate files. |
| RMC-010 | Produce independently verifiable geometry outputs convertible to canonical FBX under Phase 04 requirements. |
| RMC-011 | Do not modify approved input artifacts during inference or conversion. |
| RMC-012 | Operate within configured local hardware resource limits. |

If AI-assisted validation is used, its provider must additionally satisfy the following:

| ID | Constraint |
|---|---|
| VMC-001 | Compare multiple reference images locally. |
| VMC-002 | Identify relevant structural, anatomical, component, orientation and configuration discrepancies. |
| VMC-003 | Return structured findings identifying affected images and uncertainty. |
| VMC-004 | Preserve input imagery unchanged and execute independently from generation providers. |

## 5.15 Validation assertions

The following assertions define expected behavior, not evidence that a candidate provider has already passed. Reference Generation's own 36 assertions remain in the companion specification.

| ID | Test | Expected result |
|---|---|---|
| RMA-001 | Navigate from an existing 3D asset to Image Generation. | Asset and intended reference context are preserved. |
| RMA-002 | Navigate to Reference Generation for a coordinated sheet or extraction. | Correct workspace opens without duplicated synthesis or extraction functionality. |
| RMA-003 | Transfer selected individual Advanced views. | Reference IDs, direction, classification and component assignments remain intact. |
| RMA-004 | Transfer a Simple sheet without extraction. | Sheet remains a composite reference; no individual views are silently created. |
| RMA-005 | Transfer a complete uploaded row. | Row remains intact; extraction requires an explicit action. |
| RMA-006 | Transfer a component row with classification override and specification metadata. | Applicable semantic information is preserved. |
| RMA-007 | Select a complete humanoid profile without bottom imagery. | No universal six-view requirement is imposed. |
| RMA-008 | Select a vehicle profile with applicable underside imagery. | Relevant bottom reference can be included. |
| RMA-009 | Assign open and closed interactive prop references. | Distinct configuration states are maintained. |
| RMA-010 | Prepare interior perspective references. | Input metadata distinguishes interior-facing views from exterior cameras. |
| RMA-011 | Submit a single image to a compatible provider. | Single-view generation remains available. |
| RMA-012 | Submit multiple supported views. | Declared multi-view provider consumes the selected compatible inputs. |
| RMA-013 | Select more views than the provider accepts. | Unused references are disclosed and reduced-input confirmation is required. |
| RMA-014 | Override provider selection with incompatible inputs. | Actual incompatibility is explained before execution. |
| RMA-015 | Validate mismatched proportions or component counts. | Findings are clearly flagged; compatible generation remains available. |
| RMA-016 | Validate ambiguous imagery. | Uncertainty is reported without blocking compatible execution. |
| RMA-017 | Change a selected reference after validation. | Affected results are invalidated. |
| RMA-018 | Prepare a non-square image for a provider. | Source proportions are preserved and original artifact remains unchanged. |
| RMA-019 | Process an asymmetric subject. | No unintended mirroring occurs; direction conventions are respected. |
| RMA-020 | Compare extracted native and upscaled images. | Actual dimensions and upscaling status remain distinguishable. |
| RMA-021 | Assign an image already stored by another workspace. | No unnecessary physical duplication or automatic approval occurs. |
| RMA-022 | Deny or expire an unapproved reference. | Exclusive files and metadata are deleted, valid shared dependencies protected, unavailable selections identified. |
| RMA-023 | Approve an asset requiring pending reference dependencies. | Dependency modal explains required items and asks for explicit approval. |
| RMA-024 | Export a package containing pending artifacts. | Warning appears; continuing does not approve or extend retention. |
| RMA-025 | Execute reference preparation and geometry submission offline. | All supported operations complete locally. |
| RMA-026 | Execute sequential reference and geometry jobs. | Concurrent model residency is not required. |
| RMA-027 | Convert a reconstructed output to canonical FBX. | Required geometry information is preserved under Phase 04 validation requirements. |

## 5.16 Application responsibilities

| Responsibility | Owner |
|---|---|
| Individual concept image synthesis and refinement | Image Generation |
| Simple/Advanced sheets, row/view synthesis, locking, specification panels and assembly | Reference Generation |
| Explicit sheet extraction and component reference exports | Reference Generation |
| Asset-specific reference assignment, selection and geometry input validation | 3D Generation |
| Reference capability matching and input format preparation | Shared provider abstraction and adapters |
| Visual consistency reporting | Local validation pipeline with user review |
| Retention, dependency approval, deduplication and storage cleanup | Shared artifact infrastructure |
| Geometry reconstruction and normalized FBX output | 3D Generation providers and processing adapters |

## 5.17 MVP acceptance criteria and development dependency

Phase 05 is accepted when users can import or transfer reference artifacts for all eight asset types; use classification-appropriate reference profiles rather than mandatory universal views; preserve component, direction and configuration assignments; receive clear nonblocking visual warnings; select technically compatible single-view or multi-view providers; and submit locally prepared inputs without duplicating generation or extraction workflows. Reference transfer must preserve asset context, retention status, shared storage integrity and nondestructive editing. Downstream geometry shall conform to canonical FBX requirements.

Reference Generation shall be implemented and evaluated against `Reference_Generation_Design.md` before proceeding to Phase 06: 3D Geometry Generation. Approval of this design does not imply that the prerequisite workspace, model integrations or tests have been implemented.

## 5.18 Reconciliation and deferred implementation decisions

This finalized phase replaces the earlier Phase 05 draft's embedded per-view image generation interface with cross-workspace navigation and reference consumption. Universal Basic/Standard/Complete view-count profiles are replaced by classification-specific recommendations. Visual inconsistency no longer blocks compatible execution. The original proposed Reference Studio name is replaced by the approved Reference Generation name. Simple generation retains four source inputs; Advanced supports six source inputs and six directional slots per row. Extraction remains explicitly initiated, never an automatic result of sheet creation, assembly or transfer.

The companion specification owns flexible Base/Detail sheet layout, generation modes, per-view uploads and locks, specification panels, extraction interfaces and its four export profiles. Phase 05 owns downstream reference acquisition, assignment, compatibility, validation and geometry submission. If workspace-specific controls evolve, shared integration contracts must remain compatible with both documents.

Exact navigation payloads, schema field names, custom-view slot representation, left/right adapter conventions, camera calibration methods, visual consistency thresholds, native resolution handling, provider selection algorithms and hardware benchmarks remain implementation details. The illustrative manifest fields and additional reference roles are logical design interpretations, not a commitment to a particular database or serialization implementation. No AI models, conversion libraries or UI frameworks have been selected.
