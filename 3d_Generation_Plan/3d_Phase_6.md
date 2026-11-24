# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 06: 3D Geometry Generation**  
**Version:** 1.0  
**Status:** Finalized for MVP; implementation details deferred  
**Application location:** SWIFT Director > Asset Generation > 3D Generation  
**Preceding specifications:** `3d_Phase_1.md` through `3d_Phase_5.md`  
**Companion specification:** `Reference_Generation_Design.md`

## 6.1 Purpose and scope

The Geometry Generation stage shall convert existing visual references into actual three-dimensional mesh geometry suitable for inspection, optimization, modular construction, UV mapping, texture development, character preparation and export. Structural accuracy, reference consistency and user control take precedence over producing a finished textured asset in a single operation.

Geometry shall be independently usable without texture generation. All inference, conversion, validation and processing shall operate locally after provisioning. The architecture shall remain model agnostic. No particular model, conversion library or repair algorithm is selected by this phase.

Reference Generation implementation remains a development prerequisite. This document establishes design requirements and does not assert that the prerequisite or geometry pipeline has been implemented.

### Approved decision register

| Decision | Final disposition |
|---|---|
| D1 | User explicitly chooses Direct Generation or Master Mesh Generation. Automatic compatible provider selection remains available. |
| D2 | Geometric vertices govern the user-defined complexity budget. Polygons, triangles, edges and rendering vertices are measured independently. |
| D3 | Complexity is a target, not an exact count or mandatory percentage tolerance. |
| D4 | One candidate per request. Additional geometry requests are locked out during active generation. |
| D5 | Automatic repair disabled. Detected defects highlighted red during review. Explicit Safe Repair and Advanced Repair controls. |
| D6 | Geometry Only or Geometry with Texture. Application-managed preview color palette, no AI preview color generation. |
| D7 | Automatic and manual component budget allocation. |
| D8 | Full asset regeneration, independent component regeneration and existing-mesh refinement where compatible providers exist. Regional sculpting and geometry inpainting deferred. |

### Supersession of earlier requirements

This phase supersedes polygon-based complexity targets and profile ranges in Phases 01 through 05 wherever they occur. The same numerical boundaries now refer to geometric vertices, not polygon faces or triangles. Earlier documents remain otherwise unchanged. This is a change of measurement, not a mathematically equivalent conversion of the previous budgets. The general multi-job queue architecture in Phase 02 remains applicable to other operations, subject to the geometry-specific admission restriction in Section 6.10.

## 6.2 Geometry generation lifecycle

```text
Asset definition and classification
  -> Existing reference selection and compatibility checks
  -> Geometry configuration and user-selected strategy
  -> Compatible local provider selection
  -> Single admitted geometry generation request
  -> Native geometry output
  -> Canonical FBX normalization
  -> Non-destructive validation (no automatic repairs)
  -> Candidate review and optional explicit repair
  -> Selection, approval, denial or further processing
  -> Optimization, modular processing, UVs, textures or export
```

A Master Mesh request includes the necessary optimization steps to approach the requested final complexity. A Geometry with Texture request includes compatible texture production as part of its workflow. Such internal stages do not constitute additional user-submitted candidates. Stages shall persist necessary intermediates and permit independently executable downstream operations. A failure shall not overwrite previously retained assets.

## 6.3 Geometry inputs and reference integration

| Input | Requirement |
|---|---|
| Asset classification | Required, using Phase 03 classifications |
| Subtype | Optional |
| Structural profile | Required where applicable |
| Generation mode | Unified, Automatic Modular or Directed Modular |
| Visual references | At least one compatible image for image-to-geometry generation |
| Geometry strategy | Explicit Direct or Master Mesh selection |
| Geometry quality profile | Low, Mid or High Density |
| Target geometric vertices | Required or derived from selected preset |
| Topology preference | Triangles, Quads or Preserve Source |
| Output mode | Geometry Only or Geometry with Texture |
| Dimensions, symmetry and instructions | Optional |
| Existing geometry | Required for an existing-mesh refinement operation |
| Component definitions | Required for Directed Modular generation |
| Provider override | Optional, subject to compatibility checks |

Reference acquisition shall follow Phase 05. 3D Generation shall not duplicate image synthesis, sheet generation, assembly or extraction. Requests to create concept images shall navigate to Image Generation. Requests to create or extract reference sheets or regenerate reference views shall navigate to Reference Generation with the asset context preserved.

| ID | Requirement |
|---|---|
| GGI-001 | Support single-image reconstruction and compatible multi-view reconstruction. |
| GGI-002 | Prefer useful multi-view inputs when compatible providers exist. |
| GGI-003 | Support classification-specific reference profiles, component references and supplemental detail references. |
| GGI-004 | Preserve selected reference IDs, directions, configuration states, roles and component assignments. |
| GGI-005 | Disclose the exact inputs a provider will consume and obtain explicit confirmation when reducing a selected reference set. |
| GGI-006 | Clearly flag visual inconsistencies without automatically blocking technically compatible requests. |
| GGI-007 | Block invalid or technically incompatible inputs before execution. |
| GGI-008 | Do not describe single-input providers as multi-view providers. |
| GGI-009 | Reference use shall not approve source artifacts or reset their retention deadlines. |
| GGI-010 | Existing geometry and reference inputs shall remain unmodified by generation. |

## 6.4 Vertex-based geometry quality profiles

| Quality profile | Minimum geometric vertices | Maximum geometric vertices | Initial proposed preset |
|---|---:|---:|---:|
| Low Density | 500 | 10,000 | 5,000 |
| Mid Density | 10,001 | 30,000 | 20,000 |
| High Density | 30,001 | 500,000 | 100,000 |

The user shall select an integer target within the chosen profile. Profiles are independent of asset classification, texture resolution and topology preference. An output outside the requested profile remains reviewable and shall be clearly identified. No automatic rejection or deletion shall occur solely because the target or profile was missed.

### 6.4.1 Measurement definitions

| Metric | Definition |
|---|---|
| Geometric vertices | Mesh control points in the canonical geometry, counted from the mesh representation before render-specific expansion. Distinct control points remain distinct even if coincident. |
| Polygon faces | Actual stored polygon faces, including triangles, quads and supported n-gons. |
| Triangles | Face count after a consistent, non-destructive triangulation for measurement. |
| Edges | Unique topological edges within each mesh, derived from face connectivity. |
| Rendering vertices | Vertex records in the prepared rendering representation, including splits required by UVs, normals or other per-corner attributes. |

The same geometric control points can support different polygon topology. For example, triangulating a quad can increase face count without introducing a new control point. Rendering vertex counts can differ from geometric counts and shall identify the measured rendering representation. The exact triangulation algorithm and rendering buffer implementation remain deferred.

| ID | Requirement |
|---|---|
| GPB-001 | Use geometric vertex count as the primary complexity target and profile metric. |
| GPB-002 | Independently measure geometric vertices, polygon faces, triangles, edges and rendering vertices. |
| GPB-003 | Do not substitute provider-reported counts or expanded rendering vertices for canonical geometric counts. |
| GPB-004 | Display requested and measured counts separately, including signed deviation and profile compliance. |
| GPB-005 | Preserve geometry outside its target or profile for review and optional optimization. |
| GPB-006 | Do not enforce an exact count or mandatory percentage tolerance during generation. |
| GPB-007 | Allow users to accept geometry outside the requested target. |
| GPB-008 | Measure individual components and assembled asset totals without counting alternate representations of the same component twice. |
| GPB-009 | Do not weld coincident control points merely to reduce the measured vertex count. |
| GPB-010 | Distinguish source/master statistics from optimized derivative statistics. |
| GPB-011 | Display unknown or unavailable secondary statistics explicitly rather than substituting estimates as measurements. |
| GPB-012 | Geometry complexity shall remain independent of texture quality. |

Vertex count does not independently guarantee good topology, structural accuracy, silhouette preservation, deformation suitability or runtime performance. These characteristics shall be evaluated separately.

## 6.5 User-selected generation strategy

| Strategy | Behavior |
|---|---|
| Direct Generation | Generate geometry directly at or near the requested complexity where supported. |
| Master Mesh Generation | Generate detailed source geometry and produce an optimized derivative targeting the requested complexity. |

The user chooses the strategy. Automatic provider selection shall choose compatible providers within that strategy, not silently change the strategy. If the selected strategy cannot be executed, the application shall disclose the limitation and permit the user to change configuration.

| ID | Requirement |
|---|---|
| GQS-001 | Expose both generation strategies as user-selectable choices. |
| GQS-002 | Declare provider-native complexity controls and supported conversion or optimization stages. |
| GQS-003 | Support providers that accept vertex, polygon, triangle or other native complexity controls through compatible adapters. |
| GQS-004 | Treat translated provider targets as estimates and measure final canonical vertices independently. |
| GQS-005 | Master geometry and optimized geometry shall be distinct artifacts. |
| GQS-006 | Master geometry shall not automatically receive permanent approval. |
| GQS-007 | An independently usable optimized mesh shall not require permanent retention of its historical master. |
| GQS-008 | Users may derive additional quality profiles from retained geometry without replacing the source. |

Detailed optimization and retopology requirements are deferred to Phase 07.

## 6.6 Generation modes and component budgets

| Mode | Behavior |
|---|---|
| Unified | One primary geometry component representing the complete asset. Intentional disconnected islands are permitted. |
| Automatic Modular | Compatible providers identify and generate or extract independently manageable semantic components. Identified components are presented for review. |
| Directed Modular | User defines the intended components and their relationships, including component-specific references where available. |

Modular assets shall conform to the Phase 04 hierarchy, coordinate system and component transforms. A clean humanoid base body shall include usable underlying anatomy rather than merely removing clothing polygons from an incomplete clothed mesh.

| ID | Requirement |
|---|---|
| GGM-001 | Support all three approved generation modes through compatible local pipelines. |
| GGM-002 | Selected mode shall influence provider compatibility evaluation. |
| GGM-003 | Multiple sequential providers may collectively satisfy a generation mode. |
| GGM-004 | Present automatically identified components for user review. |
| GGM-005 | Consume user-defined components in Directed Modular mode. |
| GGM-006 | Support independent component generation and regeneration. |
| GGM-007 | Preserve unrelated components during targeted generation. |
| GGM-008 | Preserve intended relative scale, alignment and component hierarchy. |
| GGM-009 | Support complete asset references, breakaway references, parent geometry and existing component geometry where compatible. |

### 6.6.1 Component allocation

| Method | Behavior |
|---|---|
| Automatic Allocation | Distribute the assembled asset vertex target according to component complexity and importance. |
| Manual Allocation | Permit users to assign individual integer component vertex targets. |

Individual components may fall below the minimum of the complete asset quality profile. A buckle need not contain 500 vertices merely because the assembled asset uses Low Density. Allocations shall be reconciled to the selected total, with conflicts clearly disclosed. The measured assembled total shall be recalculated after component replacement. Targets are guidance, not exact output requirements.

| ID | Requirement |
|---|---|
| GCA-001 | Support automatic and manual vertex allocation for modular assets. |
| GCA-002 | Display component targets and measured counts independently. |
| GCA-003 | Allow component targets below the asset profile minimum. |
| GCA-004 | Disclose allocation conflicts and the effect of component changes on the assembled total. |
| GCA-005 | Do not force geometry regeneration of unrelated components to meet an allocation target. |

Detailed segmentation, component alignment and mesh ownership are addressed in Phase 08.

## 6.7 Reconstruction accuracy and classification requirements

Geometry shall preserve intended silhouette, proportions, pose, anatomy, component count and placement, asymmetry, functional openings, cavities and thin features where supported by the target complexity. It shall avoid unrelated background geometry, duplicate structures and unintended floating fragments. Inferred unseen surfaces shall not be represented as verified reconstruction. Additional references can reduce uncertainty but do not guarantee exact geometry.

| Parent | Asset type | Geometry priorities |
|---|---|---|
| Actors | Humanoid | Neutral A-pose or T-pose where applicable, consistent anatomy, recognizable facial features, fingers, feet and clean modular base anatomy. |
| Actors | Creature | Species-appropriate anatomy, posture, limb counts, wings, tails, horns and other specified features. |
| Scene Assets | Scene Prop | Structural clarity, placement, silhouette and intended cavities. |
| Scene Assets | Vehicle | Exterior only, hard-surface details, hull, wheels, tracks, legs, engines, landing gear and component alignment. |
| Props | Held Prop | Isolated object geometry, functional surfaces and recognizable grip areas. |
| Props | Interactive Prop | Movable components, cavities and functional structural relationships. |
| World Assets | Vehicle Interior | Interior only, usable interior volume, interior-facing surfaces and fixtures. |
| World Assets | Scenery | Exterior or interior profile, structural consistency, modularity and environmental proportions. |

Vehicle exterior and Vehicle Interior shall not be combined or automatically fitted in the MVP. Interior generation shall not fill intended usable volume merely to achieve closed geometry. Interior-facing surfaces and accessible internal space shall be reviewed. Grip and pivot points remain application-managed metadata at asset or component level. Rigging and the optional CC5 218-point alignment workflow are deferred to Phases 14 and 15.

| ID | Requirement |
|---|---|
| GRA-001 | Preserve recognizable intended silhouette and relative dimensions. |
| GRA-002 | Preserve intended anatomical or mechanical structures and configuration states. |
| GRA-003 | Preserve intended symmetry or asymmetry, visible openings and thin structures where supported. |
| GRA-004 | Identify significant structural discrepancies where detectable. |
| GRA-005 | Support classification-specific geometry expectations rather than imposing one universal mesh structure. |
| GRA-006 | Distinguish inferred geometry from verified information when that distinction can be established. |

## 6.8 Geometry integrity, red defect visualization and repair

Geometry validation shall run without modifying the generated artifact. Automatic geometry repair is disabled. All locatable detected defects shall be highlighted in red during review by default. A textual report shall identify defects that cannot be spatially localized.

| Validation category | Review objective |
|---|---|
| Degenerate faces | Identify zero or near-zero area faces. |
| Duplicate vertices and faces | Identify potentially redundant geometry without treating every coincident vertex as a defect. |
| Invalid coordinates or indices | Identify nonfinite coordinates, invalid connectivity and corrupted mesh data. |
| Non-manifold geometry | Identify problematic edge or vertex connectivity. |
| Self-intersections | Identify unintended surface intersections. |
| Inverted normals | Identify surfaces with potentially unintended facing directions. |
| Unintended holes | Identify missing surfaces without closing designed openings. |
| Floating geometry | Identify unintended disconnected fragments without removing valid components. |
| Internal geometry | Identify potentially unnecessary hidden surfaces. |
| Excessive density | Identify disproportionate geometric density. |
| Missing components | Identify absent expected geometry. |

Closed, hollow and open surface geometry are supported. Watertightness is not universally required. Defect classification shall consider intended component role and use. A visual or artistic warning shall not automatically prevent review or approval. Technical corruption may prevent incompatible downstream processing or rendering.

### Repair operations

| Operation | Behavior |
|---|---|
| No Repair | Default. Review original geometry without changes. |
| Safe Repair | User explicitly initiates supported narrowly scoped technical corrections with minimal structural impact. |
| Advanced Repair | User explicitly initiates and configures structural repairs that may alter topology, openings or connectivity. |

Safe Repair may remove invalid or degenerate faces or redundant data when the operation can preserve intended geometry. Advanced Repair may include hole closure, fragment removal and missing surface reconstruction where supported. Neither operation may silently overwrite the original candidate. Structural changes require explicit authorization.

| ID | Requirement |
|---|---|
| GIN-001 | Independently validate geometry coordinates, face indices and technical integrity. |
| GIN-002 | Classify detected defects by category and severity. |
| GIN-003 | Support intentional holes, disconnected components and open surfaces. |
| GIN-004 | Evaluate interior accessibility where applicable. |
| GRP-001 | Disable automatic geometry repair. |
| GRP-002 | Highlight all locatable detected defects in red by default during review. |
| GRP-003 | Provide independent defect category visibility controls and textual defect reporting. |
| GRP-004 | Expose separate Safe Repair and Advanced Repair actions. |
| GRP-005 | Preserve original geometry and create independent repair candidates. |
| GRP-006 | Revalidate repaired outputs and report applied corrections. |
| GRP-007 | Do not silently close intentional openings or fuse intended components. |
| GRP-008 | Defect overlays shall not alter production materials, texture data or exported geometry. |
| GRP-009 | Identify unsupported or failed repair operations without modifying the original. |

## 6.9 Topology, coordinate normalization and scale

### Topology preferences

| Preference | Description |
|---|---|
| Triangles | Triangle-oriented topology. |
| Quads | Quad-oriented topology. |
| Preserve Source | Retain provider-native topology where possible. |

Native quad generation is not mandatory for every provider. Compatible local retopology may produce a derivative meeting the requested preference. The application shall not unnecessarily triangulate canonical quad geometry to measure or render it. The exact quad-oriented acceptance threshold is deferred to Phase 07 and Phase 25.

| ID | Requirement |
|---|---|
| GTP-001 | Expose topology preferences independently of vertex targets. |
| GTP-002 | Declare native and processed topology capabilities and measure actual topology statistics. |
| GTP-003 | Preserve supported source topology during canonical conversion. |
| GTP-004 | Distinguish native topology from processed derivatives. |
| GTP-005 | Do not claim that an output satisfies a topology preference unless its applicable requirements are met. |

### Coordinate and symmetry conventions

| Property | Standard |
|---|---|
| Handedness | Right-handed |
| Up | Positive Y |
| Forward | Positive Z |
| Canonical unit | Centimeters |
| Internal rotation | Quaternion |
| User-facing rotation | Euler degrees |
| Origin | Classification-specific Phase 04 origin registry, with user override |
| Symmetry | Preserve reference, enforce selected symmetry planes where supported, or no enforcement |

Enforcement of symmetry shall be optional and shall not be applied without user selection. Provider-native orientation shall not dictate canonical orientation. Component transformations, relative positions, intended asymmetry and reference point relationships shall be preserved during conversion.

### Physical scale

Support proportional scaling based on a selected width, height or length, independent dimensional scaling with a distortion warning, and unassigned physical dimensions. Users may assign dimensions after generation. Metric and imperial display or entry conversions shall use canonical centimeters internally without altering geometry merely because display units change. Unknown real-world scale shall not be represented as a verified measurement.

| ID | Requirement |
|---|---|
| GSO-001 | Normalize canonical axes, handedness and units according to Phase 04. |
| GSO-002 | Apply classification-specific origin rules and preserve user overrides. |
| GSO-003 | Preserve relative component transforms and intended asymmetry. |
| GSO-004 | Support optional explicit symmetry enforcement where compatible. |
| GSC-001 | Support proportional and independent physical scaling. |
| GSC-002 | Warn when independent scaling changes proportions. |
| GSC-003 | Preserve applicable spatial reference relationships when scaling. |
| GSC-004 | Distinguish user-defined, inferred and unassigned dimensions. |

## 6.10 Single generation and execution locking

Each geometry request shall target one candidate, not a batch. The interface shall not expose a generation quantity input. Additional geometry generation requests shall be disabled while an active geometry generation is in progress. Admission shall be enforced at the backend as well as the interface so repeated clicks or concurrent requests cannot bypass the restriction.

| ID | Requirement |
|---|---|
| GEX-001 | Admit one geometry candidate per user request. |
| GEX-002 | Disable additional geometry submission while an admitted request is outstanding, including waiting, running and necessary internal pipeline stages. |
| GEX-003 | Enforce admission atomically on the backend and reflect it in the interface. |
| GEX-004 | Reject duplicate submissions without adding another geometry request to the queue. |
| GEX-005 | Release the admission lock following terminal success, failure or completed cancellation. |
| GEX-006 | Preserve previously selected and approved geometry after failure or cancellation. |
| GEX-007 | Permit prior pending candidates to remain accessible according to retention policy. |
| GEX-008 | Continue to respect the Phase 02 limit of one active AI inference job per generation server. |

The lock is specific to geometry-producing requests and does not remove the general queue for other workspaces. For MVP implementation, the proposed lock scope is the target generation server across sessions, including geometry regeneration and refinement. The precise multi-user scope, recovery behavior and scheduling implementation shall be confirmed in Phase 21. Waiting requests remain locked to prevent queue accumulation before inference begins.

## 6.11 Geometry output modes and preview palette

| Mode | Behavior |
|---|---|
| Geometry Only | Produce usable geometry without requiring or retaining unnecessary generated textures. |
| Geometry with Texture | Produce geometry and associated texture artifacts using a combined compatible provider or sequential local providers. |

Geometry with Texture shall preserve independently accessible geometry, material definitions and texture artifacts. Texture resolution shall remain independent of geometry density. Existing approved texture standards remain 512, 1024, 2048 and 4096 square; detailed texture and material contracts are addressed in Phases 09 through 13. The Geometry Only workflow shall not be rejected solely because UVs or texture artifacts are absent. If a combined provider cannot avoid producing incidental textures, unnecessary outputs shall not be retained as production artifacts.

The viewport shall provide a selectable application-managed preview color palette, with neutral gray as a proposed default and illustrative options such as white, graphite, clay, teal, blue, sand and purple. Preview colors require no AI inference. A custom color picker is a proposed enhancement. Preview colors are transient display overrides and shall not replace production materials or appear in production exports.

| ID | Requirement |
|---|---|
| GOP-001 | Expose exactly two geometry output modes. |
| GOP-002 | Geometry Only shall remain independently usable without texture generation. |
| GOP-003 | Geometry with Texture shall retain independently manageable geometry and texture outputs, subject to explicit approval. |
| GOP-004 | Support compatible combined or sequential generation pipelines. |
| GOP-005 | Provide selectable viewport preview colors without AI inference. |
| GOP-006 | Preview color changes shall not modify canonical geometry or production materials. |
| GOP-007 | Preview colors and defect overlays shall not be baked into exported production assets. |
| GOP-008 | Geometry and texture quality settings shall remain independent. |
| GOP-009 | Report unavailable texture capabilities or partial failures without falsely marking the requested combined result complete. |

## 6.12 Geometry workspace and review interface

The geometry stage shall remain within the unified 3D Generation studio. The interface shall expose configuration and inspection appropriate to the selected generation mode and strategy. Image creation and reference extraction controls shall not be duplicated here.

| Control | Function |
|---|---|
| Asset classification and subtype | Define structural context. |
| Reference set | Select and assign existing references, with navigation to the appropriate generation workspace. |
| Generation mode | Unified, Automatic Modular or Directed Modular. |
| Generation strategy | User-selected Direct or Master Mesh. |
| Geometry quality | Low, Mid or High Density. |
| Target vertices | Integer target within selected profile. |
| Component allocation | Automatic or manual for modular assets. |
| Topology preference | Triangles, Quads or Preserve Source. |
| Symmetry and dimensions | Optional orientation and scaling instructions. |
| Output mode | Geometry Only or Geometry with Texture. |
| Texture resolution | Applicable only when texture output is requested. |
| Generation instructions | Additional user direction. |
| Provider selection | Automatic compatible selection or advanced manual override. |
| Generate Geometry | Single request, disabled while a geometry request is outstanding. |
| Geometry statistics | Target and actual vertices, faces, triangles, edges, rendering vertices and component totals. |
| Candidate navigation | Previous and next existing candidates, not a batch generation count. |
| Preview palette | Application-managed temporary colors. |
| Defect review | Red overlays, category controls and severity report. |
| Repair actions | Separate Safe Repair and Advanced Repair buttons. |
| Approve / Deny | Explicit retention control. |

| ID | Requirement |
|---|---|
| GVI-001 | Load and display canonical FBX geometry in the viewport. |
| GVI-002 | Support orbit, pan, zoom and standard directional camera views. |
| GVI-003 | Support solid, wireframe and normal inspection modes. |
| GVI-004 | Display independently measured geometry statistics and applicable validation results. |
| GVI-005 | Support independent component visibility and existing candidate navigation. |
| GVI-006 | Review operations shall not modify source geometry. |
| GVI-007 | Use a neutral or user-selected preview color when viewing untextured geometry. |
| GVI-008 | Red defect indicators shall remain distinguishable from production and preview colors. |

Detailed viewport editing and navigation are deferred to Phase 16.

## 6.13 Validation results and candidate review

| Severity | Behavior |
|---|---|
| Informational | Display measurements and relevant geometry information. |
| Warning | Clearly identify potential inconsistencies or defects. |
| Significant Defect | Prominently identify issues requiring user attention. |
| Technical Failure | Prevent only operations that cannot safely consume the invalid artifact until corrected. |

All detected defects use red review indicators regardless of severity; severity remains separately communicated in the validation report. A target mismatch is a numerical compliance warning, not necessarily a spatial geometry defect. Validation shall not repair geometry automatically. Users shall retain creative control over technically usable artifacts, including those outside the target profile. If a technical failure makes rendering impossible, the textual validation report shall remain available where the failure can be diagnosed.

The report shall include artifact ID, measured geometry statistics, selected target and quality profile, detected issues, affected components or mesh regions where known, and applicable repair options. After explicit repair or refinement, a fresh report shall be associated with the new candidate.

## 6.14 Regeneration and existing-mesh refinement

| Operation | MVP scope |
|---|---|
| Full asset regeneration | Included. Produce a replacement candidate from the selected references and settings. |
| Independent component regeneration | Included. Produce a replacement component without changing unrelated geometry. |
| Existing-mesh refinement | Included where compatible providers exist. Consume an existing mesh and optionally additional visual references to produce an improved derivative. |
| Regional geometry sculpting or painting | Deferred until after MVP. |
| Regional geometry inpainting | Deferred until after MVP. |

| ID | Requirement |
|---|---|
| GRF-001 | Support full asset and independent component regeneration. |
| GRF-002 | Support existing-mesh refinement through compatible providers. |
| GRF-003 | Permit additional visual references for refinement where supported. |
| GRF-004 | Preserve source geometry and unrelated components. |
| GRF-005 | Produce independently identifiable and reviewable replacement candidates. |
| GRF-006 | Normalize and validate refined geometry before downstream use. |
| GRF-007 | Disclose unsupported refinement capabilities before execution. |
| GRF-008 | Apply the single-request execution lock to geometry regeneration and refinement. |
| GRF-009 | Display changes in assembled geometry complexity following component replacement. |
| GRF-010 | Do not silently replace geometry used by approved assets. |

## 6.15 Artifact retention, dependency approval and export

Successful generated candidates enter Pending status. Candidate selection, preview, locking, use in processing or export does not automatically approve permanent storage. Pending artifacts expire 10 days after successful generation unless approved. Denied or expired artifacts shall have their exclusive files and generation metadata completely deleted, including associated historical records. Shared physical files required by valid retained assets remain protected; no historical record shall be retained solely for provenance.

When approving a candidate that requires other pending artifacts for continued use, display the dependency approval modal listing all required dependencies and why each is necessary. Approval of the selected artifact and required dependencies shall be explicit and atomic. Cancel leaves approval states unchanged. Historical inputs that are not necessary for continued use shall not be silently approved. Active-job file protection and shared content-hash storage shall follow Phase 04.

| ID | Requirement |
|---|---|
| GRT-001 | Preserve distinct candidate IDs and independent approval states. |
| GRT-002 | Preserve original candidates during regeneration, repair and refinement. |
| GRT-003 | Apply the 10-day pending retention deadline without resetting it through selection or export. |
| GRT-004 | Completely delete exclusive denied and expired generation files and metadata. |
| GRT-005 | Protect shared files still required by valid retained assets and active operations under Phase 04 safeguards. |
| GRT-006 | Require explicit approval of necessary pending dependencies through the established modal. |
| GRT-007 | Do not automatically retain historical master meshes, source references or previous candidates. |
| GRT-008 | Permit pending artifact export only after the established warning and explicit confirmation. |
| GRT-009 | Export only the selected applicable artifacts and necessary dependencies, not all prior attempts. |
| GRT-010 | Export shall not approve artifacts or extend their retention deadline. |

## 6.16 Canonical geometry output and interoperability

FBX is the sole canonical MVP geometry interchange format. Provider-native formats may be used temporarily. Native geometry shall be converted locally and validated before canonical use. Conversion shall preserve supported control points, polygon topology, normals, UVs where present, material assignments, component hierarchy and transforms. Unnecessary native intermediates shall be removed after validated conversion unless required by an active job. Failed conversion shall not overwrite the source.

The common JSON `AssetManifest.json` shall identify canonical geometry, component relationships, selected artifacts and applicable metadata without embedding binary data or secrets. Geometry remains usable after the generation provider unloads. Future evaluation of GLB/glTF and other interchange formats remains post-MVP.

Illustrative geometry-stage ZIP package (only applicable files are included):

```text
Light_Cargo_Frigate.zip
  AssetManifest.json
  Geometry/
    Light_Cargo_Frigate.fbx
  Components/
    Primary_Hull.fbx
    Cockpit_Glass.fbx
    Left_Engine.fbx
    Right_Engine.fbx
  Metadata/
    Geometry_Statistics.json
    Geometry_Validation.json
    Generation_Settings.json
```

A complete asset FBX and separate component FBX files may be alternate representations; their counts must not be added together when measuring the assembled asset. Geometry export shall not require completed textures, materials, UV maps or character preparation. Geometry with Texture may include applicable PNG maps and JSON material definitions according to the approved asset manifest and later texture phases.

| ID | Requirement |
|---|---|
| GOU-001 | Use FBX as canonical geometry interchange. |
| GOU-002 | Conform to Phase 04 manifest, IDs and hierarchy requirements. |
| GOU-003 | Preserve supported topology, transforms, normals, UVs and material assignments during conversion. |
| GOU-004 | Associate measured statistics and validation reports with the correct candidate. |
| GOU-005 | Retain applicable provider and generation parameters only while the associated artifacts remain retained. |
| GOU-006 | Delete unnecessary native intermediates following validated conversion. |
| GOU-007 | Ensure geometry remains independently usable after provider unloading. |
| GOU-008 | Support downstream consumption directly or through temporary local conversion. |
| GOU-009 | Support selected-artifact ZIP export, including geometry-only assets. |

## 6.17 Geometry provider and processing constraints

The complete local pipeline must collectively satisfy these requirements. Individual providers need only satisfy the constraints applicable to their declared capabilities. The application shall not represent an unsupported capability as available. Native implicit surfaces, volumetric fields or point clouds are permitted as temporary representations if converted into usable canonical mesh geometry.

| ID | Constraint |
|---|---|
| GMC-001 | Support local-only inference and programmatic execution. |
| GMC-002 | Support image-conditioned geometry generation for reconstruction providers. |
| GMC-003 | Produce actual independently persistable mesh geometry directly or through compatible conversion. |
| GMC-004 | Support validated local FBX conversion. |
| GMC-005 | Produce recognizable structural characteristics from compatible inputs. |
| GMC-006 | Produce geometry suitable for independent measurement and validation. |
| GMC-007 | Operate within configured local hardware resources. |
| GMC-008 | Permit resource reclamation after execution. |
| GMC-009 | Declare supported reference counts, directions, formats and camera metadata. |
| GMC-010 | Multi-view providers must actually consume multiple compatible views. |
| GMC-011 | Preserve cross-view structural features within applicable evaluation tolerances. |
| GMC-012 | Declare supported asset classifications and interior or exterior capabilities. |
| GMC-013 | Declare native vertex, polygon, triangle or other density controls. |
| GMC-014 | Support pipeline targeting of geometric vertices, directly or through compatible processing. |
| GMC-015 | Declare native topology capabilities. |
| GMC-016 | Preserve supported source topology or disclose limitations. |
| GMC-017 | Produce valid coordinates and face indices. |
| GMC-018 | Preserve intended openings, thin features and asymmetry where applicable. |
| GMC-019 | Support canonical coordinate and scale normalization. |
| GMC-020 | Modular providers must produce independently accessible component geometry. |
| GMC-021 | Component providers must support isolated geometry from compatible references. |
| GMC-022 | Support intended component scale and alignment directly or through compatible processing. |
| GMC-023 | Permit independent component execution without regenerating unrelated components. |
| GMC-024 | Refinement providers must accept existing geometry and return independent derivatives. |
| GMC-025 | Declare compatibility with Direct and Master Mesh strategies. |
| GMC-026 | Support independent geometry output without mandatory texture retention. |
| GMC-027 | Texture-capable pipelines must provide independently accessible geometry and texture artifacts. |
| GMC-028 | Support downstream geometry, UV, texture and material processing where applicable. |
| GMC-029 | Support sequential execution and provider unloading. |
| GMC-030 | Do not require destructive modification of approved source artifacts. |
| GMC-031 | Do not require undocumented permanent native intermediates. |
| GMC-032 | Expose sufficient execution information to identify completion and failure. |
| GMC-033 | Meet applicable licensing requirements before integration. |

## 6.18 Validation assertions

These assertions define the initial test suite for integrated geometry pipelines. A reported mismatch is not a successful reconstruction or profile-compliance result. Quantitative reconstruction and performance thresholds shall be established in Phase 25. Provider-specific capability tests apply only to declared capabilities, while the integrated MVP must cover the approved workflows.

| ID | Test | Expected result |
|---|---|---|
| GMA-001 | Generate from one compatible image. | Recognizable usable mesh is produced. |
| GMA-002 | Generate from compatible multiple views. | Output incorporates structural information from the selected views. |
| GMA-003 | Supply inconsistent but technically valid references. | Discrepancies are flagged without automatically blocking generation. |
| GMA-004 | Supply incompatible selected references. | Incompatibility is disclosed before execution; reduction requires confirmation. |
| GMA-005 | Generate an asymmetric object. | Intended asymmetry remains present. |
| GMA-006 | Generate an object with intentional openings and thin features. | Applicable structures remain identifiable. |
| GMA-007 | Generate an isolated object. | Unrelated background geometry is absent within accepted evaluation tolerances. |
| GMA-008 | Generate a neutral humanoid. | Intended anatomy and pose remain recognizable. |
| GMA-009 | Generate a modular base body. | Underlying anatomy exists without fused unwanted clothing. |
| GMA-010 | Generate a quadruped creature. | Intended anatomy and limb count are preserved. |
| GMA-011 | Generate a scene prop. | Intended structure and cavities remain identifiable. |
| GMA-012 | Generate a held prop. | Intended isolated object and grip surfaces are identifiable. |
| GMA-013 | Generate an interactive prop. | Required movable components are independently accessible through the selected pipeline. |
| GMA-014 | Generate a vehicle exterior. | Exterior is produced without mandatory interior generation. |
| GMA-015 | Generate a vehicle interior. | Intended usable internal space and interior-facing surfaces remain present. |
| GMA-016 | Generate scenery. | Intended structural or environmental profile is preserved. |
| GMA-017 | Request Low Density. | Measured geometric vertices determine compliance with 500 to 10,000; mismatches are clearly flagged. |
| GMA-018 | Request Mid Density. | Measured geometric vertices determine compliance with 10,001 to 30,000; mismatches are clearly flagged. |
| GMA-019 | Request High Density. | Measured geometric vertices determine compliance with 30,001 to 500,000; mismatches are clearly flagged. |
| GMA-020 | Measure a known quad mesh and its triangulated derivative. | Geometric vertices, faces, triangles and edges are independently correct; geometric count remains unchanged if control points are unchanged. |
| GMA-021 | Render a mesh with UV or normal splits. | Rendering vertex count is separately measured and does not replace geometric count. |
| GMA-022 | Generate outside a requested target. | Actual deviation is displayed and candidate remains reviewable. |
| GMA-023 | Select Direct Generation. | Compatible direct pipeline is used or incompatibility is disclosed without strategy substitution. |
| GMA-024 | Select Master Mesh Generation. | Independent master and optimized derivative are produced where supported. |
| GMA-025 | Generate a quad-oriented result. | Applicable topology preference is met or incompatibility or mismatch is reported. |
| GMA-026 | Generate a Unified asset. | One primary component is available, with intentional disconnected islands allowed. |
| GMA-027 | Generate an Automatic Modular asset. | Identified components are independently accessible and reviewable. |
| GMA-028 | Generate a Directed Modular asset. | Requested components are produced or missing components clearly identified. |
| GMA-029 | Allocate component vertex budgets manually and automatically. | Targets are visible, component minima are not imposed and allocations reconcile to the asset target. |
| GMA-030 | Regenerate one component. | Unrelated geometry remains unchanged and assembled statistics update. |
| GMA-031 | Refine an existing mesh. | Original remains unchanged and independent validated candidate is produced. |
| GMA-032 | Submit one geometry request and attempt a second during execution. | Backend rejects the second request without queueing it. |
| GMA-033 | Complete, fail or cancel the active request. | Admission lock releases only after the terminal state. |
| GMA-034 | Validate geometry with known defects. | Defects are reported and locatable defects are red; original file remains unchanged. |
| GMA-035 | Explicitly run Safe Repair. | Supported corrections produce a new validated candidate and report. |
| GMA-036 | Explicitly run Advanced Repair. | Authorized structural changes produce a new validated candidate; original remains intact. |
| GMA-037 | Review intentional holes and disconnected components. | Intentional features are not automatically repaired or removed. |
| GMA-038 | Select Geometry Only. | Independently usable geometry is produced without mandatory texture retention. |
| GMA-039 | Select Geometry with Texture. | Independently accessible geometry and texture outputs are produced or partial failure is clearly reported. |
| GMA-040 | Switch preview colors. | Display changes without inference or changes to production geometry or materials. |
| GMA-041 | Export with a preview color or red defect overlay active. | Display overrides are absent from production artifacts. |
| GMA-042 | Convert native output into FBX. | Valid canonical mesh preserves supported source data. |
| GMA-043 | Normalize provider-native axes and scale. | Canonical orientation, units and origin conform to Phase 04. |
| GMA-044 | Apply a physical dimension to a modular asset. | Intended component relationships remain consistent. |
| GMA-045 | Load canonical geometry in the viewport. | Supported inspection modes render successfully. |
| GMA-046 | Pass geometry to a downstream provider. | Geometry is consumed directly or through compatible local conversion. |
| GMA-047 | Generate offline and unload the provider. | Output remains usable and resources become reclaimable. |
| GMA-048 | Simulate generation or conversion failure. | Previously retained geometry is unchanged. |
| GMA-049 | Approve a candidate with required pending dependencies. | Explicit modal lists dependencies and approval is atomic; cancel changes nothing. |
| GMA-050 | Deny or expire a pending geometry candidate. | Exclusive files and generation metadata are deleted; valid shared files remain protected. |
| GMA-051 | Export a pending geometry candidate. | Warning and confirmation occur without approval or retention extension. |
| GMA-052 | Measure a modular asset with both aggregate and component representations. | Alternate representations are not double counted. |

## 6.19 Application and provider responsibilities

| SWIFT Director | Provider or compatible processing tool |
|---|---|
| Asset classification, reference assignment and compatibility enforcement | Interpretation of supported visual inputs |
| User strategy and output configuration | Execution of declared generation capabilities |
| Vertex target and component allocation | Native density controls and geometry production |
| Independent geometry measurements | Accessible native geometry representation |
| FBX conversion and coordinate normalization orchestration | Compatible conversion and processing capabilities |
| Defect reporting, red overlays and explicit repair controls | Supported repair or refinement operations when invoked |
| Preview palette and viewport | No AI preview color generation required |
| Component hierarchy and spatial reference metadata | Semantic identification and structural reconstruction |
| Request admission lock and job scheduling | Execution status and resource release |
| Candidate approval, retention, dependency management and export | No direct permanent retention or approval control |

Deterministic conversion, measurement, validation and other application operations shall not require AI inference unless a specific operation benefits from AI-assisted processing. No provider shall control permanent artifact approval or silently discard user-selected references.

## 6.20 MVP acceptance criteria

- Single-image and compatible multi-view geometry generation are available through local pipelines for the eight approved asset types.
- The user selects Direct or Master Mesh Generation and one of the three approved generation modes.
- Vertex-based Low, Mid and High Density profiles are available, with independently measured faces, triangles, edges and rendering vertices.
- Targets remain advisory; actual counts and profile mismatches are visible.
- Automatic and manual component vertex allocation are supported.
- One candidate is admitted per request, and additional geometry requests cannot queue during the outstanding operation.
- Geometry review shows red locatable defects without automatic repair, and explicit Safe Repair and Advanced Repair actions are available.
- Geometry Only and Geometry with Texture are available, with a non-AI preview palette.
- Full asset regeneration, independent component regeneration and compatible existing-mesh refinement preserve original artifacts.
- Canonical geometry uses FBX, normalized coordinates and the approved asset manifest.
- Geometry remains inspectable, exportable and consumable by later stages independently of texture completion.
- Local execution, dependency approval, 10-day retention and complete deletion requirements are enforced.
- Capability limitations, technical failures and validation uncertainty are disclosed accurately.

## 6.21 Implementation details and deferred decisions

The eight review decisions are approved. The following technical interpretations and implementation details were introduced during consolidation and remain subject to verification or later design refinement:

- Profile preset targets of 5,000, 20,000 and 100,000 geometric vertices are proposed initial values, not independently approved numerical defaults.
- Counting canonical FBX control points, without welding coincident points for counting, is the proposed operational definition of geometric vertices. Measurement algorithms, instancing semantics and rendering buffer conventions shall be verified in Phase 07 and Phase 16.
- Server-wide geometry admission across sessions, including queued or waiting geometry requests and internal pipeline stages, is a conservative proposed interpretation of the no-queue requirement. The precise concurrency and recovery scope shall be established in Phase 21.
- Independent defect category toggles, a neutral gray default palette and an optional custom color picker are proposed interface details. No particular palette colors are mandatory.
- Safe Repair and Advanced Repair algorithms, allowed correction sets, numerical thresholds and structural repair safeguards remain to be specified and tested.
- Exact FBX version, conversion tools, model providers, texture map implementation, hardware performance and quantitative validation thresholds remain unselected.
- Detailed optimization and topology are deferred to Phase 07, modular generation to Phase 08, texture and material workflows to Phases 09 through 13, character preparation to Phases 14 and 15, viewport details to Phase 16, export contracts to Phase 18, provider and hardware orchestration to Phases 19 through 21, and evaluation thresholds to Phase 25.

The earlier phase files have not been rewritten. Their polygon-based complexity references are superseded by this document and should be reconciled when maintaining the complete software design specification. Reference Generation implementation remains a prerequisite for the integrated reference workflow.

**Next design phase:** Phase 07: Geometry Optimization and Topology.
