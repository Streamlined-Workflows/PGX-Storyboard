# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 04: Asset Data Structure and Lifecycle**  
**Version:** 1.0  
**Status:** Finalized for MVP  
**Application location:** SWIFT Director > Asset Generation > 3D Generation  
**Preceding documents:** `3d_Phase_1.md`, `3d_Phase_2.md`, `3d_Phase_3.md`

## 4.1 Purpose

This phase establishes a standardized, model-independent data structure for representing, storing, modifying, generating, and exchanging 3D assets. An asset is a logical collection of components, geometry, materials, textures, spatial references, dependencies, and metadata, rather than merely a model file.

All eight asset types use the same core structure. Individual workflows may run independently, and local providers and deterministic tools may exchange normalized artifacts without requiring concurrent inference. Phase 02 governs explicit approval, ten-day pending retention, dependency confirmation, nondestructive editing, and ZIP export. Phase 03 governs classification, generation modes, dimensions, and spatial references.

No AI models, databases, processing libraries, or storage technologies are selected in this phase.

## 4.2 Logical Data Architecture

| Entity | Responsibility |
|---|---|
| Asset | Persistent identity, classification, production definition, and selected artifacts. |
| Component | Independently manageable mesh or logical grouping with transforms and assignments. |
| Artifact | Independently identifiable file or file collection with retention and integrity information. |
| Material | Surface properties and references to independent texture artifacts. |
| Metadata | Asset properties, generation parameters, validation results, and provenance. |
| Relationship | Structural hierarchy, required dependencies, historical lineage, and associations. |

These are logical entities, not a prescribed physical database schema. Textures and spatial references are independently addressable records associated with these entities. The manifest describes the asset; binary files remain separate.

## 4.3 Asset Identity

| Property | Purpose |
|---|---|
| Asset ID | Unique persistent identifier independent of filenames. |
| Name and description | User-facing identity and intended purpose. |
| Classification | Parent, asset type, optional predefined or custom subtype. |
| Generation mode | Unified, Automatic Modular, or Directed Modular. |
| Structural profile | Exterior or Interior, where applicable. |
| Timestamps | Creation and latest modification. |
| Production and approval status | Independent readiness and retention states. |
| Dimensions | Canonical centimeters; optional until assigned. |
| Geometry settings | Quality profile, requested and measured polygon counts. |
| Texture settings | Requested output resolution. |
| References | Components, artifacts, materials, spatial references, relationships. |
| Tags | Optional organizational keywords. |
| Schema version | Version of the asset specification. |

| ID | Functional requirement |
|---|---|
| ADS-001 | Every asset shall have a unique persistent identifier. |
| ADS-002 | Renaming shall not change asset identity. |
| ADS-003 | Reclassification shall not change asset identity or overwrite artifacts. |
| ADS-004 | Identifiers shall not depend on physical filenames or paths. |
| ADS-005 | Multiple assets may share a display name. |
| ADS-006 | Metadata shall remain independently accessible from geometry files while the asset exists. |
| ADS-007 | Asset data shall support schema versioning. |
| ADS-008 | Copying an asset shall create a new asset ID without requiring physical duplication of immutable files. |

## 4.4 SWIFT Asset Manifest

The canonical manifest shall use JSON. Export packages shall include `AssetManifest.json` with portable references to the included files. Internal storage paths and credentials shall not be exposed. The following is an illustrative logical structure; field-level serialization contracts will be refined in later phases.

```json
{
  "schemaVersion": "1.0",
  "assetId": "asset-unique-id",
  "name": "Light Cargo Frigate",
  "description": "Single-pilot light cargo spacecraft",
  "classification": {
    "parent": "Scene Assets",
    "type": "Vehicle",
    "subtype": "Spacecraft",
    "structuralProfile": "Exterior"
  },
  "generationMode": "Directed Modular",
  "status": {"production": "InProgress", "approval": "Pending"},
  "dimensions": {"unit": "cm", "width": 480, "length": 1200, "height": 350},
  "geometry": {"qualityProfile": "Mid", "targetPolygonCount": 25000, "actualPolygonCount": 24862},
  "textureSettings": {"targetResolution": 2048},
  "components": [],
  "materials": [],
  "artifacts": [],
  "spatialReferences": [],
  "relationships": [],
  "metadata": {"tags": ["Spacecraft", "Cargo", "Science Fiction"]}
}
```

| ID | Functional requirement |
|---|---|
| MAN-001 | Every asset shall have a manifest. |
| MAN-002 | The manifest shall identify applicable components and artifacts. |
| MAN-003 | The manifest shall use a documented JSON structure. |
| MAN-004 | Binary artifacts shall be stored separately. |
| MAN-005 | The manifest shall record its schema version. |
| MAN-006 | `AssetManifest.json` shall be included in the ZIP export. |
| MAN-007 | Export references shall be portable and resolve within the package. |
| MAN-008 | Manifests shall exclude credentials and sensitive server configuration. |
| MAN-009 | Validation shall detect missing required artifacts. |
| MAN-010 | Schema changes shall support migration of older retained manifests. |

## 4.5 Component Hierarchy

A Unified asset has one primary geometry component when geometry exists. Automatic Modular and Directed Modular assets may have multiple mesh components and logical groups. A group need not have geometry.

```text
Light Cargo Frigate
  Hull Assembly
    Primary Hull
    Cockpit Glass
  Engine Assembly
    Left Engine
    Right Engine
  Cargo Assembly
    Cargo Door
      Door Hinge
  Landing Gear
```

Component records include ID, name, parent ID, node type, geometry reference, local position, rotation, scale, visibility, editing lock, material assignments, spatial references, semantic role, measured polygon count, and associated artifact approval state.

| ID | Functional requirement |
|---|---|
| CMP-001 | Every component shall have a unique identifier. |
| CMP-002 | Components shall support parent-child relationships. |
| CMP-003 | Mesh components shall support independent geometry artifacts. |
| CMP-004 | Logical groups shall not require geometry. |
| CMP-005 | Components shall support independent position, rotation, and scale. |
| CMP-006 | Components shall support visibility and editing locks. |
| CMP-007 | Components shall support independent material assignments. |
| CMP-008 | Components shall support individual regeneration. |
| CMP-009 | Regeneration shall not overwrite unrelated components. |
| CMP-010 | Hierarchy and transforms shall be preserved during export. |
| CMP-011 | Circular parent-child relationships shall be rejected. |
| CMP-012 | Users shall be able to rename and reorganize components. |
| CMP-013 | Parent transformations shall preserve applicable child relationships. |
| CMP-014 | Components shall support classification-specific semantic roles. |
| CMP-015 | Unified assets shall support subsequent modular processing without overwriting source geometry. |

## 4.6 Coordinate System, Origins, and Transformations

| Property | Canonical convention |
|---|---|
| Handedness | Right-handed |
| Horizontal axis | X |
| Vertical axis | Y; positive Y is up |
| Depth axis | Z; positive Z is asset forward |
| Horizontal positive direction | Positive X, the approved coordinate-axis right convention |
| Units | Centimeters |
| Internal rotation | Quaternion |
| User-facing rotation | Euler angles in degrees |
| Scale | Independent X, Y, Z values |

Coordinate adapters shall explicitly account for destination handedness, axes, units, and asset-facing conventions. Coordinate-axis right is not assumed to be the anatomical right of an actor facing positive Z. Exact Euler rotation order and FBX axis conversion contracts shall be established during implementation design.

### 4.6.1 Default Origins

| Asset type | Default origin |
|---|---|
| Humanoid | Ground Center |
| Creature | Ground Center |
| Scene Prop | Ground Center |
| Vehicle | Ground Center or Floor Center, according to vehicle type |
| Held Prop | Bounding Center |
| Interactive Prop | Bounding Center |
| Vehicle Interior | Floor Center |
| Scenery | Ground Center or Floor Center, according to structural profile |

| Vehicle type or locomotion | Default origin guidance |
|---|---|
| Wheeled | Ground Center |
| Tracked | Ground Center |
| Legged | Ground Center |
| Watercraft | Floor Center |
| Aircraft | Ground Center or Floor Center |
| Spacecraft | Ground Center or Floor Center |
| Hybrid or Custom | User-selected Ground Center or Floor Center |

These locomotion distinctions refine the existing Vehicle classification, rather than introducing new primary asset types. Ground Center is the horizontal center at the intended ground-contact plane. Floor Center is the horizontal center at a designated floor plane. Bounding Center is the geometric center of the bounding volume. Custom Origin is user-positioned. Exterior-only vehicles may require a manually designated floor plane. Users may override defaults.

| ID | Functional requirement |
|---|---|
| TRF-001 | Maintain a canonical coordinate convention. |
| TRF-002 | Store canonical spatial measurements in centimeters. |
| TRF-003 | Normalize imported and generated geometry to the canonical convention. |
| TRF-004 | Convert exports according to destination conventions. |
| TRF-005 | Support parent-relative transforms. |
| TRF-006 | Calculate world transforms from component relationships. |
| TRF-007 | Permit origin adjustment and classification-aware defaults. |
| TRF-008 | Unit display changes shall not change asset scale. |
| TRF-009 | Transforms shall preserve component alignment and spatial references. |
| TRF-010 | Applied transformations shall not destructively overwrite retained source geometry. |

## 4.7 Spatial Reference Data

Each asset and each component may independently define Primary Grip, Secondary Grip, Tertiary Grip, and custom Pivot. Each has its own enable toggle, owner-relative position and orientation. Disabling a custom pivot does not eliminate the mathematical mesh origin.

```json
{
  "referenceId": "reference-unique-id",
  "type": "TertiaryGrip",
  "name": "Magazine Interaction",
  "enabled": true,
  "owner": {"type": "Component", "componentId": "component-magazine"},
  "transform": {
    "position": {"x": 0, "y": 12.5, "z": -4.2},
    "rotation": {"x": 0, "y": 0, "z": 0, "w": 1}
  },
  "unit": "cm"
}
```

| ID | Functional requirement |
|---|---|
| SPD-001 | Every spatial reference shall have a unique identifier. |
| SPD-002 | Each reference shall support an independent enabled state. |
| SPD-003 | Each reference shall identify its owning asset or component. |
| SPD-004 | Store position and orientation. |
| SPD-005 | Coordinates shall be relative to the owner. |
| SPD-006 | References shall follow owner transformations. |
| SPD-007 | References shall not modify mesh topology. |
| SPD-008 | Disabled references shall be excluded from active export metadata. |
| SPD-009 | References shall be independently editable. |

## 4.8 Artifact Classification

| Category | Examples |
|---|---|
| Reference Image | Concept art and individual reference views |
| Geometry | Imported or generated FBX mesh |
| Optimized Geometry | Low, Mid, High derivatives |
| Component Geometry | Independent mesh parts |
| UV Layout | Surface mapping data |
| Texture Map | Base color, normal, roughness, metallic |
| Material | Reusable surface definition |
| Surface Mask | Painting or inpainting selection |
| Landmark Data | Anatomical coordinates |
| Landmark Texture | CC5 218-point overlay |
| Preview | Thumbnail or rendered preview |
| Generation Metadata | Prompt, parameters, provider and validation information |
| Export Package | ZIP delivery archive |
| Temporary Processing Data | Native provider files and inference intermediates |

Artifact records include ID, category, format, storage reference, size, content hash, source IDs, required dependency IDs, generation job ID, creation timestamp, approval state, expiration timestamp, provider ID and version.

| ID | Functional requirement |
|---|---|
| ART-001 | User-facing artifacts shall be independently identifiable. |
| ART-002 | Physical filenames shall not serve as permanent IDs. |
| ART-003 | Record artifact category and format. |
| ART-004 | Record storage size. |
| ART-005 | Support integrity verification. |
| ART-006 | Retain applicable generation metadata only for the lifetime of its valid associated records. |
| ART-007 | Identify required dependencies. |
| ART-008 | Apply the Phase 02 retention policy. |
| ART-009 | Support independent reuse where compatible. |
| ART-010 | Clean temporary files after completion or failure unless required by active processing. |
| ART-011 | Identical immutable files shall share physical storage where appropriate. |
| ART-012 | Shared physical storage shall not unintentionally merge logical approval states. |

## 4.9 Materials and Textures

Materials define scalar surface properties and references to texture maps. Textures are independent image artifacts. Multiple components and assets may use one material or texture without duplicating physical files. Detailed PBR channels, UV requirements, and texture processing are defined in later phases.

| ID | Functional requirement |
|---|---|
| MATD-001 | Materials shall have unique persistent IDs. |
| MATD-002 | Support scalar properties and texture references. |
| MATD-003 | Materials may be assigned to multiple components. |
| MATD-004 | Components may have multiple material assignments. |
| MATD-005 | Textures shall remain independently identifiable. |
| MATD-006 | Each texture shall identify its material channel. |
| MATD-007 | Materials shall support independent approval and retention. |
| MATD-008 | Shared resource edits shall not silently alter other assets. |
| MATD-009 | Required material and texture dependencies participate in approval. |
| MATD-010 | Materials shall support reuse across assets and projects. |

### 4.9.1 Shared Resource Modification

Before modifying a shared material or texture, display a modal listing **all current assets** using the resource, directly or indirectly, with affected components and material assignments. The user shall choose Create Independent Copy, Update Shared Resource, or Cancel. Independent copy is the recommended default. Shared updates require explicit confirmation; new generated replacements must follow the normal approval and dependency policy before replacing approved resources. Existing approved resources remain intact until the replacement is approved and applied.

| ID | Functional requirement |
|---|---|
| SHR-001 | Detect shared material usage before editing. |
| SHR-002 | Detect shared texture usage before editing. |
| SHR-003 | Resolve direct and indirect affected assets. |
| SHR-004 | List every currently affected asset in the modal. |
| SHR-005 | Identify affected components and material assignments. |
| SHR-006 | Provide an independent copy option. |
| SHR-007 | Provide a shared update option. |
| SHR-008 | Require explicit confirmation for shared updates. |
| SHR-009 | Independent copies shall leave other assets unchanged. |
| SHR-010 | Apply retention and dependency approval rules to modifications. |
| SHR-011 | Cancellation shall leave all resources and assets unchanged. |

| ID | Validation assertion | Expected result |
|---|---|---|
| SHA-001 | Edit a material shared by multiple assets. | Every affected asset is listed. |
| SHA-002 | Edit a texture shared through multiple materials. | Direct and indirect affected assets are listed. |
| SHA-003 | Create an independent copy. | Only the selected assignment changes. |
| SHA-004 | Confirm a shared update. | All confirmed assignments update. |
| SHA-005 | Cancel. | No changes are committed. |
| SHA-006 | Generate a replacement for an approved resource. | Original remains intact until replacement approval and explicit application. |

## 4.10 Relationships and Dependencies

| Relationship | Meaning |
|---|---|
| Parent-child | Structural hierarchy and inherited transformations |
| Contains | Membership of components or artifacts |
| Requires | Operational dependency necessary for continued functionality |
| Derived From | Source of a generated or modified artifact |
| Uses Material | Geometry-to-material assignment |
| Uses Texture | Material-to-texture assignment |
| Generated From | Historical generation input |
| Alternative To | Variation of an asset or component |
| References | Nonmandatory association between entities |

Required dependencies, including transitive dependencies, must be resolved before approval. Pending required dependencies trigger the Phase 02 modal listing each dependency, its purpose, and additional storage. Approval is explicit and atomic. Historical generation inputs are not automatically retained. Exterior and interior assets may be associated without requiring combined generation.

| ID | Functional requirement |
|---|---|
| REL-001 | Relationships shall identify source and destination entities. |
| REL-002 | Relationships shall identify their type. |
| REL-003 | Required dependencies shall be distinct from historical references. |
| REL-004 | Required dependencies shall support recursive evaluation. |
| REL-005 | Circular required dependencies shall be rejected. |
| REL-006 | Support shared dependencies. |
| REL-007 | Historical relationships shall not automatically require permanent retention. |
| REL-008 | Deleting dependencies shall not silently invalidate approved assets. |
| REL-009 | Delete relationship records exclusive to denied or expired generations; do not retain historical records solely to track deleted generations. |
| REL-010 | Associated exterior and interior assets shall remain independently manageable. |

## 4.11 Asset Production Lifecycle

Production readiness, artifact approval, and job execution are independent lifecycle dimensions. An incomplete asset may be approved, and a validated asset may remain pending. Validation is not approval; approval is not validation.

| Production status | Description |
|---|---|
| Draft | Definition exists; production has not started. |
| In Progress | Additional production work remains. |
| Ready for Review | Selected workflow has completed. |
| Validated | Applicable validation requirements have passed. |
| Archived | Removed from active production without deletion; retention rules still apply. |

| Artifact state | Description |
|---|---|
| Pending | Successfully generated, awaiting explicit approval for up to 10 days from successful generation. |
| Approved | Explicitly retained until user-directed deletion. |
| Denied | Rejected; exclusive files and metadata are deleted. |
| Expired | Ten-day deadline reached without approval; exclusive files and metadata are deleted. |

Denied and Expired are deletion transitions, not permanent historical records. Job execution states (queued, running, completed, failed, cancelled) are governed separately and will be expanded in Phase 21.

| ID | Functional requirement |
|---|---|
| LFC-001 | Production and approval statuses shall remain independent. |
| LFC-002 | Job status shall remain independent of production readiness. |
| LFC-003 | Users shall be able to approve incomplete assets. |
| LFC-004 | Users shall be able to export pending assets after explicit confirmation. |
| LFC-005 | Generation completion shall not automatically approve artifacts. |
| LFC-006 | Validation shall not automatically approve artifacts. |
| LFC-007 | Approval shall not automatically validate an asset. |
| LFC-008 | Pending retention shall expire 10 days after successful generation, without extension through export. |
| LFC-009 | Archived approved assets shall remain retained until explicitly deleted. |
| LFC-010 | Readiness shall be evaluated against the intended workflow. |

### 4.11.1 Complete Deletion Policy

Denial and expiration shall delete all data exclusively associated with the rejected or expired generation, including geometry, textures, materials, masks, landmarks, previews, temporary files, prompts, parameters, seeds, generation history, artifact metadata, and exclusive relationship records. No permanent historical archive or lightweight tombstone shall be maintained solely to track rejected or expired generations.

Shared physical files and required dependencies shall be protected only while another valid artifact references them. This protects existing assets without retaining rejected generation history. When the final valid reference is removed, the physical file shall be deleted. A retained asset's own generation record remains valid, but references to deleted historical input files must not imply that those files remain available. Cleanup shall not invalidate approved assets or interrupt active jobs; required files actively in use shall be protected until the job releases them, without silently approving or extending the pending retention period.

| ID | Functional requirement |
|---|---|
| DEL-001 | Denied artifacts shall be permanently deleted, subject to safe shared-file handling. |
| DEL-002 | Unapproved artifacts shall be deleted after 10 days. |
| DEL-003 | Exclusive prompts, parameters, and seeds shall be deleted. |
| DEL-004 | Exclusive generation records shall be deleted. |
| DEL-005 | Exclusive previews and thumbnails shall be deleted. |
| DEL-006 | Exclusive artifact metadata shall be deleted. |
| DEL-007 | Exclusive relationship records shall be deleted. |
| DEL-008 | Unreferenced physical files shall be removed from local storage. |
| DEL-009 | Shared files shall remain only while referenced by another valid artifact or protected active job. |
| DEL-010 | Required dependencies of approved assets shall remain protected. |
| DEL-011 | Deleted generations shall not remain visible in generation history. |
| DEL-012 | No permanent archive of rejected or expired generations shall be maintained. |

| ID | Validation assertion | Expected result |
|---|---|---|
| DEA-001 | Deny a generated asset. | All exclusive files and metadata are removed. |
| DEA-002 | Allow a pending asset to expire. | All exclusive files and metadata are automatically removed. |
| DEA-003 | Inspect generation history after deletion. | Deleted generation is absent. |
| DEA-004 | Delete an artifact sharing a file with an approved asset. | Approved asset remains functional. |
| DEA-005 | Delete the final valid reference to a shared file. | Physical file is deleted when no active job requires it. |
| DEA-006 | Run expiration cleanup against approved artifacts. | Approved artifacts remain unchanged. |

## 4.12 Generation Provenance

For existing valid artifacts, generation records shall identify the generation ID, asset and optional component IDs, operation type, provider ID and version, input and output artifact references, user prompt, resolved prompt, negative prompt where supported, parameters, seed where supported, execution duration, completion status, and validation results.

Provenance does not guarantee deterministic reproduction. Deleted generations shall not retain their own provenance records under the complete deletion policy. Missing historical input files shall be treated as unavailable rather than silently restored or permanently retained.

| ID | Functional requirement |
|---|---|
| PRV-001 | Each generation operation shall receive a unique identifier. |
| PRV-002 | Generation records shall identify applicable input and output artifacts. |
| PRV-003 | Record provider identifiers and versions. |
| PRV-004 | Record applicable prompts and parameters while the generation record remains valid. |
| PRV-005 | Record random seeds where supported. |
| PRV-006 | Distinguish provider-specific parameters from application settings. |
| PRV-007 | Records shall be readable independently of the generating model. |
| PRV-008 | Provider replacement shall not invalidate existing valid generation records. |
| PRV-009 | Indicate known deterministic reproduction capabilities without promising reproducibility. |
| PRV-010 | Records shall exclude credentials and authentication secrets. |

## 4.13 Local Artifact Storage and Deduplication

The logical asset structure shall be independent of physical storage. Identical immutable files shall be stored once where appropriate using content hashes and shared references. Separate logical artifacts shall retain independent approval states. Editing shared resources shall create new content or explicitly update confirmed assignments rather than mutating immutable shared files.

For example, three assets referencing an identical 100 MB texture set may consume 100 MB of physical texture storage rather than 300 MB, excluding metadata and other artifacts. Copying an asset creates a new logical identity without requiring immediate physical duplication.

| ID | Functional requirement |
|---|---|
| STO-001 | All MVP artifacts shall be stored locally. |
| STO-002 | Physical storage locations shall be independent of display names. |
| STO-003 | Support shared file references. |
| STO-004 | Verify file integrity using content hashes. |
| STO-005 | Deduplicate identical immutable files. |
| STO-006 | Account for all valid references before physical deletion. |
| STO-007 | Remove expired and otherwise unreferenced physical files. |
| STO-008 | Measure storage usage at artifact and asset levels, distinguishing shared and physical usage. |
| STO-009 | Distinguish pending, approved, and temporary storage consumption. |
| STO-010 | Preserve required dependencies of approved assets during cleanup. |
| STO-011 | Detect unavailable required artifacts without retaining deleted-generation records solely for history. |
| STO-012 | Export applicable artifacts without exposing internal storage paths. |

Storage limits, cleanup scheduling, physical persistence, and crash recovery will be expanded in Phase 22. No storage engine or hash algorithm is selected here.

## 4.14 Model Input and Output Interchange

Model providers shall exchange standardized artifacts through provider adapters. Providers need not implement the complete SWIFT manifest internally. Adapters translate application parameters into native inputs, convert outputs, normalize geometry and spatial conventions, and validate artifacts before subsequent stages consume them.

### 4.14.1 MVP Format Registry

| Data category | Canonical or supported MVP format |
|---|---|
| Geometry | FBX (sole canonical geometry interchange format) |
| Reference images | PNG, JPEG, WebP |
| Texture maps | PNG |
| Surface masks | PNG |
| Material definitions | JSON |
| Asset manifest | JSON (`AssetManifest.json`) |
| Landmark coordinates | JSON |
| Landmark overlay | PNG |
| Asset delivery | ZIP |

FBX is selected for production interoperability and the ability to preserve supported editable topology, hierarchy, UV data, and character preparation information. The viewport shall load canonical FBX directly, with independent SWIFT material definitions and texture artifacts. No persistent GLB duplicate is required for MVP.

Providers may use other native formats temporarily. Generated geometry must become validated FBX before it is accepted as a canonical artifact. Temporary native geometry files are deleted after successful validated conversion unless required by an active processing job. If conversion loses required information, the output shall fail validation rather than silently discarding that information. Existing approved source artifacts must remain intact on failure. Retention of native files during active processing does not imply support for a second canonical format.

### 4.14.2 General Interchange Requirements

| ID | Functional requirement |
|---|---|
| INT-001 | Providers shall use standardized application contracts. |
| INT-002 | Provider adapters shall perform native format conversions. |
| INT-003 | Interchange artifacts shall be independently accessible. |
| INT-004 | Normalize outputs before unrelated processing stages consume them. |
| INT-005 | Conversion shall preserve required geometry and surface information. |
| INT-006 | Detect unsupported or incompatible inputs before execution. |
| INT-007 | Native intermediate data may be retained temporarily during active processing. |
| INT-008 | Providers need not understand the complete SWIFT hierarchy. |
| INT-009 | The application shall manage component and artifact relationships. |
| INT-010 | Failed conversions shall not overwrite approved source artifacts. |

### 4.14.3 Geometry Interchange Requirements

| ID | Functional requirement |
|---|---|
| GEO-INT-001 | FBX shall be the sole canonical geometry interchange format for MVP. |
| GEO-INT-002 | Providers may use alternative native formats temporarily. |
| GEO-INT-003 | Convert native geometry to FBX before canonical acceptance. |
| GEO-INT-004 | Preserve required supported topology, UV coordinates, normals, materials, hierarchy, and spatial transformations. |
| GEO-INT-005 | Delete unnecessary native files following successful validated conversion. |
| GEO-INT-006 | The viewport shall support direct loading of canonical FBX geometry. |
| GEO-INT-007 | Materials and textures shall remain independently managed through the manifest. |
| GEO-INT-008 | All geometry conversion shall execute locally. |
| GEO-INT-009 | Failed conversions shall not overwrite source artifacts. |
| GEO-INT-010 | Future geometry formats shall be introducible without restructuring the common asset data model. |

### 4.14.4 Geometry Interchange Assertions

| ID | Test | Expected result |
|---|---|---|
| GEO-IMA-001 | Convert native provider geometry to FBX. | Valid FBX is produced. |
| GEO-IMA-002 | Convert geometry containing quads. | Required supported quad topology is preserved. |
| GEO-IMA-003 | Convert modular geometry. | Hierarchy and transformations remain intact. |
| GEO-IMA-004 | Convert textured geometry. | UVs and material assignments remain valid. |
| GEO-IMA-005 | Load canonical FBX into the viewport. | Geometry renders successfully. |
| GEO-IMA-006 | Pass FBX into a subsequent provider. | Provider consumes it directly or through validated temporary conversion. |
| GEO-IMA-007 | Finish conversion and validation. | Unnecessary native files are deleted. |
| GEO-IMA-008 | Execute conversion on target local hardware. | Conversion completes within supported resource limits. |

### 4.14.5 Post-MVP Format Evaluation

| Candidate | Potential purpose |
|---|---|
| GLB/glTF | Optimized web rendering and runtime delivery |
| OpenUSD | Complex asset composition and production interchange |
| OBJ | General-purpose static geometry interchange |
| STL | 3D printing |
| PLY | Point cloud and reconstruction workflows |

These are future evaluation candidates, not implementation commitments. Additional formats must demonstrate measurable benefit relative to added storage, processing, maintenance, and conversion complexity. Supported FBX versions, local conversion libraries, licensing, malformed-input handling, and target hardware compatibility must be validated before provider integration.

## 4.15 Asset Data Model Constraints

These constraints apply according to the provider's declared role. A geometry provider is not required to generate textures, and a texture provider is not required to generate geometry. Multiple local providers and deterministic tools may collectively satisfy a workflow.

| ID | Model or processing constraint |
|---|---|
| ADMC-001 | Outputs must be independently persistable outside the inference process. |
| ADMC-002 | Compatible input artifacts must be accepted programmatically. |
| ADMC-003 | Outputs must be convertible into supported interchange formats. |
| ADMC-004 | Geometry must contain sufficient information for coordinate and scale normalization. |
| ADMC-005 | Modular outputs must preserve identifiable relationships or support their reconstruction. |
| ADMC-006 | Texture outputs must be identifiable by material channel. |
| ADMC-007 | Providers must declare supported output formats. |
| ADMC-008 | Outputs must be associable with inputs and generation parameters. |
| ADMC-009 | Providers must not require permanent undocumented temporary files. |
| ADMC-010 | Providers must execute without destructive modification of approved sources. |
| ADMC-011 | Outputs must be independently validatable. |
| ADMC-012 | Artifacts must support subsequent processing directly or through deterministic conversion. |
| ADMC-013 | Providers must declare relevant output limitations. |
| ADMC-014 | Execution must be local-only. |
| ADMC-015 | Geometry outputs must be convertible to canonical FBX. |
| ADMC-016 | Conversion must preserve required supported topology, UVs, normals, and component information. |
| ADMC-017 | Converted geometry must be readable by the SWIFT viewport. |
| ADMC-018 | Providers must not require permanent retention of native geometry after validated conversion. |
| ADMC-019 | FBX conversion must execute locally within target hardware constraints. |

## 4.16 Asset Data Model Assertions

| ID | Test | Expected result |
|---|---|---|
| ADMA-001 | Generate and unload provider. | Valid artifacts remain accessible. |
| ADMA-002 | Convert generated mesh to FBX. | Required geometry remains intact. |
| ADMA-003 | Normalize geometry from two providers. | Both follow canonical spatial conventions. |
| ADMA-004 | Assemble independent components. | Alignment and transforms remain valid. |
| ADMA-005 | Pass geometry to a texture provider. | Provider consumes compatible geometry. |
| ADMA-006 | Generate multiple texture channels. | Each channel is identifiable. |
| ADMA-007 | Regenerate approved artifact. | Original remains unchanged; new result is pending. |
| ADMA-008 | Inspect valid generation provenance. | Inputs, settings, provider and outputs are recorded. |
| ADMA-009 | Restart infrastructure. | Retained asset data and pending expiration timestamps remain readable. |
| ADMA-010 | Replace provider. | Existing canonical artifacts remain usable. |
| ADMA-011 | Submit incompatible format. | Validation prevents incompatible execution. |
| ADMA-012 | Simulate failed conversion. | Approved sources remain intact. |
| ADMA-013 | Remove unnecessary temporary files after successful generation. | Completed canonical artifact remains functional. |
| ADMA-014 | Process entirely offline. | Artifact operations complete locally. |
| ADMA-015 | Export pending asset after confirmation. | ZIP is valid; approval state and deadline remain unchanged. |
| ADMA-016 | Approve artifact with pending transitive dependencies. | Explanatory modal lists dependencies; approval requires confirmation. |
| ADMA-017 | Cancel dependency approval. | Existing approval states remain unchanged. |
| ADMA-018 | Store identical immutable files under separate logical artifacts. | Physical storage is deduplicated without merging approval states. |
| ADMA-019 | Rename or reclassify an asset. | Persistent identity and retained files remain unchanged. |
| ADMA-020 | Transform component with enabled grip and pivot references. | Owner-relative positions and orientations are preserved. |
| ADMA-021 | Change metric/imperial display. | Canonical dimensions and geometry scale remain unchanged. |
| ADMA-022 | Export asset with required artifacts. | Manifest references resolve within ZIP; no internal paths or secrets are exposed. |

## 4.17 Application Responsibilities and Acceptance Criteria

SWIFT is responsible for identity assignment, manifest validation, hierarchy management, coordinate normalization, physical storage and deduplication, retention cleanup, dependency resolution, shared resource impact analysis, spatial reference editing, and export packaging. Providers are responsible for generating or processing their declared artifact types; provider adapters mediate format conversions and validation. AI is not responsible for deciding retention or approval.

Phase 04 implementation shall be accepted when:

- All eight asset types use the common JSON asset structure and independently identifiable components, artifacts, materials, and references.
- FBX is the sole canonical geometry interchange format, loads in the viewport, and exchanges geometry between local processing stages without unacceptable loss of required information.
- Canonical centimeter-based coordinates and classification-aware origins are preserved across transforms and exports.
- Asset-level and component-level grips and pivots retain independent enable states, position, orientation, and ownership.
- Materials and textures are reusable; shared resource modification lists every affected asset and requires the user's selected modification scope.
- Immutable duplicate files share physical storage without merging independent approval states.
- Required dependencies are resolved recursively and approved only through explicit confirmation.
- Pending artifacts expire after 10 days; denial and expiration remove exclusive files, metadata, and generation history rather than retaining a permanent archive.
- Cleanup protects approved assets and valid shared references, and removes unreferenced files.
- Production readiness, approval, and job execution remain independent.
- Applicable provenance is recorded for valid artifacts without promising exact reproduction.
- ZIP exports include portable `AssetManifest.json` and applicable artifacts; exporting pending assets requires confirmation and does not approve or extend retention.
- All workflows remain local-only and compatible with sequential execution.

## 4.18 Finalized Decisions and Deferred Implementation Details

| Decision | Final MVP direction |
|---|---|
| Manifest | JSON, `AssetManifest.json` in exports |
| Coordinates | Right-handed, Y-up, positive Z forward, centimeters, quaternion rotations internally |
| Geometry | FBX only as canonical interchange; direct viewport loading |
| Shared storage | Content-hash-based immutable file deduplication with independent logical records |
| Shared edits | Independent copy or explicitly confirmed shared update; list all affected assets |
| Expiration and denial | Complete deletion of exclusive generation files and metadata |
| Origins | Classification-aware; ground or floor center for vehicles according to type |
| Spatial references | Independent grip and custom pivot allocation at asset and component levels |
| Alternative geometry formats | Evaluate after MVP; no implementation commitment |

Phase 04 supersedes conflicting earlier suggestions for GLB-based canonical geometry, indefinite historical generation retention, or a universal bounding-center vehicle origin. The Phase 02 approval and export policies remain authoritative.

The logical JSON examples are illustrative rather than finalized schemas. Physical database design, ID generation strategy, exact coordinate adapter conventions and Euler order, supported FBX versions and conversion libraries, storage limits, concurrency-safe cleanup implementation, and quantitative conversion tolerances remain deferred. Vehicle locomotion-specific origin guidance and active-job file protection are technical interpretations of the approved origin and retention policies; they do not introduce new primary classifications or automatic permanent retention.

**Next phase:** Phase 05, Reference Image and Multi-View Generation.
