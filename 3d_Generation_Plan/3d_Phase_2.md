# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 02: Architectural Principles**  
**Version:** 1.0  
**Status:** Finalized for MVP, with proposed technical safeguards identified separately  
**Application location:** SWIFT Director > Asset Generation > 3D Generation  
**Preceding document:** `3d_Phase_1.md`

## 2.1 Purpose

This phase establishes the foundational architectural requirements governing the design, development, and operation of the SWIFT Director 3D Generation Studio. These requirements apply to generation workflows, model integrations, processing services, data structures, and user-facing functionality.

The architecture prioritizes local execution, modularity, interoperability, resource efficiency, user control, storage-conscious retention, and nondestructive asset production. All capabilities shall be housed within one unified studio while remaining independently executable.

This document is model agnostic. Specific AI models, programming languages, storage technologies, and infrastructure configurations shall be evaluated in later phases.

### Approved MVP decisions

| Decision | Requirement |
|---|---|
| Deployment | Local-only inference, processing, and artifact storage. |
| Application structure | One unified 3D Generation Studio within Asset Generation. |
| Model selection | Automatic compatible provider selection with an advanced manual override. |
| Job concurrency | Multiple queued jobs; one active AI inference job per generation server. |
| Workflow independence | Major production stages can execute independently against compatible inputs. |
| Editing | Nondestructive by default. |
| Artifact retention | Generated artifacts are pending until explicitly approved, denied, or expired. |
| Pending retention period | 10 days following successful generation. |
| Permanent storage | Explicit user approval required. |
| Export | Unified ZIP package of applicable asset artifacts. |
| Pending export | Permitted after an explicit retention warning and confirmation; does not approve the artifact. |
| Dependency approval | Explicit confirmation after identification and explanation of required unapproved dependencies. |

### Relationship to Phase 01

The approval-based retention policy in this phase supersedes any language in Phase 01 that could imply indefinite storage of every generated revision or intermediate artifact. Nondestructive editing protects source and approved artifacts from unintended modification; it does not guarantee permanent recovery of denied or expired pending generations.

## 2.2 Local-Only Architecture

All MVP AI inference, geometry processing, material extraction, texture generation, asset editing, and artifact storage shall operate within locally hosted infrastructure. The user-facing application may communicate with a locally hosted generation server; inference need not execute on the same physical device as the interface.

| ID | Architectural requirement |
|---|---|
| ARC-001 | All AI inference shall execute locally. |
| ARC-002 | No generation workflow shall require a third-party inference API. |
| ARC-003 | Asset data shall not be transmitted to external generation services. |
| ARC-004 | Models shall be stored within locally managed infrastructure. |
| ARC-005 | Intermediate and final artifacts shall be stored locally, subject to the retention policy. |
| ARC-006 | Generation workflows shall remain operational without internet connectivity after initial provisioning. |
| ARC-007 | Model installation and updates shall be separate from normal inference operations. |
| ARC-008 | The application shall not fall back to cloud-based inference when local generation fails. |

## 2.3 Modular Architecture

Each functional component shall have a defined responsibility and documented interfaces. The architecture shall support independently maintainable generation and processing capabilities without exposing them as separate top-level applications.

### Conceptual architecture

```text
SWIFT Director
  Asset Generation
    3D Generation
      Unified Studio Interface
        Workflow Orchestrator
          Reference Processing
          Geometry Generation
          Component Generation
          Mesh Processing and UV Mapping
          Material Generation
          Texture Generation
          Surface Editing
          Character Preparation
          Validation and Export
        Provider Abstraction Layer
          Local AI Model Providers
          Deterministic Processing Tools
        Resource and Job Manager
        Shared Local Artifact Storage
          Artifact Metadata and Dependencies
          Approval and Retention Management
```

This structure is conceptual and does not prescribe deployment boundaries or require a separate service or container for every component.

| ID | Architectural requirement |
|---|---|
| ARC-009 | Each functional component shall have a defined responsibility. |
| ARC-010 | Components shall communicate through documented interfaces. |
| ARC-011 | Components shall be independently maintainable and testable. |
| ARC-012 | Replacing one model provider shall not require rebuilding unrelated components. |
| ARC-013 | Application business logic shall remain separate from model-specific implementation logic. |
| ARC-014 | Functional components shall exchange standardized asset artifacts. |
| ARC-015 | All functional components shall remain accessible through the unified 3D Generation Studio. |

## 2.4 Model Independence and Selection

Models shall be selected according to their ability to satisfy the functional requirements, constraints, and assertions established in the design documents. A single provider may satisfy multiple functional roles, or multiple specialized providers and deterministic tools may cooperate to satisfy one requirement.

The application shall automatically select a compatible local provider based on the requested capability and settings. Advanced users shall be able to override automatic selection with another compatible provider. Unsupported settings shall be identified before execution rather than silently ignored or substituted.

| ID | Architectural requirement |
|---|---|
| ARC-016 | Model providers shall be interchangeable where equivalent capabilities exist. |
| ARC-017 | Model-specific input and output conversions shall be handled through provider adapters. |
| ARC-018 | Models shall not directly control application navigation or interface behavior. |
| ARC-019 | Providers shall declare their supported capabilities and limitations. |
| ARC-020 | Multiple providers may be registered for the same functional capability. |
| ARC-021 | Individual providers shall be capable of being updated, disabled, or replaced. |
| ARC-022 | A capability may be implemented through a combination of AI models and deterministic processing tools. |
| ARC-023 | Retained assets shall remain accessible after a provider is replaced or removed. |
| ARC-088 | SWIFT shall automatically select a compatible local provider for the requested operation. |
| ARC-089 | Advanced users shall be able to manually select a compatible provider. |
| ARC-090 | Incompatible provider selections shall be rejected with an explanation. |

## 2.5 Sequential Execution and Resource Management

Multiple specialized models may participate in a workflow without remaining loaded concurrently. The application infrastructure shall manage model loading, execution, artifact persistence, and resource reclamation.

The MVP shall permit multiple queued jobs but limit each generation server to one active AI inference job. Sequential execution shall not prevent independent interface interaction or require all providers to remain resident in memory.

```text
Load provider A -> Execute -> Validate and save output -> Release resources
                                                              |
Load provider B <- Validated intermediate artifact <----------+
  -> Execute -> Validate and save output -> Release resources
```

| ID | Architectural requirement |
|---|---|
| ARC-024 | Models shall support independent execution. |
| ARC-025 | Intermediate outputs shall persist between model executions, subject to retention and active-job protections. |
| ARC-026 | Models shall be capable of releasing computational resources following execution. |
| ARC-027 | Generation jobs shall respect configured hardware resource limits. |
| ARC-028 | Dependent stages shall not execute until required inputs are available and validated. |
| ARC-029 | Failure of one stage shall not invalidate successfully completed stages. |
| ARC-030 | Failed stages shall be independently retryable when their required inputs remain available. |
| ARC-031 | Model loading and unloading shall be managed by application infrastructure. |
| ARC-032 | Concurrent model execution shall not be required to complete any MVP workflow. |
| ARC-091 | Each generation server shall execute no more than one active AI inference job at a time. |
| ARC-092 | Multiple generation jobs shall be permitted to wait in a local queue. |

## 2.6 Independent Workflow Execution

The production lifecycle shall not be strictly linear. Users may import compatible artifacts, bypass unnecessary stages, revisit earlier stages, and regenerate selected components within the unified studio.

| User scenario | Workflow entry point |
|---|---|
| Upload concept artwork | Geometry Generation |
| Upload multiple reference views | Multi-View Geometry Generation |
| Import an existing 3D model | Mesh Processing |
| Import a high-poly model | Geometry Optimization |
| Upload a surface image | Material Generation |
| Import an untextured model | Texture Generation |
| Import a textured model | Surface Editing |
| Import an existing humanoid | Character Preparation |
| Import a completed asset | Validation and Export |

| ID | Architectural requirement |
|---|---|
| ARC-033 | Each major functional capability shall support independent execution. |
| ARC-034 | Imported assets shall be usable as intermediate workflow inputs. |
| ARC-035 | Users shall be permitted to bypass unnecessary stages. |
| ARC-036 | Users shall be permitted to revisit previously completed stages when required artifacts remain available. |
| ARC-037 | Changing one stage shall not automatically regenerate unrelated stages. |
| ARC-038 | The application shall identify missing or incompatible dependencies before execution. |
| ARC-039 | Available intermediate artifacts shall be reusable across assets and projects. |
| ARC-040 | Users shall be capable of exporting available intermediate artifacts through the unified ZIP export at applicable production stages. |

## 2.7 Artifact Retention and Nondestructive Editing

Nondestructive editing shall preserve original imported source assets and approved artifacts from unintended modification. New generation results shall be stored separately from their sources and shall require explicit user approval for permanent retention.

The application shall temporarily save successful generations for review. Users may approve an artifact to retain it or deny it to delete it. If no approval is given within 10 days of successful generation, the artifact shall automatically expire and its files shall be deleted.

### Artifact states

| State | Description | Retention |
|---|---|---|
| Generating | Artifact is actively being produced. | Until job completion or failure. |
| Pending | Successful generation awaits user approval. | 10 days from successful generation. |
| Approved | User has explicitly approved permanent storage. | Until explicitly deleted, subject to dependency integrity. |
| Denied | User has rejected the artifact. | Delete immediately, subject to dependency integrity and active operations. |
| Expired | Approval period has elapsed without approval. | Automatically delete artifact files. |
| Failed | Generation did not complete successfully. | Clean up incomplete output files. |

```text
Successful generation
        |
        v
Pending approval (10 days)
   |          |          |
Approve      Deny       No approval by expiration
   |          |          |
Retain       Delete     Automatically delete
```

The retention period applies to each pending generation result. Exporting, viewing, or using an artifact as an input shall not silently approve it or restart its retention period. Required dependencies must be handled according to Section 2.14.

| ID | Architectural requirement |
|---|---|
| ARC-041 | Original imported assets shall remain unchanged during processing. |
| ARC-042 | Original reference images shall remain unchanged during processing and be retained when required by approved assets. |
| ARC-043 | Geometry optimization shall produce derivative meshes without overwriting source geometry. |
| ARC-044 | Successfully generated artifacts shall initially enter a pending approval state. |
| ARC-045 | Users shall explicitly approve generated artifacts for permanent retention. |
| ARC-046 | Denied artifacts shall be deleted from local storage, subject to dependency integrity. |
| ARC-047 | Unapproved artifacts shall automatically expire 10 days after successful generation. |
| ARC-048 | Approved artifacts shall not be subject to automatic expiration. |
| ARC-049 | Regenerating an asset component shall not overwrite unrelated components. |
| ARC-050 | Derived artifacts shall retain source identification and generation metadata. |
| ARC-051 | The application shall display the remaining retention period for pending artifacts. |
| ARC-052 | The application shall provide automated cleanup of expired artifacts. |
| ARC-053 | Artifact cleanup shall not delete files required by approved assets. |
| ARC-054 | The application should support approving or denying multiple generated artifacts simultaneously, subject to explicit dependency confirmation. |

### Retention assertions

| ID | Test | Expected result |
|---|---|---|
| ARA-001 | Complete a generation job. | Artifact enters pending status with a 10-day expiration timestamp. |
| ARA-002 | Approve a pending artifact with all required dependencies satisfied. | Artifact becomes approved and exempt from automatic expiration. |
| ARA-003 | Deny a pending artifact without protected dependencies or active operations. | Artifact files are deleted. |
| ARA-004 | Allow an unapproved artifact to reach its 10-day expiration. | Artifact files are automatically deleted, subject to safe cleanup of active operations. |
| ARA-005 | Allow an approved artifact to reach 10 days after generation. | Artifact remains available. |
| ARA-006 | Restart the generation server. | Approval states and original expiration timestamps persist. |
| ARA-007 | Run automatic cleanup. | Approved assets and required dependencies remain intact. |
| ARA-008 | Regenerate an approved asset. | Original asset remains unchanged and new generation awaits approval. |

## 2.8 Separation of Responsibilities

AI providers shall perform inference. SWIFT shall perform deterministic validation, orchestration, lifecycle management, and enforcement of approved requirements independently of the selected provider.

| AI model responsibilities | SWIFT application responsibilities |
|---|---|
| Reference reconstruction | Input validation and reference management |
| Geometry inference | Polygon measurement, topology processing, and validation |
| Semantic component identification | Asset hierarchy and component management |
| Material inference | Material assignment and metadata management |
| Texture synthesis | Texture resolution and channel validation |
| Regional texture generation | Mask management and preservation of unaffected regions |
| Anatomical landmark estimation | Landmark numbering, validation, overlay generation, and export |
| Content generation | Artifact storage, approval, retention, and dependency management |

A provider may generate a mesh outside the requested polygon budget. SWIFT shall measure the output and perform or request appropriate optimization before treating it as satisfying the requested profile. Similarly, AI-generated landmark estimates shall not be accepted as a verified CC5 alignment overlay without application-side validation.

## 2.9 Architectural Model Constraints

The following constraints apply to model integration. Capability-specific constraints shall be established in subsequent phases. A provider adapter or deterministic processing stage may satisfy interface and artifact conversion requirements on behalf of a model.

| ID | Model constraint |
|---|---|
| AMC-001 | Must support local inference. |
| AMC-002 | Must support programmatic execution without requiring manual interaction with a separate application. |
| AMC-003 | Must support independent loading and execution. |
| AMC-004 | Must accept inputs through a documented or adaptable interface. |
| AMC-005 | Must produce outputs that can be independently persisted. |
| AMC-006 | Must support execution within configured hardware resource limits. |
| AMC-007 | Must allow sufficient resource reclamation after inference. |
| AMC-008 | Must not require persistent connectivity to an external service. |
| AMC-009 | Must not depend on artifact formats that cannot be converted or consumed by subsequent stages. |
| AMC-010 | Must allow supported inference parameters to be supplied programmatically. |
| AMC-011 | Must allow outputs to be associated with their generation parameters. |
| AMC-012 | Must not require destructive modification of source artifacts. |
| AMC-013 | Must expose or allow detection of inference completion and failure. |
| AMC-014 | Must be capable of integration without imposing its own interface on SWIFT Director. |
| AMC-015 | Supported capabilities and limitations must be available through the provider adapter for compatibility-based selection. |
| AMC-016 | Licensing must permit the intended local deployment and usage scenario. |

## 2.10 Architectural Model Assertions

| ID | Test | Expected result |
|---|---|---|
| AMA-001 | Disconnect external internet access after provisioning and execute inference. | Local inference completes successfully. |
| AMA-002 | Execute the provider independently. | No unrelated model provider is required. |
| AMA-003 | Release the provider following inference. | Allocated computational resources become reclaimable. |
| AMA-004 | Save generated output and restart the provider within the retention window. | Output remains accessible. |
| AMA-005 | Pass generated output into a compatible subsequent stage. | Output is successfully processed. |
| AMA-006 | Execute inference using programmatically supplied parameters. | Supported parameters are applied correctly. |
| AMA-007 | Submit invalid input. | Failure is detected without asset corruption. |
| AMA-008 | Replace a provider with an equivalent implementation. | Unrelated application components continue operating. |
| AMA-009 | Regenerate a derived artifact. | Original source artifact remains unchanged. |
| AMA-010 | Terminate a failed generation job. | Previously completed, retained artifacts remain available. |
| AMA-011 | Execute a workflow using sequentially loaded providers. | Workflow completes without concurrent model residency. |
| AMA-012 | Execute inference from the unified studio. | No separate model-specific interface is required. |
| AMA-013 | Submit a capability request with a compatible registered provider. | Automatic selection chooses a compatible provider. |
| AMA-014 | Select a compatible alternative provider manually. | Requested alternative provider is used. |
| AMA-015 | Select an incompatible provider. | Execution is blocked and incompatibility is explained. |
| AMA-016 | Submit multiple generation jobs to one server. | No more than one AI inference job is active at any time. |
| AMA-017 | Review provider licensing and deployment requirements. | Intended usage is permitted or the provider is excluded. |

## 2.11 Architectural Acceptance Criteria

Phase 02 shall be considered successfully implemented when all of the following conditions are satisfied:

- All MVP generation and processing workflows execute locally without cloud inference dependencies.
- Multiple specialized models can execute sequentially and release resources between stages as required.
- Compatible providers can be selected automatically or overridden manually.
- Individual model providers can be replaced independently of unrelated application components.
- Multiple jobs may be queued with one active AI inference job per generation server.
- Independent workflows can operate against compatible imported and intermediate artifacts.
- Failed stages can be independently retried when their inputs remain available.
- Original and approved assets remain protected from unintended modification.
- Successful generations await explicit approval and unapproved artifacts expire after 10 days.
- Users can approve or deny generated artifacts, with required dependencies explicitly confirmed before approval.
- Assets can be exported in a unified ZIP package at applicable production stages.
- Pending exports require an explicit warning and confirmation without modifying approval status or expiration.
- All functionality remains accessible within the unified 3D Generation Studio.

## 2.12 Unified Asset Export

The MVP shall provide a unified ZIP-based export that packages the selected asset and its applicable artifacts. Independent meshes, texture maps, and other supported components remain independently accessible within the extracted archive. Separate per-artifact download interfaces are not required for MVP.

Export may occur at any applicable stage of production, including before texturing or character preparation. Only available, applicable artifacts associated with the selected asset shall be included.

### Illustrative export structure

```text
Asset_Name.zip
  Geometry/
    Complete_Asset.glb
    Base_Mesh.fbx
  Components/
    Component_01.fbx
    Component_02.fbx
  Textures/
    BaseColor.png
    Normal.png
    Roughness.png
    Metallic.png
  Materials/
    Material_Definitions.json
  References/
    Front.png
    Rear.png
    Left.png
    Right.png
  Landmarks/
    CC5_218_Overlay.png
    CC5_218_Landmarks.json
  Metadata/
    Asset_Manifest.json
    Generation_Settings.json
```

The filenames, file formats, and directory layout above are illustrative, not finalized format commitments. Export formats, required metadata, and package schemas shall be defined in the Export and Interoperability phase. No unused directory or unrelated generation attempt is required. Historical reference images may be included only if applicable and still available.

| ID | Architectural requirement |
|---|---|
| ARC-055 | Asset exports shall be packaged into a single ZIP archive. |
| ARC-056 | The export package shall maintain a standardized directory structure. |
| ARC-057 | Independent mesh components shall remain independently accessible within the package. |
| ARC-058 | Texture maps shall remain independently accessible within the package. |
| ARC-059 | The package shall include an asset manifest describing its contents. |
| ARC-060 | Export shall be available at any applicable production stage. |
| ARC-061 | Export shall not modify the source asset. |
| ARC-062 | The package shall include only applicable artifacts associated with the selected asset. |
| ARC-063 | Unrelated generation attempts and rejected artifacts shall not be included. |
| ARC-064 | The package shall preserve applicable material assignments and component relationships. |

### Export assertions

| ID | Test | Expected result |
|---|---|---|
| AEA-001 | Export an untextured model. | ZIP contains geometry and applicable metadata. |
| AEA-002 | Export a textured model. | ZIP contains geometry, textures, and applicable material definitions. |
| AEA-003 | Export a modular humanoid. | ZIP contains independently accessible mesh components. |
| AEA-004 | Export a character with generated landmarks. | ZIP contains applicable landmark artifacts. |
| AEA-005 | Extract the exported ZIP. | Included files are readable, correctly organized, and consistent with the manifest. |
| AEA-006 | Export an asset with multiple previous generation attempts. | Only the selected asset and applicable artifacts are included. |

## 2.13 Pending Artifact Export

Users shall be permitted to export pending artifacts without approving them for permanent local storage. Before exporting a package containing any pending artifact, the application shall display a confirmation modal explaining the retention policy and the remaining time before automatic expiration.

The modal shall identify the pending artifacts, explain that downloading does not approve them or prevent local deletion, and ask the user whether to continue. The export operation shall not change the approval state or expiration timestamp of any artifact.

### Modal specification

**Title:** Export Unapproved Asset

**Body:** This export contains artifacts that have not been approved for permanent storage. These artifacts will be automatically deleted from local storage when their retention periods expire unless you approve them before that time. Exporting does not approve the artifacts or extend their retention periods. Your downloaded ZIP file will not be affected by local deletion. Do you wish to continue with the export?

**Displayed information:** Selected asset, pending artifacts, approval status, and remaining retention time for each pending artifact.

| Action | Behavior |
|---|---|
| Cancel | Close the modal without exporting or changing approval states. |
| Continue Export | Generate the ZIP package without approving artifacts or changing expiration timestamps. |

| ID | Architectural requirement |
|---|---|
| ARC-065 | Users shall be permitted to export pending artifacts. |
| ARC-066 | Exporting a pending artifact shall not change its approval status. |
| ARC-067 | The application shall display a confirmation modal before exporting a package containing pending artifacts. |
| ARC-068 | The modal shall identify pending artifacts and their remaining retention periods. |
| ARC-069 | The modal shall explain that exporting does not prevent automatic expiration. |
| ARC-070 | Users shall explicitly confirm or cancel the export. |
| ARC-071 | Exporting an artifact shall not reset or extend its retention period. |
| ARC-072 | Downloaded copies shall remain independent of locally stored artifacts. |

### Pending export assertions

| ID | Test | Expected result |
|---|---|---|
| AEA-007 | Initiate export containing a pending artifact. | Confirmation modal appears. |
| AEA-008 | Confirm pending artifact export. | ZIP is generated and approval states remain unchanged. |
| AEA-009 | Cancel pending artifact export. | Export does not proceed. |
| AEA-010 | Export a pending artifact and check its expiration timestamp. | Original expiration timestamp remains unchanged. |
| AEA-011 | Allow an exported pending artifact to expire. | Local artifact is deleted without affecting the downloaded copy. |
| AEA-012 | Export an entirely approved asset. | Pending artifact warning is not displayed. |

## 2.14 Dependency Approval Management

Before approving an artifact, the application shall evaluate dependencies required to preserve the artifact's functionality, appearance, and integrity. If required dependencies remain pending, the application shall display a confirmation modal identifying each dependency and explaining why it must be retained.

The user shall explicitly approve the selected artifact together with its required dependencies or cancel the approval operation. Dependencies shall not be silently approved. If the user cancels, the selected artifact and dependencies shall retain their existing approval states.

### Proposed dependency classifications

| Classification | Description | Example |
|---|---|---|
| Required dependency | Necessary for the asset to remain usable or preserve its current appearance. | Base mesh, assigned texture maps |
| Transitive dependency | Required by another required dependency. | Texture referenced by a material definition |
| Historical reference | Used during generation but not required by the finished asset. | Concept image |
| Optional artifact | Adds functionality or alternatives not required by the selected asset. | Alternate texture variation |
| Temporary artifact | Internal processing output not required by the retained asset. | Intermediate inference files |

Only required dependencies, including required transitive dependencies, are proposed for mandatory approval. Historical, optional, and temporary artifacts shall not be retained merely because they participated in a generation workflow, unless they are independently approved or are actually required by the retained asset.

### Modal specification

**Title:** Approve Required Dependencies

**Body:** The asset you are attempting to approve depends on additional artifacts that have not yet been approved for permanent storage. These dependencies are required to preserve the asset's functionality or appearance. If they are not retained, the asset may become incomplete or unusable when its pending dependencies expire. Would you like to approve this asset and all of its required dependencies?

**Displayed information:** Selected asset; each unapproved required dependency; its type and reason for retention; and, as a proposed safeguard, its storage size and the total additional permanent storage required.

| Example dependency | Reason for retention |
|---|---|
| Base mesh | Provides the geometry used by the selected textured asset. |
| UV layout | Defines texture placement if stored separately and required by the asset. |
| Material definition | Preserves assigned surface properties. |
| Texture maps | Preserve the selected asset's surface appearance. |

| Action | Behavior |
|---|---|
| Cancel | Leave all existing approval states unchanged. |
| Approve All | Approve the selected artifact and all identified required pending dependencies together. |

### Functional requirements

| ID | Architectural requirement |
|---|---|
| ARC-073 | The application shall maintain dependency relationships between stored artifacts. |
| ARC-074 | The application shall evaluate required dependencies before approving an artifact. |
| ARC-075 | The application should recursively evaluate transitive dependencies. |
| ARC-076 | Unapproved required dependencies shall trigger a confirmation modal. |
| ARC-077 | The modal shall identify each unapproved required dependency. |
| ARC-078 | The modal shall explain why each dependency is required. |
| ARC-079 | The modal should display the additional permanent storage required. |
| ARC-080 | Users shall explicitly confirm approval of the selected artifact and its required dependencies. |
| ARC-081 | Cancelling dependency approval shall leave existing approval states unchanged. |
| ARC-082 | Approval of the artifact and its required dependencies should occur as a single atomic operation. |
| ARC-083 | Already approved dependencies shall not require additional approval. |
| ARC-084 | Historical references and optional artifacts shall not be silently approved. |
| ARC-085 | Required dependencies of approved assets shall be protected from automatic expiration. |
| ARC-086 | The application shall prevent approval of an artifact with missing or invalid required dependencies. |
| ARC-087 | Shared dependencies should not be duplicated solely because multiple assets reference them. |

### Dependency assertions

| ID | Test | Expected result |
|---|---|---|
| ADA-001 | Approve an artifact with pending required dependencies. | Dependency approval modal appears. |
| ADA-002 | Inspect the dependency approval modal. | Each required pending dependency and its purpose is displayed. |
| ADA-003 | Confirm dependency approval. | Selected artifact and all required dependencies become approved. |
| ADA-004 | Cancel dependency approval. | All existing approval states remain unchanged. |
| ADA-005 | Approve an artifact with nested dependencies. | Required transitive dependencies are identified. |
| ADA-006 | Approve an artifact with already approved dependencies. | Those dependencies do not require additional approval. |
| ADA-007 | Run expiration cleanup following dependency approval. | Approved asset and required dependencies remain intact. |
| ADA-008 | Approve an artifact with missing required dependencies. | Approval is blocked and missing dependencies are identified. |
| ADA-009 | Approve two assets sharing a dependency. | Shared dependency is retained without unnecessary duplication, if the proposed shared-storage safeguard is implemented. |
| ADA-010 | Simulate failure during dependency approval. | No partial approval transaction is committed, if the proposed atomic approval safeguard is implemented. |
| ADA-011 | Approve an asset containing nonrequired historical references. | Historical references retain their existing approval status. |

## 2.15 Proposed Technical Safeguards and Deferred Decisions

The following implementation safeguards support the approved product requirements but are not independently approved technical commitments. They shall be resolved during the applicable detailed design phases. In this document, requirements using **should** identify proposed safeguards; requirements using **shall** identify required behavior.

| Safeguard or decision | Proposed direction |
|---|---|
| Recursive dependency resolution | Evaluate the complete required dependency graph before approval. |
| Atomic approval | Commit approval of the selected artifact and required dependencies together or not at all. |
| Shared dependency storage | Reference shared artifacts without unnecessary physical duplication. |
| Storage estimates | Display the additional permanent storage needed before dependency approval. |
| Dependency classification | Distinguish required artifacts from historical, optional, and temporary inputs. |
| Bulk review | Support approving or denying multiple pending generations in one operation. |
| Active-operation protection | Prevent cleanup from interrupting an active generation or export that is using an expiring artifact; delete eligible files once safe without extending their approval window. |
| Dependency deletion | Prevent deletion of a required dependency while an approved asset relies on it; define explicit dependency-aware deletion behavior in the asset lifecycle phase. |
| Cleanup scheduling | Persist expiration timestamps across restarts and define cleanup frequency and recovery after downtime. |
| Imported artifact retention | Define retention and approval rules for imported copies and reference images; never modify or delete original user files outside managed storage. |
| Metadata after deletion | Define whether minimal job or audit metadata remains after artifact file deletion. |
| Export package schema | Finalize formats, directory names, and manifest fields during the Export and Interoperability phase. |

No specific AI models, libraries, storage engines, hardware thresholds, or deployment technologies are selected by this phase.

## 2.16 Phase Completion

Phase 02 establishes the architectural foundation for subsequent capability-specific design phases. The next phase is **Phase 03: Asset Classification**, covering Humanoid, Creature, Held Prop, Scene Prop, Vehicle, and Scenery profiles, including their functional requirements, model constraints, and validation assertions.

