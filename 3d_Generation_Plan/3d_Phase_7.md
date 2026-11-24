# Phase 07: Geometry Optimization and Topology

**Product:** SWIFT Director  
**Workspace:** Asset Generation > 3D Generation  
**Version:** 1.0  
**Status:** Finalized design specification  
**Scope:** Local-only MVP

## 7.1 Purpose and scope

Geometry Optimization and Topology shall allow users to reduce, increase, redistribute, and reconstruct the geometric structure of generated or imported assets independently of AI geometry generation. Processing shall preserve intended asset identity, structural characteristics, component relationships, and source artifacts. The output shall be independently reviewable canonical FBX geometry.

The requirements in Phases 02 through 06 remain applicable, including local execution, nondestructive processing, vertex-based budgets, artifact approval, 10-day pending retention, and complete deletion of denied or expired artifacts and their exclusive metadata. This phase does not introduce direct regional sculpting, regional geometry inpainting, automatic repair, automatic texture generation, or automatic texture rebaking.

## 7.2 Supported operations

All seven operations are included in the MVP and shall be independently selectable.

| ID | Operation | Purpose |
|---|---|---|
| OOP-001 | Geometry Reduction | Reduce vertex density while preserving shape and important structural details. |
| OOP-002 | Retopology | Reconstruct mesh connectivity and edge flow. |
| OOP-003 | Remeshing | Rebuild the surface using a different geometric structure. |
| OOP-004 | Subdivision | Increase density by subdividing existing faces. |
| OOP-005 | Smoothing | Reduce unwanted surface irregularities. |
| OOP-006 | Triangulation | Convert polygon faces into triangles. |
| OOP-007 | Quadrangulation | Convert or reconstruct geometry into primarily quad faces. |

Level of Detail (LOD) generation is an additional dedicated workflow for creating alternative density representations. Geometry repair is a separate, explicitly initiated operation governed by Phase 06. Deterministic local processing shall be preferred when it satisfies the requested operation without AI inference.

## 7.3 Processing workflow and execution modes

1. Select a generated, imported, or previously processed source artifact.
2. Analyze geometry statistics, topology, components, and existing surface assignments.
3. Select the operation or Advanced processing pipeline.
4. Configure applicable targets, topology profiles, component allocation, and preservation controls.
5. Identify protected components and surface regions.
6. Validate provider compatibility, resource availability, and protection constraints.
7. Execute locally and normalize resulting geometry to canonical FBX.
8. Validate and compare the resulting candidate against its source.
9. Approve, deny, export, or initiate another operation.

Optimization may also be invoked as part of the user-selected Master Mesh Generation strategy from Phase 06. The same nondestructive and validation requirements apply.

| ID | Requirement |
|---|---|
| OPL-001 | Support independent operations in Standard mode. |
| OPL-002 | Support configurable sequential pipelines in Advanced mode. |
| OPL-003 | Users shall be able to add, remove, and reorder pipeline operations. |
| OPL-004 | Each operation shall have independent settings. |
| OPL-005 | Each operation shall consume the applicable output of the preceding operation. |
| OPL-006 | Validate pipeline compatibility before execution. |
| OPL-007 | Stop dependent operations when a required operation fails. |
| OPL-008 | Preserve original source geometry. |
| OPL-009 | Never automatically insert repair operations. |
| OPL-010 | Intermediate artifacts shall follow the established retention and dependency policies. |
| OPL-011 | Present the final pipeline candidate for review before approval. |

## 7.4 Geometry density and measurement

| Profile | Minimum geometric vertices | Maximum geometric vertices |
|---|---:|---:|
| Low Density | 500 | 10,000 |
| Mid Density | 10,001 | 30,000 |
| High Density | 30,001 | 500,000 |

These Phase 06 profiles supersede earlier polygon-based budgets. The ranges apply to the complete assembled asset, not each component. Individual components may contain fewer than 500 vertices. Targets are goals, not exact-count requirements, and no mandatory percentage tolerance applies.

Measure geometric vertices independently of expanded rendering vertices. Also measure edges, polygon faces, triangles, rendering vertices, components, connected islands, boundary edges, and non-manifold elements. Report topology composition as triangles, quads, and n-gons. Counting conventions shall be consistent with Phase 06 and shall not require destructive welding or triangulation of the canonical asset.

| ID | Requirement |
|---|---|
| OVB-001 | Use geometric vertices as the primary user-defined complexity budget. |
| OVB-002 | Support all three density profiles. |
| OVB-003 | Allow an integer target within the chosen profile where applicable. |
| OVB-004 | Independently measure actual vertex counts after processing. |
| OVB-005 | Display requested and actual counts and their difference. |
| OVB-006 | Do not automatically reject or delete results solely for target deviation. |
| OVB-007 | Measure component counts independently. |
| OVB-008 | Account for all included components in assembled asset statistics. |
| OVB-009 | Independently report polygon, triangle, edge, and rendering vertex counts. |
| OVB-010 | Clearly identify results outside the selected density profile. |

## 7.5 Geometry reduction

Reduction shall prioritize efficient vertex removal without unnecessary loss of silhouette or function. Flat surfaces may tolerate aggressive reduction, while curved surfaces, faces, joints, thin structures, mechanical edges, attachment surfaces, and intentional cavities require appropriate preservation.

| ID | Requirement |
|---|---|
| OGR-001 | Support vertex-targeted reduction. |
| OGR-002 | Preserve intended silhouette. |
| OGR-003 | Preserve structural proportions. |
| OGR-004 | Preserve recognizable anatomical and mechanical features. |
| OGR-005 | Preserve intended component separation. |
| OGR-006 | Preserve intentional openings and cavities. |
| OGR-007 | Support sharp-edge preservation. |
| OGR-008 | Support thin-structure preservation. |
| OGR-009 | Report significant structural deviation. |
| OGR-010 | Produce a separate optimized artifact. |

## 7.6 Subdivision and density increase

Subdivision shall increase geometry density without implying that new reconstructed detail or accuracy has been obtained.

| Method | Behavior |
|---|---|
| Linear | Subdivide without intentional smoothing. |
| Smooth | Subdivide while explicitly smoothing the surface. |
| Adaptive | Subdivide according to structural complexity where compatible tools exist; user-assigned regional density priorities remain post-MVP. |

| ID | Requirement |
|---|---|
| OSU-001 | Support independent density increase. |
| OSU-002 | Support linear subdivision. |
| OSU-003 | Support smooth subdivision. |
| OSU-004 | Support adaptive subdivision where compatible processing exists, without introducing weighted regional priority controls. |
| OSU-005 | Preview estimated complexity increases where available. |
| OSU-006 | Preserve the original artifact. |
| OSU-007 | Explicitly identify smoothing. |
| OSU-008 | Do not claim subdivision alone reconstructs new surface detail. |

## 7.7 Topology reconstruction

| Preference | Intended output |
|---|---|
| Preserve Source | Retain source topology wherever possible. |
| Triangles | Triangular faces. |
| Quads | Primarily quad-based geometry; actual composition must be reported. |

| ID | Requirement |
|---|---|
| OTR-001 | Support independent topology reconstruction. |
| OTR-002 | Support triangular topology. |
| OTR-003 | Support quad-oriented topology. |
| OTR-004 | Support preservation of source topology. |
| OTR-005 | Measure actual topology composition. |
| OTR-006 | Preserve defining surface characteristics. |
| OTR-007 | Preserve component boundaries. |
| OTR-008 | Preserve intentional openings. |
| OTR-009 | Avoid unnecessary triangulation during FBX conversion. |
| OTR-010 | Identify topology limitations before processing. |
| OTR-011 | Produce independently reviewable derivatives. |
| OTR-012 | Retopology shall not automatically rig or animate assets. |

Remeshing and quadrangulation shall disclose their effects on connectivity, protected regions, and existing surface assignments. Selecting Quads shall not be represented as a guarantee of exclusively quad faces or animation-ready topology.

## 7.8 Processing profile registry

Profiles describe processing priorities and do not replace the eight asset classifications.

| Profile | Objective |
|---|---|
| General Purpose | Balanced shape preservation and optimization. |
| Organic / Deformable | Anatomy, facial edge flow, joints, curvature, deformation suitability. |
| Hard Surface | Mechanical precision, sharp edges, planar surfaces. |
| Environmental / Structural | Architectural dimensions, openings, modular interfaces. |
| Thin Surface | Open boundaries, thin structures, surface continuity. |
| Custom | User-defined processing settings. |

| Asset type | Recommended profile |
|---|---|
| Humanoid | Organic / Deformable |
| Creature | Organic / Deformable |
| Scene Prop | General Purpose or Hard Surface |
| Vehicle | Hard Surface |
| Held Prop | General Purpose or Hard Surface |
| Interactive Prop | Hard Surface |
| Vehicle Interior | Environmental / Structural |
| Scenery | Environmental / Structural |

All six profiles shall be assignable at asset and component level. Component assignments override inherited asset recommendations. Users may override defaults. For example, a humanoid may use Organic / Deformable for anatomy, Hard Surface for armor, and Thin Surface for a cape.

## 7.9 Preservation controls

Support applicable preservation options for silhouette, sharp edges, open boundaries, component boundaries, curvature, symmetry, asymmetry, UV seams, material boundaries, attachment surfaces, and spatial reference points.

| ID | Requirement |
|---|---|
| OPR-001 | Allow users to configure supported preservation options. |
| OPR-002 | Providers shall declare supported preservation capabilities. |
| OPR-003 | Disclose unsupported preservation requirements before execution. |
| OPR-004 | Do not silently remove protected component boundaries. |
| OPR-005 | Do not silently change asset origins. |
| OPR-006 | Preserve access to spatial reference metadata, including grip and pivot points. |
| OPR-007 | Flag significant deviation from attachment surfaces. |
| OPR-008 | Preserve UV and material relationships where supported. |
| OPR-009 | Notify users when surface assignments require reconstruction. |

## 7.10 Regional geometry protection

Binary regional protection is included in the MVP. Regional Density Priority, weighted optimization masks, regional vertex allocation, and graded protection strength are deferred until after MVP. Protection is not regional sculpting or geometry inpainting.

| ID | Requirement |
|---|---|
| ORP-001 | Allow users to select surface regions for protection. |
| ORP-002 | Allow users to add and remove protected regions. |
| ORP-003 | Visually identify protected regions in the viewport. |
| ORP-004 | Protected geometry shall remain unchanged during compatible processing. |
| ORP-005 | Protected vertices shall count toward the total budget. |
| ORP-006 | Identify conflicts between protected geometry and target budgets. |
| ORP-007 | Protection overlays shall not modify production materials or textures. |
| ORP-008 | Associate selections with the applicable geometry artifact. |
| ORP-009 | Disclose unsupported regional protection before execution. |
| ORP-010 | Protected region boundaries shall remain compatible with surrounding processed geometry. |

A processor incapable of honoring a selected lock shall not silently disregard it. Users may select a compatible operation or explicitly change the protection configuration. Selection representation and cross-topology mapping are deferred implementation details. A proposed blue overlay distinguishes protected regions from red defects.

## 7.11 Modular component optimization

| Method | Behavior |
|---|---|
| Automatic Allocation | Distribute the total budget among unlocked components. |
| Manual Allocation | Configure individual component targets. |
| Independent Optimization | Process only a selected component. |

| ID | Requirement |
|---|---|
| OCO-001 | Support complete modular asset optimization. |
| OCO-002 | Support individual component optimization. |
| OCO-003 | Support automatic component allocation. |
| OCO-004 | Support manual component allocation. |
| OCO-005 | Support component locking. |
| OCO-006 | Locked components shall remain unchanged. |
| OCO-007 | Locked vertices shall count toward the overall budget. |
| OCO-008 | Preserve hierarchy. |
| OCO-009 | Preserve relative component transforms. |
| OCO-010 | Do not modify unrelated geometry. |
| OCO-011 | Reevaluate component compatibility after optimization. |
| OCO-012 | Flag budgets that cannot accommodate protected components. |

## 7.12 Existing UV, material, and texture handling

**Preserve Existing** shall be the default when source surface assignments are present.

| Mode | Behavior |
|---|---|
| Preserve Existing | Attempt to preserve existing UV, material, and texture relationships. |
| Transfer Surface Data | Explicitly transfer compatible surface information. |
| Geometry Only | Produce geometry without existing surface assignments. |

| ID | Requirement |
|---|---|
| OSP-001 | Detect existing UV, material, and texture assignments. |
| OSP-002 | Preserve existing UV coordinates where compatible. |
| OSP-003 | Preserve material assignments where compatible. |
| OSP-004 | Identify affected or invalidated surface assignments. |
| OSP-005 | Inform users when transfer or rebaking is necessary. |
| OSP-006 | Preserve original textures and materials. |
| OSP-007 | Never automatically regenerate textures or rebake them. |
| OSP-008 | Optimized geometry shall remain independently usable without textures. |
| OSP-009 | Surface derivatives shall follow the approved artifact lifecycle. |

Detailed transfer, UV reconstruction, and rebaking requirements are deferred to the applicable later phases. A compatibility report shall distinguish available source textures from verified alignment on the optimized mesh.

## 7.13 Geometry smoothing

Smoothing is an independent operation and shall execute only when selected by the user, including within an explicitly configured pipeline. It shall not be automatically included in Safe Repair.

Proposed applicable controls include strength, iteration count, volume preservation, sharp-edge preservation, and boundary preservation. The application shall disclose supported controls and report meaningful shape changes. No smoothing operation may silently disregard component or regional protection.

## 7.14 Level of Detail generation

LOD variants are alternative geometry representations of the same asset. They retain identity, compatible origins, physical scale, and applicable component relationships, rather than becoming unrelated assets.

| ID | Requirement |
|---|---|
| OLD-001 | Generate density variants from existing geometry. |
| OLD-002 | Allow user-defined targets for each LOD. |
| OLD-003 | Preserve asset identity. |
| OLD-004 | Preserve compatible origins and physical scale. |
| OLD-005 | Preserve applicable component relationships. |
| OLD-006 | Make each variant independently reviewable. |
| OLD-007 | Support independent approval and retention. |
| OLD-008 | Associate LOD metadata with its asset. |
| OLD-009 | Export selected variants together. |
| OLD-010 | Support configurable custom levels. |
| OLD-011 | Support absolute vertex targets. |
| OLD-012 | Support percentage targets relative to measured source vertices. |
| OLD-013 | Generate one selected level independently per request. |
| OLD-014 | Preserve unrelated levels when regenerating a level. |
| OLD-015 | Compare a level against its source. |
| OLD-016 | Preserve canonical coordinate conventions. |
| OLD-017 | Preserve applicable spatial reference metadata. |
| OLD-018 | Report surface assignment compatibility. |
| OLD-019 | Never automatically regenerate textures or rebake them. |
| OLD-020 | Support combined and independent exports of selected variants. |

Illustrative configuration for a source containing 100,000 vertices:

| Level | Source percentage | Target vertices |
|---|---:|---:|
| LOD 0 | 100% | 100,000 |
| LOD 1 | 30% | 30,000 |
| LOD 2 | 10% | 10,000 |
| LOD 3 | 2% | 2,000 |

These levels and percentages are examples, not mandatory defaults. Users shall not be required to generate an entire set. Runtime switching distances and engine-specific export configuration are deferred to Phase 18.

Illustrative export:

```text
Cargo_Frigate_LOD_Package.zip
  AssetManifest.json
  Geometry/
    Cargo_Frigate_LOD0.fbx
    Cargo_Frigate_LOD1.fbx
    Cargo_Frigate_LOD2.fbx
  Metadata/
    LODManifest.json
  Textures/
    [Applicable selected texture artifacts]
```

Only selected variants and applicable dependencies shall be included.

## 7.15 Optimization workspace

Optimization shall use the common 3D Generation viewport, asset hierarchy, and artifact infrastructure. It shall not require a separate application.

| ID | Requirement |
|---|---|
| OUI-001 | Support source geometry selection. |
| OUI-002 | Support independent operations and Advanced pipeline configuration. |
| OUI-003 | Support applicable vertex target controls. |
| OUI-004 | Support topology preferences. |
| OUI-005 | Support processing profile selection. |
| OUI-006 | Support component selection, locking, and regional protection. |
| OUI-007 | Support preservation and surface handling settings. |
| OUI-008 | Support the four approved comparison modes. |
| OUI-009 | Support shared solid and wireframe inspection. |
| OUI-010 | Highlight detected defects in red. |
| OUI-011 | Display independently measured geometry statistics. |
| OUI-012 | Support approval, denial, regeneration, and export. |
| OUI-013 | Provide explicit Safe Repair and Advanced Repair controls. |
| OUI-014 | Provide dedicated LOD configuration and selected-level generation. |

The interface shall display the selected source artifact, actual source complexity, requested complexity, operation settings, compatibility warnings, processing status, and resulting statistics. No image generation controls are duplicated in this workspace.

## 7.16 Geometry comparison

Exactly four primary comparison modes are included in the MVP.

| Mode | Purpose |
|---|---|
| Source Only | Inspect the original geometry. |
| Side by Side | Inspect source and optimized geometry simultaneously. |
| Overlay | Superimpose aligned source and optimized geometry. |
| Deviation Heatmap | Display measured surface displacement. |

Optimized Only is not a separate comparison mode. Optimized artifacts remain viewable through the normal asset viewport. Synchronized cameras and wireframe are shared viewport controls rather than additional comparison modes.

| ID | Requirement |
|---|---|
| OCP-001 | Support all four approved comparison modes. |
| OCP-002 | Preserve independent access to source and optimized artifacts. |
| OCP-003 | Support synchronized camera transforms where applicable. |
| OCP-004 | Preserve common scale and orientation during comparison. |
| OCP-005 | Support aligned overlay comparison. |
| OCP-006 | Support measured surface deviation visualization. |
| OCP-007 | Distinguish displacement visualization from red defect highlighting. |
| OCP-008 | Display vertex, polygon, and triangle differences. |
| OCP-009 | Comparison shall not modify artifacts. |

Heatmaps shall be based on measured geometric displacement, not AI-generated visual similarity estimates. Measurement units, direction, scale, and method shall be identifiable. Exact sampling and deviation thresholds remain for Phase 25.

## 7.17 Validation and manual repair

Every completed optimization candidate shall undergo validation consistent with Phase 06. Evaluate invalid coordinates and indices, degenerate or duplicate faces, non-manifold elements, self-intersections where detectable, inverted normals, unintended openings, floating geometry, component compatibility, surface deviation, vertex density, and UV/material compatibility.

All locatable detected defects shall be highlighted in red during review. Nonlocatable defects shall be listed clearly. Intentional openings and disconnected components shall not automatically be considered defects. Visual discrepancies and target deviations shall be flagged without automatic rejection; actual technical corruption may prevent incompatible processing.

Automatic repair remains disabled. Safe Repair and Advanced Repair shall be explicitly initiated, produce independent candidates, report applied changes, and undergo subsequent validation. Original and optimized source artifacts shall remain unchanged. Repair shall not be silently inserted into a processing pipeline.

## 7.18 Artifact management and execution locking

| ID | Requirement |
|---|---|
| OAM-001 | Assign independent identifiers to optimization results. |
| OAM-002 | Never overwrite source geometry. |
| OAM-003 | New completed derivatives initially enter Pending. |
| OAM-004 | Unapproved completed derivatives expire after 10 days. |
| OAM-005 | Delete denied and expired derivatives and all exclusive associated metadata and files. |
| OAM-006 | Do not automatically approve source artifacts. |
| OAM-007 | Required operational dependencies participate in explicit dependency approval. |
| OAM-008 | Historical provenance alone shall not require permanent retention of source geometry. |
| OAM-009 | Support independent export of selected artifacts. |
| OAM-010 | Pending export requires the established confirmation and does not approve or extend retention. |

Shared physical files still required by valid retained artifacts shall remain protected. No historical generation records shall be retained solely for denied or expired artifacts. Active-job file protection shall follow the established lifecycle rules.

| ID | Requirement |
|---|---|
| OEX-001 | One final candidate per optimization request. |
| OEX-002 | Prevent additional optimization submissions while active optimization is executing. |
| OEX-003 | Prevent geometry generation for the affected asset during optimization. |
| OEX-004 | Process components sequentially. |
| OEX-005 | Enforce locking at both interface and backend. |
| OEX-006 | Failed operations shall not modify approved source artifacts. |
| OEX-007 | Release locks only after successful completion or safe termination, including cancellation. |
| OEX-008 | Advanced pipelines shall follow the same execution restrictions; one active pipeline per asset. |
| OEX-009 | AI-assisted operations shall comply with the existing one-active-inference-job-per-generation-server restriction. |

Existing geometry may remain available for nondestructive inspection while processing executes. Broader cross-asset deterministic concurrency and orchestration details remain for Phase 21.

## 7.19 Provider architecture and constraints

Local deterministic processing is preferred where sufficient. Counting, triangulation, subdivision, smoothing, and geometric deviation measurement may be deterministic. Reduction, retopology, remeshing, and semantic assistance may use compatible deterministic or AI-assisted processors. Automatic provider selection and advanced compatible manual override remain available. No provider or implementation library is selected by this specification.

| ID | Constraint |
|---|---|
| OMC-001 | Support local execution. |
| OMC-002 | Support programmatic requests. |
| OMC-003 | Accept canonical FBX directly or through compatible temporary conversion. |
| OMC-004 | Produce outputs convertible to canonical FBX. |
| OMC-005 | Declare supported operations. |
| OMC-006 | Declare supported topology types. |
| OMC-007 | Declare supported complexity controls. |
| OMC-008 | Support vertex-targeted optimization directly or through application-managed processing where applicable. |
| OMC-009 | Preserve intended structure within declared capabilities. |
| OMC-010 | Support independent component processing where applicable. |
| OMC-011 | Declare preservation and regional protection capabilities. |
| OMC-012 | Preserve intentional open geometry where applicable. |
| OMC-013 | Declare UV and material preservation capabilities. |
| OMC-014 | Never require destructive source modification. |
| OMC-015 | Produce independently persistable outputs. |
| OMC-016 | Produce geometry suitable for independent validation. |
| OMC-017 | Operate within configured local resource constraints. |
| OMC-018 | Permit resource reclamation after execution. |
| OMC-019 | Expose completion and failure information. |
| OMC-020 | Satisfy applicable licensing requirements. |

The integrated pipeline shall collectively satisfy MVP requirements. Individual processors need only satisfy applicable declared capabilities. Temporary native formats shall be removed following successful validated conversion when no longer required by an active operation.

## 7.20 Validation assertions

| ID | Test | Expected result |
|---|---|---|
| OMA-001 | Reduce High Density geometry to a Low Density target. | Reduced candidate and actual vertices are reported. |
| OMA-002 | Apply linear subdivision. | Vertex density increases without intentional smoothing. |
| OMA-003 | Apply smooth subdivision. | Increased density and smoothing are measurable. |
| OMA-004 | Produce a result outside its target. | Deviation is reported without automatic deletion. |
| OMA-005 | Measure topology statistics. | Geometric and rendering vertices, polygons, triangles, and edges are independently reported. |
| OMA-006 | Triangulate quad geometry. | Faces are converted into triangles. |
| OMA-007 | Request quad-oriented retopology. | Quad-oriented output is produced or incompatibility is reported. |
| OMA-008 | Retopologize humanoid geometry. | Defining anatomy remains identifiable. |
| OMA-009 | Optimize mechanical geometry. | Protected sharp edges remain within applicable tolerances. |
| OMA-010 | Optimize thin geometry. | Intended open boundaries remain present. |
| OMA-011 | Optimize one component. | Unrelated components remain unchanged. |
| OMA-012 | Optimize with locked components. | Locked geometry remains unchanged. |
| OMA-013 | Apply automatic allocation. | Component targets account for the total budget. |
| OMA-014 | Apply manual allocation. | Individual targets are preserved and reported. |
| OMA-015 | Optimize intentional cavities. | Cavities are not unintentionally filled. |
| OMA-016 | Optimize asymmetric geometry. | Intended asymmetry remains present. |
| OMA-017 | Optimize with grip and pivot metadata. | Associated reference points remain accessible. |
| OMA-018 | Optimize textured geometry. | Surface assignments are preserved or affected assignments identified. |
| OMA-019 | Compare source and optimized geometry. | Both artifacts remain independently accessible. |
| OMA-020 | Synchronize comparison cameras. | Corresponding views remain aligned. |
| OMA-021 | Evaluate surface displacement. | Measured deviation is reported. |
| OMA-022 | Detect a locatable geometry defect. | Defect is highlighted in red. |
| OMA-023 | Complete optimization with defects. | Automatic repair does not execute. |
| OMA-024 | Initiate Safe Repair manually. | Separate repair candidate is produced. |
| OMA-025 | Optimize imported FBX geometry. | Processing completes without AI geometry generation. |
| OMA-026 | Normalize output to FBX. | Valid canonical geometry is produced. |
| OMA-027 | Generate alternative density variant. | Source geometry remains unchanged. |
| OMA-028 | Export selected geometry. | Applicable selected artifacts and metadata are included. |
| OMA-029 | Execute without internet connectivity. | Local processing completes. |
| OMA-030 | Deny a result. | Exclusive files and metadata are deleted. |
| OMA-031 | Expire a pending result. | Retention and complete deletion policies are enforced. |
| OMA-032 | Simulate optimization failure. | Source remains accessible and unchanged. |
| OMA-033 | Execute a configured pipeline. | Operations execute in the specified order. |
| OMA-034 | Simulate intermediate failure. | Dependent operations do not execute. |
| OMA-035 | Protect a selected region. | Protected geometry remains unchanged during compatible processing. |
| OMA-036 | Request budget below protected vertex count. | Conflict is clearly identified. |
| OMA-037 | Generate one LOD. | Unrelated levels remain unchanged. |
| OMA-038 | Configure percentage-based LOD target. | Corresponding vertex target is calculated correctly. |
| OMA-039 | Export selected LOD variants. | Selected FBX and applicable metadata are included. |
| OMA-040 | Optimize textured geometry with defaults. | Preserve Existing is selected. |
| OMA-041 | Detect invalidated UVs. | Affected assignments are flagged without automatic rebaking. |
| OMA-042 | Switch among the four comparison modes. | Correct presentation is displayed. |
| OMA-043 | Submit another optimization during execution. | Additional request is prevented. |
| OMA-044 | Cancel active optimization. | Lock releases after safe termination. |
| OMA-045 | Assign different component profiles. | Each component uses its assigned profile. |

Quantitative accuracy, shape preservation, topology quality, and performance thresholds shall be established in Phase 25. Passing an error-reporting assertion does not establish that an unsupported provider satisfies the corresponding functional capability.

## 7.21 MVP acceptance criteria and approved decisions

Phase 07 shall be considered implemented when the integrated local pipeline supports all seven operations, Standard and Advanced sequential processing, all six processing profiles, vertex-based targets, independent component optimization and locking, binary regional protection, individual LOD generation and selected export, Preserve Existing surface handling by default, the four approved comparison modes, red defect review and manual repair, canonical FBX output, and nondestructive artifact approval and retention. Execution locking shall prevent concurrent conflicting requests as specified above.

| Decision | Final approval |
|---|---|
| D1 | All seven operations included. |
| D2 | Both independent operations and configurable sequential pipelines. |
| D3 | Six processing profiles at asset and component levels. |
| D4 | Regional protection in MVP; Regional Density Priority post-MVP. |
| D5 | Configurable LOD generation included. |
| D6 | Preserve Existing by default; flag affected UVs or textures; no automatic rebaking or regeneration. |
| D7 | Source Only, Side by Side, Overlay, Deviation Heatmap. |
| D8 | Single-request execution locking. |

## 7.22 Technical interpretations and deferred details

The following are proposed implementation details, not separately approved product decisions: blue protected-region overlay; absolute and percentage LOD target controls; synchronized cameras and wireframe as shared viewport controls; stopping dependent pipeline steps on failure; Standard mode as the default; and engine-specific LOD switching deferred to Phase 18. Example LOD percentages are illustrative. Exact topology algorithms, protection selection representation and boundary mapping, geometric measurement algorithms, compatibility tolerances, and processor choices remain unselected. Adaptive subdivision is conditional on compatible tools and does not include user-weighted regional density controls. No specific AI models or implementation libraries have been selected.

Post-MVP: Regional Density Priority, weighted masks, graded regional protection, regional vertex allocation, and direct regional geometry sculpting or inpainting. The approved binary protection capability must not be deferred with these features.

**Next phase:** Phase 08: Modular Mesh Generation and Segmentation.
