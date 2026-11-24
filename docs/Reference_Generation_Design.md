# SWIFT Director | Reference Generation

**Software Design Specification**  
**Version:** 1.0  
**Scope:** MVP  
**Status:** Approved product decisions; proposed technical safeguards identified separately  
**Application location:** SWIFT Director > Asset Generation > Reference Generation

## 1. Purpose and scope

Reference Generation shall replace the existing Character Generation placeholder within Asset Generation. It shall provide a unified workspace for creating, assembling, refining, and extracting visual asset reference sheets for all eight approved asset types. Its outputs shall support both standalone visual documentation and downstream 3D Generation workflows.

The MVP shall operate locally only. No external inference services or cloud fallback shall be required. Existing SWIFT Director image generation infrastructure shall be reused wherever compatible. Specialized providers may be introduced when existing capabilities cannot satisfy the requirements. This specification defines capabilities and evaluation criteria, not particular AI models or implementation libraries.

The workspace shall expose two separately initiated workflows:

- **Sheet Generation:** Simple generation or Advanced row and view generation, followed by assembly where applicable.
- **Sheet Extraction:** Import or select an existing reference sheet and extract independently usable images.

Generation and assembly shall never automatically initiate extraction. The 3D Generation workspace shall consume reference artifacts and navigate users to Image Generation or Reference Generation when new imagery is required, rather than duplicating image generation controls.

## 2. Governing architectural requirements

| ID | Requirement |
|---|---|
| RG-001 | All inference, image processing, assembly, extraction, and artifact storage shall occur locally. |
| RG-002 | Providers shall be independently executable and interchangeable through documented interfaces. |
| RG-003 | Multiple jobs may be queued, with one active AI inference job per generation server. |
| RG-004 | Automatic provider selection shall account for requested capabilities, with an advanced manual override subject to compatibility validation. |
| RG-005 | Source images and approved artifacts shall not be destructively overwritten by generation, extraction, or assembly. |
| RG-006 | New generation results shall be pending until explicitly approved or denied. Unapproved results shall expire ten days after successful generation. |
| RG-007 | Denied or expired results shall be deleted together with exclusive files, prompts, parameters, previews, metadata, and generation history. Shared files required by other valid artifacts shall remain protected. |
| RG-008 | Required dependencies shall be disclosed with explanations before approval; the user shall explicitly approve the item and its required dependencies together or cancel. |
| RG-009 | Selecting, locking, assigning, or exporting a pending image shall not automatically approve it or extend its retention period. |
| RG-010 | Shared physical files shall not be unnecessarily duplicated. Logical artifact identities and approval states shall remain independent. |
| RG-011 | Visual consistency findings shall be clearly flagged without blocking generation. Actual execution incompatibilities shall be identified before submission. |
| RG-012 | The workspace shall preserve asset context during navigation to and from other Asset Generation workspaces. |

## 3. Asset classification and reference profiles

Users shall select an asset classification before generation. Subtypes are optional and include a Custom option. The classification shall inform default reference views, row templates, prompts, and specification fields. Users may override recommended views. Completeness shall be defined by the asset's requirements, not a universal six-view rule.

| Parent | Asset type | Subtypes |
|---|---|---|
| Actors | Humanoid | Organic, Mechanical, Hybrid |
| Actors | Creature | Quadruped, Bipedal, Winged, Aquatic, Serpentine, Insectoid |
| Scene Assets | Scene Prop | Furniture, Container, Machinery, Decoration, Fixture |
| Scene Assets | Vehicle | Ground, Water, Aircraft, Spacecraft, Hybrid |
| Props | Held Prop | Tool, Instrument, Equipment, Weapon, Container |
| Props | Interactive Prop | Door, Window, Container, Switch, Lever, Mechanism, Furniture |
| World Assets | Vehicle Interior | Cockpit, Cabin, Cargo Hold, Passenger Compartment, Engineering Compartment, Complete Interior |
| World Assets | Scenery | Architecture, Vegetation, Terrain, Natural Formation, Modular Structure |

### 3.1 Recommended reference templates

| Asset type | Base section | Detail section |
|---|---|---|
| Humanoid | Complete character and optional clean base anatomy; front, right, rear, left; consistent A-pose or T-pose | Head front, sides and rear; hands, feet, eyes, teeth and tongue, head hair, facial hair, clothing, footwear, armor, accessories |
| Creature | Complete creature in a consistent anatomy-appropriate neutral pose; directional views appropriate to anatomy | Head, paws, claws, teeth, tail, wings, horns, fur, scales, equipment; optional expressions and poses |
| Scene Prop | Complete isolated object; directional views appropriate to its structure | Materials, structural features, cavities, removable components |
| Vehicle | Exterior front, right, rear, left, top and bottom as applicable | Hull, engines, glass, landing gear, wheels, tracks, doors, accessories |
| Held Prop | Complete isolated object; directional views as applicable | Grip surfaces, functional details, materials, removable components |
| Interactive Prop | Complete object and explicitly distinguished configuration states | Moving parts, cavities, hinges, handles, attachment surfaces |
| Vehicle Interior | Forward, rearward, left, right, ceiling and floor as applicable; optional layout reference | Fixtures, controls, furniture, doors, structural surfaces |
| Scenery | Exterior or interior reference profile, depending on the selected structural type | Roof, walls, vegetation, foundations, architectural components, materials |

These templates are recommended starting points, not mandatory row lists. Top and bottom views shall be recommended only where useful. Exterior and interior generation remain separate in the MVP. Interactive open and closed states, actor expressions, and alternate poses shall be distinguished from directional views of the same configuration.

## 4. Reference sheet structure

A reference sheet shall contain two vertically stacked sections:

- **Base:** Complete asset, silhouette, proportions, and primary directional references.
- **Detail:** Feature close-ups, breakaway components, and configuration variants.

The Base section shall appear above the Detail section by default. Each section may contain multiple rows. Layouts shall support unequal image dimensions, variable row widths, and differing aspect ratios. Assembly shall not stretch imagery to fit a uniform grid.

The supplied Rue canine and Skald character reference sheets establish the design intent: reference sheets can include large identity portraits, multiple full-body perspectives, close-ups, clothing variants, isolated details, and specification text. They are illustrative references, not fixed layout templates.

| ID | Requirement |
|---|---|
| RSS-001 | Support Base and Detail sections with independently configurable content. |
| RSS-002 | Support classification-aware recommended layouts and optional views. |
| RSS-003 | Preserve source image proportions during assembly. |
| RSS-004 | Support multiple rows and unequal cell dimensions. |
| RSS-005 | Support component-specific and feature-specific imagery. |
| RSS-006 | Allow users to include or exclude applicable content. |

## 5. Generation modes

| Capability | Simple | Advanced |
|---|---|---|
| Source references | Up to four per sheet | Up to six per row |
| Complete sheet generation | Coordinated generation request | Deterministic assembly of selected rows and views |
| Independent row generation and upload | No | Yes |
| Independent directional view generation and upload | No | Yes |
| Directional image locking | No | Yes |
| Row-specific classification and prompts | No | Yes |
| Reference inheritance | No | Yes |
| Specification panels | Optional | Optional Base panel and one per Detail row |
| Extraction | Separate workflow | Separate workflow |

### 5.1 Simple mode

Simple mode shall generate a complete reference sheet using up to four source images and a classification-aware, editable prompt. It is intended for initial concept development and quick visual documentation of an asset and its appearance, including worn or attached items.

| ID | Requirement |
|---|---|
| RSM-001 | Accept up to four source images. |
| RSM-002 | Generate a complete coordinated reference sheet. |
| RSM-003 | Require asset classification and allow optional subtype selection. |
| RSM-004 | Provide an editable classification-aware generation prompt. |
| RSM-005 | Support an integer generation count from 1 to 10 complete sheets. |
| RSM-006 | Provide previous and next navigation and active result selection. |
| RSM-007 | Support independent approval and denial of generated sheets. |
| RSM-008 | Support target resolutions and compatible aspect ratios. |
| RSM-009 | Never automatically initiate extraction. |

### 5.2 Advanced mode

Advanced mode shall allow users to construct detailed reference projects one row or one image at a time. A row represents a complete asset, base anatomy, feature, isolated component, or configuration variant. For example, a character project may include a complete character row, clean base anatomy row, and separate rows for a pirate hat, coat, boots, eyes, hair, and other attachments.

Each row shall support up to six source reference inputs and up to six independently manageable directional image slots: Front, Left, Right, Rear, Top, Bottom. These are distinct concepts: source inputs condition inference, while directional slots hold selected outputs or uploaded views. Not every slot must be enabled or populated. Custom detail rows and relevant non-directional feature imagery shall be supported without forcing inappropriate camera directions.

| ID | Requirement |
|---|---|
| RAM-001 | Support independently manageable Base and Detail rows. |
| RAM-002 | Allow adding, removing, renaming, and reordering rows. |
| RAM-003 | Support up to six source reference images per row. |
| RAM-004 | Provide independently editable row prompts and resolution settings. |
| RAM-005 | Support an integer generation count from 1 to 10 row candidates. |
| RAM-006 | Provide previous and next navigation and result selection at row level. |
| RAM-007 | Support complete row image upload without automatic extraction. |
| RAM-008 | Support individual view upload, generation, and regeneration. |
| RAM-009 | Allow users to lock individual populated views and entire rows. |
| RAM-010 | Preserve unrelated rows during generation or regeneration. |
| RAM-011 | Support independent row and view artifact approval and denial. |
| RAM-012 | Use selected row and view results during assembly. |
| RAM-013 | Support multiple visual perspectives of an isolated component. |
| RAM-014 | Allow row-level component assignment and optional classification override. |
| RAM-015 | Support independent generation or upload of each row without requiring completion of other rows. |

### 5.3 Directional slot behavior

Each slot shall display its selected image, direction, enabled state, lock state, candidate navigation, upload control, generation or regeneration control, and applicable approval controls.

| Operation | Behavior |
|---|---|
| Generate Row | Generate candidates for enabled, unlocked slots. |
| Regenerate Row | Generate replacement candidates for enabled, unlocked slots without destructively overwriting existing images. |
| Generate Missing Views | Populate enabled empty slots only. |
| Generate or Regenerate Individual View | Generate candidates for the selected enabled, unlocked slot only. |
| Upload Individual View | Populate a selected unlocked slot with an existing image. |
| Upload Complete Row | Supply a coordinated row image for assembly without automatic extraction. |
| Lock View | Protect the selected populated image from generation or replacement. |
| Lock Row | Protect the selected row and its populated views from unintended replacement. |
| Disable View | Exclude the slot from generation and assembly. |

| ID | Requirement |
|---|---|
| RAV-001 | Support six directional slots per Advanced row. |
| RAV-002 | Enable or disable each slot independently. |
| RAV-003 | Accept direct uploads into individual unlocked slots. |
| RAV-004 | Generate and regenerate each unlocked view independently. |
| RAV-005 | Preserve locked selected images during row and view generation. |
| RAV-006 | Exclude disabled slots from generation and assembly. |
| RAV-007 | Support missing-view generation without modifying populated slots. |
| RAV-008 | Provide row-level locking and individual lock controls. |
| RAV-009 | Support previous and next candidate navigation in each slot. |
| RAV-010 | Display the views targeted by a generation request before execution. |
| RAV-011 | Apply artifact approval and retention rules to all candidates. |
| RAV-012 | Preserve existing selected images while new candidates are generated. |
| RAV-013 | Never modify unrelated views or rows during individual view generation. |

Locked images may serve as identity conditioning references when supported by the provider. The adapter shall disclose which references are actually consumed. Locking alone shall not extend retention or grant permanent approval.

### 5.4 Reference inheritance and row classification

Users shall be able to select reference inputs from uploads, existing image assets, or selected results from other rows. Inheritance shall use artifact references rather than unnecessary physical copies. Changing a source row shall not automatically regenerate a dependent row. Unavailable inherited inputs shall be clearly identified.

Each Advanced row may optionally define its own asset classification and subtype, inheriting the project classification by default. A component role shall separately identify base anatomy, headwear, clothing, equipment, or another part. For example, a pirate hat may inherit Humanoid classification with component role Headwear, while a companion animal may use Actors / Creature.

| ID | Requirement |
|---|---|
| RIN-001 | Support selection of existing image assets and other row results as source references. |
| RIN-002 | Enforce the applicable six-input row limit and provider capability limits. |
| RIN-003 | Preserve identifiable inherited references without unnecessary duplication. |
| RIN-004 | Allow users to replace inherited references. |
| RIN-005 | Do not automatically regenerate dependent rows when source selection changes. |
| RIN-006 | Identify unavailable inherited references and prevent circular operational dependencies. |
| RCL-001 | Support optional row-level classification and subtype. |
| RCL-002 | Default to inheriting the project classification. |
| RCL-003 | Maintain a separate component role and component association. |
| RCL-004 | Preserve row classification and component metadata during export and 3D transfer. |

### 5.5 Simple to Advanced conversion

Users shall be able to convert a Simple project to Advanced mode, preserving its identity, classification, selected sheets, source imagery, and applicable specification metadata. The existing Simple sheet may be used as an input for new rows. Conversion shall not automatically extract its contents or alter the original image.

## 6. Specification panels

Each project shall support one optional Base specification panel and one optional panel per Detail row. Every panel shall include editable **Label** and **Sub Label** fields, for example, Label: Pirate Hat; Sub Label: Headwear.

Panels may include classification, dimensions, build, materials, colors, style, descriptive notes, and user-defined fields. Canonical dimensions shall use centimeters, with metric (meters and centimeters) or imperial (feet and inches) presentation.

| ID | Requirement |
|---|---|
| RSP-001 | Support one Base panel and one panel per Detail row. |
| RSP-002 | Support editable Label and Sub Label fields. |
| RSP-003 | Allow adding, editing, removing, and reordering specification fields. |
| RSP-004 | Provide an independent checkbox to include each panel in the final image. |
| RSP-005 | Excluding a panel shall not delete its metadata. |
| RSP-006 | Render included panel text through deterministic application composition, not AI-generated lettering. |
| RSP-007 | Support configurable visual styling, optional branding, and classification-aware defaults. |
| RSP-008 | Include applicable panel metadata in reference package exports. |
| RSP-009 | Component sheet exports shall respect the associated panel inclusion setting. |
| RSP-010 | Panels shall not force uniform row or image cell dimensions. |

Simple generation produces the visual sheet through AI; optional application-rendered specification text may be composited afterward. Advanced assembly renders panels alongside selected imagery without regenerating it.

## 7. Deterministic sheet assembly

Advanced assembly shall combine selected images into a single reference sheet without asking an AI provider to regenerate the selected imagery. Assembly shall preserve source artifacts and their appearance, allowing nondestructive scaling and placement.

| Setting | Supported controls |
|---|---|
| Section | Base or Detail |
| Row order | Drag and drop |
| Row width | Full, half, custom |
| Image sizing | Fit without distortion |
| Image alignment | Configurable |
| Background | Transparent or solid color |
| Labels | Enabled or disabled |
| Specification panels | Independent inclusion |
| Spacing and margins | Configurable |
| Canvas orientation | Landscape or portrait |
| Sheet dimensions | Automatic or user-defined |
| Branding | Optional project branding |
| Output resolution | Configurable |

| ID | Requirement |
|---|---|
| RSA-001 | Assemble selected rows and views deterministically. |
| RSA-002 | Preserve section assignments, row ordering, and source aspect ratios. |
| RSA-003 | Accommodate unequal image dimensions and flexible row layouts. |
| RSA-004 | Render configured labels, specification panels, spacing, and margins. |
| RSA-005 | Provide an assembled sheet preview before export or approval. |
| RSA-006 | Store assembled sheets as independently identifiable artifacts. |
| RSA-007 | Reassembly shall not alter source row or view images. |
| RSA-008 | Assembly shall not automatically initiate extraction. |

## 8. Resolution and image presentation

Reference resolution shall be independent of final 3D texture resolution. Supported target profiles are 512, 1024, 2048, and 4096, with non-square aspect ratios where appropriate. The application shall declare actual pixel dimensions and validate provider compatibility. A 1024 target is the proposed general default; users may choose a higher target for detailed sheets.

Sheet resolution, individual view resolution, and extracted image resolution shall remain distinct. Extracted images may retain their original crop dimensions or target 512, 1024, 2048, or 4096. Upscaling shall be disclosed as such, with native and resulting dimensions recorded. A 2048 by 2048 sheet containing four equal cells has at most 1024 by 1024 native pixels per cell before margins.

Reference imagery shall prioritize clear silhouettes, consistent pose, controlled lighting, unobstructed features, and isolated subjects where appropriate. Orthographic views are preferred for exterior directional references; perspective views are appropriate for interiors and supplemental details. Generated views that look orthographic shall not be represented as verified calibrated projections without evidence.

## 9. Sheet Extraction

Extraction shall be a separate user-initiated workflow within Reference Generation. Users may import an external PNG, JPEG, or WebP reference sheet or select an existing local sheet. Both automatic region detection and manual rectangular selection shall be available.

The extraction interface shall display the source sheet, detected or manually selected boundaries, editable direction and component assignments, and individual output previews. Detection shall support nonuniform layouts, annotations, and differently sized image regions rather than assuming a fixed grid.

| ID | Requirement |
|---|---|
| RSE-001 | Support importing or selecting existing reference sheets. |
| RSE-002 | Automatically detect individual visual reference regions where supported. |
| RSE-003 | Support manual rectangular region selection and boundary adjustment. |
| RSE-004 | Recommend directional and component assignments and allow manual correction. |
| RSE-005 | Distinguish visual reference regions from text and decorative elements. |
| RSE-006 | Clearly flag ambiguous or uncertain detected orientations. |
| RSE-007 | Extract individual images without modifying the source sheet. |
| RSE-008 | Store extracted views as independently manageable artifacts. |
| RSE-009 | Preserve original source pixels during ordinary extraction. |
| RSE-010 | Support optional background removal, padding, centering, resizing, and format normalization as separate explicit operations. |
| RSE-011 | Preserve asymmetric features without automatic mirroring. |
| RSE-012 | Support Base, Detail, feature, component, and configuration-state assignments. |
| RSE-013 | Allow independent approval, denial, and subsequent regeneration of extracted images. |
| RSE-014 | Support assignment of extracted references to existing or new 3D assets. |
| RSE-015 | Never automatically extract upon generation, assembly, upload of a complete row, or Simple to Advanced conversion. |
| RSE-016 | Apply approved retention and complete deletion rules. |

### 9.1 Extraction versus generation

| Operation | Meaning |
|---|---|
| Extract | Crop existing source pixels. |
| Normalize | Adjust dimensions, padding, centering, or format without inventing visual detail. |
| Refine | Explicit optional image processing to improve an extracted image. |
| Regenerate | AI produces a replacement image. |
| Generate Missing View | AI synthesizes a perspective absent from the source sheet. |

Extraction shall not silently introduce AI-generated details. A missing side view cannot be extracted from a sheet containing only front and rear views; it requires an explicitly initiated generation operation.

## 10. Validation and provider compatibility

Validation shall report asset identity, structural proportions, component counts and placement, anatomy, pose, materials, color consistency, orientation, asymmetry, isolation, projection, and configuration-state discrepancies where applicable.

Visual warnings shall be prominently displayed with affected images and descriptions. Visual inconsistency or inability to validate shall not block generation. Users retain creative control. Technical incompatibilities, including unsupported formats or missing mandatory provider inputs, shall prevent incompatible execution until resolved.

Providers shall declare supported reference input counts, output counts, image dimensions, aspect ratios, formats, supported directions, and any required camera information. The application shall disclose unused selected references and obtain confirmation before proceeding with a reduced reference set. Unknown calibration information shall not be recorded as verified.

## 11. Export profiles

| Profile | Contents |
|---|---|
| Sheet Only | Selected complete reference sheet image. |
| Individual Views | ZIP containing available selected individual reference images. |
| Complete Reference Package | ZIP containing selected sheet, available individual views, and applicable reference metadata. |
| Component Reference Sheets | ZIP containing separate sheets for selected clothing, props, anatomical components, and other available component rows, with applicable metadata. |

Export shall not automatically generate missing images or initiate extraction. If only a complete sheet or row image exists, individual views must be explicitly extracted before they can be included as separate files. A component sheet may be deterministically assembled from already available component imagery.

Example package:

```text
Character_Component_References.zip
├── Base_Anatomy/Base_Anatomy_Reference.png
├── Head/Head_Reference.png
├── Head_Hair/Head_Hair_Reference.png
├── Clothing/Pirate_Coat_Reference.png
├── Headwear/Pirate_Hat_Reference.png
├── Props/Prop_Reference.png
└── ReferenceManifest.json
```

Before export of any pending artifact, a modal shall identify pending items and remaining retention time, explain that export does not approve local retention and that local files will expire, and ask whether to continue. Cancellation shall prevent export. A downloaded copy shall remain independent of subsequent local deletion.

## 12. Reference project data and integration

The logical data model shall extend Phase 04 rather than introduce an incompatible asset format. JSON metadata shall reference separately stored image artifacts. The exact schema and persistence implementation remain implementation decisions.

| Entity | Required logical information |
|---|---|
| Reference project | Persistent ID, name, classification, subtype, mode, Base and Detail sections, selected sheet, layout and specification settings |
| Row | Persistent ID, section, order, label, component role, optional classification override, prompt, source references, generation settings, selected output, lock state |
| View slot | Direction or feature role, enabled state, lock state, selected image artifact, candidate references, generation parameters |
| Specification panel | Owner section or row, Label, Sub Label, custom fields, inclusion flag, styling |
| Image artifact | Artifact ID, format, native/output dimensions, source relationships, approval state, expiration, provider metadata |
| Extraction region | Source artifact, crop boundaries, assigned view/role, component association, detection uncertainty |
| Generation job | Job ID, provider/version, inputs, outputs, requested count, parameters, execution status |

Reference Generation shall support transfer of selected artifacts to an originating or newly defined 3D asset. Context shall include the asset identifier, classification, intended reference role, and component assignment. Navigation back to 3D Generation shall preserve existing progress. Transfer shall not duplicate physical files unnecessarily or automatically approve pending artifacts.

## 13. Model constraints

Constraints apply to the provider or combination of providers assigned to the relevant capability, not necessarily to every individual model.

### 13.1 Generation providers

| ID | Constraint |
|---|---|
| RMC-001 | Support local-only inference and programmatic requests. |
| RMC-002 | Support image-conditioned generation. |
| RMC-003 | Support up to four source images for Simple and six per Advanced row, directly or through compatible application-managed preparation. |
| RMC-004 | Support coordinated multi-view representations of the same asset. |
| RMC-005 | Preserve recognizable identity, proportions, component placement, colors, materials, and intended asymmetry. |
| RMC-006 | Support classification-aware prompts and anatomy-appropriate poses. |
| RMC-007 | Support isolated breakaway components and multiple perspectives of those components. |
| RMC-008 | Support individual requested directional views and independent row execution. |
| RMC-009 | Support up to six directional output slots per Advanced row through coordinated or sequential execution. |
| RMC-010 | Declare supported input counts, output resolutions, aspect ratios, formats, and batch limits. |
| RMC-011 | Produce independently accessible images at the view or row level as appropriate to the workflow. |
| RMC-012 | Permit conditioning on selected existing views where supported. |
| RMC-013 | Produce outputs compatible with deterministic sheet assembly and downstream geometry preparation. |
| RMC-014 | Operate within configured local hardware limits and permit resource reclamation after inference. |
| RMC-015 | Avoid permanent retention of unnecessary temporary inference data. |
| RMC-016 | Support traceable generation parameters while the associated artifact remains retained. |

### 13.2 Extraction and validation providers

| ID | Constraint |
|---|---|
| EMC-001 | Support local execution and programmatically accessible outputs. |
| EMC-002 | Detect multiple reference regions in nonuniform sheets. |
| EMC-003 | Return usable region coordinates, bounding boxes, or segmentation masks. |
| EMC-004 | Identify likely viewing directions and report uncertainty. |
| EMC-005 | Distinguish visual regions from annotations and decorative content. |
| EMC-006 | Preserve source content during ordinary extraction; cropping remains deterministic. |
| VMC-001 | Support local comparison of multiple reference images where AI validation is used. |
| VMC-002 | Identify structural, anatomical, component, orientation, and configuration discrepancies relevant to declared capabilities. |
| VMC-003 | Return structured findings identifying affected images and uncertainty. |
| VMC-004 | Do not modify reference images during validation. |

## 14. Validation assertions

| ID | Test | Expected result |
|---|---|---|
| RMA-001 | Generate a Simple sheet using four compatible inputs. | Complete coordinated sheet is produced; consumed inputs are disclosed. |
| RMA-002 | Request three Simple generations. | Three independently selectable complete sheets are produced. |
| RMA-003 | Generate a humanoid Base row. | Requested views preserve intended identity, anatomy, and neutral pose. |
| RMA-004 | Generate vehicle and creature references. | Defining structures, component counts, and anatomical features remain consistent. |
| RMA-005 | Generate an isolated clothing or hair row. | Component remains isolated and consistent across requested views. |
| RMA-006 | Generate an intentionally asymmetric asset. | Intended asymmetric features remain present. |
| RMA-007 | Configure all six Advanced directional slots and six source references. | Each slot is independently manageable; provider limits are enforced and disclosed. |
| RMA-008 | Upload a rear view. | Other selected views remain unchanged. |
| RMA-009 | Lock front and left views, then regenerate the row. | Locked image hashes and selected artifact IDs remain unchanged. |
| RMA-010 | Generate missing views. | Existing populated views remain unchanged. |
| RMA-011 | Disable bottom view. | It is excluded from generation and assembly. |
| RMA-012 | Regenerate one view or row. | Unrelated views and rows remain unchanged. |
| RMA-013 | Upload a complete row. | Row is available for assembly without automatic extraction. |
| RMA-014 | Select a reference from another row. | Reference is available without unnecessary file duplication. |
| RMA-015 | Change a source row selection. | Dependent rows are not automatically regenerated. |
| RMA-016 | Override classification for a component row. | Row classification is preserved in export and transfer metadata. |
| RMA-017 | Assemble unequal image sizes. | No unintended stretching or distortion occurs. |
| RMA-018 | Assemble an Advanced sheet. | Source images remain unchanged and extraction does not initiate. |
| RMA-019 | Create Base and Detail specification panels. | Panels are independently editable with Label and Sub Label. |
| RMA-020 | Disable a panel before assembly. | Panel is omitted from the image but its metadata remains available. |
| RMA-021 | Convert Simple to Advanced. | Existing sheet and metadata remain accessible without automatic extraction. |
| RMA-022 | Import a nonuniform reference sheet with annotations. | Visual regions can be detected and corrected manually. |
| RMA-023 | Adjust an extraction boundary. | Output uses the corrected region. |
| RMA-024 | Extract a view without refinement. | Source pixels are preserved without invented imagery. |
| RMA-025 | Extract ambiguous directional views. | Uncertainty is flagged and manual assignment is available. |
| RMA-026 | Validate conflicting reference images. | Discrepancies are clearly flagged without blocking compatible generation. |
| RMA-027 | Submit technically incompatible inputs. | Incompatibility is explained before inference. |
| RMA-028 | Export each of the four profiles. | Applicable selected artifacts are packaged correctly without automatic extraction or generation. |
| RMA-029 | Export component sheets with specification panels. | Each selected component respects its panel inclusion setting. |
| RMA-030 | Export a pending sheet. | Warning modal appears; confirmation does not change approval or expiration. |
| RMA-031 | Approve a sheet with required pending dependencies. | Modal lists dependencies and reasons; confirmation approves the required set. |
| RMA-032 | Deny or expire a generation. | Exclusive files and generation metadata are removed, with valid shared references protected. |
| RMA-033 | Navigate from 3D Generation and transfer results back. | Asset context and reference assignments are preserved. |
| RMA-034 | Execute generation, extraction, and assembly offline. | All supported operations complete locally. |
| RMA-035 | Execute sequential provider jobs. | No concurrent model residency is required. |
| RMA-036 | Compare native and upscaled reference outputs. | Actual dimensions and upscaling status are correctly reported. |

Quantitative visual consistency thresholds and hardware performance thresholds shall be established during provider evaluation. These assertions define expected behavior; they do not claim that a candidate model has already passed testing.

## 15. Application responsibilities

SWIFT shall manage classification, reference slots, row state, prompt editing, lock enforcement, candidate selection, artifact identity, dependency approval, retention, deterministic cropping and assembly, specification text, validation reporting, export packaging, and navigation. AI providers shall perform only the generation, detection, segmentation, or semantic analysis capabilities assigned to them.

## 16. MVP implementation sequence and acceptance criteria

Reference Generation is a development prerequisite before proceeding to Phase 06 of the 3D Generation design.

1. Replace the Character Generation placeholder and establish the two separate workflows.
2. Implement shared project classification, reference state, artifact integration, and provider capability contracts.
3. Implement Simple sheet generation and candidate management.
4. Implement Advanced row and individual view controls, uploads, locks, reference inheritance, and classification overrides.
5. Implement specification panels, deterministic assembly, preview, and Simple to Advanced conversion.
6. Implement manual extraction, automatic region detection, and assignment correction.
7. Implement validation reporting, four export profiles, retention modals, and cross-workspace transfer.
8. Evaluate compatible local providers against the documented constraints and assertions.

The MVP is accepted when both generation modes and the separate extraction workflow are operational locally; Advanced rows support six inputs and independently controlled directional views; selected locked images survive regeneration unchanged; flexible Base and Detail layouts and optional panels assemble without distortion; all four export profiles work with the approved retention and dependency rules; and selected references can be transferred into 3D Generation without losing context or duplicating image generation functionality.

## 17. Technical interpretations and open implementation details

The following safeguards are proposed technical interpretations of approved product decisions:

- Locked images may serve as conditioning references where supported; locking is independent of approval and does not extend retention.
- Generate Missing Views is distinct from regenerating all unlocked views.
- Excluded specification panels remain metadata while their owning project remains retained.
- Complete row uploads remain intact until extraction is explicitly requested.
- Component roles remain distinct from primary asset classifications.
- Source inputs and directional output slots are separate logical collections, each with the approved Advanced row maximum of six.
- The general 1024 reference resolution default and classification-specific row templates are configurable starting points rather than mandatory settings.
- Exact custom-view slot representation, native aspect-ratio behavior, provider selection algorithms, visual validation thresholds, storage implementation, and UI details remain subject to implementation and testing.

No specific AI models, provider libraries, databases, or implementation frameworks are selected by this document. No repository changes or application implementation are represented as completed.
