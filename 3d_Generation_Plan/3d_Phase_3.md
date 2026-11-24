# SWIFT Director | 3D Generation

**Software Design Document**  
**Phase 03: Asset Classification**  
**Version:** 1.0  
**Status:** Finalized for MVP  
**Application location:** SWIFT Director > Asset Generation > 3D Generation  
**Preceding documents:** `3d_Phase_1.md`, `3d_Phase_2.md`

## 3.1 Purpose

Asset classification establishes the intended purpose, structural characteristics, generation requirements, and processing expectations of a three-dimensional asset. Classification is a configurable generation profile rather than merely an organizational tag. It informs reference preparation, compatible provider selection, geometry generation, component identification, material assignment, and export preparation.

This phase remains model agnostic. Requirements may be satisfied by one or more local AI providers and deterministic processing tools. No specific model or implementation technology is selected.

All workflows inherit Phase 02 requirements for local-only execution, sequential inference, nondestructive editing, explicit artifact approval, ten-day pending retention, dependency approval, and ZIP export.

## 3.2 Classification Registry

| ID | Parent classification | Asset type | Optional subtypes |
|---|---|---|---|
| AC-01 | Actors | Humanoid | Organic, Mechanical, Hybrid, Custom |
| AC-02 | Actors | Creature | Quadruped, Bipedal, Winged, Aquatic, Serpentine, Insectoid, Custom |
| AC-03 | Scene Assets | Scene Prop | Furniture, Container, Machinery, Decoration, Fixture, Custom |
| AC-04 | Scene Assets | Vehicle | Ground, Water, Aircraft, Spacecraft, Hybrid, Custom |
| AC-05 | Props | Held Prop | Tool, Instrument, Equipment, Weapon, Container, Custom |
| AC-06 | Props | Interactive Prop | Door, Window, Container, Switch, Lever, Mechanism, Furniture, Custom |
| AC-07 | World Assets | Vehicle Interior | Cockpit, Cabin, Cargo Hold, Passenger Compartment, Engineering Compartment, Complete Interior, Custom |
| AC-08 | World Assets | Scenery | Architecture, Vegetation, Terrain, Natural Formation, Modular Structure, Custom |

Classification is based on intended use, not appearance alone. A decorative chest is a Scene Prop; a chest with an independently opening lid is an Interactive Prop. Vehicle exteriors and interiors are distinct asset types. A Custom subtype does not create a new parent classification or asset type.

## 3.3 Classification Selection

| ID | Functional requirement |
|---|---|
| ACR-001 | Users shall select a parent classification and one of its registered asset types before geometry generation. |
| ACR-002 | Subtype selection shall be optional. |
| ACR-003 | Each asset type shall support a user-defined Custom subtype. |
| ACR-004 | Classification shall determine applicable controls and generation defaults. |
| ACR-005 | The application may recommend a classification using local AI analysis of references. |
| ACR-006 | AI recommendations shall require user confirmation and shall not override an explicit selection. |
| ACR-007 | Users shall be able to classify imported assets and reclassify existing assets. |
| ACR-008 | Reclassification shall not automatically regenerate or overwrite existing artifacts. |
| ACR-009 | Parent, type, and subtype shall be recorded in the asset manifest. |
| ACR-010 | Classification shall influence compatible provider selection. |

The asset definition interface shall present parent selection, asset type, optional subtype, custom subtype text when applicable, asset name, and generation mode. Classification-specific controls shall appear as applicable. Automatic provider selection and advanced manual override shall comply with Phase 02.

## 3.4 Classification-Specific Requirements

The following requirements describe pipeline-level capabilities. A provider need only satisfy the constraints of the role for which it is selected. Assertions shall be evaluated using appropriate reference fixtures and the selected generation mode; unsupported mandatory capabilities shall be detected before execution.

### 3.4.1 Actors / Humanoid

Humanoids possess generally humanoid anatomy, regardless of species, artistic style, or organic composition. Potential components include base body, eyes, teeth and mouth, hair, facial hair, clothing, footwear, armor, accessories, horns, tails, wings, and other anatomical additions.

| ID | Functional requirement |
|---|---|
| HUM-001 | Support neutral A-pose and T-pose reference generation. |
| HUM-002 | Support clean base anatomy without fused clothing or accessories. |
| HUM-003 | Support independent generation or extraction of clothing and accessories where technically possible. |
| HUM-004 | Preserve anatomical proportions across reference views. |
| HUM-005 | Support separately identifiable eyes, hair, facial hair, and mouth components. |
| HUM-006 | Maintain consistent positioning and scale across components. |
| HUM-007 | Support organic, mechanical, and hybrid humanoids. |
| HUM-008 | Support optional CC5 landmark preparation. |
| HUM-009 | Support intentional symmetry and asymmetry. |
| HUM-010 | Preserve species-specific anatomical characteristics. |

| ID | Model constraint |
|---|---|
| HUM-MC-001 | Support humanoid geometry from visual references. |
| HUM-MC-002 | Preserve the requested neutral pose. |
| HUM-MC-003 | Support anatomically consistent multi-view reconstruction. |
| HUM-MC-004 | Generate clean base anatomy or provide output compatible with subsequent base-body reconstruction. |
| HUM-MC-005 | Support independent component generation or compatibility with component extraction. |
| HUM-MC-006 | Produce geometry suitable for subsequent anatomical landmark mapping where requested. |
| HUM-MC-007 | Preserve visible fingers, ears, limbs, and species-specific features. |

| ID | Model assertion | Expected result |
|---|---|---|
| HUM-MA-001 | Generate from consistent multi-view references. | Anatomy and proportions agree with references. |
| HUM-MA-002 | Generate A-pose and T-pose fixtures. | Requested pose is preserved. |
| HUM-MA-003 | Generate clean base body. | Clothing and accessories are not fused into anatomy. |
| HUM-MA-004 | Generate a modular clothed character. | Requested components are independently accessible. |
| HUM-MA-005 | Remove an independent garment. | Underlying body geometry remains present. |
| HUM-MA-006 | Pass humanoid to landmark processing. | Geometry is accepted by the landmark workflow. |
| HUM-MA-007 | Generate a nonhuman humanoid. | Intended species-specific features are preserved. |

The CC5 218-point alignment overlay will be specified in Phase 15. Native CC5 point import and automated rigging are not assumed.

### 3.4.2 Actors / Creature

Creatures possess nonstandard humanoid or nonhumanoid anatomy and may be organic, mechanical, or hybrid. Classification shall accommodate diverse body plans without imposing human anatomy.

| ID | Functional requirement |
|---|---|
| CRE-001 | Support multiple nonhumanoid anatomical structures. |
| CRE-002 | Preserve intended limb counts and attachment locations. |
| CRE-003 | Support classification-specific neutral poses. |
| CRE-004 | Support independent horns, wings, tails, armor, and accessories where applicable. |
| CRE-005 | Support separately identifiable eyes, teeth, claws, and other anatomical features. |
| CRE-006 | Support organic, mechanical, and hybrid creatures. |
| CRE-007 | Preserve body proportions across reference views. |
| CRE-008 | Permit future creature-specific landmark and rigging preparation profiles. |

| ID | Model constraint |
|---|---|
| CRE-MC-001 | Support nonhumanoid anatomical geometry. |
| CRE-MC-002 | Avoid imposing unintended humanoid anatomy. |
| CRE-MC-003 | Preserve intended limb counts and attachments. |
| CRE-MC-004 | Support complex silhouettes and extended anatomy. |
| CRE-MC-005 | Produce geometry compatible with modular processing. |

| ID | Model assertion | Expected result |
|---|---|---|
| CRE-MA-001 | Generate a quadruped. | Four intended limbs are correctly positioned. |
| CRE-MA-002 | Generate a winged creature. | Wings are present and appropriately attached. |
| CRE-MA-003 | Generate nonhumanoid anatomy. | No unintended humanoid characteristics appear. |
| CRE-MA-004 | Generate from multiple reference views. | Anatomy remains consistent across views. |
| CRE-MA-005 | Process an independent creature component. | Scale and alignment remain appropriate. |

### 3.4.3 Scene Assets / Scene Prop

Scene props are independently placeable environmental objects. They prioritize placement, structural fidelity, reusable components, and compatibility with scene construction tools.

| ID | Functional requirement |
|---|---|
| SPR-001 | Support independently placeable environmental objects. |
| SPR-002 | Support user-defined dimensions and scale. |
| SPR-003 | Support ground-aligned, wall-mounted, ceiling-mounted, and freestanding placement profiles. |
| SPR-004 | Support independent components where requested. |
| SPR-005 | Support configurable pivots and applicable spatial reference points. |
| SPR-006 | Preserve visible cavities, openings, and functional surfaces. |
| SPR-007 | Support optional collision geometry preparation, subject to later scope confirmation. |
| SPR-008 | Support reusable modular components. |

| ID | Model constraint |
|---|---|
| SPR-MC-001 | Support isolated environmental object generation. |
| SPR-MC-002 | Preserve defining shape and proportions. |
| SPR-MC-003 | Support hard-surface and organic object geometry as declared. |
| SPR-MC-004 | Preserve openings and cavities. |
| SPR-MC-005 | Produce geometry compatible with component extraction or generation. |

| ID | Model assertion | Expected result |
|---|---|---|
| SPR-MA-001 | Generate furniture. | Required structural features remain present. |
| SPR-MA-002 | Generate an open container. | Visible interior cavity is reconstructed. |
| SPR-MA-003 | Request a modular component. | Component is independently accessible. |
| SPR-MA-004 | Generate from multiple views. | Geometry is consistent across visible perspectives. |

### 3.4.4 Scene Assets / Vehicle

Vehicles are transportation platforms or mobile structures. Vehicle generation is exterior-only during the MVP; interiors are generated separately under Vehicle Interior.

| ID | Functional requirement |
|---|---|
| VEH-001 | Support ground, water, aircraft, spacecraft, and hybrid vehicles. |
| VEH-002 | Support consistent front, rear, left, right, top, and bottom orientation. |
| VEH-003 | Support user-defined overall dimensions. |
| VEH-004 | Support independent structural components. |
| VEH-005 | Support separate glass and transparent surfaces. |
| VEH-006 | Support independent wheels, doors, hatches, landing gear, and similar movable components. |
| VEH-007 | Generate exterior geometry only. |
| VEH-008 | Support component-specific pivots and applicable spatial reference points. |
| VEH-009 | Preserve intended symmetry or asymmetry. |
| VEH-010 | Support optional collision geometry preparation, subject to later scope confirmation. |

| ID | Model constraint |
|---|---|
| VEH-MC-001 | Support complex hard-surface geometry. |
| VEH-MC-002 | Support consistent multi-view vehicle reconstruction. |
| VEH-MC-003 | Preserve recognizable structural features. |
| VEH-MC-004 | Preserve component positioning and proportions. |
| VEH-MC-005 | Support modular generation or compatibility with component extraction. |
| VEH-MC-006 | Preserve openings and transparent surface boundaries. |
| VEH-MC-007 | Support intentionally asymmetrical designs. |

| ID | Model assertion | Expected result |
|---|---|---|
| VEH-MA-001 | Generate from orthogonal references. | Structural design agrees across perspectives. |
| VEH-MA-002 | Generate a vehicle with multiple engines. | Engine count and positioning are preserved. |
| VEH-MA-003 | Generate a vehicle with cockpit glass. | Glass boundaries permit independent material assignment. |
| VEH-MA-004 | Generate a modular vehicle. | Requested components remain independently accessible and aligned. |
| VEH-MA-005 | Generate an asymmetrical vehicle. | Unrequested symmetry is not introduced. |
| VEH-MA-006 | Request exterior-only generation. | No separately generated interior is required or included. |

### 3.4.5 Props / Held Prop

Held Props are objects intended to be carried, held, worn as equipment, or manipulated by a character. They prioritize orientation, scale, and interaction metadata.

| ID | Functional requirement |
|---|---|
| HPR-001 | Generate independently usable held objects. |
| HPR-002 | Support user-defined dimensions. |
| HPR-003 | Support independently toggled primary, secondary, and tertiary grips. |
| HPR-004 | Support configurable orientation and optional custom pivot. |
| HPR-005 | Support independent movable or removable components. |
| HPR-006 | Preserve functional geometry such as handles, grips, and attachment surfaces. |
| HPR-007 | Export applicable spatial reference metadata. |
| HPR-008 | Support single-handed and multi-point interaction configurations. |

| ID | Model constraint |
|---|---|
| HPR-MC-001 | Preserve functional object geometry. |
| HPR-MC-002 | Produce isolated object geometry without unintended character or hand geometry. |
| HPR-MC-003 | Preserve identifiable grip surfaces. |
| HPR-MC-004 | Support thin geometry and required openings. |
| HPR-MC-005 | Produce geometry compatible with component and spatial reference processing. |

| ID | Model assertion | Expected result |
|---|---|---|
| HPR-MA-001 | Generate a prop from a reference showing it held by a character. | Intended prop is isolated. |
| HPR-MA-002 | Generate a handled object. | Handle remains identifiable. |
| HPR-MA-003 | Generate a prop with openings. | Required openings remain present. |
| HPR-MA-004 | Process a modular held prop. | Components remain correctly aligned. |

### 3.4.6 Props / Interactive Prop

Interactive Props support direct interaction, manipulation, movement, or physical configuration changes. Examples include doors, windows, opening containers, switches, and mechanisms. This phase prepares assets for interaction; it does not implement animation or physical simulation.

| ID | Functional requirement |
|---|---|
| IPR-001 | Support independent static and movable components. |
| IPR-002 | Support independent component pivots. |
| IPR-003 | Support configurable grip and interaction points. |
| IPR-004 | Preserve functional openings, cavities, and connection surfaces. |
| IPR-005 | Support independent component material assignments. |
| IPR-006 | Preserve alignment between movable and stationary components. |
| IPR-007 | Support user-defined physical dimensions. |
| IPR-008 | Support component hierarchies and parent-child relationships. |
| IPR-009 | Support all three generation modes. |
| IPR-010 | Support export of independently manipulable geometry when generated in a modular mode. |

| ID | Model constraint |
|---|---|
| IPR-MC-001 | Preserve identifiable functional components. |
| IPR-MC-002 | Support independent component generation or compatibility with extraction. |
| IPR-MC-003 | Preserve visible cavities and openings. |
| IPR-MC-004 | Preserve relative component positioning and proportions. |
| IPR-MC-005 | Produce geometry compatible with application-managed pivots and interaction points. |

| ID | Model assertion | Expected result |
|---|---|---|
| IPR-MA-001 | Generate a modular door. | Door and frame are independently accessible. |
| IPR-MA-002 | Generate a modular opening chest. | Body and lid are independent; cavity remains present. |
| IPR-MA-003 | Generate a modular lever. | Lever is independently manipulable. |
| IPR-MA-004 | Rotate a component about its configured pivot. | Unrelated components remain unchanged. |
| IPR-MA-005 | Export a modular interactive prop. | Component geometry and spatial relationships are preserved. |

The final two assertions validate integrated application behavior, not native AI inference alone.

### 3.4.7 World Assets / Vehicle Interior

Vehicle Interiors are independent environmental spaces representing internal transportation compartments. An exterior vehicle asset is not a prerequisite.

| ID | Functional requirement |
|---|---|
| VIN-001 | Support independent vehicle interior generation. |
| VIN-002 | Support compartment-specific reference images. |
| VIN-003 | Support individual compartments or complete interiors without exterior generation. |
| VIN-004 | Support independent floors, walls, ceilings, and structural components. |
| VIN-005 | Support independent interior fixtures. |
| VIN-006 | Preserve openings, entrances, and passageways. |
| VIN-007 | Support user-defined interior dimensions. |
| VIN-008 | Support independently accessible doors and interactive components in modular modes. |
| VIN-009 | Maintain consistent spatial orientation across components. |
| VIN-010 | Support all three generation modes. |
| VIN-011 | Support independent interior material assignments. |
| VIN-012 | Support geometry suitable for viewing from inside the asset. |

| ID | Model constraint |
|---|---|
| VIN-MC-001 | Support interior-focused geometry reconstruction. |
| VIN-MC-002 | Preserve usable internal spatial geometry. |
| VIN-MC-003 | Avoid filling intended internal spaces with solid geometry. |
| VIN-MC-004 | Preserve visible entrances, openings, and passageways. |
| VIN-MC-005 | Support consistent reconstruction across interior views. |
| VIN-MC-006 | Support modular component generation or extraction. |
| VIN-MC-007 | Produce geometry compatible with interior-facing materials and normals. |

| ID | Model assertion | Expected result |
|---|---|---|
| VIN-MA-001 | Generate a cockpit. | Usable interior and intended cockpit features are present. |
| VIN-MA-002 | Generate an empty cargo compartment. | Intended internal space remains unobstructed. |
| VIN-MA-003 | Generate a modular interior. | Structural components remain independently accessible. |
| VIN-MA-004 | Inspect from inside the asset. | Interior-facing surfaces render correctly. |
| VIN-MA-005 | Generate an interior with an entrance. | Intended opening remains accessible. |
| VIN-MA-006 | Apply materials to interior surfaces. | Materials are assigned to intended surfaces. |
| VIN-MA-007 | Generate from multiple interior references. | Spatial layout agrees across supplied views. |

### 3.4.8 World Assets / Scenery

Scenery establishes the physical setting of a scene through architectural, natural, and modular environmental assets. Applicable scenery workflows may generate exterior-only or interior-only geometry, but never both together in the MVP.

| ID | Functional requirement |
|---|---|
| SCN-001 | Support architectural, natural, and modular environmental assets. |
| SCN-002 | Support user-defined dimensions. |
| SCN-003 | Support independent structural components. |
| SCN-004 | Support separate exterior-only and interior-only profiles where applicable. |
| SCN-005 | Preserve windows, entrances, passages, and other intended openings. |
| SCN-006 | Support ground alignment and configurable origins. |
| SCN-007 | Support repeatable and reusable architectural components. |
| SCN-008 | Support modular connection metadata, subject to later detailed design. |
| SCN-009 | Support vegetation and natural geometry. |
| SCN-010 | Support optional collision geometry preparation, subject to later scope confirmation. |
| SCN-011 | Support terrain segments without requiring an entire environment. |

| ID | Model constraint |
|---|---|
| SCN-MC-001 | Support architectural or natural geometry according to declared capabilities. |
| SCN-MC-002 | Preserve large-scale structural proportions. |
| SCN-MC-003 | Support multi-view reconstruction. |
| SCN-MC-004 | Preserve visible architectural openings. |
| SCN-MC-005 | Support modular component processing. |
| SCN-MC-006 | Preserve complex natural silhouettes where applicable. |
| SCN-MC-007 | Support usable internal spatial geometry when interior generation is declared. |

| ID | Model assertion | Expected result |
|---|---|---|
| SCN-MA-001 | Generate a building from multiple references. | Structure agrees across views. |
| SCN-MA-002 | Generate a structure with a doorway. | Intended doorway remains open. |
| SCN-MA-003 | Generate modular architecture. | Requested structural components remain independently accessible. |
| SCN-MA-004 | Generate vegetation. | Intended natural silhouette is preserved. |
| SCN-MA-005 | Process a modular scenery component. | Component is independently placeable. |
| SCN-MA-006 | Generate an interior-only architectural space. | Intended internal space is usable without requiring exterior geometry. |

## 3.5 Modular Generation Modes

| Mode | Required behavior |
|---|---|
| Unified | Produce one complete mesh. |
| Automatic Modular | Identify and produce independently accessible semantic components using the local pipeline. |
| Directed Modular | Accept a user-defined component list and generate independently accessible requested components. |

| ID | Functional requirement |
|---|---|
| MOD-001 | All eight asset types shall expose the three generation modes. |
| MOD-002 | Directed Modular shall allow users to add, remove, and select requested components before generation. |
| MOD-003 | Automatic Modular shall identify components appropriate to the asset classification. |
| MOD-004 | Modular components shall preserve shared scale, orientation, and alignment. |
| MOD-005 | The application shall validate provider compatibility before executing a selected mode. |
| MOD-006 | Multiple local providers may collectively satisfy a generation mode through sequential processing. |
| MOD-007 | Regenerating a component shall not overwrite unrelated or approved artifacts. |

| ID | Constraint or assertion | Expected behavior |
|---|---|---|
| MOD-MC-001 | Provider compatibility | Provider declares supported modes or intermediate outputs compatible with subsequent component processing. |
| MOD-MA-001 | Generate in Unified mode. | One complete mesh is returned. |
| MOD-MA-002 | Generate in Automatic Modular mode. | Identifiable requested-class components are independently accessible. |
| MOD-MA-003 | Generate in Directed Modular mode. | Explicitly requested components are independently accessible and aligned, or a structured failure is reported. |
| MOD-MA-004 | Select an unsupported mode. | Incompatibility is identified before execution. |

## 3.6 Shared Generation Settings

Geometry and texture quality remain independent of one another and of asset classification.

| Geometry profile | Minimum polygon count | Maximum polygon count |
|---|---:|---:|
| Low Poly | 500 | 10,000 |
| Mid Poly | 10,001 | 30,000 |
| High Poly | 30,001 | 500,000 |

| Texture profile | Output dimensions |
|---|---|
| 512 | 512 x 512 |
| 1024 | 1024 x 1024 |
| 2048 | 2048 x 2048 |
| 4096 | 4096 x 4096 |

Shared settings include asset name and description, parent classification, asset type, optional subtype, artistic style, reference images, optional physical dimensions, geometry profile and target polygon count, texture resolution, generation mode, symmetry preferences, generation instructions, automatic compatible provider selection, and advanced manual provider override. Polygon measurement conventions and quality tolerances will be established in the geometry phases; native versus processed texture resolution will be addressed in the texture phase.

## 3.7 Measurement System

Centimeters are the canonical internal measurement unit. Metric input and display use meters and centimeters; imperial input and display use feet and inches. Conversion shall use 100 cm per meter, 30.48 cm per foot, and 2.54 cm per inch.

| ID | Functional requirement |
|---|---|
| DIM-001 | Store canonical asset dimensions in centimeters. |
| DIM-002 | Support input and display in meters and centimeters. |
| DIM-003 | Support input and display in feet and inches. |
| DIM-004 | Changing display units shall not change actual asset scale. |
| DIM-005 | Dimensions shall be optional during initial generation. |
| DIM-006 | Users may assign or modify dimensions before export. |
| DIM-007 | Export processing shall account for destination format measurement conventions. |
| DIM-008 | Dimensional adjustments shall preserve component alignment. |
| DIM-009 | Users may proportionally scale an entire asset. |

Model providers need not generate natively in centimeters. SWIFT shall normalize generated geometry and maintain unit-consistent component transforms.

| ID | Validation assertion | Expected result |
|---|---|---|
| DIM-A-001 | Enter 1 m and 25 cm. | Canonical value is 125 cm. |
| DIM-A-002 | Enter 2 ft and 6 in. | Canonical value is 76.2 cm. |
| DIM-A-003 | Switch display units repeatedly. | Canonical dimensions remain unchanged. |
| DIM-A-004 | Scale an assembled modular asset proportionally. | Components and enabled spatial points remain aligned. |
| DIM-A-005 | Export an asset with specified dimensions. | Exported scale matches the destination format convention. |

## 3.8 Structural Profiles

| Asset type | MVP structural profile |
|---|---|
| Vehicle | Exterior Only |
| Vehicle Interior | Interior Only |
| Scenery | Exterior Only or Interior Only, where applicable |
| All other types | Object-specific geometry |

Combined interior and exterior generation, automatic fitting of independent interiors to exteriors, and automatic structural alignment between them are outside MVP scope. An interior does not require an existing exterior asset. Visible functional cavities, such as an open container, remain supported and do not constitute combined interior/exterior world generation.

| ID | Validation assertion | Expected result |
|---|---|---|
| STR-A-001 | Select Vehicle. | Exterior-only workflow is available. |
| STR-A-002 | Select Vehicle Interior without a vehicle asset. | Independent interior generation is available. |
| STR-A-003 | Select an architectural Scenery subtype. | Applicable exterior-only and interior-only profiles are available separately. |
| STR-A-004 | Request combined interior and exterior generation. | Unsupported MVP combination is identified before execution. |

## 3.9 Grip and Pivot Configuration

Four optional spatial reference point types shall be supported: Primary Grip, Secondary Grip, Tertiary Grip, and custom Pivot. Each is independently enabled or disabled. Points shall be manually configurable at asset or component level and shall include position and orientation. A tertiary grip may identify an additional interaction location on a removable component rather than a simultaneous handhold.

| ID | Functional requirement |
|---|---|
| SRP-001 | Independently enable or disable Primary Grip. |
| SRP-002 | Independently enable or disable Secondary Grip. |
| SRP-003 | Independently enable or disable Tertiary Grip. |
| SRP-004 | Independently enable or disable a custom Pivot. |
| SRP-005 | Display enabled reference points in the 3D viewport. |
| SRP-006 | Allow manual placement of enabled points. |
| SRP-007 | Store position and rotation for each enabled point. |
| SRP-008 | Associate points with the complete asset or an individual component. |
| SRP-009 | Maintain relative positions during asset or component transforms. |
| SRP-010 | Store positional coordinates in canonical centimeters. |
| SRP-011 | Include enabled points and component associations in the asset manifest. |
| SRP-012 | Exclude disabled points from active export metadata. |
| SRP-013 | Reference point editing shall not modify underlying mesh geometry. |

Disabling the custom pivot does not remove the intrinsic mathematical mesh origin. Native grip or pivot prediction is not required of geometry providers. Optional model recommendations shall remain subject to user control.

| ID | Validation assertion | Expected result |
|---|---|---|
| SRP-MA-001 | Enable Primary Grip. | Editable point appears. |
| SRP-MA-002 | Enable all three grips. | Each remains independently configurable. |
| SRP-MA-003 | Associate a grip with a removable component. | Point follows its assigned component. |
| SRP-MA-004 | Transform a parent asset. | Points maintain their relative positions and orientations. |
| SRP-MA-005 | Disable a point. | Point is excluded from active export metadata. |
| SRP-MA-006 | Export enabled points. | Position, orientation, and component association are preserved. |
| SRP-MA-007 | Rotate a component about its custom pivot. | Rotation occurs about the configured location. |

## 3.10 Classification Capability Matrix

All asset types support multi-view inputs, modular generation, geometry optimization, material generation, and texture editing at the application level. Specialized controls shall be displayed where applicable.

| Capability | Humanoid | Creature | Scene Prop | Vehicle | Held Prop | Interactive Prop | Vehicle Interior | Scenery |
|---|---|---|---|---|---|---|---|---|
| Neutral pose | Yes | Yes | N/A | N/A | N/A | N/A | N/A | N/A |
| Clean base anatomy | Yes | Optional | N/A | N/A | N/A | N/A | N/A | N/A |
| CC5 landmarks | Optional | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Grip points | As applicable | As applicable | As applicable | As applicable | Optional | Optional | As applicable | As applicable |
| Custom pivot | Optional | Optional | Optional | Optional | Optional | Optional | Optional | Optional |
| Component-level points | Optional | Optional | Optional | Optional | Optional | Optional | Optional | Optional |
| Ground alignment | Yes | Yes | As applicable | As applicable | As applicable | As applicable | As applicable | As applicable |
| Movable components | As applicable | As applicable | As applicable | Modular | As applicable | Modular | Modular | As applicable |
| Interior-only world generation | N/A | N/A | N/A | N/A | N/A | N/A | Yes | As applicable |
| Exterior-only world generation | N/A | N/A | N/A | Yes | N/A | N/A | N/A | As applicable |

Optional collision geometry and generalized connection metadata remain subject to later detailed scope confirmation; they are not prerequisites for approval of this phase.

## 3.11 Classification Model Constraints

| ID | Constraint |
|---|---|
| ACMC-001 | Providers must declare supported asset classifications. |
| ACMC-002 | Providers must declare supported input types and reference views. |
| ACMC-003 | Providers must declare supported structural and anatomical capabilities. |
| ACMC-004 | Providers must accept classification-specific instructions where supported. |
| ACMC-005 | Providers must not be selected for unsupported mandatory capabilities. |
| ACMC-006 | Outputs must be compatible with subsequent classification-specific processing. |
| ACMC-007 | Providers must support independent local execution. |
| ACMC-008 | Generated outputs must be capable of validation against classification requirements. |
| ACMC-009 | Providers must expose known classification-specific limitations through their adapters. |
| ACMC-010 | Multiple providers may collectively satisfy classification requirements through sequential execution. |

## 3.12 Classification Model Assertions

| ID | Test | Expected result |
|---|---|---|
| ACMA-001 | Query provider capabilities. | Supported classifications are returned. |
| ACMA-002 | Select an unsupported classification. | Incompatible providers are excluded from automatic selection. |
| ACMA-003 | Generate under a supported classification. | Applicable supported settings are passed to the provider. |
| ACMA-004 | Reclassify an existing asset. | Existing geometry and textures remain unchanged. |
| ACMA-005 | Request functionality requiring multiple providers. | Compatible providers execute sequentially. |
| ACMA-006 | Request an unsupported mandatory capability. | Limitation is identified before execution. |
| ACMA-007 | Export a classified asset. | Parent, type, subtype, and applicable metadata appear in the manifest. |
| ACMA-008 | Manually override provider selection. | Compatibility is validated before execution. |
| ACMA-009 | Attempt geometry generation without confirmed classification. | Generation is blocked until selection is confirmed. |

Qualitative assertions in this phase establish evaluation intent. Repeatable fixtures, quantitative tolerances, and model qualification thresholds shall be defined in the relevant technical phases and Phase 25. Assertions involving export, point placement, or deterministic mesh processing validate the integrated pipeline rather than the AI provider in isolation.

## 3.13 Application Responsibilities

| SWIFT application responsibility | AI provider responsibility |
|---|---|
| Classification selection and registry | Optional classification recommendation |
| Generation profile management | Classification-aware generation |
| Dimension and scale management | Relative proportion preservation |
| Polygon measurement and validation | Geometry reconstruction |
| Component hierarchy and relationships | Semantic component identification and generation |
| Grip, pivot, and orientation editing | Optional spatial point estimation |
| Capability validation and provider selection | Declared capability execution |
| Artifact approval, retention, and dependency protection | Generation of persistable intermediate artifacts |
| Manifest and ZIP export | Compatible output artifacts |

## 3.14 Acceptance Criteria

- Four parent classifications and eight asset types are available with optional predefined and Custom subtypes.
- Parent and asset type must be confirmed before geometry generation.
- All three generation modes are available at the application level, with compatibility validated before execution.
- Classification-specific geometry, component, and reference requirements can be tested against appropriate fixtures.
- Reclassification does not automatically regenerate or overwrite artifacts.
- Centimeters are canonical; metric and imperial display and input do not alter scale.
- Vehicle exteriors, vehicle interiors, and applicable scenery structural profiles are generated independently.
- Primary, secondary, and tertiary grips and custom pivots can be independently enabled, manually positioned, oriented, and assigned at asset or component level.
- Applicable classification and spatial metadata are preserved in the unified export package.
- All workflows comply with Phase 02 architecture and retention requirements.

## 3.15 Approved Decisions and Deferred Details

All classification hierarchy, subtype, generation mode, measurement system, structural profile, and spatial reference decisions in this document are approved for MVP. The original six-type registry in Phase 01 is superseded by the four-parent, eight-type registry in this phase. The earlier combined interior/exterior proposal is superseded by separate structural profiles.

Detailed axis conventions, transform representation, topology metrics, component schemas, automatic landmark placement, collision geometry scope, generalized connection metadata, and quantitative model validation thresholds will be addressed in subsequent phases. Full skeletal animation, physical interaction simulation, and automatic interior/exterior fitting are not required by this phase.

No specific AI models have been selected.

**Next phase:** Phase 04: Asset Data Structure and Lifecycle.
