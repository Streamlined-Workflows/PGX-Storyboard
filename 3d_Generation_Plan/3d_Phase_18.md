# Phase 18: Export and Interoperability

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 18.1 Purpose and scope

Make selected assets and intermediate artifacts portable from the unified local studio to another project or an external tool. Export packages shall contain the chosen representation and required operational dependencies rather than an entire internal project or generation history. The canonical contract remains FBX for geometry, PNG for texture maps, and a JSON `AssetManifest.json` for SWIFT identities and packaging metadata.

A destination profile may constrain file selection, transforms, material mappings, tangents, naming, or limits. Such a profile does not change canonical storage. MVP includes the standard SWIFT ZIP, the Phase 15 CC5 handoff, and a qualified Blender preset. Direct GLB export is post-MVP; FBX remains the sole canonical geometry exchange format. No target interoperability claim may exceed executed compatibility tests.

## 18.2 Export profiles

| Profile | Package contents or inherited behavior |
| --- | --- |
| Geometry / intermediate | Selected canonical FBX, classification, intended scale, and any enabled applicable spatial metadata. Earlier production stages remain exportable without unrelated files. |
| Component or named configuration | Selected component(s) and exact variants, hierarchy and transforms, optional active UVs/materials, required dependencies, and coordinate mode in the manifest. |
| UV | Preserve Phase 09's Geometry with UVs, UV Layout, Component UV Package, and Complete UV Package choices, including FBX and PNG payloads as applicable. |
| Texture / material | Preserve all four Phase 10 selections (individual map, set, component package, textured asset). Include applicable reusable material definitions and only their required maps, semantics, UV assignments and declared normal convention. |
| Character preparation / CC5 guide | Clean prepared body and selected modular companion files as appropriate, optional separate landmark texture and numbered reference views, and landmark JSON where available. Output remains an assisted handoff, not a CC5-native character. |
| LOD | Selected approved or confirmed Pending LOD derivatives, original or baseline only if requested/applicable, measured counts, bindings, and explicit destination naming or unsupported feature report. |
| Standard SWIFT ZIP | Selected usable geometry, configuration, surfaces, material definitions, applicable supported metadata, manifest and short compatibility report. Original references and detailed generation history are opt-in. Unselected variants and unrelated records stay excluded. |
| Blender | Tested FBX-based preset with the selected geometry, hierarchy, PNG files and portable material bindings where supported. Confirm any omitted features for a usable subset. A receiver test must establish supported features and Blender version, not just packaging success. |

Unified ZIP remains the asset and package delivery route. Preserve the explicitly defined Phase 09 FBX Geometry with UVs and PNG UV Layout outputs and the Phase 10 PNG Individual Texture Map output as format-specific stage exports. They do not create a second complete-asset delivery workflow. Any included FBX/PNG files shall remain independently accessible within a ZIP where the selected profile is a package.

## 18.3 Workflow and controls

1. Select asset, variant or configuration, subset or stage profile, and target where available. Display Asset-Space and Component-Space when supported. Asset-Space keeps assembly positions; Component-Space normalizes to the designated component-local origin and stores equivalent parent placement and enabled references where applicable.
2. Resolve the selected dependency graph. Show included artifacts, the reason for inclusion, optional supported items, pending expiry times, warnings, omitted destination features, and clearly differentiable preflight errors. Missing required files block export of the affected profile. Missing optional files are disclosed and omitted.
3. If any included artifact is Pending, present the Phase 02 warning listing it and its remaining retention time. Require explicit confirmation without approval or extension. Independently disclose each destination omission and require explicit confirmation before exporting a usable compatible subset. Block output that lacks required content or would be unusable.
4. Recheck artifact availability and revision identity after confirmation. Hold required files only while active export needs them. Write to staging, validate the target file or archive, and publish the final output atomically. On cancel or failure, remove partial output and preserve original artifacts.
5. Return a short compatibility report with standard packages. Inspect or import in the selected supported local destination as applicable. For an eligible SWIFT ZIP, preflight the package and reconstruction plan, then explicitly reimport into Director as an editable asset. Compare included component hierarchy, transforms, material assignments, and variants against the source manifest. Display package validation separately from production approval.

## 18.4 Package contract

```text
AssetName.zip
  AssetManifest.json
  Geometry/                 Canonical FBX payload(s)
  Textures/                 Canonical PNG payload(s)
  Materials/                Portable definitions, if applicable
  Landmarks/                Optional point data and removable guides
  Documentation/            Short compatibility report, plus applicable destination instructions
```

Only occupied, applicable folders are necessary. Do not include original references or detailed generation history unless explicitly requested, lawful to include, still available, and applicable to the exact export. Do not include internal storage paths, credentials or excluded histories in any report. The manifest shall identify schema and profile versions, selected asset/component/variant IDs, parent and placement transforms, geometry revision, canonical and destination axis/unit conventions, export coordinate modes, applicable vertex and mesh metrics, materials and texture slots, and enabled interaction references. Use normalized safe relative paths and checksums for payload files. Artifact relationships shall distinguish dependencies from optional context. Never serialize internal paths, credentials, or deleted histories.

Provide enough information for generic readers to consume FBX and PNG payloads without Director. The Blender preset shall document the qualified receiver version, expected coordinate and surface mappings, and anything the application or the preset cannot represent. The CC5 preset shall follow the exact build and guide qualification of Phase 15. A Director-aware reader can additionally verify groupings, materials, and canonical source metadata. If an adapter converts axis, units, normals, channels or hierarchy, record exactly what it converted and what cannot be represented. Preserve canonical files and do not mislabel a convention conversion as a mere filename change.

## 18.5 Requirements

| ID | Requirement |
| --- | --- |
| EX-001 | Export applicable stages and exact selected configuration revisions through unified ZIP, preserving the explicitly defined standalone Phase 09/10 file profiles. Do not require texturing, landmarking, or any unrelated future phase. |
| EX-002 | Preserve canonical FBX/PNG and asset coordinate semantics. Apply target conversions only in package output and identify any data intentionally omitted. |
| EX-003 | Resolve and deduplicate required files by portable identity while preserving every independent logical reference. Package chosen configuration and enabled grips/pivots but never infer inclusion from viewport visibility. |
| EX-004 | Preserve per-component material slots and independent texture sets with compatible UV channels and common resolution. A target that cannot represent a map shall disclose the omission and require confirmation before exporting a compatible subset, or block if required content is missing or the result would be unusable. Do not silently generate an atlas or bake textures. |
| EX-005 | Warnings, licensing restrictions and external compatibility shall be assessed per profile. Required payloads, manifest and a short compatibility report are included by default in standard ZIPs; original references and detailed generation history are opt-in. A Pending export shall not approve, regenerate, alter or retain artifacts past their normal expiry. |
| EX-006 | Validate output before result publication, including archive and manifest validation for packages. Detect unsafe paths, missing files, duplicate normalized names and failed integrity checks. |
| EX-007 | Distinguish a core canonical package from any target derivative. Output compatibility reports shall name target and tested version and distinguish proven, unverified, unsupported and deliberately omitted features. |
| EX-008 | Validate and reimport eligible SWIFT ZIPs as editable assets, reconstructing included components, exact relationships, transforms, material assignments, compatible texture references and variants without inventing omitted content or history. Handle identities and conflicts through Phase 22; never overwrite unrelated retained content. Unsupported newer schemas, invalid archives or unresolved required references shall not result in partial activation. |
| EX-009 | Exports shall not automatically invoke an external application, upload assets, or return source content to providers. Supply local handoff instructions for any certified destination. |
| EX-010 | A successful export shall produce one ready ZIP or one selected stage file, not multiple competing candidates, and leave no incomplete output visible as a final result. Heavy FBX conversion and ZIP export wait until generation finishes under Phase 20. Preserve source locks throughout active reads. |
| EX-011 | MVP destination set is standard SWIFT ZIP, one qualified CC5 guide handoff, and a qualified Blender preset. Direct GLB export is not part of MVP. |

## 18.6 Provider constraints and application responsibilities

Export planning, packaging, editable reimport, approval checks, security, path normalization, integrity checks and technical logging are deterministic Director responsibilities. A local FBX or optional destination adapter shall declare supported version and features, coordinate conversion, preserved metadata, limits and lossy behavior before execution. It may return converted payloads and a report but cannot update approval, mutate sources, or claim an untested import. No AI inference is required for package correctness.

## 18.7 Validation assertions

| ID | Test | Expected result |
| --- | --- | --- |
| EX-A01 | Export a geometry-only prop. | ZIP contains FBX and validated manifest, no false texture dependencies, and correct scale and classification. |
| EX-A02 | Export a named configuration with a hidden active component and an inactive visible candidate. | The active component is included; the inactive candidate is not. |
| EX-A03 | Export an asymmetric nested component in both coordinate modes. | Asset-Space preserves the known assembly pose; Component-Space matches designated local origin and frame. Enabled reference positions and orientations resolve correctly. |
| EX-A04 | Export a textured two-component asset with independent UV sets and maps. | Resolved portable paths, slot bindings, UV identities, resolutions and normal convention agree with the manifest. |
| EX-A05 | Modify one archive byte or introduce an unsafe relative path to a package fixture. | Verification refuses the corrupt or unsafe package without modifying retained assets. |
| EX-A06 | Cancel after the Pending modal, then confirm in a separate run. | Cancellation creates no final archive. Confirmed download leaves all expiry and approval fields unchanged. |
| EX-A07 | Run nominated Blender and Phase 15 CC5 fixtures against the exact documented versions. | Supported handoffs, fields and dimensions meet Phase 25 tolerances. Unsupported fields are disclosed, and compatibility is not claimed without passed evidence. |
| EX-A08 | Simulate an interrupted staging write or target disk exhaustion. | No final archive is presented; exclusive temporary output is removed or marked for safe cleanup. |
| EX-A09 | Request a legacy or incompatible destination without a declared adapter. | Export offers a generic package or blocks that destination profile rather than claiming compatibility. |
| EX-A10 | Export Geometry with UVs, UV Layout, and Individual Texture Map. | The selected FBX or PNG is delivered with the documented semantics and applicable Pending confirmation without requiring an unrelated asset package. |
| EX-A11 | Reimport an eligible ZIP of the modular humanoid, with nested components, multiple material assignments and variants. | The included graph is editable and equivalent to the manifest after ID resolution. No omitted or unavailable content or history is invented. Existing project content is unchanged. |
| EX-A12 | Test a named destination with a nonessential loss, then one with a required omission. | The former discloses the omission and exports only after confirmation; the latter blocks even if the operator would accept it. |
| EX-A13 | Export with defaults and with references and history selected. | Both have required files, manifest and summary. Optional permitted context appears only when explicitly selected; deleted history is never reconstructed. |

## 18.8 MVP acceptance

Build and verify restart-safe local export and editable reimport. The static prop and modular humanoid are the required Phase 26 release fixtures. Verify selected geometry, surfaces, assemblies, UV work, an LOD package and applicable character preparation outputs with suitable fixtures. The Phase 26 gate includes the editable SWIFT ZIP round trip. Qualify the Blender preset and CC5 handoff before MVP release. External acceptance requires measured, documented tests, and certification does not imply lossless support for every optional field.

## 18.9 Approved decisions and boundaries

- **Q18-01:** Standard SWIFT ZIP, the Phase 15 CC5 handoff, and one qualified Blender preset are the MVP destination set.
- **Q18-02:** Direct GLB export is post-MVP. FBX remains canonical.
- **Q18-03:** Required usable files, manifest and short compatibility report are included by default. Original references and detailed generation history are opt-in where eligible.
- **Q18-04:** Permit a usable compatible subset only after disclosing omissions and receiving explicit confirmation. Block missing required content and unusable results.
- **Q18-05:** Reimport an eligible SWIFT ZIP as an editable asset with included relationships, material assignments and variants reconstructed. Prove it at the Phase 26 gate.
