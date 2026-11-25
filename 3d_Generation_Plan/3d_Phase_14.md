# Phase 14: Character Preparation

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 14.1 Purpose and boundaries

Prepare a clean, modular character for downstream authoring without requiring the character to be regenerated or its accessories to be welded into the body. MVP provides full humanoid preparation and general creature inspection. Dedicated creature preparation is outside MVP. The full path assembles and validates a clean humanoid base, applicable separate components, canonical transforms, and an explicitly reviewed A-pose or T-pose. Preparation is not certification of animation readiness. Phase 15 owns character landmarks and the CC5 alignment handoff. Phase 18 owns packages and destination-specific export.

Phase 08 established independent component production, configurations, and explicit fitting. This phase applies those tools to characters rather than creating a competing generator. Local processing, canonical FBX, right-handed Y-up and +Z asset forward, centimeters, explicit dependency approval, automatic validation with red defect overlays, manual repair, and the ten-day pending lifecycle all carry forward. The first working demo includes character preparation, and MVP acceptance includes a modular humanoid fixture as defined in Phase 26.

The general character tools in this phase are distinct from the CC5 handoff. Phase 15 does not require the user to place, adjust, or approve landmarks individually in Director.

## 14.2 Inputs, prepared artifacts, and roles

| Direction | Record | Notes |
|---|---|---|
| Input | Confirmed actor classification and optional subtype | Humanoid and Creature remain distinct. No additional primary classification is created. |
| Input | Base and optional components | Existing or generated geometry, plus independent textures, materials, UVs, and references. Bind explicit revisions and inspection pose. |
| Input | Preparation profile | Intended handoff, A-pose or T-pose selection, feet/ground alignment, stature if specified, attachment selections, and required/optional roles. |
| Input | Optional compatible rig and skin-weight transfer pair | Pin the selected source rig/weights and target mesh revisions. Verify skeleton, coordinate space, and binding applicability before execution. |
| Output | Character preparation record | Manifest-compatible role bindings, transforms, user-confirmed scale, pose, completeness, applicability, diagnostics, and artifact IDs. |
| Output | Optional independently reviewable candidate derivatives | Any explicit automatic A/T conversion, skin-weight transfer, fit, base reconstruction, or other repair creates a separate artifact. No geometry derivative is mandatory for an already compatible source. |
| Output | Phase 15 handoff selection | The exact clean base, pose, UV revision, role and side definitions, and an eligibility report, with no generated landmark data yet. |

The base body must be independently viewable with clothing and accessories hidden. Independent component roles may include eye meshes, teeth, tongue, scalp hair, facial hair, horns, clothing, footwear, and equipment as applicable. Keep a clean base mandatory for humanoid preparation. Require separate eyes, teeth, and tongue only if called for by the selected workflow. Clothing, hair, and accessories remain distinct optional components. Do not treat generated hidden anatomy as observed evidence. Supported imported rigging and explicit transfer of existing weights are in scope. New rig generation, articulated facial motion, painting weights from scratch, runtime physics, and full morph authoring are not.

## 14.3 Preparation workflow

1. Select an existing actor and preparation purpose. Assign stable component roles and anatomical laterality where meaningful. Keep the source identified even if a candidate is under review. Distinguish anatomical right and left from coordinate axis signs.
2. Isolate the base and confirm required coverage. Inspect hidden body areas, through-holes, intersections, neck, mouth, eye sockets, hands and feet as applicable to the chosen profile. An open seam designed for a separate component is not automatically a defect. Distinguish intentional openings from unexpectedly missing geometry.
3. Classify any missing body region as a defect. Offer explicit Phase 08 reconstruction, an alternate existing or independently generated body, or manual repair. Removing clothing alone does not restore concealed skin. Never create hidden geometry without an explicit request.
4. Inspect neutral pose and standing orientation. Accept A-pose and T-pose when compatible with the chosen workflow. When conversion is needed, explicitly initiate automatic A-to-T or T-to-A conversion. Review the derivative and affected components, and use it only after acceptance. Verify destination-specific pose requirements separately. Allow whole-character rigid transform corrections without suggesting that rigid rotation can fix limb articulation. Use a corrected import if the input does not qualify for supported conversion. Separate global transform, root, ground origin, and component-local transforms.
5. Inspect eyes, mouth and apparel in isolation and as an assembly. Confirm placement and fit against the chosen pose and normalized scale. Manual Fitting, Automatic Alignment, and Automatic Geometry Fitting follow Phase 08. A fit updates only a selected source derivative, never the body target. Existing base, UVs, and textures remain untouched unless an independently scoped edit is requested.
6. When needed, select a compatible source rig/weights and target mesh. Preview compatibility, intentionally run skin-weight transfer, and inspect the separate candidate under reference poses. Preserve both original meshes. Report unmapped bones, unsupported influences, invalid or incomplete coverage, and deviations. Do not call an artifact animation-ready solely because its weight data is valid.
7. Review the preparation report. Distinguish source geometry faults, profile-specific incompatibilities, warnings, and manual checks. Mark a handoff eligible only when the specified profile's required checks pass. Optionally retain an incomplete working character without calling it export-ready.

## 14.4 Functional requirements and controls

| ID | Requirement |
|---|---|
| CHP-001 | Reuse the Phase 03 classification and Phase 08 component system. Show semantic role, source, retained state, variant, component-local transform, and side where it applies. Expose full humanoid preparation and general Creature inspection without advertising dedicated Creature preparation. |
| CHP-002 | Provide base-only, assembled, component isolation, and selected close-up inspection. Toggling component visibility cannot delete it, fuse geometry, or alter the retained texture bindings. |
| CHP-003 | Validate scale, ground reference, canonical facing, pose applicability, duplicate or missing required components, and known geometry faults. A clean base is required for every humanoid preparation profile. Separate eyes, teeth, or tongue are required only where the workflow calls for them. Separate objective checks and human-confirmed character completeness. |
| CHP-004 | Permit profile-appropriate geometry review of lips and interior mouth, intentional symmetry or asymmetry, eyes and socket placement, and fit-sensitive component intersections. Never describe a static check as facial deformation validation. |
| CHP-005 | Preserve independently reusable wearable components and variant references. Applying an assembly candidate cannot rewrite the source base, including its mesh, UVs, surfaces, and attachment metadata. |
| CHP-006 | Changes to topology, UVs, or pose that affect fitted or downstream assets shall invalidate only affected compatibility claims. Flag the impacted components, texture sets, saved masks and landmarks. Rebind or repair only by explicit action. |
| CHP-007 | Report whether a source contains a skeleton, weights, blend shapes or animation. Preserve supported imported rigging and weights. Do not strip, transfer, rename, or modify them silently. Destination profiles needing a clean unrigged body must require explicit compatible inputs or a separately authorized derivative operation. |
| CHP-008 | Prevent repeated or conflicting preparation generation submissions within the affected workflow while active. Footprint changes and manual inspection are separate from job admission. |
| CHP-009 | Provide automated validation and explicit Safe or Advanced repair actions where available. Defect regions display red separately from deliberate component and body-part overlays. |
| CHP-010 | Provide a pinned handoff to Phase 15 without auto-running mapping or copying its overlay into production maps. Passing Phase 14 alone does not imply CC5 compatibility or automated transfer. |
| CHP-011 | Use the common pending lifecycle and approval dependency prompt. Permit pending export only through the approved warning and confirmation flow, without marking the source permanently approved. |
| CHP-012 | Accept applicable A-pose and T-pose inputs. Provide user-initiated automatic A-to-T and T-to-A conversion for compatible inputs. Review each derivative, recheck profile pose requirements and affected dependencies, and preserve the source and original transforms. |
| CHP-013 | Allow explicit skin-weight transfer between compatible meshes using existing source weights. Validate influence correspondence, finite nonnegative weights, normalization within the declared tolerance, and weighted vertex coverage. Produce a separate reviewable target derivative and preserve both originals. |

Workspace controls: profile, selected body and role overrides, optional stature, neutral pose designation and conversion, source/target skin-weight transfer controls, ground guide, mesh-versus-assembly inspect modes, fit action and clearance control where supported, component and texture locks, and review disposition.

## 14.5 Provider constraints and application responsibilities

| ID | Provider constraint | SWIFT responsibility |
|---|---|---|
| CPC-001 | Declare applicable classifications, compatible A/T conversion inputs, body region coverage, supported component roles, rig and weight transfer compatibility, and preservation capabilities. | Map to existing asset roles, validate required features and reject inapplicable operations before execution. |
| CPC-002 | Any permitted reconstruction, pose conversion, skin-weight transfer or fitting returns an independent, reviewable result with changed regions and potential dependency impact. | Preserve target and original assets, canonicalize validated FBX only, and record affected slots, UVs and downstream dependencies. |
| CPC-003 | Do not claim deformation quality, stable vertex indexing, or rig preservation without relevant output guarantees and reproducible fixtures. | Validate actual topology, ordering, bindings and transforms wherever required by the active profile. Treat uncertain role inference as a reviewer suggestion. |
| CPC-004 | Report inability to reconstruct a role, pose, hidden region, or asset component rather than emitting a pretend complete result. | Present incomplete results honestly and offer compatible manual recovery paths. |

## 14.6 Validation assertions and acceptance

| ID | Test | Pass condition |
|---|---|---|
| CPA-001 | Hide garments on a known complete character and an intentionally incomplete source | Complete base remains visible. Incomplete coverage is flagged without creating anatomy. |
| CPA-002 | Load standing and bent-limb reference fixtures | Rigid world alignment is correct, and the bent pose fails a neutral-pose-specific gate unless intentionally corrected. |
| CPA-003 | Fit a garment in a chosen pose | Fitting produces a reviewable wearable derivative and preserves body geometry, UV and texture hashes. |
| CPA-004 | Load a fixture with duplicate eyes, displaced teeth, and a deliberate opening | Diagnostics identify known issues with correct roles and sides. Configured intentional openings are not mislabeled. |
| CPA-005 | Swap a clothing variant and then change the body UV revision | Variant swap does not change the body. Only affected mappings and downstream compatibility are invalidated. |
| CPA-006 | Prepare an imported rigged source | Supported imported rigging and weights are preserved on the compatible preparation path. Original files remain intact even if an operation creates a derivative. Unsupported carry-through is disclosed. |
| CPA-007 | Hand off one clean base to Phase 15 | Canonical scales, orientation and revision-bound IDs agree, and no landmark, overlay, or model generation starts automatically. |
| CPA-008 | Explicitly convert A-to-T and T-to-A on compatible fixtures | Each candidate meets the target pose gate, identifies affected fit and binding claims, and leaves the original pose, source mesh and rig hashes unchanged. |
| CPA-009 | Transfer weights from a compatible source to an eligible target, then try incompatible influences | A valid candidate has measured normalization and coverage, passes reference-pose inspection, and leaves both original checksums intact. Unsupported or missing mappings are blocked or flagged before use. |
| CPA-010 | Switch between general and anatomy-specific humanoid profiles and open a Creature fixture | Both humanoid profiles require a clean base. Separate eyes, teeth, and tongue are required only where the workflow calls for them. The Creature fixture can be inspected without a dedicated preparation claim. |

Phase 14 passes when an operator can prepare a clean, modular humanoid assembly, distinguish visual completeness from profile readiness, independently inspect or replace apparel, explicitly convert between supported neutral poses, inspect a separate compatible skin-weight transfer result, and hand a precise eligible clean mesh revision to Phase 15. A non-applicable profile does not block retaining the character for another use.

## 14.7 MVP boundary and decision trace

**Decisions applied:** Q14-01 humanoid preparation and general creature inspection, Q14-02 reviewed automatic conversion between A-pose and T-pose, Q14-03 mandatory clean base with workflow-specific separate anatomy, Q14-04 imported rigging preservation and explicit compatible skin-weight transfer.
