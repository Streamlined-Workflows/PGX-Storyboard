# Phase 09: UV Mapping

**Product:** SWIFT Director | Asset Generation | 3D Generation  
**Version:** 1.0  
**Status:** Finalized design, implementation pending  
**Dependencies:** Phases 01 through 08 and Reference Generation Design

## 9.1 Purpose and scope

The UV Mapping workflow shall establish, inspect, modify, validate, and manage the relationship between three-dimensional geometry and two-dimensional texture coordinates. It shall provide the foundation for texture generation, material application, direct surface painting, regional texture generation, and external interoperability.

Users shall be able to process imported or generated geometry independently of geometry generation. All processing shall execute locally, preserve original artifacts, and produce independently reviewable derivatives. FBX remains the canonical MVP geometry interchange format. UV mapping shall not automatically generate or rebake textures.

## 9.2 Terminology

| Term | Definition |
|---|---|
| UV coordinate | Two-dimensional texture coordinate associated with a mesh surface, typically stored per face corner or equivalent representation. |
| UV seam | Boundary at which UV continuity is separated; not necessarily a physical mesh cut. |
| UV island | Connected region of a flattened UV layout. |
| Unwrapping | Parameterization of a three-dimensional surface into two-dimensional texture space. |
| Packing | Arrangement of UV islands within available texture space. |
| Texel density | Texture resolution allocated per unit of physical surface length or area. |
| Padding | Separation between islands or applicable texture boundaries. |
| Overlap | Multiple mapped surfaces occupying the same texture coordinates. |
| UV channel | Independently stored set of UV coordinates. |
| Texture set | Collection of texture maps associated with a defined surface or material mapping. |
| Texture atlas | Shared texture layout containing multiple surface regions or components. |
| UDIM | Convention for organizing UV coordinates across multiple numbered texture tiles. |

## 9.3 Workflow lifecycle

1. Select existing canonical geometry and its applicable component or asset revision.
2. Analyze existing UV channels, seams, islands, and surface dependencies.
3. Select the operation, processing profile, scope, channel, texture set, and applicable settings.
4. Generate, preserve, or edit seams as required.
5. Unwrap selected surfaces or perform the requested independent UV operation.
6. Pack islands where requested, respecting locks and pins.
7. Validate UV coverage, distortion, overlap, padding, and surface compatibility.
8. Review the result in the 3D View or Split View, then approve, deny, export, or process again.

Not every operation requires every step. Repacking existing islands shall not require a complete unwrap. Validation shall remain independently executable without modifying geometry or UV coordinates.

## 9.4 Supported UV operations

| ID | Requirement |
|---|---|
| UOP-001 | Support independent UV operations on imported and generated geometry. |
| UOP-002 | Generate UV maps for geometry without suitable UV coordinates. |
| UOP-003 | Preserve and inspect existing UV coordinates. |
| UOP-004 | Support complete re-unwrapping and partial unwrapping of selected regions or components. |
| UOP-005 | Support seam generation and manual seam editing. |
| UOP-006 | Support island repacking independently of unwrapping. |
| UOP-007 | Support texel density normalization and manual allocation. |
| UOP-008 | Support UV channel creation, selection, renaming, duplication, and removal. |
| UOP-009 | Support compatible UV transfer between geometry revisions. |
| UOP-010 | Support nondestructive UV validation. |
| UOP-011 | UV operations shall not intentionally alter geometric vertex positions or physical topology. UV seams may affect expanded rendering vertex counts. |
| UOP-012 | UV changes shall produce independently reviewable derivatives and preserve source geometry and UV data. |
| UOP-013 | UV operations shall not automatically generate or rebake textures. |

## 9.5 UV unwrapping methods

All seven methods are included in the MVP. Users may assign methods to complete assets, individual components, or selected regions where compatible.

| ID | Method | Primary application |
|---|---|---|
| UUM-001 | Automatic | General-purpose automatic seam selection and parameterization. |
| UUM-002 | Seam-Based | Explicit seam definitions for organic and complex surfaces. |
| UUM-003 | Planar | Flat surfaces and directional projection. |
| UUM-004 | Box | Rectangular and hard-surface geometry. |
| UUM-005 | Cylindrical | Pipes, handles, barrels, and tubular surfaces. |
| UUM-006 | Spherical | Rounded or approximately spherical geometry. |
| UUM-007 | View Projection | Projection from a selected viewport orientation. |
| UUM-008 | Method selection | Users shall explicitly select the method or automatic method. |
| UUM-009 | Compatibility | Providers shall declare supported methods and input constraints. |
| UUM-010 | Preservation | Unwrapping shall preserve source geometry, component relationships, and unrelated UV assignments. |

## 9.6 Classification and processing profiles

Reuse the six Phase 07 profile names with independently configurable UV settings. The UV profile may inherit the geometry processing profile as a recommendation, with user override at asset and component level.

| Profile | UV priority |
|---|---|
| General Purpose | Balanced distortion and texture utilization. |
| Organic / Deformable | Anatomical continuity, low distortion around deformation regions. |
| Hard Surface | Mechanical boundaries and sharp transitions. |
| Environmental / Structural | Efficient planar mapping and consistent texture density. |
| Thin Surface | Continuity across open or thin surfaces. |
| Custom | User-defined seam, unwrapping, and packing settings. |

| Asset type | Mapping priorities |
|---|---|
| Humanoid | Facial continuity, anatomical seams, deformation compatibility. |
| Creature | Limb separation, curved surfaces, anatomical continuity. |
| Scene Prop | Efficient packing and material-specific allocation. |
| Vehicle | Mechanical panel boundaries, exterior surfaces. |
| Held Prop | Grip and visible functional surfaces. |
| Interactive Prop | Independent moving components and exposed surfaces. |
| Vehicle Interior | Interior-facing surfaces and consistent density. |
| Scenery | Large planar surfaces, repeating materials, modular mapping. |

These are recommendations, not new asset classifications or guarantees of animation-ready topology.

## 9.7 Seam management

| ID | Requirement |
|---|---|
| USM-001 | Support automatic seam generation. |
| USM-002 | Support manual seam marking and removal through edge selection. |
| USM-003 | Support seam generation from material boundaries. |
| USM-004 | Support seam recommendations from sharp-edge detection. |
| USM-005 | Support use of component boundaries as seams. |
| USM-006 | Preserve existing seam definitions where available. |
| USM-007 | Display seams in the viewport and allow correction of automatic recommendations. |
| USM-008 | Reuse shared geometry selection infrastructure from Phases 07 and 08, extending it to edge-level selection. |
| USM-009 | Associate seam definitions with the relevant geometry revision. |
| USM-010 | Seam editing shall not physically cut the underlying mesh. |
| USM-011 | Distinguish imported explicit seam metadata from inferred UV discontinuities when explicit seam metadata is unavailable. |

## 9.8 UV island management

The 2D UV Editor shall be available within Split View. All approved island capabilities shall be included.

| ID | Requirement |
|---|---|
| UIM-001 | Support single and multiple island selection. |
| UIM-002 | Support island translation, rotation, and scaling. |
| UIM-003 | Support explicit mirroring and alignment. |
| UIM-004 | Support compatible stitching and splitting of UV regions. |
| UIM-005 | Support independent island locking. |
| UIM-006 | Locked islands shall remain unchanged during compatible processing. |
| UIM-007 | Support individual UV coordinate pinning. |
| UIM-008 | Pinned coordinates shall remain unchanged during compatible unwrapping. |
| UIM-009 | Support island normalization and texel density adjustment. |
| UIM-010 | Synchronize island selections with corresponding 3D geometry. |
| UIM-011 | UV island edits shall not move physical geometry. |
| UIM-012 | Unsupported lock or pin constraints shall be disclosed before execution; protected coordinates shall not be silently changed. |

## 9.9 Packing and texture resolution

The approved square texture resolutions are 512, 1024, 2048, and 4096 pixels per side. UV coordinates are resolution-independent, but pixel padding and texel density depend on target resolution. Selecting a target resolution does not generate a texture.

| ID | Requirement |
|---|---|
| UPK-001 | Support automatic packing and manual arrangement. |
| UPK-002 | Support configurable island padding in pixels at the selected resolution. |
| UPK-003 | Convert pixel padding to normalized UV distance using the applicable texture dimensions. |
| UPK-004 | Support optional island rotation or preservation of orientation. |
| UPK-005 | Respect locked islands and pinned coordinates where applicable. |
| UPK-006 | Measure occupied texture area and report utilization. |
| UPK-007 | Identify unintended overlap and insufficient padding. |
| UPK-008 | Report constraints preventing successful placement, including insufficient available space. |
| UPK-009 | Packing shall not automatically regenerate or rebake textures. |
| UPK-010 | Validate packing results independently of provider claims. |

## 9.10 Texel density management

All three density controls are approved: Uniform Density, Manual Island Scaling, and Component Priority.

| ID | Requirement |
|---|---|
| UTD-001 | Measure texel density where reliable physical dimensions are available. |
| UTD-002 | Support normalization toward consistent density across applicable surfaces. |
| UTD-003 | Support independent island scaling. |
| UTD-004 | Support component-level texture allocation and priority. |
| UTD-005 | Account for texture resolution and mapped surface area. |
| UTD-006 | Identify inconsistent density and report requested versus measured results. |
| UTD-007 | Protect locked islands during normalization. |
| UTD-008 | Do not represent physical texel density as verified if physical scale is unknown. Relative density may still be reported. |
| UTD-009 | Component Priority in MVP shall operate on independent texture sets through resolution selection and applicable island allocation, not cross-component atlas packing. |
| UTD-010 | Density changes shall not increase or decrease geometric vertex count. |

Regional geometry density priority remains Post-MVP under Phase 07. Texture density is a separate concept.

## 9.11 Modular texture layout strategy

**Approved D4:** Independent component UV layouts and texture sets shall be the standard architecture for newly generated MVP modular assets. Shared Atlas and Hybrid generation are explicitly deferred until Post-MVP. The decision is finalized, not pending.

| Capability | Scope |
|---|---|
| Independent component UV layouts and texture sets | MVP |
| Multiple material assignments per component | MVP |
| Different texture resolutions per component | MVP |
| Preserve imported shared UV layouts and dependencies | MVP |
| Shared Atlas generation | Post-MVP |
| Hybrid texture layout generation | Post-MVP |
| Conversion of independent textures into shared atlases | Post-MVP |
| Texture Atlas Optimization for production or export | Post-MVP |

| ID | Requirement |
|---|---|
| UMM-001 | Each newly generated modular component shall support independent UV layouts and texture sets. |
| UMM-002 | Components shall remain independently mappable, replaceable, and textureable. |
| UMM-003 | Support multiple material assignments and applicable texture sets per component. |
| UMM-004 | Support independent component texture resolution settings. |
| UMM-005 | Preserve compatible existing shared layouts on imported assets without requiring atlas generation. |
| UMM-006 | Identify affected components and dependencies when an imported shared layout is edited. |
| UMM-007 | Component replacement shall not silently alter unrelated UV layouts. |
| UMM-008 | UV layouts shall identify their applicable geometry variants and texture sets. |
| UMM-009 | Named assembly configurations shall resolve applicable component and texture set references without unnecessary duplication. |
| UMM-010 | Preserve approved source UV data until a replacement is explicitly selected under the established lifecycle. |
| UMM-011 | Keep the data architecture extensible for future atlas and hybrid mapping without requiring their implementation in MVP. |

## 9.12 UV channels

| ID | Requirement |
|---|---|
| UCH-001 | Detect existing UV channels. |
| UCH-002 | Support multiple user-defined, independently editable UV channels. |
| UCH-003 | Support channel creation, naming, duplication, selection, and removal. |
| UCH-004 | Editing one channel shall not modify unrelated channels. |
| UCH-005 | Material assignments shall identify applicable UV channels. |
| UCH-006 | Identify dependencies before removing a referenced channel. |
| UCH-007 | Preserve supported channels through canonical FBX export and import. |
| UCH-008 | Disclose provider, viewport, and export channel limitations. No arbitrary application-wide maximum is established. |

Example channels include UV 0 for surface materials, UV 1 for lightmaps, and additional user-defined channels. These names are examples, not mandatory channel assignments.

## 9.13 Texture space and UDIM

Standard single-tile UV space and multiple independent texture sets are included in MVP. Newly generated unique layouts shall normally occupy normalized 0 to 1 texture space. Imported repeating or intentionally out-of-range mappings shall be identified and preserved where compatible, rather than silently clamped.

UDIM multi-tile authoring, generation, packing, and dedicated rendering support are deferred until Post-MVP. Unsupported imported UDIM layouts shall be disclosed; preservation of raw compatible coordinates does not imply full UDIM support.

## 9.14 UV overlap management

| Policy | Behavior |
|---|---|
| Unique UVs | Default for newly generated layouts; attempt non-overlapping coordinates. |
| Allow Intentional Overlap | Permit explicitly authorized shared coordinates. |
| Preserve Existing | Retain existing mappings and flag potential conflicts. |

| ID | Requirement |
|---|---|
| UOL-001 | Detect measurable UV overlap within the applicable channel and shared sampling domain. Independent texture sets shall not be treated as overlapping merely because both use 0 to 1 coordinates. |
| UOL-002 | Distinguish intentional, unintended, and unclassified overlap. |
| UOL-003 | Allow users to mark and revoke intentional overlap. |
| UOL-004 | Highlight confirmed unintended overlap in red. |
| UOL-005 | Do not automatically classify authorized overlap as defective. |
| UOL-006 | Warn that painting or generating unique details on shared coordinates may affect multiple surfaces. |
| UOL-007 | Do not automatically repair overlaps. |
| UOL-008 | Support stricter non-overlap requirements for lightmap or other unique-coordinate channels. |

## 9.15 UV distortion and integrity analysis

Automatic validation shall evaluate applicable UV defects without modifying the source or candidate.

| Category | Validation objective |
|---|---|
| Stretching and compression | Measure changes in local scale. |
| Angular distortion | Measure changes in local angles. |
| Overlap | Identify conflicting or authorized shared coordinates. |
| Missing coordinates | Identify unmapped faces or corners. |
| Invalid coordinates | Detect nonfinite or malformed UV values. |
| Degenerate UV faces | Identify collapsed or unusable texture area. |
| Padding | Detect insufficient island or boundary spacing. |
| Out-of-bounds islands | Identify coordinates inconsistent with intended layout policy. |
| Flipped orientation | Identify reversed coordinates and distinguish intentional mirroring. |
| Texel density | Measure inconsistencies in texture allocation. |
| Coverage and utilization | Report mapped geometry coverage and occupied texture area separately. |

Confirmed locatable defects shall be highlighted in red during review. Checkerboard previews shall reveal visible mapping distortion. Measured distortion heatmaps shall use a separate color scale and shall not be represented as AI-generated estimates. Intentional overlap, mirroring, or valid repeating mappings shall not automatically be classified as defects.

## 9.16 Manual UV repair

| ID | Requirement |
|---|---|
| URP-001 | Automatic UV validation shall be enabled. |
| URP-002 | Automatic UV repair shall be disabled. |
| URP-003 | Provide explicit Safe UV Repair and Advanced UV Repair controls. |
| URP-004 | Safe UV Repair shall correct supported technical defects with minimal impact on unaffected UV regions. |
| URP-005 | Advanced UV Repair may re-unwrap, repack, or reconstruct selected UV regions after explicit user initiation. |
| URP-006 | Both operations shall produce independent candidates and preserve original geometry and UV data. |
| URP-007 | Report applied changes and revalidate repaired candidates. |
| URP-008 | Repair shall respect locks and pins and disclose incompatible operations. |
| URP-009 | Neither repair mode shall automatically generate or rebake textures. |
| URP-010 | Unusable UV data may prevent incompatible downstream operations; visual discrepancies alone shall not cause automatic deletion. |

## 9.17 UV mapping workspace

Exactly two primary workspace views are included in MVP.

| View | Purpose |
|---|---|
| 3D View | Full-width geometry inspection, seam editing, surface selection, checkerboard previews, and defect visualization. |
| Split View | Synchronized 3D viewport and interactive 2D UV Editor. |

A standalone UV Editor view is excluded from MVP. The 2D editing tools remain fully accessible in Split View.

| ID | Requirement |
|---|---|
| UUI-001 | Provide the shared 3D geometry viewport. |
| UUI-002 | Provide Split View with interactive 2D UV editing. |
| UUI-003 | Synchronize applicable geometry and UV selections bidirectionally. |
| UUI-004 | Support checkerboard preview, seams, and defect display controls. |
| UUI-005 | Support measured UV distortion heatmap inspection. |
| UUI-006 | Support channel, component, texture set, and region selection. |
| UUI-007 | Expose applicable unwrapping, seam, packing, and island controls. |
| UUI-008 | Display UV statistics, coverage, utilization, and validation results. |
| UUI-009 | Support explicit repair controls and independent operation execution. |
| UUI-010 | Support candidate review, approval, denial, and export. |
| UUI-011 | Preview overlays shall not modify production textures or materials. |

A resizable Split View divider is a proposed usability detail, not an additional workspace mode.

## 9.18 Existing surface data and dependencies

Changing UV coordinates may invalidate the appearance of existing textures even when physical geometry is unchanged. Moving, rotating, scaling, re-unwrapping, or repacking islands changes where texture data is sampled. Creating a separate UV channel may avoid disturbing existing assignments.

| ID | Requirement |
|---|---|
| USD-001 | Detect existing material, texture, and UV channel dependencies. |
| USD-002 | Identify operations that may invalidate texture alignment. |
| USD-003 | Inform users of affected surface assignments before execution. |
| USD-004 | Preserve original materials, textures, and geometry artifacts. |
| USD-005 | Never automatically generate replacement textures or rebake existing textures. |
| USD-006 | Support independently retained UV derivatives. |
| USD-007 | Allow creating a new channel without replacing existing channels. |
| USD-008 | Identify affected assignments during review and distinguish preserved, affected, uncertain, and missing dependencies. |
| USD-009 | Respect existing shared artifact approval and replacement safeguards from Phase 04. |

## 9.19 UV transfer between geometry revisions

Geometry optimization, component fitting, reconstruction, and LOD generation may produce new geometry requiring compatible UV information.

| Method | Behavior |
|---|---|
| Direct Correspondence | Transfer coordinates using verified matching geometry relationships. |
| Surface Projection | Transfer using spatial correspondence between source and target surfaces. |
| Reference-Guided Transfer | Use compatible reference-conditioned processing where available. |

| ID | Requirement |
|---|---|
| UTR-001 | Support compatible UV transfer between geometry revisions. |
| UTR-002 | Support transfer to optimized geometry. |
| UTR-003 | Support transfer to LOD variants. |
| UTR-004 | Support transfer to fitted components where compatible. |
| UTR-005 | Preserve original source and target artifacts. |
| UTR-006 | Identify uncertain or failed correspondence; do not report unsuccessful transfer as successful. |
| UTR-007 | Validate transferred coordinates and applicable channels. |
| UTR-008 | Identify affected texture alignment and downstream dependencies. |
| UTR-009 | Do not automatically rebake textures. |

## 9.20 UV data structure and persistence

UV coordinates shall be embedded in canonical FBX geometry where supported. Separate UV metadata shall extend the common asset manifest without introducing incompatible storage or duplicating binary geometry unnecessarily. UV identifiers shall reference the applicable geometry revision, component, channel, and texture set.

Illustrative metadata, not a finalized schema:

```json
{
  "uvLayoutId": "uv-layout-unique-id",
  "geometryArtifactId": "geometry-artifact-id",
  "componentId": "component-unique-id",
  "textureSetId": "texture-set-unique-id",
  "channel": {"index": 0, "label": "Surface Materials"},
  "configuration": {
    "unwrapMethod": "SeamBased",
    "targetResolution": 2048,
    "paddingPixels": 8,
    "overlapPolicy": "UniqueUVs"
  },
  "statistics": {
    "islandCount": 24,
    "surfaceCoverage": 1.0,
    "textureUtilization": 0.814
  },
  "seamDefinitions": [],
  "lockedIslandIds": [],
  "pinnedUVIds": [],
  "validationResults": []
}
```

| ID | Requirement |
|---|---|
| UDP-001 | UV layouts shall have persistent unique identifiers. |
| UDP-002 | Associate layouts with applicable geometry revisions, components, channels, and texture sets. |
| UDP-003 | Retain seam definitions, locks, pins, intentional overlap declarations, and validation metadata where applicable. |
| UDP-004 | New UV derivatives shall initially enter Pending state. |
| UDP-005 | Pending derivatives expire 10 days after successful generation unless approved. |
| UDP-006 | Denied or expired derivatives and exclusive metadata shall be deleted in accordance with the established lifecycle. |
| UDP-007 | Required operational dependencies shall participate in explicit dependency approval; historical provenance alone shall not require retention. |
| UDP-008 | UV changes shall not overwrite approved source artifacts. |
| UDP-009 | Selecting, locking, or exporting a pending layout shall not approve it or reset its retention period. |
| UDP-010 | Shared files shall remain protected while required by valid retained artifacts. |

## 9.21 Execution locking and resource management

Follow the established single-request execution philosophy. Each submitted UV processing request shall produce one final candidate. Additional UV submissions shall be locked during active execution. Geometry generation, optimization, and component geometry changes affecting the active asset shall be prevented during UV processing.

Frontend and backend shall enforce locking. Completion, failure, or cancellation shall release the lock only after processing terminates safely. Existing source artifacts shall remain available for nondestructive inspection. Manual editing shall not require AI inference. AI-assisted operations shall use the shared local server resource restrictions, with no concurrent AI inference jobs on the same generation server. Providers shall release computational resources following execution. No external inference or cloud processing is permitted.

## 9.22 Export and interoperability

All four export profiles are included in MVP.

| Export profile | Format | Contents |
|---|---|---|
| Geometry with UVs | FBX | Canonical geometry with applicable embedded UV channels. |
| UV Layout | PNG | Selected UV layout reference image. |
| Component UV Package | ZIP | Selected component geometry, layouts, and applicable metadata. |
| Complete UV Package | ZIP | Selected geometry, UV layouts, texture set definitions, and applicable metadata. |

PNG layout images shall support 512, 1024, 2048, and 4096 square resolutions and transparent backgrounds. Export shall preserve applicable channels, canonical units, axis conventions, hierarchy, and component-space or asset-space conventions established in Phase 08. Layout images are visual references, not substitutes for machine-readable UV coordinates.

Illustrative package:

```text
Pirate_Captain_UV_Package.zip
  AssetManifest.json
  Geometry/Pirate_Captain.fbx
  Components/Base_Body.fbx
  Components/Pirate_Hat.fbx
  Components/Pirate_Coat.fbx
  UV_Layouts/Base_Body_UV0.png
  UV_Layouts/Pirate_Hat_UV0.png
  UV_Layouts/Pirate_Coat_UV0.png
  Metadata/UVManifest.json
  Metadata/TextureSets.json
  Metadata/UVValidation.json
```

Only applicable selected artifacts and required dependencies shall be included. Pending exports shall display the established retention warning and require confirmation without approving artifacts or resetting expiration. Export shall not automatically unwrap, pack, generate atlases, regenerate textures, or rebake textures.

## 9.23 Provider constraints

Deterministic local processing shall be preferred where it can satisfy the requested operation. Compatible AI-assisted providers may be used for operations that benefit from inference. Automatic compatible provider selection and advanced manual override shall follow the common provider architecture. A provider need only satisfy constraints applicable to its declared capabilities; the integrated MVP pipeline shall collectively meet the required capabilities.

| ID | Constraint |
|---|---|
| UMC-001 | Support local execution. |
| UMC-002 | Support programmatic processing. |
| UMC-003 | Accept canonical FBX directly or through temporary compatible conversion. |
| UMC-004 | Produce UV information compatible with canonical FBX output. |
| UMC-005 | Declare supported unwrapping methods. |
| UMC-006 | Preserve physical geometry positions and topology. |
| UMC-007 | Permit independent UV layout validation. |
| UMC-008 | Declare seam-generation capabilities. |
| UMC-009 | Declare UV packing capabilities. |
| UMC-010 | Support configurable padding where applicable. |
| UMC-011 | Declare island locking and UV pinning capabilities. |
| UMC-012 | Support applicable component and region-specific processing. |
| UMC-013 | Declare supported texture space configurations. |
| UMC-014 | Declare UV channel support and limitations. |
| UMC-015 | Produce usable UV coordinate outputs. |
| UMC-016 | Declare intentional overlap capabilities. |
| UMC-017 | Support or permit independent distortion measurement. |
| UMC-018 | Declare UV transfer capabilities where applicable. |
| UMC-019 | Preserve original source artifacts. |
| UMC-020 | Operate within configured local resource limits. |
| UMC-021 | Support resource reclamation following execution. |
| UMC-022 | Expose sufficient completion and failure information. |
| UMC-023 | Satisfy applicable licensing requirements. |
| UMC-024 | Require no external inference or cloud processing after provisioning. |

## 9.24 Validation assertions

These are specification-level acceptance tests, not completed implementation tests. Quantitative tolerances and benchmarks remain reserved for Phase 25. A provider incompatibility report is not equivalent to successful execution of a required MVP capability; the integrated pipeline must demonstrate the approved capabilities.

| ID | Test | Expected result |
|---|---|---|
| UMA-001 | Automatically unwrap geometry without existing UVs. | Valid UV coordinates are produced. |
| UMA-002 | Unwrap using manually defined seams. | Applicable seam definitions are respected. |
| UMA-003 | Apply planar projection. | Suitable directional coordinates are produced. |
| UMA-004 | Apply cylindrical projection. | Cylindrical surfaces receive applicable coordinates. |
| UMA-005 | Apply spherical projection. | Rounded geometry receives applicable coordinates. |
| UMA-006 | Apply box projection. | Appropriate hard-surface regions are mapped. |
| UMA-007 | Unwrap a component independently. | Unrelated component UV data remains unchanged. |
| UMA-008 | Generate automatic seams. | Editable seam recommendations are produced. |
| UMA-009 | Mark and remove seams manually. | Definitions reflect user changes without physical mesh cuts. |
| UMA-010 | Select a UV island. | Corresponding 3D geometry is identifiable. |
| UMA-011 | Move, rotate, and scale an island. | UV coordinates change without moving physical geometry. |
| UMA-012 | Lock an island and repack. | Locked island coordinates remain unchanged. |
| UMA-013 | Pin UV coordinates before unwrapping. | Pinned coordinates remain protected during supported processing. |
| UMA-014 | Pack islands with specified pixel padding. | Resulting spacing is measured against the selected resolution. |
| UMA-015 | Generate independent component layouts. | Components remain independently mappable. |
| UMA-016 | Import an existing shared atlas. | Compatible original layout and dependencies are preserved. |
| UMA-017 | Inspect MVP texture layout creation options. | Shared Atlas, Hybrid, and UDIM generation are not exposed as MVP operations. |
| UMA-018 | Replace an independently mapped component. | Unrelated UV layouts remain unchanged. |
| UMA-019 | Edit an imported shared layout. | Affected component and texture dependencies are identified. |
| UMA-020 | Create a second UV channel. | Original channel remains unchanged. |
| UMA-021 | Analyze deliberately stretched coordinates. | Measured distortion is displayed. |
| UMA-022 | Detect unintended overlap. | Affected regions are highlighted in red. |
| UMA-023 | Authorize intentional overlap. | Overlap remains identified without being classified as unintended. |
| UMA-024 | Detect insufficient island padding. | Affected islands are identified. |
| UMA-025 | Detect missing UV coordinates. | Affected geometry is identified. |
| UMA-026 | Validate defective UV data. | Automatic repair does not execute. |
| UMA-027 | Explicitly initiate UV repair. | Independent derivative is produced and validated. |
| UMA-028 | Repack existing textured geometry. | Affected texture assignments are identified. |
| UMA-029 | Transfer UVs to optimized geometry. | Compatible coordinates are transferred and validated, or failure is disclosed. |
| UMA-030 | Transfer UVs to an LOD variant. | Applicable correspondence is preserved or flagged. |
| UMA-031 | Complete a UV operation. | Texture generation and rebaking do not automatically execute. |
| UMA-032 | Export and reimport FBX with multiple UV channels. | Supported channels remain independently accessible. |
| UMA-033 | Export a 2048-resolution layout. | A 2048 by 2048 PNG is produced. |
| UMA-034 | Execute UV mapping without internet access. | Processing completes locally. |
| UMA-035 | Deny a generated UV derivative. | Exclusive files and metadata are deleted. |
| UMA-036 | Allow a pending UV derivative to expire. | Established retention policy is enforced. |
| UMA-037 | Simulate UV processing failure. | Original geometry and UV artifacts remain unchanged. |
| UMA-038 | Submit another UV request during execution. | Execution locks prevent the additional request. |
| UMA-039 | Apply View Projection from a selected orientation. | Result reflects the selected projection. |
| UMA-040 | Generate material, sharp-edge, and component-boundary seams. | Each supported method produces editable seam definitions. |
| UMA-041 | Mirror, align, stitch, and split compatible islands. | Requested UV edits are applied without altering physical geometry. |
| UMA-042 | Normalize texel density. | Measured density is reported and locked islands are unchanged. |
| UMA-043 | Assign different component texture resolutions and priorities. | Independent allocation is preserved without creating a shared atlas. |
| UMA-044 | Measure physical density on an asset with unknown scale. | Verified physical density is not falsely reported. |
| UMA-045 | Compare two independent texture sets using identical normalized coordinates. | No cross-set overlap defect is reported. |
| UMA-046 | Switch between 3D View and Split View. | Applicable controls remain available; no standalone UV Editor mode is required. |
| UMA-047 | Select geometry in Split View. | Corresponding UV selection updates, and vice versa. |
| UMA-048 | Initiate Safe UV Repair and Advanced UV Repair separately. | Each produces a distinct reviewable candidate and reports applied corrections. |
| UMA-049 | Remove a referenced UV channel. | Affected dependencies are disclosed before the operation. |
| UMA-050 | Export each of the four approved profiles. | Each contains only applicable selected artifacts and required dependencies. |
| UMA-051 | Cancel active UV processing. | Locks release only after safe termination. |
| UMA-052 | Export a pending UV artifact. | Warning and confirmation occur without approval or expiration reset. |

## 9.25 MVP acceptance criteria

Phase 09 implementation is complete only when the integrated local pipeline demonstrates all approved capabilities: seven unwrapping methods; six seam management capabilities; all approved island editing controls; independent component texture sets; preservation of compatible imported shared layouts; independently editable UV channels; configurable packing at approved resolutions; all three texel density controls and overlap policies; automatic validation with red defect highlighting and a distinct distortion heatmap; explicitly initiated Safe and Advanced UV Repair; compatible UV transfer; 3D View and Split View with synchronized selection; all four export profiles; and established retention, dependency approval, execution locking, and FBX interoperability.

Shared Atlas generation, Hybrid layout generation, Texture Atlas Optimization, UDIM support, and standalone UV Editor view are not MVP acceptance requirements. No provider selection, algorithm selection, or implementation testing is implied by design approval.

## 9.26 Final decision register and technical interpretations

| Decision | Approved scope |
|---|---|
| D1 | All seven unwrapping methods. |
| D2 | All six seam management capabilities. |
| D3 | All proposed island editing capabilities. |
| D4 | Independent texture sets for MVP; Shared Atlas and Hybrid deferred to Post-MVP. Decision finalized. |
| D5 | Multiple user-defined UV channels, subject to compatible pipeline limitations. |
| D6 | UDIM deferred until Post-MVP. |
| D7 | Uniform Density, Manual Island Scaling, and Component Priority. |
| D8 | Unique UVs, Allow Intentional Overlap, and Preserve Existing. |
| D9 | Automatic validation, manual Safe and Advanced UV Repair, red defects, distinct distortion heatmap. |
| D10 | 3D View and Split View only; all four export profiles retained. |

Technical interpretations and details requiring later verification:

- Component Priority in MVP is implemented through independent resolution and island allocation rather than shared atlas area allocation. The exact allocation algorithm remains open.
- Preservation of compatible imported shared layouts does not establish an atlas creation workflow. Imported layout editing must disclose affected dependencies.
- The six Phase 07 profile names are reused as UV processing recommendations; their exact UV-specific presets remain to be defined.
- A resizable Split View divider is proposed. No standalone UV Editor is required.
- UV seam persistence, per-corner coordinate representation, FBX round-trip support, channel limits, and safe repair definitions require implementation validation.
- Exact padding conventions, default texture resolution, numerical distortion thresholds, transfer accuracy, and packing benchmarks remain open. The JSON example values are illustrative, not approved defaults.
- Additional assertions UMA-039 through UMA-052 and revised UMA-016 through UMA-017 and UMA-019 consolidate approved decisions into testable requirements; they have not been executed.
- No AI models, UV libraries, packing algorithms, or processing technologies have been selected. Reference Generation implementation remains a prerequisite for the wider 3D production roadmap, not a requirement to re-generate references for independent UV processing.

**Next phase:** Phase 10: Texture Generation.
