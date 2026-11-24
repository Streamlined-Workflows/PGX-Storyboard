# Phase 10: Texture Generation

**Product:** SWIFT Director | Asset Generation | 3D Generation  
**Version:** 1.0  
**Status:** Finalized design, implementation pending  
**Dependencies:** Phases 01 through 09 and Reference Generation Design

## 10.1 Purpose and scope

Texture Generation shall enable users to generate, reconstruct, transfer, process, and independently manage texture maps associated with three-dimensional geometry. The objective is visually consistent, editable, reusable surface information while preserving the independence of geometry, UV layouts, materials, and modular components.

Texture Generation shall remain independently accessible within the 3D Generation Studio. Users shall be able to generate textures from prompts, references, existing geometry and UV layouts; produce individual maps or coordinated sets; transfer and bake compatible surface information; independently texture components; regenerate textures without regenerating geometry; and review, approve, deny, and export texture artifacts. All processing shall execute locally, preserve original artifacts, and follow the established nondestructive artifact lifecycle. FBX remains the canonical geometry interchange format; PNG remains the canonical texture format.

## 10.2 Terminology and responsibility boundaries

| Entity or term | Responsibility |
|---|---|
| Geometry | Physical surface structure. |
| UV layout | Relationship between geometric surfaces and texture coordinates. |
| Texture | Image containing spatially varying surface information. |
| Texture set | Related maps sharing a surface coordinate definition and common output resolution. |
| Material | Rendering properties, scalar values, colors, texture references, and surface assignments. |
| Texture variant | Alternate surface appearance for the same compatible geometry. |
| Baking | Calculation or transfer of source surface information into a target texture layout. |
| Projection | Mapping existing imagery or surface data onto geometry using spatial correspondence. |
| Derivation | Calculation or estimation of a map from existing information. |
| Surface completion | Filling unobserved surface information through inference or existing compatible surface data. |
| PBR | Physically based rendering; the MVP map registry supports a metallic-roughness workflow. |

Phase 10 focuses on asset-bound surface textures. Phase 11 shall address reusable material extraction, generation, and assignment. Phases 12 and 13 shall define direct surface painting, masking, and regional texture generation/inpainting. Shared infrastructure shall be reused rather than duplicating these workflows. Texture generation shall not intentionally alter geometry or UV layouts. A missing or incompatible UV layout shall be identified and resolved through the UV workflow, not silently replaced.

## 10.3 Texture map registry

All eight map types are included in MVP. No map is universally mandatory. Constant material properties shall not require unnecessary image artifacts.

| Map | Typical channels | Purpose |
|---|---|---|
| Base Color / Albedo | RGB or RGBA | Surface colors, markings, and patterns, normally without baked directional lighting. |
| Normal | RGB | Apparent surface orientation and fine detail without changing physical geometry. |
| Roughness | Grayscale | Surface roughness and distribution of reflected light. |
| Metallic | Grayscale | Metallic and nonmetallic response in the metallic-roughness workflow. |
| Ambient Occlusion | Grayscale | Localized geometric occlusion. |
| Height / Displacement | Grayscale | Relative surface elevation for compatible bump, parallax, or displacement workflows. |
| Emissive | RGB | Surface emission information. |
| Opacity / Alpha | Grayscale or explicitly identified alpha channel | Transparency, partial opacity, or cutout information. |

Generating a Height / Displacement map does not itself displace geometry. Rendering interpretation belongs to material and interoperability workflows. Specialized subsurface scattering, anisotropy, transmission, and clearcoat maps are not required by this phase; Phase 11 or later scope review may evaluate them.

## 10.4 Texture generation lifecycle

1. Select source geometry, applicable asset/component variant, UV layout, and UV channel.
2. Select prompts, reference images, existing textures, or material references as appropriate.
3. Select production method, requested maps, texture-set resolution, lighting policy, and surface completion method where applicable.
4. Resolve compatible local providers and disclose unsupported inputs or controls.
5. Generate, project, derive, or bake the requested surface information through a compatible pipeline.
6. Normalize output to the canonical format and common resolution when explicitly permitted by the request; distinguish native from processed output.
7. Validate technical integrity, surface coverage, map consistency, and compatibility.
8. Present independent candidate maps and the assembled preview for review, approval, denial, regeneration, or export.

Users may enter at any applicable stage. A single-map operation shall not require unrelated maps to be regenerated. No texture operation shall silently regenerate geometry or UVs.

## 10.5 Input requirements

| Input | Requirement |
|---|---|
| Source geometry | Required for asset-bound texture generation. |
| Component and variant | Required when targeting an individual component or variant. |
| UV layout and channel | Required for UV-bound output; select the channel where multiple exist. |
| Reference imagery | Optional according to production method. |
| Descriptive prompt | Optional according to production method. |
| Existing textures or material references | Optional or required according to transfer, derivation, and completion method. |
| Target texture-set resolution | Required. |
| Requested maps | Required; at least one applicable map. |
| Provider override | Optional advanced control. |

Reference imagery may originate from Reference Generation, Image Generation, existing asset reference sets, component breakaway references, imported photographs or illustrations, existing texture images, and retained material references. Phase 05 reference roles, validation, selection, and compatibility policies remain applicable. Texture Generation consumes references; it does not duplicate the image/reference generation workspaces.

| ID | Requirement |
|---|---|
| TIN-001 | Support texture generation using existing geometry. |
| TIN-002 | Support applicable UV layout inputs. |
| TIN-003 | Support image-conditioned texture generation. |
| TIN-004 | Support prompt-conditioned texture generation. |
| TIN-005 | Support existing texture inputs. |
| TIN-006 | Support component-specific reference images. |
| TIN-007 | Support geometry- and UV-conditioned processing. |
| TIN-008 | Identify incompatible provider inputs before execution. |
| TIN-009 | Disclose reference inputs that will not be consumed; obtain explicit confirmation for reduced input sets under Phase 05. |
| TIN-010 | Texture generation shall not automatically approve source references. |

Visual reference inconsistencies shall be flagged, not used as an automatic artistic gate. Invalid required inputs or unsupported technical combinations may prevent execution. Automatic compatible provider selection and advanced manual override shall follow the model-independent architecture.

## 10.6 Texture production methods

All five production methods shall be supported and independently selectable for applicable maps. A coordinated request may combine methods. Deterministic processing is preferred when it satisfies the requested operation.

| Method | Purpose |
|---|---|
| Reference-Guided Generation | Generate surface colors, patterns, markings, and other information from reference imagery. |
| Prompt-Guided Generation | Generate surface information from descriptive instructions, optionally supplemented by geometry and imagery. |
| Image Projection | Project existing image information onto applicable geometry surfaces using known or estimated alignment. |
| Texture Baking | Calculate or transfer surface information from geometry, textures, or compatible source materials. |
| Map Derivation | Estimate or calculate additional maps from existing surface information. |

| ID | Requirement |
|---|---|
| TGM-001 | Support reference-guided generation. |
| TGM-002 | Support prompt-guided generation. |
| TGM-003 | Support image projection. |
| TGM-004 | Support texture baking. |
| TGM-005 | Support map derivation. |
| TGM-006 | Support different production methods for individual maps. |
| TGM-007 | Prefer deterministic processing where it satisfies the operation. |
| TGM-008 | Identify derived or estimated maps in metadata. |
| TGM-009 | Preserve original input artifacts. |
| TGM-010 | Disclose unsupported production methods. |

## 10.7 Texture resolution and normalization

The approved square texture resolutions remain independent of geometric vertex budgets. The application shall use one common output resolution per texture set, with no individual map override. Separate component texture sets may have different resolutions.

| Resolution | Pixels per map | Illustrative use, not a restriction |
|---|---:|---|
| 512 x 512 | 262,144 | Small accessories and minor props. |
| 1024 x 1024 | 1,048,576 | General props and clothing components. |
| 2048 x 2048 | 4,194,304 | Characters and detailed objects. |
| 4096 x 4096 | 16,777,216 | High-detail and close-up surfaces. |

A Low Density geometry asset may use a 4096 texture set, and a High Density asset may use a 512 texture set. For example, a base body can use 4096 while hair uses 1024 and a coat uses 2048. All maps within each respective set inherit its resolution. Total pixel counts do not establish actual storage or rendering memory, which depend on channels, precision, compression, and mipmaps.

| ID | Requirement |
|---|---|
| TRS-001 | Support all four approved texture resolutions. |
| TRS-002 | Texture resolution shall remain independent of geometry density. |
| TRS-003 | Components shall support independently configurable texture-set resolutions. |
| TRS-004 | Actual output dimensions shall be verified independently. |
| TRS-005 | Provider-native resolution shall be disclosed. |
| TRS-006 | Upscaled output shall be identified as upscaled. |
| TRS-007 | Upscaling shall not be represented as native detail generation. |
| TRS-008 | Resolution changes shall trigger applicable UV padding reevaluation. |
| TRS-009 | Each texture set shall maintain one common output resolution. |
| TRS-010 | All maps within a texture set shall conform to its configured resolution. |
| TRS-011 | Independent per-map resolution overrides shall not be supported. |
| TRS-012 | Components shall retain independently configurable texture-set resolutions. |
| TRS-013 | Individually regenerated maps shall inherit the existing set resolution. |
| TRS-014 | Imported maps with inconsistent dimensions shall be identified during validation. |
| TRS-015 | Changing the resolution of an existing set shall require explicit user action. |
| TRS-016 | Resolution normalization shall preserve original texture artifacts. |

Imported maps shall not be automatically resized merely because validation identifies inconsistent dimensions. Normalization or a deliberate set-resolution change shall be an explicit derivative operation. Locked maps shall not be altered silently to satisfy a new set resolution; incompatible locks must be resolved by the user before that operation. The application shall not activate a mixed-resolution derivative as a conforming newly generated texture set.

## 10.8 Individual maps, coordinated sets, and map locking

| Generation strategy | Behavior |
|---|---|
| Individual Map | Generate or regenerate one selected map. |
| Coordinated Set | Generate multiple selected maps using a common surface definition. |
| Generate Missing Maps | Generate only requested map types absent from the current set. |

Each set may contain any applicable subset of the eight map types. A coordinated set is one execution request and one final set candidate, containing separately identifiable map artifacts. Individual maps may originate from different compatible production methods. Completed maps shall remain accessible following partial failure; missing requested maps shall be reported rather than silently declared complete.

| ID | Requirement |
|---|---|
| TST-001 | Support individual map generation. |
| TST-002 | Support coordinated texture-set generation. |
| TST-003 | Users shall select requested maps. |
| TST-004 | Unrequested maps shall not be unnecessarily generated or retained. |
| TST-005 | Each map shall remain independently identifiable. |
| TST-006 | Maps shall support independent regeneration. |
| TST-007 | Sets shall identify applicable geometry and UV revisions. |
| TST-008 | Coordinated maps shall maintain compatible feature alignment. |
| TST-009 | Partial texture sets shall remain valid where appropriate, without misrepresenting completion. |
| TST-010 | Missing requested maps shall be clearly identified. |
| TST-011 | Support Generate Missing Maps without overwriting existing completed maps. |
| TST-012 | Support independent map locks and explicit unlocking. |
| TST-013 | Locked maps shall remain unchanged during compatible set regeneration. |
| TST-014 | Regeneration shall identify map dependencies and compatibility limitations. |
| TST-015 | Locking or selecting a map shall not constitute approval or extend retention. |

Where a provider requires an internal intermediate or supplementary map, the application may use it as temporary processing data; unnecessary outputs shall not become retained production artifacts. Locked maps may serve as compatible conditioning inputs without modification. A provider that cannot respect requested map protections shall not silently override them.

## 10.9 Map generation, derivation, and provenance

| Map | Applicable production methods |
|---|---|
| Base Color | AI generation, image projection, texture transfer. |
| Normal | AI estimation, height conversion, high-to-low baking. |
| Roughness | AI estimation, user configuration, existing material transfer. |
| Metallic | AI estimation, material assignments, user-defined masks. |
| Ambient Occlusion | Geometry baking or compatible estimation. |
| Height | AI estimation, source height information, compatible geometry baking. |
| Emissive | AI generation, image transfer, user-defined regions. |
| Opacity | Source alpha, AI segmentation, user-defined masks. |

| Origin | Meaning |
|---|---|
| Generated | Created through AI or procedural generation. |
| Derived | Calculated or estimated from existing map information. |
| Baked | Calculated from geometry or an existing surface representation. |
| Projected | Transferred from reference imagery. |
| Imported | Obtained from an external file. |
| User Authored | Created or explicitly edited by the user. |

Provenance shall distinguish directly supplied, calculated, baked, and inferred information. A roughness or metallic map inferred from a photograph is not a verified physical measurement. A map derived from another estimated map shall not lose that uncertainty in its recorded provenance. Map production metadata shall identify applicable input artifacts, processing method, and provider information while retained.

## 10.10 Multi-view texture generation

Texture Generation shall use Phase 05 references and prioritize compatible multi-view input when available. Single-image generation remains supported. The pipeline shall attempt to preserve surface colors, patterns, intentional asymmetry, logos, decorative features, material transitions, component boundaries, cross-view continuity, and supplemental detail references. Unknown camera alignment shall not be treated as calibrated projection.

| ID | Requirement |
|---|---|
| TMV-001 | Support compatible single-image texture generation. |
| TMV-002 | Support compatible multi-view texture generation. |
| TMV-003 | Prioritize compatible multi-view inputs where available. |
| TMV-004 | Preserve intentional asymmetric details. |
| TMV-005 | Support supplemental detail references. |
| TMV-006 | Identify inconsistent reference appearances. |
| TMV-007 | Disclose provider limitations and excluded references. |
| TMV-008 | Inferred surface information shall not be represented as directly observed. |
| TMV-009 | Evaluate cross-view texture consistency independently where practical. |

## 10.11 Unobserved surface handling

The approved surface completion modes are exactly the following two. Leave Unmapped is excluded as a generation mode. The intended result is complete coverage of applicable geometry surfaces, not necessarily every pixel in unused UV space.

| Mode | Behavior |
|---|---|
| Infer Missing Surfaces | Generate compatible unseen surface information using references, geometry, and user instructions. |
| Apply Existing Surface | Complete unobserved surfaces using a user-selected compatible texture or material. |

Surface completion is an explicitly authorized part of the generation request, not automatic repair. Unintentionally missing coverage caused by processing failure shall remain visible as a defect. The application shall disclose when a provider cannot reliably distinguish observed and inferred surfaces; complete coverage shall not be presented as proof of reconstruction accuracy. Intentional transparency is not missing texture coverage.

| ID | Requirement |
|---|---|
| TUS-001 | Support inference of unobserved surface information. |
| TUS-002 | Support completion using existing textures or materials. |
| TUS-003 | Users shall select the intended surface completion method. |
| TUS-004 | Inferred information shall not be represented as directly observed. |
| TUS-005 | Existing surface information shall remain unchanged unless explicitly regenerated. |
| TUS-006 | Preserve intended component and material boundaries. |
| TUS-007 | Applied existing surfaces shall identify applicable source dependencies. |
| TUS-008 | Completed textures shall undergo surface coverage validation. |
| TUS-009 | Unintentionally missing information shall be flagged during review. |
| TUS-010 | Surface completion shall produce independently reviewable texture artifacts. |

## 10.12 Modular texture management and appearance variants

Phase 09 establishes Independent Texture Sets as the standard for newly generated MVP assets. Components and their geometry variants shall support independent surface assignments, resolutions, and texture variants. Multiple materials per component remain supported. Existing imported shared layouts may be preserved where compatible; this does not introduce new atlas generation.

| ID | Requirement |
|---|---|
| TMT-001 | Components shall support independent texture sets. |
| TMT-002 | Component texture generation shall not modify unrelated components. |
| TMT-003 | Component variants shall support independent texture assignments. |
| TMT-004 | Assembly configurations shall reference applicable component textures. |
| TMT-005 | Support multiple materials per component. |
| TMT-006 | Component texture-set resolutions shall be independently configurable. |
| TMT-007 | Shared texture files shall follow existing dependency and copy-on-edit policies. |
| TMT-008 | Preserve imported shared texture assignments where compatible. |
| TMT-009 | Newly generated shared atlases shall be Post-MVP. |
| TMT-010 | Hybrid texture layout generation shall remain Post-MVP. |
| TMT-011 | UDIM generation shall remain Post-MVP. |
| TMT-012 | Support independently identifiable appearance variants for compatible geometry. |
| TMT-013 | Preview and activate texture variants without regenerating geometry. |
| TMT-014 | Assembly configurations shall reference geometry and texture variants independently. |
| TMT-015 | Validate texture variant compatibility with active geometry and UV revisions. |
| TMT-016 | Variant selection shall not silently approve pending artifacts. |

A pirate hat may retain weathered brown leather, black leather, and red leather variants while using the same compatible geometry and UV layout. Assembly configurations may choose different appearances without duplicating shared geometry. Changing a geometry variant shall trigger validation of its selected texture variant; an incompatible assignment shall not be silently presented as valid. Existing shared imported texture edits shall disclose affected dependencies and follow the approved shared editing policy.

## 10.13 Surface consistency, UV seams, and padding

Texture maps shall correspond to their selected UV layout and neighboring surface regions. Related maps shall maintain compatible surface feature alignment. Unintentional color, pattern, or detail discontinuities across UV boundaries shall be identified. Deliberate seams such as stitching, mechanical joints, and material transitions shall not automatically be classified as defects.

| ID | Requirement |
|---|---|
| TSC-001 | Generated maps shall correspond to the selected UV layout. |
| TSC-002 | Related maps shall maintain compatible feature placement. |
| TSC-003 | Significant unintended seam discontinuities shall be flagged. |
| TSC-004 | Preserve intentional material boundaries. |
| TSC-005 | Texture padding shall account for applicable UV island spacing. |
| TSC-006 | Attempt to avoid unintended texture bleeding. |
| TSC-007 | Preserve distinguishable intentional asymmetrical details. |
| TSC-008 | Seam correction shall not automatically execute after validation. |

Intentional UV overlap may cause multiple surfaces to sample the same texture information. Phase 09 overlap policies remain applicable, and users shall be informed when unique markings or regional edits cannot be represented independently without changing the UV layout. Texture Generation shall not silently alter that layout.

## 10.14 Texture lighting separation

| Policy | Behavior |
|---|---|
| Lighting Neutral | Attempt to remove unintended directional lighting from Base Color; default for PBR-oriented generation. |
| Preserve Reference Lighting | Retain the supplied surface appearance, including existing lighting. |
| Stylized Lighting | Preserve or intentionally generate artistic shading. |

All three policies are included. Lighting removal from arbitrary images shall not be represented as perfect physical recovery. Intentional stylistic shading shall be distinguished from unintended lighting contamination during validation. Preview lighting shall remain independent of production texture data.

## 10.15 Texture map processing

All proposed processing capabilities shall be available through compatible local processing. Operations shall be nondestructive, map-type aware, and independently reviewable.

| Operation | Purpose |
|---|---|
| Resize | Change dimensions to the selected compatible output size. |
| Upscale / Downscale | Increase or decrease dimensions with appropriate processing and provenance. |
| Color Adjustment | Adjust brightness, contrast, saturation, or hue on applicable color maps. |
| Invert | Reverse applicable scalar values or channels. |
| Channel Extraction | Extract individual image channels. |
| Channel Packing | Combine separate compatible maps into selected image channels. |
| Normal Convention Conversion | Convert supported tangent-space normal orientations. |
| Edge Padding | Extend island border pixels into available unused texture space. |
| Texture Transfer | Transfer surface information between compatible layouts. |

Individual maps shall remain canonical production artifacts. Packed maps shall be optional derivatives, not replacements for original maps. For example, an ORM derivative may store Ambient Occlusion in red, Roughness in green, and Metallic in blue; that channel assignment shall be recorded rather than assumed universally. Packing requires compatible surface mapping and dimensions. Channel extraction shall preserve the meaning of the selected data. Color transforms intended for display colors shall not silently be applied to non-color data maps.

A resize operation on a retained set shall respect the common-resolution rule. Standalone intermediate or export derivatives shall not introduce mixed resolutions into a conforming active set. Normal map resampling and other map-specific processing shall preserve the applicable data interpretation where compatible. The exact processing algorithms and engine-specific export presets remain to be established.

## 10.16 Canonical texture standards

| Property | Standard |
|---|---|
| Canonical image format | PNG. |
| Base Color | sRGB color; alpha interpreted separately as non-color opacity data where present. |
| Emissive | sRGB color or explicitly declared linear data. |
| Normal | Non-color data. |
| Roughness, Metallic, Ambient Occlusion, Height, Opacity | Non-color data. |
| Canonical tangent-space Normal convention | Positive Y, commonly called OpenGL-style. |
| Alternate tangent-space convention | Negative Y, commonly called DirectX-style; conversion supported. |
| Standard resolution | 512, 1024, 2048, or 4096 square, common within each set. |
| Standard precision | 8 bits per channel. |
| Higher precision | Optional 16 bits per channel PNG where appropriate and supported. |

Texture metadata shall identify channel semantics, color space, bit depth, and normal convention where applicable. Data maps shall not be subjected to unintended display gamma transforms. Convention conversion shall preserve the represented surface orientation under the destination convention, not merely relabel the file. Higher precision is useful for height and displacement data, but shall not be claimed if a lower precision source was merely re-encoded. Exact tangent basis interoperability shall be verified in later implementation and export evaluation.

## 10.17 Texture transfer and baking

All six baking and transfer operations are included in MVP. Baking shall remain explicitly initiated; geometry optimization, fitting, reconstruction, LOD generation, and UV changes shall not automatically trigger rebaking.

| Operation | Purpose |
|---|---|
| High-to-Low Normal Bake | Transfer detailed source geometry orientation into target Normal maps. |
| Ambient Occlusion Bake | Calculate localized geometric occlusion. |
| Base Color Transfer | Transfer compatible existing surface colors. |
| Material Map Transfer | Transfer roughness, metallic, or other compatible source data. |
| Height Bake | Capture compatible relative geometric elevation. |
| Texture Reprojection | Transfer existing surface information between different UV layouts. |

| ID | Requirement |
|---|---|
| TBK-001 | Support explicitly initiated texture baking. |
| TBK-002 | Support source and target geometry selection. |
| TBK-003 | Support target UV channel selection. |
| TBK-004 | Support high-to-low Normal map baking. |
| TBK-005 | Support Ambient Occlusion baking. |
| TBK-006 | Support compatible texture reprojection. |
| TBK-007 | Identify unsuccessful or uncertain surface correspondence. |
| TBK-008 | Support applicable projection distance configuration. |
| TBK-009 | Preserve original source and target geometry artifacts. |
| TBK-010 | Baking shall not automatically modify geometry. |
| TBK-011 | Baking shall produce independently reviewable texture artifacts. |

Source and target geometry shall be spatially compatible or explicitly aligned before transfer. Failed correspondence shall be reported rather than treated as verified surface transfer. Baked output shall be associated with the target geometry and UV revision. Historical high-density source geometry need not be retained if the baked artifact can operate independently; required dependencies shall be evaluated using the established approval policy.

## 10.18 Texture Generation workspace

The workspace shall reuse the common 3D viewport and asset management infrastructure. Exactly two primary views are included: 3D View for complete geometry inspection and Split View for simultaneous geometry and selected map inspection. A standalone texture-only workspace is not required. Users shall select the component, geometry variant, texture variant, UV channel, generation method, map types, common resolution, applicable completion and lighting policies, and compatible advanced processing settings. Map controls shall show active, locked, pending, failed, or missing status where applicable. Preview rendering shall support material preview, unlit inspection, and configurable lighting independent of production maps.

| ID | Requirement |
|---|---|
| TUI-001 | Support complete 3D texture preview. |
| TUI-002 | Support synchronized Split View. |
| TUI-003 | Support independent map inspection. |
| TUI-004 | Support component and component variant selection. |
| TUI-005 | Support applicable UV channel selection. |
| TUI-006 | Support common texture-set resolution configuration. |
| TUI-007 | Support material preview and unlit inspection. |
| TUI-008 | Support configurable preview lighting. |
| TUI-009 | Support texture validation visualization. |
| TUI-010 | Preview lighting shall not modify production textures. |
| TUI-011 | Support approval, denial, regeneration, and export. |

## 10.19 Texture validation and defect review

Automatic validation shall run for generated and processed candidates. Technical integrity and artistic agreement shall remain distinct. Confirmed locatable defects shall be highlighted in red on applicable maps or surfaces, without changing production pixels. Uncertain visual findings shall be reported separately. Invalid technical artifacts may prevent dependent operations; artistic discrepancies shall remain reviewable and shall not automatically prevent retention of technically usable results.

| Category | Validation objective |
|---|---|
| File Integrity | Confirm image decoding and valid file structure. |
| Image Dimensions | Measure actual dimensions and compare against the common set resolution. |
| Channel Integrity | Confirm applicable channel count, semantics, and precision. |
| Color Space | Confirm declared color or data interpretation. |
| UV Compatibility | Confirm association with intended geometry revision and UV layout/channel. |
| Texture Coverage | Identify unintended missing surface information, distinguishing unused UV space and intentional opacity. |
| Seam Discontinuity | Identify unexpected transitions across corresponding surface boundaries. |
| Map Alignment | Evaluate related map feature placement and coordinate compatibility. |
| Texture Bleeding | Identify unintended neighboring island contamination and padding problems. |
| Lighting Contamination | Flag potential unintended baked directional lighting under the selected policy. |
| Normal Convention | Confirm applicable normal orientation metadata and compatible interpretation. |
| Reference Consistency | Evaluate recognizable surface agreement and intentional asymmetry. |

Report nonlocatable findings in the validation list. Display requested versus produced maps, native versus processed dimensions, coverage and compatibility findings where measurable, and applicable warnings or uncertainty. Quantitative tolerances and performance benchmarks remain Phase 25 work. Missing or failed requested maps shall not be represented as successful outputs.

## 10.20 Texture repair

Automatic repair shall remain disabled. Safe Texture Repair and Advanced Texture Repair shall be explicitly initiated and produce independent candidates.

| Mode | Purpose |
|---|---|
| Safe Texture Repair | Correct supported technical defects with minimal visual impact, such as compatible metadata or channel corrections and edge padding. |
| Advanced Texture Repair | Explicitly authorized corrections that may change appearance, such as seam blending or surface reconstruction. |

The exact Safe Repair operation registry requires implementation validation. Regional painting, masking, and inpainting controls required for localized advanced changes shall be defined in Phases 12 and 13. Repair shall respect map locks and shall not automatically regenerate unrelated maps, alter UVs, or modify geometry. Surface completion selected as part of initial generation is not automatic repair.

| ID | Requirement |
|---|---|
| TRP-001 | Automatic texture repair shall remain disabled. |
| TRP-002 | Validation shall not modify texture artifacts. |
| TRP-003 | Confirmed locatable defects shall be highlighted in red. |
| TRP-004 | Users shall explicitly initiate repair operations. |
| TRP-005 | Repairs shall preserve original texture artifacts. |
| TRP-006 | Repairs shall produce independently reviewable candidates. |
| TRP-007 | Repaired textures shall undergo validation. |
| TRP-008 | Applied corrections shall be reported. |
| TRP-009 | Repair shall not automatically regenerate unrelated maps. |

## 10.21 Texture execution locking

| Execution rule | Behavior |
|---|---|
| Texture processing request | One active request producing one final map or set candidate. |
| Coordinated set | Multiple selected maps within one request, processed sequentially. |
| Additional submissions | Prevent additional texture generation submissions during active execution, at frontend and backend. |
| Component processing | Sequential. |
| Geometry modifications | Lock affected geometry during processing. |
| UV modifications | Lock affected UV layouts during processing. |
| Map protection | Preserve locked map bytes and prevent incompatible changes. |
| Failure or cancellation | Release locks only after safe termination. |

A request may comprise multiple compatible local operations. Dependencies shall be resolved in execution order. If a map fails, dependent operations shall not proceed using invalid inputs. Independently completed maps remain accessible; report incomplete sets and allow a later explicit retry after safe termination. Do not silently replace an approved set on failure. One active AI inference job per generation server remains the resource constraint. Load, execute, and release compatible providers sequentially, with broader queue and deterministic concurrency policies addressed in Phases 20 and 21. No request quantity control is required. Manual preview and inspection of retained artifacts shall remain nondestructive.

## 10.22 Texture data structure and persistence

Extend the approved Asset, Component, Material, Artifact, Metadata, and Relationship architecture. Texture sets and maps shall have independent stable identifiers. Texture variants shall reference existing compatible sets, without unnecessary binary duplication. A texture set identifies applicable geometry and UV revisions and its common resolution. Each map records actual dimensions, precision, interpretation, provenance, and applicable dependencies. Binary files remain separate from JSON metadata.

Illustrative metadata, not a final implementation schema:

```json
{
  "textureSetId": "texture-set-unique-id",
  "componentId": "component-unique-id",
  "geometryArtifactId": "geometry-artifact-id",
  "uvLayoutId": "uv-layout-unique-id",
  "uvChannel": 0,
  "label": "Weathered Leather",
  "resolution": 2048,
  "lightingPolicy": "LightingNeutral",
  "surfaceCompletionMethod": "InferMissingSurfaces",
  "maps": [
    {
      "textureArtifactId": "base-color-artifact-id",
      "mapType": "BaseColor",
      "origin": "Generated",
      "width": 2048,
      "height": 2048,
      "colorSpace": "sRGB",
      "channels": "RGB",
      "bitDepth": 8,
      "fileFormat": "PNG",
      "locked": false
    },
    {
      "textureArtifactId": "normal-artifact-id",
      "mapType": "Normal",
      "origin": "Baked",
      "width": 2048,
      "height": 2048,
      "colorSpace": "NonColor",
      "normalConvention": "PositiveY",
      "bitDepth": 8,
      "fileFormat": "PNG",
      "locked": true
    }
  ],
  "validationResults": []
}
```

| ID | Requirement |
|---|---|
| TDP-001 | Texture sets shall have persistent unique identifiers. |
| TDP-002 | Individual maps shall have independent artifact identifiers. |
| TDP-003 | Sets shall identify applicable geometry and UV revisions. |
| TDP-004 | Artifacts shall contain map-type metadata. |
| TDP-005 | Retain applicable color space information. |
| TDP-006 | Retain applicable normal conventions. |
| TDP-007 | Distinguish native and processed dimensions. |
| TDP-008 | Retain provenance while applicable artifacts remain available. |
| TDP-009 | Texture variants shall reference independently identifiable sets. |
| TDP-010 | Binary texture files shall remain separate from JSON metadata. |

## 10.23 Texture artifact lifecycle

Generated maps and applicable derivative set artifacts shall enter Pending state. Approved artifacts shall be retained. Pending artifacts expire 10 days after successful generation unless approved. Denial and expiration shall delete exclusive files and associated generation metadata, while protecting content still required by valid retained artifacts. Selection, variant activation, locking, export, and saving an assembly configuration shall not silently approve maps or extend expiration.

| Action | Behavior |
|---|---|
| Approve | Retain selected artifacts and explicitly approved required dependencies. |
| Deny | Delete exclusive associated data under established dependency safeguards. |
| Regenerate | Produce independent replacement candidate. |
| Select | Assign candidate without automatic approval. |
| Lock | Protect map from applicable processing; does not exempt retention. |
| Expire | Delete unapproved artifacts after the established retention period. |
| Export | Export selected artifacts using the established pending warning and confirmation. |

Approval shall use the existing dependency modal when required operational dependencies are pending. The modal shall identify the dependencies and explain why they are required, with no silent approval. A texture may require its specific UV layout and geometry revision to remain usable within an assembly; historical references and generation sources need not be retained merely because they were inputs. Shared immutable files shall follow deduplication and copy-on-edit rules. A shared update shall disclose affected assets, components, and dependent assignments and activate only after replacement approval. Deletion shall respect retained dependencies; unresolved or expired assignments shall be clearly identified. Temporary native files and intermediates shall be removed when no longer necessary after successful canonical conversion and validation or safe failure cleanup.

## 10.24 Export and interoperability

PNG is the canonical texture image format. FBX is the canonical geometry interchange format. Four export profiles shall be supported.

| Profile | Contents |
|---|---|
| Individual Texture Map | Selected PNG texture. |
| Texture Set | Selected related maps and applicable metadata in ZIP. |
| Component Texture Package | Applicable maps, UV layout, and component metadata in ZIP. |
| Textured Asset Package | Applicable FBX geometry, UV information, textures, and manifest data in ZIP. |

Example package structure:

```text
Pirate_Captain_Textured.zip
|-- AssetManifest.json
|-- Geometry/
|   `-- Pirate_Captain.fbx
|-- UV_Layouts/
|   `-- Applicable_UV_Layouts.png
|-- Textures/
|   |-- Base_Body/
|   |   |-- BaseColor.png
|   |   |-- Normal.png
|   |   `-- Roughness.png
|   |-- Pirate_Hat/
|   |   |-- BaseColor.png
|   |   |-- Normal.png
|   |   `-- Roughness.png
|   `-- Pirate_Coat/
|       |-- BaseColor.png
|       |-- Normal.png
|       `-- Metallic.png
`-- Metadata/
    |-- TextureManifest.json
    `-- TextureValidation.json
```

Export only selected and applicable current artifacts and required dependencies, not every historical generation attempt. Include applicable map semantics, UV associations, color space, normal convention, precision, and packed channel assignments. Pending export requires the established warning and explicit confirmation; export does not approve artifacts or reset expiration. Engine-specific compression, packed map presets, additional image export formats, and detailed interoperability validation remain Phase 18 topics. Texture atlasing is Post-MVP and shall not be silently performed during export.

## 10.25 Provider constraints

The integrated local pipeline shall collectively satisfy the approved capabilities. No individual model is required to perform every operation. Deterministic processing is preferred where sufficient. Provider-specific declarations shall inform compatibility selection and advanced manual overrides.

| ID | Constraint |
|---|---|
| TMC-001 | Support local-only execution. |
| TMC-002 | Support programmatic processing requests. |
| TMC-003 | Declare supported generation methods. |
| TMC-004 | Declare supported texture map types. |
| TMC-005 | Declare supported reference input counts. |
| TMC-006 | Declare supported image resolutions. |
| TMC-007 | Distinguish native from processed resolution. |
| TMC-008 | Support applicable geometry-conditioned processing where declared. |
| TMC-009 | Support applicable UV-conditioned processing where declared. |
| TMC-010 | Produce independently accessible texture outputs. |
| TMC-011 | Support conversion to canonical PNG output. |
| TMC-012 | Preserve applicable UV surface relationships. |
| TMC-013 | Support component-specific processing where applicable. |
| TMC-014 | Declare supported texture map combinations. |
| TMC-015 | Support single-map generation or processing where applicable. |
| TMC-016 | Coordinated generation shall maintain compatible map alignment. |
| TMC-017 | Preserve intentional reference asymmetry where supported. |
| TMC-018 | Declare color space and channel conventions. |
| TMC-019 | Normal map providers shall declare applicable normal conventions. |
| TMC-020 | Support independent output validation. |
| TMC-021 | Preserve original source artifacts. |
| TMC-022 | Support applicable local resource limitations. |
| TMC-023 | Support resource reclamation after execution. |
| TMC-024 | Expose sufficient completion and failure information. |
| TMC-025 | Satisfy applicable licensing requirements. |
| TMC-026 | Do not require cloud inference or external processing. |

Compatibility declarations shall also identify supported bit depths, available surface completion and lighting policies, map protection limitations, and whether observed versus inferred surface provenance can be localized. The orchestration layer shall enforce common output resolution and canonical formats through compatible processing, without misrepresenting provider-native capabilities. Provider selection and evaluation remain separate roadmap phases.

## 10.26 Validation assertions

The following assertions define required implementation behavior. They are planned tests, not executed results. Quantitative texture quality metrics, reference consistency thresholds, seam tolerances, and performance benchmarks remain Phase 25 work.

| ID | Test | Expected result |
|---|---|---|
| TMA-001 | Generate texture from an image reference. | Applicable surface information is produced. |
| TMA-002 | Generate texture from a descriptive prompt. | Texture reflects supported user instructions. |
| TMA-003 | Generate texture using geometry and UV inputs. | Result corresponds to applicable surfaces. |
| TMA-004 | Generate using multi-view references. | Supported directional information is incorporated. |
| TMA-005 | Generate for an asymmetric asset. | Intentional asymmetric features are preserved. |
| TMA-006 | Generate a coordinated selected set. | Requested maps are produced or missing maps identified. |
| TMA-007 | Generate one Normal map. | Unrelated maps remain unchanged. |
| TMA-008 | Generate one texture without supplementary maps. | Unnecessary maps are not retained. |
| TMA-009 | Generate at resolution 512. | Output dimensions are verified. |
| TMA-010 | Generate at resolution 1024. | Output dimensions are verified. |
| TMA-011 | Generate at resolution 2048. | Output dimensions are verified. |
| TMA-012 | Generate at resolution 4096. | Output dimensions are verified. |
| TMA-013 | Upscale a lower-resolution native output. | Native and processed resolutions are distinguishable. |
| TMA-014 | Derive Normal from Height. | Compatible Normal map is produced. |
| TMA-015 | Convert normal conventions. | Applicable orientation is converted correctly. |
| TMA-016 | Pack individual maps into channels. | Original maps remain unchanged. |
| TMA-017 | Generate texture for one component. | Unrelated component textures remain unchanged. |
| TMA-018 | Assign independent component resolutions. | Each set uses its selected common resolution. |
| TMA-019 | Replace active texture variant. | Component geometry remains unchanged. |
| TMA-020 | Generate alternate appearances. | Independent sets remain accessible. |
| TMA-021 | Switch assembly configurations. | Applicable retained textures are resolved. |
| TMA-022 | Modify a shared texture independently. | Copy-on-edit policy is preserved. |
| TMA-023 | Bake high-density detail onto low-density geometry. | Compatible Normal map is produced. |
| TMA-024 | Bake Ambient Occlusion. | Applicable occlusion information is produced. |
| TMA-025 | Transfer between compatible UV revisions. | Information is transferred or failure identified. |
| TMA-026 | Bake using incompatible geometry. | Correspondence limitations are reported. |
| TMA-027 | Complete baking. | Source and target geometry remain unchanged. |
| TMA-028 | Detect corrupted texture output. | Technical failure is identified. |
| TMA-029 | Detect incorrect texture dimensions. | Actual and requested dimensions are reported. |
| TMA-030 | Detect unintended seam discontinuity. | Affected regions are highlighted where locatable. |
| TMA-031 | Detect missing surface coverage. | Affected surfaces are identified. |
| TMA-032 | Detect incompatible map alignment. | Affected relationships are identified. |
| TMA-033 | Validate with detected defects. | Automatic repair does not execute. |
| TMA-034 | Explicitly initiate texture repair. | Independent corrected artifact is produced. |
| TMA-035 | Change preview lighting. | Texture files remain unchanged. |
| TMA-036 | Export an individual texture. | Valid PNG output is produced. |
| TMA-037 | Export a complete texture set. | Applicable maps and metadata are included. |
| TMA-038 | Execute generation offline. | Processing completes locally. |
| TMA-039 | Unload a generation provider. | Artifacts remain independently accessible. |
| TMA-040 | Submit an additional request during execution. | Applicable execution locks prevent submission. |
| TMA-041 | Deny a texture candidate. | Exclusive files and metadata are deleted. |
| TMA-042 | Allow an unapproved texture to expire. | Established retention policy is enforced. |
| TMA-043 | Simulate generation failure. | Approved textures remain unchanged. |
| TMA-044 | Generate missing maps in an existing set. | Completed maps remain unchanged. |
| TMA-045 | Regenerate a set containing locked maps. | Locked artifacts remain unchanged. |
| TMA-046 | Generate multiple maps within one set. | All requested maps conform to common resolution. |
| TMA-047 | Regenerate an individual map. | Map inherits existing set resolution. |
| TMA-048 | Import maps with inconsistent resolutions. | Discrepancies are identified without automatic resizing. |
| TMA-049 | Generate from incomplete references using inference. | Compatible unseen information is produced and identified as inferred. |
| TMA-050 | Complete unseen surfaces using existing material. | Selected information is applied and dependencies recorded. |
| TMA-051 | Detect unintended missing coverage after completion. | Affected regions are flagged for review. |
| TMA-052 | Generate lighting-neutral texture. | Unintended directional lighting is minimized within provider capabilities. |
| TMA-053 | Preserve intentional stylized lighting. | Requested artistic shading remains present. |
| TMA-054 | Generate a supported 16-bit map. | Output precision is independently verified. |
| TMA-055 | Generate packed channels. | Canonical individual maps remain unchanged. |
| TMA-056 | Switch texture variants via assembly configuration. | Appearance changes without geometry regeneration. |
| TMA-057 | Simulate partial coordinated-set failure. | Completed maps remain accessible; missing maps are identified. |

## 10.27 MVP acceptance criteria

Phase 10 implementation shall be considered complete when the integrated local pipeline demonstrates all eight approved map types, all five production methods, Individual Map and Coordinated Set and Generate Missing Maps strategies, independent map locking, the four square texture resolutions with one common resolution per set, both surface completion modes, independent component texture sets and appearance variants, all three lighting policies, all nine processing capability groups, canonical PNG and color/normal/precision standards, all six explicitly initiated baking and transfer operations, 3D View and Split View, independent map inspection and preview lighting, automatic validation with red defect highlighting, explicitly initiated Safe and Advanced Texture Repair, single-request execution locking, and all four export profiles. Geometry and UV data shall remain protected, and the approved retention and dependency policies shall be enforced.

Shared Atlas generation, Hybrid texture layout generation, Texture Atlas Optimization, and UDIM remain Post-MVP. Per-map resolution overrides and Leave Unmapped generation mode are excluded, not required future features. Preserving existing compatible imported shared layouts does not introduce an atlas generation workflow. Advanced regional editing interfaces remain the responsibility of Phases 12 and 13. No model selection or implementation testing is implied by design approval.

## 10.28 Final decision register and technical interpretations

| Decision | Approved scope |
|---|---|
| D1 | All eight map types. |
| D2 | All five production methods, independently selectable per applicable map. |
| D3 | Individual Map, Coordinated Set, Generate Missing Maps. |
| D4 | Independent map-level locks. |
| D5 | One common texture-set resolution; no per-map overrides. |
| D6 | Infer Missing Surfaces or Apply Existing Surface; no Leave Unmapped mode. |
| D7 | Independent appearance variants and assembly configuration references. |
| D8 | All three lighting policies, Lighting Neutral default for PBR. |
| D9 | All nine processing capability groups; canonical individual maps and optional packed derivatives. |
| D10 | PNG, declared color spaces, Positive Y normals with Negative Y conversion, 8-bit and supported 16-bit precision. |
| D11 | All six baking and transfer operations, explicit initiation. |
| D12 | 3D View and Split View, preview lighting and unlit inspection, automatic validation, red defects, manual repair, sequential single-request processing. |

Technical interpretations and details requiring later verification:

- Imported mixed-resolution maps are flagged rather than automatically resized. Set normalization is an explicit nondestructive operation. Locks must be resolved before incompatible resolution changes.
- Coverage means applicable mapped surfaces, not unused atlas pixels or intentional transparency. Observed, inferred, and reused surface provenance shall be distinguished where technically possible; exact provenance representation remains open.
- Partial coordinated-set failure preserves independently usable completed maps and stops operations dependent on failed outputs. A subsequent retry is explicitly initiated.
- A texture variant references existing compatible geometry and UV revisions. Exact configuration schema, material-slot relationships, and rendering defaults remain to be established.
- The example metadata, 2048 resolution, and example channel assignments are illustrative rather than universal defaults.
- Exact Safe Repair eligibility, texture projection methods, tangent basis interoperability, color management, map resampling, higher precision support, and quantitative validation require implementation evaluation.
- No AI models, texture processing libraries, baking algorithms, or implementation technologies have been selected or tested. All 57 validation assertions remain planned tests.

**Next phase:** Phase 11: Material Extraction and Generation.
