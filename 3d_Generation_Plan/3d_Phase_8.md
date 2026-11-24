# Phase 08: Modular Mesh Generation and Segmentation

**Product:** SWIFT Director  
**Workspace:** Asset Generation / 3D Generation  
**Version:** 1.0  
**Design status:** Approved  
**Scope:** MVP unless explicitly deferred

## 8.1 Purpose and scope

The modular mesh workflow shall enable users to generate, segment, extract, reconstruct, import, fit, organize, replace, and independently manage geometry components across all eight approved asset types. Components shall remain individually usable and collectively form compatible assemblies. Removing clothing, for example, shall reveal complete underlying anatomy when a complete modular humanoid is intended, rather than merely exposing holes in a clothed mesh.

All processing shall execute locally, preserve original artifacts, and comply with the canonical FBX interchange standard, vertex-based complexity budgets, manual repair policy, and artifact lifecycle established in Phases 01 through 07. No specific AI model, algorithm, or library is selected by this specification.

## 8.2 Terminology and architecture

| Term | Definition |
|---|---|
| Asset | Complete independently identifiable object or assembly. |
| Base component | Primary geometry used as a foundation for other components. |
| Component | Independently manageable portion of an asset. |
| Subcomponent | Component nested beneath another component. |
| Logical group | Organizational node that need not contain geometry. |
| Geometry island | Disconnected geometric region within a mesh. |
| Segmentation | Identification and assignment of existing geometry regions. |
| Extraction | Creation of independent geometry from selected existing surfaces. |
| Reconstruction | Creation of missing or incomplete geometry. |
| Breakaway component | Independently represented component with dedicated references. |
| Attachment | Spatial relationship between components. |
| Variant | Alternative geometry for a component role. |
| Assembly configuration | Named combination of components, variants, and applicable transforms. |

A component may contain multiple disconnected islands. An island is not automatically a component. Segmentation, extraction, reconstruction, alignment, and geometry fitting are distinct operations. The application shall use the common asset, component, artifact, material, metadata, and relationship entities established in Phase 04.

## 8.3 Modular production workflows and generation modes

| Workflow | Behavior |
|---|---|
| Generate Independently | Generate isolated components from dedicated references. |
| Segment Existing Mesh | Identify existing regions and explicitly extract components. |
| Reconstruct Component | Complete missing or partial geometry through explicit user action. |
| Import Component | Import externally created compatible geometry. |
| Hybrid Assembly | Combine components produced through different methods. |

The production method shall be independently selectable for each component. Hybrid assemblies may use multiple providers. The three established generation modes remain Unified, Automatic Modular, and Directed Modular.

- **MGM-001:** Support all three generation modes and all five production workflows.
- **MGM-002:** Support conversion of Unified geometry into a modular assembly without mandatory full regeneration.
- **MGM-003:** Preserve original source artifacts during conversion.
- **MGM-004:** Automatic Modular mode shall identify recommended semantic components and present them for review.
- **MGM-005:** Directed Modular mode shall accept user-defined components and relationships.
- **MGM-006:** Accept component definitions and applicable breakaway references from Reference Generation.
- **MGM-007:** Support independently generated and imported components.
- **MGM-008:** Support independent component regeneration and production method selection.
- **MGM-009:** Support components originating from different compatible local providers.
- **MGM-010:** Modular conversion shall not automatically approve new artifacts.

Reference imagery shall be created in Image Generation or Reference Generation, not duplicated inside the 3D workspace. Transfer applicable reference IDs, classification, role, directional assignments, and specification metadata without duplicating files or silently approving references. Missing or incompatible inputs shall be disclosed according to Phase 05.

## 8.4 Classification-specific component templates

| Parent classification | Asset type | Recommended component categories |
|---|---|---|
| Actors | Humanoid | Base anatomy, eyes, teeth, tongue, hair, facial hair, clothing, armor, footwear, accessories |
| Actors | Creature | Base anatomy, eyes, teeth, tongue, horns, wings, tail, fur, equipment |
| Scene Assets | Scene Prop | Primary structure, panels, decoration, removable parts |
| Scene Assets | Vehicle | Hull, engines, wheels, tracks, landing gear, doors, glass, exterior accessories |
| Props | Held Prop | Primary body, grip, functional parts, removable attachments |
| Props | Interactive Prop | Primary structure, movable parts, hinges, handles, internal geometry |
| World Assets | Vehicle Interior | Floor, ceiling, walls, controls, seating, doors, fixtures |
| World Assets | Scenery | Foundations, walls, roofs, architectural modules, terrain, vegetation, decoration |

Templates are configurable recommendations, not mandatory component counts. Asset classification, optional independent component classification, semantic role, user-defined label, and applicable subtype shall remain distinct. A clothing role does not introduce a ninth primary asset type. Vehicle remains exterior-only, Vehicle Interior remains interior-only, and Scenery shall use its chosen interior or exterior scope. Combined exterior/interior generation and fitting remain outside MVP.

## 8.5 Component hierarchy

- **MCH-001:** Components shall maintain persistent unique identifiers independent of names and paths.
- **MCH-002:** Support parent-child relationships and nested subcomponents.
- **MCH-003:** Support logical groups without geometry.
- **MCH-004:** Support component creation, renaming, and reorganization.
- **MCH-005:** Reject circular hierarchy relationships.
- **MCH-006:** Preserve hierarchy in the common AssetManifest.json.
- **MCH-007:** Organization shall not require geometry fusion.
- **MCH-008:** Reparenting shall support preserving assembled position, orientation, and scale; disclose transforms that cannot be represented without loss.
- **MCH-009:** Maintain parent-relative transforms and independent geometry references.
- **MCH-010:** Preserve applicable metadata and relationships during hierarchy changes.

## 8.6 Segmentation

| Method | Purpose |
|---|---|
| Connected Geometry | Identify disconnected islands. |
| Material-Based | Identify existing material regions. |
| Semantic | Identify recognizable anatomy, clothing, objects, or mechanical parts. |
| Reference-Guided | Identify regions using compatible supplied visual references. |
| Manual Selection | Allow direct user-defined region assignments. |
| Hybrid | Combine automatic identification with manual correction. |

All six methods are MVP capabilities. Provider-specific methods require compatible local processing. Segmentation initially produces editable region assignments, not modified geometry.

- **MSG-001:** Support connected segmentation.
- **MSG-002:** Support material-based segmentation.
- **MSG-003:** Support semantic segmentation.
- **MSG-004:** Support reference-guided segmentation.
- **MSG-005:** Support manual and hybrid segmentation.
- **MSG-006:** Display identifiable region assignments in the viewport.
- **MSG-007:** Permit correction of automatic assignments before extraction.
- **MSG-008:** Preserve source geometry.
- **MSG-009:** Flag uncertain, unassigned, or conflicting assignments rather than silently inventing certainty.
- **MSG-010:** Segmentation shall not automatically extract or reconstruct geometry.

## 8.7 Shared manual geometry selection

| Tool or mode | Function |
|---|---|
| Brush | Select geometry with adjustable brush size. |
| Rectangle | Select within a rectangular viewport region. |
| Lasso | Select within a freeform boundary. |
| Connected Geometry | Select connected regions. |
| Material Selection | Select geometry sharing material assignments. |
| Expand / Contract | Extend or reduce the current selection. |
| Clear / Invert | Clear the current selection or invert it within its eligible scope. |
| Visible Surface | Restrict selection to visible surfaces. |
| Through Selection | Select eligible geometry through the mesh depth. |

Users shall be capable of adding and removing geometry from component assignments. Selection shall respect applicable locks and identify its owning geometry artifact. Selection overlays shall not alter production textures or materials. Reuse the selection infrastructure established for Phase 07 Regional Protection and extend it for Phase 12 surface painting and Phase 13 regional inpainting. Regional Density Priority remains Post-MVP; shared selection does not imply that weighted regional optimization is included.

## 8.8 Component extraction

| Mode | Result |
|---|---|
| Copy as Component | Independent copy of selected existing geometry; the source representation retains its selected region. |
| Separate as Component | Extracted geometry and corresponding remainder geometry. |
| Extract as New Asset | Independently identifiable asset and manifest with selected geometry. |

- **MEX-001:** Support extraction of manual selections.
- **MEX-002:** Support extraction of automatically segmented regions after review.
- **MEX-003:** Assign independent IDs to extracted components and new assets.
- **MEX-004:** Preserve applicable vertex attributes, normals, UVs, and material assignments; disclose affected data.
- **MEX-005:** Preserve original assembled placement through applicable transforms.
- **MEX-006:** All modes shall preserve original source artifacts.
- **MEX-007:** Identify newly exposed boundaries and incomplete geometry during validation.
- **MEX-008:** Do not automatically close extracted boundaries.
- **MEX-009:** Do not automatically reconstruct missing surfaces.
- **MEX-010:** Make extracted components independently reviewable and exportable.

Copying overlapping geometry into an assembly shall not silently remove or fuse the original region. The application shall make resulting overlap apparent during review.

## 8.9 Component reconstruction and completeness

Reconstruction shall always require explicit user action, including when missing geometry is detected automatically. Extraction alone cannot create surfaces absent from the source. Automatic Modular workflows shall present incomplete components and available reconstruction actions rather than silently completing them.

| Reconstruction action | Purpose |
|---|---|
| Reconstruct Missing Surfaces | Generate missing portions of extracted geometry. |
| Reconstruct Base Component | Generate complete underlying geometry. |
| Complete Component | Complete an incomplete independent mesh. |
| Generate Replacement | Produce an alternative component using applicable references. |

| Completeness status | Meaning |
|---|---|
| Not Evaluated | Completeness has not been assessed. |
| Complete | Meets applicable independent-use requirements. |
| Partial | Contains only part of intended geometry. |
| Reconstruction Required | Missing geometry prevents intended independent use. |
| Review Required | Completeness cannot reliably be determined. |

- **MRC-001:** Support missing geometry reconstruction through compatible local providers.
- **MRC-002:** Support complete underlying base anatomy rather than merely deleting clothing from incomplete geometry.
- **MRC-003:** Support reference-conditioned reconstruction.
- **MRC-004:** Preserve intended scale and proportions.
- **MRC-005:** Preserve compatible attachment relationships.
- **MRC-006:** Identify inferred surfaces as reconstructed, not verified source geometry.
- **MRC-007:** Require explicit initiation for reconstruction.
- **MRC-008:** Produce independent candidates.
- **MRC-009:** Preserve existing components until a replacement is explicitly activated.
- **MRC-010:** Validate reconstructed geometry and assembly compatibility.

Completeness shall be classification-aware and role-aware. Watertightness shall not be universally required. A complete cape may be an open surface. Incomplete geometry remains available for inspection; locatable defects and missing-surface boundaries shall be highlighted in red. Uncertain or unlocatable issues shall be reported textually. Completeness is separate from production status, approval status, and job status.

## 8.10 Component alignment and transforms

| Alignment method | Purpose |
|---|---|
| Preserve Source Transform | Retain source placement. |
| Manual Alignment | Adjust position, rotation, and scale. |
| Bounding Volume Alignment | Estimate placement from geometric bounds. |
| Reference-Guided Alignment | Estimate placement from compatible references. |
| Attachment Point Alignment | Align compatible spatial points. |
| Surface-Assisted Alignment | Position relative to a selected surface. |

- **MAL-001:** Support independent component position, rotation, and scale.
- **MAL-002:** Maintain parent-relative transforms.
- **MAL-003:** Support manual adjustment and reset.
- **MAL-004:** Use canonical right-handed, Y-up, positive-Z-forward coordinates and centimeters.
- **MAL-005:** Use internal quaternion rotation and user-facing Euler degrees.
- **MAL-006:** Do not alter unrelated component geometry during alignment.
- **MAL-007:** Support inherited physical dimensions and distinguish unknown scale.
- **MAL-008:** Present automatic alignment results for review.
- **MAL-009:** Flag significant placement discrepancies.
- **MAL-010:** Support independent transform locks.

## 8.11 Attachment point metadata

Attachment points extend the existing grip and pivot registry without replacing it.

| Reference type | Quantity per owner | Purpose |
|---|---|---|
| Primary Grip | One optional slot | Primary interaction location |
| Secondary Grip | One optional slot | Secondary interaction location |
| Tertiary Grip | One optional slot | Additional interaction location |
| Pivot | One optional slot | Rotation or movement origin |
| Attachment | Variable | Mounting and alignment between independent components |

- **MAT-001:** Assets and components shall support independently identifiable attachment points.
- **MAT-002:** Support multiple attachment points per owner.
- **MAT-003:** Support user-defined labels.
- **MAT-004:** Support semantic roles.
- **MAT-005:** Store position and orientation.
- **MAT-006:** Support enabled and disabled states.
- **MAT-007:** Store coordinates relative to the owning asset or component.
- **MAT-008:** Support manual editing.
- **MAT-009:** Compatible enabled points shall support automatic alignment.
- **MAT-010:** Do not require skeletal rigging.
- **MAT-011:** Preserve attachment metadata in applicable exports.
- **MAT-012:** Attachment metadata shall not create or modify geometry.

Examples include headwear mounts, backpack mounts, engine mounts, doorframe attachments, and accessory mounts. Compatibility across different assets is conditional on geometry and attachment definitions, not guaranteed by matching labels alone.

## 8.12 Assembly compatibility validation

Validate relative scale, orientation, attachment alignment, unexpected intersections, gaps, clearance, completeness, spatial references, and configuration compatibility. Intentional overlaps such as clothing layers, fasteners, and structural joints shall not automatically be classified as defects. Locatable defects shall appear red in review. Visual discrepancies shall be flagged without automatically preventing technically compatible processing. Corrupt or incompatible data may prevent affected operations. No automatic repair or reconstruction shall execute.

## 8.13 Component variants and assembly configurations

- **MCV-001:** Support independently identifiable alternatives for a component role.
- **MCV-002:** Support selection and preview of an active variant.
- **MCV-003:** Variant activation shall not alter unrelated components.
- **MCV-004:** Variants support independent approval and retention.
- **MCV-005:** Preserve applicable role and attachment metadata.
- **MCV-006:** Revalidate replacement compatibility.
- **MCV-007:** Preview variants before activation.
- **MCV-008:** Activation does not constitute retention approval.

- **MAC-001:** Support multiple named assembly configurations.
- **MAC-002:** Store selected component variants.
- **MAC-003:** Store included and excluded components separately from viewport visibility.
- **MAC-004:** Support applicable configuration-specific transforms.
- **MAC-005:** Create, rename, duplicate, and delete configurations.
- **MAC-006:** Switch configurations explicitly.
- **MAC-007:** Switching shall not regenerate existing geometry.
- **MAC-008:** Reference shared artifacts without unnecessary file duplication.
- **MAC-009:** Identify missing or expired references.
- **MAC-010:** Measure independent configuration geometry statistics.
- **MAC-011:** Export selected configurations independently.
- **MAC-012:** Saving a configuration shall not silently approve dependencies.
- **MAC-013:** Reevaluate compatibility when required components change.

Example: Indoor Attire and Outdoor Attire share the same base body, hair, and facial hair, but reference different outer garments and footwear. A configuration is an assembly definition rather than a duplicated asset. Deleting a configuration shall not delete geometry still retained by another valid reference.

## 8.14 Visibility and locking

| Control | Function |
|---|---|
| Visibility | Show or hide a component in the viewport. |
| Geometry Lock | Protect component geometry from processing or replacement. |
| Transform Lock | Protect position, rotation, and scale. |
| Selection Lock | Prevent unintended viewport selection. |

Visibility shall not delete geometry, exclude it from the active assembly budget, or change hierarchy membership. Locks shall not constitute retention approval. Operations affecting protected geometry or transforms shall require explicit unlocking; no operation may silently bypass locks. Configuration switches and hierarchy changes shall disclose conflicts with locks.

## 8.15 Modular vertex budgets

| Profile | Total active assembly geometric vertices |
|---|---:|
| Low Density | 500 to 10,000 |
| Mid Density | 10,001 to 30,000 |
| High Density | 30,001 to 500,000 |

- **MVB-001:** Measure component geometric vertices independently.
- **MVB-002:** Measure the complete active assembly.
- **MVB-003:** Support automatic allocation across eligible components.
- **MVB-004:** Support manual component vertex targets.
- **MVB-005:** Individual components may contain fewer than 500 vertices.
- **MVB-006:** Locked components count toward the active budget.
- **MVB-007:** Inactive variants do not count toward the active budget.
- **MVB-008:** Viewport visibility does not change active assembly statistics.
- **MVB-009:** Recalculate statistics following component replacement or configuration changes.
- **MVB-010:** Independently measure polygons, triangles, edges, and rendering vertices.

Targets are not exact acceptance requirements. Display requested and actual counts, profile deviations, and conflicts with locked or protected geometry. Do not reject geometry solely for target deviation. Count included component instances in the active assembly even when their underlying physical files are shared.

## 8.16 Grouping, joining, and fusion

| Operation | Behavior |
|---|---|
| Group | Logical organization without geometry changes. |
| Join | Combine selected mesh objects while retaining existing surfaces where compatible. |
| Fuse | Explicitly reconstruct connected surfaces through compatible union or welding operations. |

- **MGF-001:** Support logical groups.
- **MGF-002:** Grouping shall not modify geometry.
- **MGF-003:** Grouping shall be reversible.
- **MGF-004:** Support joining selected components.
- **MGF-005:** Preserve existing surfaces during joining where compatible.
- **MGF-006:** Support explicitly initiated fusion.
- **MGF-007:** Warn of potential topology, UV, material, and boundary changes before fusion.
- **MGF-008:** Joining and fusion produce independent derivative artifacts.
- **MGF-009:** Original component artifacts remain unchanged.
- **MGF-010:** Validate joined and fused outputs.
- **MGF-011:** Respect geometry and transform locks.

Fusion shall never occur automatically during assembly.

## 8.17 Component fitting

All three fitting methods are included in MVP.

| Method | Behavior |
|---|---|
| Manual Fitting | User-controlled position, rotation, proportional or independent axis scale, and attachment relationships. |
| Automatic Alignment | Calculate component placement without intentionally modifying mesh topology. |
| Automatic Geometry Fitting | Adapt source geometry to a selected target through compatible local processing. |

Automatic Geometry Fitting shall be explicitly initiated. Potential methods include surface conformity, volume fitting, intersection correction, and reference-guided fitting. Applicable controls may include physical clearance, shape and detail preservation, and topology preservation. Exact methods and controls depend on validated provider capabilities. Target geometry protection is mandatory, not an optional permission to modify the target.

- **MFT-001:** Support manual fitting without requiring AI inference.
- **MFT-002:** Support automatic alignment.
- **MFT-003:** Support automatic geometry fitting through compatible local processing.
- **MFT-004:** Require explicit source and target selection.
- **MFT-005:** Require explicit initiation of geometry fitting.
- **MFT-006:** Preserve original source geometry.
- **MFT-007:** Never modify target geometry during fitting.
- **MFT-008:** Produce reviewable fitted candidates before activation.
- **MFT-009:** Preserve defining source characteristics where possible.
- **MFT-010:** Account for intended attachment relationships.
- **MFT-011:** Support applicable surface clearance requirements.
- **MFT-012:** Validate integrity and assembly compatibility.
- **MFT-013:** Flag unexpected intersections.
- **MFT-014:** Do not automatically remove intentional intersections.
- **MFT-015:** Disclose affected topology, UVs, and texture relationships.
- **MFT-016:** Respect geometry and transform locks.
- **MFT-017:** Do not automatically initiate repair, rebaking, or texture regeneration.
- **MFT-018:** Apply the common artifact lifecycle to fitted geometry.

Static fitting, surface conformity, and intersection correction are MVP capabilities. Comprehensive physics-based clothing simulation, dynamic fabric deformation, and animated collision responses are Post-MVP. Skeletal weight transfer remains subject to later character preparation phases. A static fit does not guarantee animation-ready deformation.

## 8.18 Data structure and persistence

Use the common asset manifest and stable references. The following conceptual example is not a finalized schema:

```json
{
  "componentId": "component-id",
  "assetId": "asset-id",
  "parentComponentId": "parent-id",
  "label": "Pirate Hat",
  "role": "Headwear",
  "classification": {"inherited": true, "assetType": "Humanoid"},
  "productionMethod": "Generate Independently",
  "geometryArtifactId": "geometry-id",
  "activeVariantId": "variant-id",
  "transform": {
    "position": [0, 0, 0],
    "rotationQuaternion": [0, 0, 0, 1],
    "scale": [1, 1, 1]
  },
  "state": {
    "visible": true,
    "geometryLocked": false,
    "transformLocked": false,
    "selectionLocked": false
  },
  "statistics": {"geometricVertices": 1200, "polygonFaces": 1100, "triangles": 2200},
  "completeness": "Not Evaluated",
  "referenceIds": [],
  "attachmentPointIds": [],
  "variantIds": [],
  "validationResults": []
}
```

Attachment records shall include stable ID, owning asset or component ID, label, role, owner-relative position, orientation, and enabled state. Configuration records shall identify included components, variants, and applicable transforms. Segmentation selections shall reference their exact source geometry revision; topology changes may invalidate them and shall be disclosed. Binary geometry and image data remain separate from JSON. No secrets shall enter portable manifests.

## 8.19 Workspace and execution

The unified 3D workspace shall expose component hierarchy, production method, reference assignment, segmentation method and selection tools, extraction actions, completeness and reconstruction actions, alignment and fitting controls, attachment metadata, variant and configuration management, locks, vertex statistics, validation, approval, denial, and export. Reuse the viewport and comparison infrastructure from previous phases. Geometry defects remain red; selection and component assignment overlays shall be distinguishable from defects and production materials.

The single-request execution philosophy of Phases 06 and 07 applies. Each requested processing operation shall produce one reviewable result (which may contain multiple related artifacts, such as component and remainder). Prevent duplicate submissions and conflicting operations on the affected asset through interface and backend locks. Process components sequentially, allow only one active AI inference job per generation server, and release locks only after completion or safe termination. Preserve source artifacts on cancellation or failure. Exact cross-asset deterministic concurrency is deferred to resource and queue design phases.

## 8.20 Artifact lifecycle

New geometry derivatives shall begin Pending and expire 10 days after successful generation unless approved. Denial or expiration shall delete exclusive artifacts and associated generation metadata. Source assets, approved dependencies, and files referenced by other valid retained artifacts remain protected. Shared physical storage shall not imply shared approval. Selection, locks, configuration saving, and exporting shall not silently approve geometry or reset retention.

Required operational dependencies shall be identified in the approval modal with reasons, and approved only after explicit confirmation. Historical provenance alone shall not force source retention. Pending export requires the established warning and confirmation. No indefinite generation history shall be retained. Existing approved artifacts shall not be silently overwritten by component regeneration, fitting, extraction, joining, or fusion.

## 8.21 Export and interoperability

| Profile | Contents |
|---|---|
| Complete Modular Asset | Selected active hierarchy and applicable component geometry. |
| Selected Components | Selected components and applicable metadata. |
| Individual Component | One independently usable component. |
| Unified Geometry | Combined representation of selected assembly; no implicit fusion. |
| Component Variants | Selected alternate representations. |
| Assembly Configuration | Selected named configuration and applicable dependencies. |

| Coordinate mode | Purpose |
|---|---|
| Asset-Space | Preserve placement relative to the complete asset origin. |
| Component-Space | Export relative to the designated component-local origin. |

- **MEC-001:** Support Asset-Space export.
- **MEC-002:** Support Component-Space export.
- **MEC-003:** Permit explicit coordinate mode selection.
- **MEC-004:** Preserve canonical centimeters.
- **MEC-005:** Preserve canonical axes and orientation.
- **MEC-006:** Transform attachment, grip, and pivot metadata consistently with geometry.
- **MEC-007:** Identify coordinate mode in export metadata.
- **MEC-008:** Export shall not modify retained geometry.
- **MEC-009:** Export selected assembly configurations.
- **MEC-010:** Maintain independently accessible FBX component geometry.

Illustrative ZIP structure (only applicable selected artifacts included):

```text
Pirate_Captain_Modular.zip
  AssetManifest.json
  Geometry/Pirate_Captain.fbx
  Components/Base_Body.fbx
  Components/Eyes.fbx
  Components/Teeth.fbx
  Components/Tongue.fbx
  Components/Head_Hair.fbx
  Components/Facial_Hair.fbx
  Components/Pirate_Hat.fbx
  Components/Pirate_Coat.fbx
  Components/Boots.fbx
  Metadata/ComponentHierarchy.json
  Metadata/AttachmentPoints.json
  Metadata/AssemblyConfigurations.json
  Textures/ [applicable texture artifacts]
```

FBX is the sole canonical MVP geometry interchange format. Compatible native intermediate formats shall be converted locally and validated, with unnecessary temporary files removed. Detailed engine-specific export behavior remains in Phase 18.

## 8.22 Provider constraints

The integrated local pipeline shall collectively satisfy MVP capabilities. Individual providers shall satisfy the constraints applicable to their declared roles. Deterministic processing is preferred when sufficient. Automatic provider selection and compatible manual override remain available; unsupported capabilities shall be disclosed before execution.

| ID | Segmentation provider constraint |
|---|---|
| MSM-001 | Support local execution. |
| MSM-002 | Support programmatic requests. |
| MSM-003 | Accept compatible geometry directly or through temporary conversion. |
| MSM-004 | Identify independently manageable regions. |
| MSM-005 | Return usable face, vertex, or region assignments. |
| MSM-006 | Preserve source geometry. |
| MSM-007 | Semantic providers identify recognizable components. |
| MSM-008 | Semantic providers communicate uncertainty. |
| MSM-009 | Reference-guided providers consume declared inputs. |
| MSM-010 | Outputs support independent extraction and review. |

| ID | Component generation provider constraint |
|---|---|
| MCM-001 | Support local inference. |
| MCM-002 | Support independently generated component meshes. |
| MCM-003 | Accept applicable component references. |
| MCM-004 | Preserve defining component characteristics. |
| MCM-005 | Support isolated component generation. |
| MCM-006 | Preserve or support compatible scale and orientation. |
| MCM-007 | Produce geometry convertible to FBX. |
| MCM-008 | Support independent component processing. |
| MCM-009 | Declare supported classifications and roles. |
| MCM-010 | Produce independently validatable geometry. |

| ID | Reconstruction, alignment, and fitting provider constraint |
|---|---|
| MRM-001 | Reconstruction providers accept existing partial geometry or applicable references. |
| MRM-002 | Produce independently accessible completed geometry. |
| MRM-003 | Preserve applicable structural characteristics. |
| MRM-004 | Do not require destructive modification of approved sources. |
| MRM-005 | Alignment providers return usable component transformations. |
| MRM-006 | Support canonical coordinate normalization. |
| MRM-007 | Declare applicable limitations, input requirements, and preservation capabilities. |
| MRM-008 | Comply with local resource management and licensing requirements. |
| MRM-009 | Fitting providers accept explicitly selected source and target geometry. |
| MRM-010 | Fitting providers produce independent source derivatives without modifying targets. |
| MRM-011 | Declare supported clearance, topology, and surface preservation controls. |
| MRM-012 | Support validation of resulting geometry and compatibility. |

## 8.23 Validation assertions

The following assertions define tests to be performed during implementation and provider evaluation. They are not completed test results. Quantitative tolerances and performance benchmarks shall be established in Phase 25.

| ID | Test | Expected result |
|---|---|---|
| MMA-001 | Segment disconnected islands. | Connected regions are independently identified. |
| MMA-002 | Segment by material. | Applicable material regions are identified. |
| MMA-003 | Semantically segment a clothed humanoid. | Recognizable anatomy and clothing regions are identified. |
| MMA-004 | Correct an automatic assignment. | Updated assignment is retained. |
| MMA-005 | Segment without extraction. | Original mesh remains unchanged. |
| MMA-006 | Submit ambiguous geometry. | Uncertain assignments are reported. |
| MMA-007 | Extract a selected region. | Independent component geometry is produced. |
| MMA-008 | Separate a component. | Component and remainder artifacts are accessible. |
| MMA-009 | Extract incomplete underlying surfaces. | Missing or uncertain surfaces are identified. |
| MMA-010 | Reconstruct a partial component. | Independent reconstructed candidate is produced. |
| MMA-011 | Generate complete base anatomy. | Required anatomy exists independently of clothing. |
| MMA-012 | Extract intentionally open geometry. | Intended open surfaces remain present. |
| MMA-013 | Import an independent component. | Component becomes available for assembly. |
| MMA-014 | Adjust component alignment. | Position, rotation, and scale are independently configurable. |
| MMA-015 | Reparent a component. | Assembled placement can be preserved. |
| MMA-016 | Align compatible attachment points. | Compatible transforms are calculated. |
| MMA-017 | Replace an active variant. | Unrelated components remain unchanged. |
| MMA-018 | Hide clothing on a complete modular actor. | Complete underlying geometry is accessible. |
| MMA-019 | Detect unexpected penetration. | Locatable affected regions are flagged in red. |
| MMA-020 | Assemble intentional overlaps. | No automatic repair occurs. |
| MMA-021 | Regenerate an unlocked component. | Locked components remain unchanged. |
| MMA-022 | Move a transform-locked component. | Unintended transform changes are prevented. |
| MMA-023 | Activate another component variant. | Active assembly statistics update. |
| MMA-024 | Hide an active component. | Complete active vertex count remains unchanged. |
| MMA-025 | Optimize one component. | Unrelated geometry remains unchanged. |
| MMA-026 | Transfer Advanced reference project. | Breakaway rows can be assigned to components. |
| MMA-027 | Export an individual component. | Canonical FBX is accessible independently. |
| MMA-028 | Export a complete assembly. | Applicable hierarchy, geometry, and metadata are preserved. |
| MMA-029 | Execute modular generation offline. | Processing completes locally. |
| MMA-030 | Deny a candidate. | Exclusive files and generation metadata are deleted. |
| MMA-031 | Simulate component generation failure. | Retained components remain unchanged. |
| MMA-032 | Unload provider. | Generated artifacts remain accessible. |
| MMA-033 | Assign different production methods. | Each component uses its selected workflow. |
| MMA-034 | Copy selected source geometry. | Independent component is produced; original remains unchanged. |
| MMA-035 | Extract as a new asset. | Independent identity and manifest are created. |
| MMA-036 | Detect incomplete extracted geometry. | Missing geometry is flagged and reconstruction options are available. |
| MMA-037 | Segment geometry with missing surfaces. | No automatic reconstruction executes. |
| MMA-038 | Use through-selection. | Eligible geometry behind visible surfaces is selectable. |
| MMA-039 | Create multiple attachment points. | Each remains independently configurable. |
| MMA-040 | Disable an attachment point. | It is excluded from applicable alignment. |
| MMA-041 | Save multiple assembly configurations. | Each retains its component selections. |
| MMA-042 | Switch configurations. | Shared geometry remains unchanged. |
| MMA-043 | Delete a configuration. | Geometry retained by other valid references remains accessible. |
| MMA-044 | Group components. | Geometry files remain unchanged. |
| MMA-045 | Join components. | Independent combined geometry is produced. |
| MMA-046 | Fuse components. | Independent reconstructed geometry is produced and validated. |
| MMA-047 | Manually fit a component. | Requested transforms are applied. |
| MMA-048 | Automatically align a component. | Placement is calculated without intentional topology changes. |
| MMA-049 | Automatically fit a garment to base geometry. | Independent adapted geometry candidate is produced. |
| MMA-050 | Compare target before and after fitting. | Target geometry remains unchanged. |
| MMA-051 | Fit a textured component. | Affected UV and texture relationships are reported. |
| MMA-052 | Export multiple components in Asset-Space. | Assembled positions remain compatible. |
| MMA-053 | Export in Component-Space. | Designated local origin is used. |
| MMA-054 | Export a named configuration. | Selected components and applicable dependencies are included. |

## 8.24 MVP acceptance criteria

Phase 08 implementation shall be accepted when the integrated local pipeline supports all eight asset types, all three generation modes, all five production workflows, all six segmentation methods, all three extraction modes, explicit reconstruction, complete underlying base anatomy, shared manual selection, nested hierarchy, attachment points, variants, assembly configurations, grouping, joining, fusion, all three fitting methods, independent and assembled vertex budgets, both export coordinate modes, and canonical FBX output. It shall preserve original artifacts, enforce locks and lifecycle policies, report completeness and compatibility discrepancies, and provide independent review before activation or retention. Automatic repair, reconstruction, fusion, and texture regeneration shall not occur implicitly. Applicable provider constraints and validation assertions must be satisfied, not merely displayed in the interface.

## 8.25 Approved decisions and implementation boundaries

| Decision | Final requirement |
|---|---|
| D1 | All five workflows, independently selectable production method per component. |
| D2 | All six segmentation methods. |
| D3 | All three extraction modes. |
| D4 | Manual reconstruction only, with clear flags and reconstruction actions. |
| D5 | Shared manual selection tools and visible/through selection. |
| D6 | Independent attachment metadata with variable point count. |
| D7 | Component variants and named assembly configurations. |
| D8 | Group, Join, and Fuse. |
| D9 | Manual Fitting, Automatic Alignment, and Automatic Geometry Fitting. |
| D10 | Asset-Space and Component-Space exports. |

The following are technical interpretations for implementation verification rather than additional individually approved settings:

- Named configurations reference existing artifacts instead of duplicating geometry and may retain configuration-specific transforms.
- Geometry fitting changes only the source derivative, never the target. Detailed clearance, conformity, and preservation controls depend on validated provider capabilities.
- Proposed export defaults: Asset-Space for complete assemblies and Component-Space for individual reusable components. Both remain selectable.
- Selection masks are source-revision-specific; exact remapping methods, attachment matching conventions, component instance counting implementation, and lock interactions require implementation verification.
- Comprehensive physics-based fitting, dynamic clothing deformation, animated collision response, regional geometry sculpting, and regional density priorities remain Post-MVP. Skeletal weight transfer is addressed in later character preparation design.
- Provider selection, exact algorithms, file schema, numerical tolerances, cross-asset concurrency, and engine-specific export settings remain deferred. No implementation or tests are represented as completed.

**Next design phase:** Phase 09: UV Mapping.
