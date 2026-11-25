# Phase 15: Character Landmark Mapping and CC5 Integration

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 15.1 Purpose and scope

Prepare a clean humanoid from Phase 14 for assisted Body Wrap in Character Creator 5 (CC5). Director shall automatically place and validate the 218 landmarks on a selected body revision and present numbered reference views, plus a separate removable guide texture when suitable UVs can display it clearly. The workflow must save the artist work rather than introduce another alignment task. Director has no point placement, adjustment, or point-by-point approval tools. Director does not produce a rig, morphs, or a CC5-native character.

MVP shall qualify one exact CC5 build and its **Default Full Body 218-point Body Wrap preset** with standard applicable anatomy. Reallusion documents the [Default preset](https://manual.reallusion.com/Character-Creator-5/Content/ENU/5.2/09-Body-Wrap/Setting-Character-Presets.htm), [Full Body numbering](https://manual.reallusion.com/Character-Creator-5/Content/ENU/5.2/09-Body-Wrap/Using-Part-Modes.htm), and [Body Wrap workflow](https://manual.reallusion.com/Character-Creator-5/Content/ENU/5.2/09-Body-Wrap/Quick-Guide.htm). The published documentation does not establish an import integration for Director landmark data. An FBX import alone is not a qualification pass, and no automatic transfer into CC5 is assumed. Extra, Core, Freeform, other presets or builds, and native round-trip automation are outside MVP.

## 15.2 Workflow and controls

1. Select the clean Phase 14 base body and geometry revision. Show pose, anatomical orientation, base component, dimensions and available UV channels. Reject an incompatible body or unsupported pose for the preset. If rerunning Phase 14 is necessary, make it a separate explicit operation rather than automatically altering the input.
2. Choose the bundled rights-cleared mapping template or a compatible authorized local template. Validate the profile version, inspect the geometry and start one local automatic mapping job. The selected template and adapter are pinned for the request. Never replace an incompatible template or model silently.
3. Automatically register and project the 218 landmarks. Validate surface placement, anatomical side, count, coverage and available confidence evidence. Block the pass state for missing, unreliable or ambiguous correspondences. The artist may inspect the result and diagnostics, choose another compatible template or body revision, or explicitly rerun. A failed mapping never opens a point editor or manual fallback.
4. Generate numbered reference views from the validated point set. Generate a removable guide PNG only when its selected UV channel can display the overlay without misleading overlap or unreadable labels. Orthographic references may include close views to make small landmarks readable. Report skipped UV output, and keep all production maps clean.
5. Package clean FBX, numbered views, applicable guide PNG and diagnostic metadata through Phase 18. A guide PNG is optional in the package when UVs are unsuitable, but the numbered views are required for the profile. The end-to-end compatibility test shall show the resulting guide assists the approved CC5 workflow without requiring a manual point-tweaking pass. If that cannot be demonstrated on the nominated build, record the failure and withhold compatibility certification rather than assuming a JSON, texture or API import works.

## 15.3 Requirements

| ID | Requirement |
| --- | --- |
| LM-001 | Declare profile and template version, CC5 target build/preset once qualified, the complete ID registry, semantic region, anatomical side where applicable, and template provenance. Extra points do not count toward the Default profile. |
| LM-002 | A placed point shall identify profile ID, mesh/component revision, source face and barycentric coordinates where representable, derived canonical position in centimeters, template provenance and validation status. Anchors shall be tied to geometry identity, not assumed to survive FBX reordering. |
| LM-003 | Automatically place and validate exactly 218 points for profile success. Missing, ambiguous, off-surface, duplicate, invalid-side and unreliable placements shall be flagged; no missing point shall be marked valid by substitution or guessed as verified. |
| LM-004 | Do not require or offer manual placement, coordinate adjustment or per-point approval. An operator may inspect diagnostics and explicitly retry or choose another compatible input. Artifact retention remains a single separate approval decision. |
| LM-005 | Bundle a rights-cleared local template for automatic mapping, and support optional authorized local template import. Template rights and compatibility must be verified before bundling; imported proprietary template payloads shall not be copied into the export by default. Do not ship or distribute third-party data without applicable rights. |
| LM-006 | Generate numbered reference views and, where UVs are suitable, a removable guide PNG. Both must use the same landmark IDs. Bind a guide PNG to the exact geometry and UV revisions. Unreadable labels or overlap shall block the PNG or affected profile validation, not silently create duplicated or misleading labels. |
| LM-007 | Keep source geometry and production textures immutable. A topology change invalidates face-anchored results unless explicitly regenerated and validated. A UV-only change invalidates the affected guide PNG, not still-valid mesh anchors and independent reference views. |
| LM-008 | A request produces one independently reviewable result, which may include the point data and multiple guide files. Provenance and applicable operational dependencies shall be recorded. Generated candidates enter Pending for ten days, require explicit retention approval and applicable dependency confirmation, and are subject to complete denial or expiry cleanup. Export does not retain them. |
| LM-009 | Report technical validity, automatic mapping reliability, artifact approval, and verified CC5 compatibility separately. A generic package may contain clearly labeled diagnostic intermediate output where applicable, but it shall not carry the CC5-ready designation for an invalid or unverified mapping. |
| LM-010 | Use only locally processed inputs and qualified adapters. Guide files and Director's point JSON are companion artifacts; do not advertise them as CC5 importer inputs unless supported and demonstrated on the nominated build. |

## 15.4 Provider constraints and application responsibilities

| Layer | Responsibilities |
| --- | --- |
| Local automatic mapping provider | Declare compatible poses, anatomy, template versions and required inputs. Return stable profile correspondences, explicit failed regions and useful uncertainty information. Preserve the input and support terminating safely with no claim of verified placement for unsupported anatomy. |
| Director | Validate source and template identity, the 218 required correspondences and applicable geometry revision, and produce numbered references and eligible PNG. Manage job admission, immutable assets, diagnostics, review flags, lifecycle, and packaging. Director shall not expose point-edit controls. |
| Qualification | Use one exact CC5 build and Default preset with authorized fixtures. Verify the end-to-end assisted workflow, no mandatory manual point-tweaking pass, and a clean production appearance. Any unsupported vendor import is out of scope unless verified. |

## 15.5 Validation assertions

| ID | Test | Expected result |
| --- | --- | --- |
| LM-A01 | Run automatic mapping on a qualified asymmetric full-body fixture. | Exactly one valid on-surface anchor for each ID 1 through 218, no extra IDs in the profile, and measured landmark accuracy passes frozen Phase 25 thresholds. |
| LM-A02 | Feed a fixture with missing or incompatible anatomy, a reversed side mapping, or an off-surface point. | The affected mapping is flagged and readiness is blocked. No point-tweaking controls or manual fallback are offered. |
| LM-A03 | Load the bundled template, then test an authorized local alternative and an incompatible profile. | The qualified sources work locally; the incompatible profile is rejected without silently substituting another template. |
| LM-A04 | Change topology and make a UV-only revision in separate tests. | The topology edit invalidates anchors and dependent guides. UV-only invalidates the affected PNG and preserves the still-valid independent data. |
| LM-A05 | Generate numbered views and the PNG when suitable, then test overlapping UVs. | IDs match across outputs. Unsuitable UVs omit the PNG with a reason and leave numbered views available. Production PNG hashes are unchanged. |
| LM-A06 | Run an end-to-end handoff using the one nominated CC5 build and Default preset. | Show the package assists Body Wrap without a manual point-tweaking pass and no marker pixels survive into production appearance. Do not certify a workflow that only imports geometry or needs point-by-point intervention. |
| LM-A07 | Export a valid Pending profile following confirmation. | Included artifacts are correctly labeled and local approval and expiration remain unchanged. |

Use a clean prepared humanoid with asymmetric features and separately maintained ground-truth points. Capture errors in centimeters and, where useful, as a fraction of body height. Include pose, build, preset and template versions in the qualification report. Exact numeric thresholds are Phase 25 work and must be frozen before qualification.

## 15.6 MVP acceptance

The phase passes when a rights-cleared template is available, a compatible body automatically yields a validated 218-point mapping and associated guides, original surfaces remain unchanged, and the exact CC5 build and Default preset pass the live handoff and evidence gate. Optional authorized local template import must also work. No manual point-placement or correction workflow is required. Compatibility is not yet tested.

## 15.7 Approved decisions and boundaries

- **Q15-01:** Rights-cleared bundled automatic template plus optional authorized local template import.
- **Q15-02:** Numbered reference views plus a removable guide PNG when UVs can display it correctly.
- **Q15-03:** Superseded. No individual or regional point confirmation, manual correction or point editor.
- **Q15-04:** One CC5 build and Default 218-point preset in MVP, with executed compatibility qualification before release.

Template identity and rights verification, the nominated build, empirical error tolerances and exact local mapping implementation are implementation and qualification details, not new product decisions.
