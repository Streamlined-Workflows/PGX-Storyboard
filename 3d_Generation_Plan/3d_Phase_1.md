# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 01: Purpose, Vision and Scope**  
**Version:** 1.0  
**Status:** Finalized for MVP  
**Application location:** SWIFT Director > Asset Generation > 3D Generation

## 1.1 Purpose

SWIFT Director's 3D Generation Studio is a unified, modular, AI-assisted 3D asset production environment designed to enable users to generate, refine, customize, optimize, and export three-dimensional assets.

The studio combines reference image generation, multi-view reconstruction, geometry generation, mesh processing, material extraction, texture generation, and direct surface editing within a cohesive production environment.

Multiple specialized AI model providers and deterministic processing tools may work together throughout the asset production lifecycle. Models are not required to run concurrently. Each production stage shall be capable of operating independently while maintaining compatibility with subsequent stages.

The MVP shall operate entirely within locally hosted infrastructure. No external AI inference provider or cloud-based generation service is required or permitted as part of the MVP generation workflow.

## 1.2 Product Vision

The vision of the 3D Generation Studio is to provide users with creative control over the complete AI-assisted 3D asset production lifecycle.

Users shall not be limited to receiving a completed, inseparable 3D model from a single generation request. They shall be capable of directing how an asset is constructed, how its components are organized, how its surfaces are textured, and how the completed asset is optimized for its intended application.

Users shall be able to progress from initial concept images to production-ready assets without unnecessarily regenerating previously approved components. All major production capabilities shall be housed within one unified studio, while remaining independently executable.

AI serves as a production tool under the direction of the user rather than as the sole decision-maker in asset creation.

This aligns with the SWIFT Director philosophy:

**Your story. Your vision. Directed by you, Built by AI.**

## 1.3 Core Objectives

| ID | Objective | Description |
| --- | --- | --- |
| OBJ-01 | Asset Generation | Convert single-view and multi-view reference images into 3D assets. |
| OBJ-02 | Geometry Control | Provide configurable polygon budgets and topology optimization. |
| OBJ-03 | Modular Construction | Support independently generated and editable mesh components. |
| OBJ-04 | Texture Generation | Generate and apply configurable-resolution textures to existing geometry. |
| OBJ-05 | Material Extraction | Derive reusable surface materials from reference images. |
| OBJ-06 | Regional Editing | Enable painting, masking, and targeted texture generation directly on 3D surfaces. |
| OBJ-07 | Character Preparation | Prepare humanoid assets for external character development and rigging workflows. |
| OBJ-08 | Interoperability | Export assets using widely supported 3D and texture formats. |
| OBJ-09 | Local Execution | Perform all MVP generation and processing within locally hosted infrastructure. |
| OBJ-10 | Model Independence | Allow specialized AI models to be replaced or upgraded independently. |
| OBJ-11 | Nondestructive Editing | Preserve original assets and approved components throughout production. |
| OBJ-12 | Asset Reusability | Enable generated geometry, materials, textures, and components to be reused across projects. |

## 1.4 Application Structure

All MVP functionality shall be accessible within the following application hierarchy:

```text
SWIFT Director
└── Asset Generation
    └── 3D Generation
        ├── Reference Development
        ├── Geometry Generation
        ├── Mesh Components
        ├── Geometry Optimization
        ├── UV Mapping
        ├── Material Generation
        ├── Texture Generation
        ├── Surface Editing
        ├── Character Preparation
        └── Validation and Export
```

The listed capabilities represent functional areas, not finalized navigation labels or separate applications. Each capability shall be independently accessible and executable within the same studio.

## 1.5 Asset Production Lifecycle

| Stage | Responsibility |
| --- | --- |
| 01. Asset Definition | Asset classification, intended use, and generation requirements. |
| 02. Reference Development | Concept images and consistent multi-view references. |
| 03. Geometry Generation | Initial 3D mesh reconstruction. |
| 04. Component Generation | Independent geometry and semantic mesh layers. |
| 05. Geometry Optimization | Polygon density, topology refinement, and UV mapping. |
| 06. Material and Texture Development | Surface properties, reference extraction, and PBR maps. |
| 07. Surface Refinement | Painting, masking, and regional texture regeneration. |
| 08. Asset Preparation | Classification-specific preparation and character landmarks. |
| 09. Validation and Export | Quality verification and export of production-ready assets. |

The lifecycle shall not be strictly linear. Users shall be permitted to revisit individual stages, import existing assets, bypass unnecessary stages, and regenerate selected components without restarting the entire workflow.

For example, a user importing an existing FBX model shall be able to proceed directly to material generation or texture editing without performing geometry generation.

## 1.6 MVP Scope

### 1.6.1 Asset Classification

The studio shall support six primary asset classifications:

- Humanoid
- Creature
- Held Prop
- Scene Prop
- Vehicle
- Scenery

Classification-specific generation and processing requirements shall be defined in subsequent phases.

### 1.6.2 Geometry Generation and Optimization

The studio shall support single-image and multi-view image-to-3D generation, with multi-view generation prioritized for improved spatial consistency and depth reconstruction.

The following polygon ranges are established for the MVP:

| Geometry profile | Minimum polygons | Maximum polygons |
| --- | ---: | ---: |
| Low Poly | 500 | 10,000 |
| Mid Poly | 10,001 | 30,000 |
| High Poly | 30,001 | 500,000 |

Geometry quality and texture resolution shall remain independently configurable. Polygon measurement conventions, default targets, and optimization methods shall be established in the geometry-specific design phases.

The studio shall support topology refinement, mesh optimization, and UV mapping.

### 1.6.3 Modular Asset Construction

The studio shall support independently editable mesh components and hierarchical asset organization wherever applicable.

Humanoid generation shall support a clean base body mesh and independently generated or reconstructed components such as clothing, hair, horns, and accessories. Equivalent component separation shall be supported for other asset classifications where appropriate.

Components shall remain independently accessible without requiring regeneration of the complete asset.

### 1.6.4 Materials and Textures

The studio shall support image-guided and prompt-guided texturing of existing geometry, reusable material extraction from reference images, and physically based rendering (PBR) material properties.

The following square texture output resolutions shall be supported:

| Texture resolution | Dimensions |
| --- | --- |
| 512 | 512 x 512 |
| 1024 | 1024 x 1024 |
| 2048 | 2048 x 2048 |
| 4096 | 4096 x 4096 |

Texture output resolution is a pipeline requirement. Individual providers may satisfy it through native generation or compatible post-processing. The distinction between native and upscaled textures shall be retained.

### 1.6.5 Direct Surface Editing

The studio shall support direct painting and masking on 3D geometry, targeted material application, and regional texture generation and inpainting.

Regional editing shall preserve unaffected surface regions and previously approved source artifacts.

### 1.6.6 Character Preparation

The studio shall support preparation of humanoid assets for external character development workflows, including clean base anatomy and independently accessible clothing and accessories.

The studio shall target an optional Character Creator 5 (CC5) Default 218-point alignment reference overlay. Landmark placement shall be treated as an assisted preparation workflow, with a removable overlay rather than permanent markings on the original skin texture.

Direct programmatic import into CC5 is not established as an MVP requirement. Exact landmark mapping, reference-template permissions, and compatibility shall be validated in the character landmark design phase.

### 1.6.7 Asset Management and Interoperability

The studio shall support asset imports and exports, generation history, recoverable revisions, reusable assets and materials, and independent preservation of intermediate artifacts.

Specific file formats, interchange contracts, and storage implementation shall be established in subsequent phases.

### 1.6.8 Local Model Orchestration

All MVP AI inference and asset processing shall execute within locally hosted infrastructure. Specialized models may execute sequentially and exchange intermediate artifacts without requiring concurrent model residency.

The application shall remain model agnostic. No specific AI models are selected in this phase.

## 1.7 Scope Boundaries

The following capabilities are outside the proposed initial asset-production scope. They may be considered for future development or integration with other SWIFT products.

| Capability | Rationale |
| --- | --- |
| External inference providers | Explicitly excluded from the local-only MVP. |
| Full skeletal animation authoring | Separate animation production workflow. |
| Advanced facial animation | Specialized character animation functionality. |
| Physics simulation | Separate simulation or rendering functionality. |
| Full scene construction | Overlaps with SWIFT Sculpt. |
| Precision CAD modeling | Different geometry and engineering requirements. |
| Full character morph system | Specialized character creation functionality. |
| Final cinematic rendering | Separate production stage within SWIFT Director. |

Except for external inference providers, these boundaries are proposed scope assumptions retained for subsequent design review. They do not prevent the studio from generating assets suitable for those purposes.

## 1.8 Global Model Constraints

These constraints apply to all MVP model providers. Capability-specific constraints shall be established in subsequent phases. A requirement may be fulfilled through a compatible provider adapter or deterministic processing stage where appropriate.

| ID | Constraint |
| --- | --- |
| GMC-001 | Models shall support locally hosted inference. External inference providers are excluded from the MVP. |
| GMC-002 | Models shall be executable independently of unrelated generation models. |
| GMC-003 | Models shall support sequential execution without requiring all pipeline models to remain loaded concurrently. |
| GMC-004 | Models shall expose a programmable inference interface or support an application-managed wrapper. |
| GMC-005 | Model outputs shall be convertible into documented, interoperable asset formats. |
| GMC-006 | Intermediate outputs shall be independently persistable. |
| GMC-007 | Models shall support noninteractive inference suitable for automated job execution. |
| GMC-008 | Model licensing shall permit the intended deployment and usage scenarios. |
| GMC-009 | Models shall operate within the configured hardware resource constraints of the intended deployment environment. |
| GMC-010 | Model capabilities, supported parameters, and limitations shall be identifiable through the provider adapter. |
| GMC-011 | Models shall not require irreversible modification of previously approved source assets. |
| GMC-012 | Model providers shall expose sufficient execution information to identify successful, unsuccessful, and incomplete generation jobs. |

## 1.9 Global Model Assertions

Assertions establish testable conditions that shall be satisfied before a model is approved for its intended role within the MVP pipeline.

| ID | Test assertion | Expected result |
| --- | --- | --- |
| GMA-001 | Execute inference without external internet access after provisioning. | Generation completes locally. |
| GMA-002 | Execute a model without loading unrelated model providers. | Generation completes independently. |
| GMA-003 | Unload a model following inference. | Allocated computational resources are released or reclaimable. |
| GMA-004 | Pass an intermediate artifact to a compatible subsequent processing stage. | The artifact is successfully consumed. |
| GMA-005 | Restart the inference service following generation. | Previously generated artifacts remain accessible. |
| GMA-006 | Submit invalid or unsupported input. | A structured failure is returned without corrupting existing assets. |
| GMA-007 | Query provider capabilities. | Supported inputs, outputs, parameters, and limitations are returned. |
| GMA-008 | Execute inference against an existing approved asset. | The original asset remains unchanged. |
| GMA-009 | Monitor resource consumption during inference. | Resource usage remains within configured deployment limits. |
| GMA-010 | Review model licensing and distribution requirements. | Intended usage is permitted or appropriately restricted. |

These assertions establish evaluation requirements, not claims that any candidate model has already passed testing.

## 1.10 Definition of Success

The MVP shall be considered successful when a user can:

1. Define and classify an intended asset.
2. Supply or generate consistent reference images, including multiple views.
3. Generate a three-dimensional representation of the asset locally.
4. Select an appropriate geometry quality profile within the approved polygon ranges.
5. Separate or independently generate relevant mesh components.
6. Generate and apply materials and textures at the requested output resolution.
7. Modify selected surface regions without unnecessarily altering the remaining asset.
8. Perform classification-specific preparation where applicable.
9. Save, restore, and reuse intermediate assets and components.
10. Export the completed asset for use in external applications.

All major production stages shall remain independently executable from the unified studio. Original and previously approved artifacts shall remain recoverable. The complete MVP workflow shall operate without external inference services.

## 1.11 Approved Design Decisions

| ID | Decision | Approved MVP direction |
| --- | --- | --- |
| DD-001 | Deployment | Local-only. |
| DD-002 | Application hierarchy | SWIFT Director > Asset Generation > 3D Generation. |
| DD-003 | Studio structure | All functionality shall be housed within one unified studio. |
| DD-004 | Workflow independence | Each major production stage shall be independently executable, including against compatible imported assets. |
| DD-005 | Editing philosophy | Nondestructive by default, preserving original and approved source artifacts. |
| DD-006 | Model orchestration | Multiple specialized models may cooperate through sequential execution. Concurrent execution is not required. |
| DD-007 | Model selection | Model agnostic requirements and validation assertions shall be established before selecting specific providers. |

Phase 01 establishes the product scope and baseline requirements. Phase 02 shall define the architectural principles governing their implementation.
