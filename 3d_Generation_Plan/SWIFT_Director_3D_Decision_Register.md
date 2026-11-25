# SWIFT Director 3D Generation: MVP Decision Register

Design baseline 1.0 | November 25, 2026

This register closes all 63 design questions for Phases 11–26: 62 decisions and one superseded question (Q15-03). The linked phase files define requirements and acceptance tests. This register does not claim that an integration, build, runtime, or benchmark passed.

## [Phase 11](3d_Phase_11.md)

- **Q11-01**: Portable metallic-roughness PBR with basic transparency and cutouts stays in MVP. Refraction, clearcoat and skin scattering wait. Phase 09 UV and Phase 10 map decisions remain unchanged.
- **Q11-02**: UV-based materials in MVP. Keep image projection as a Phase 10 texture production method. No live triplanar material mapping for MVP.
- **Q11-03**: Allow a new material slot from deliberate face selection as a nondestructive edit, without cutting the mesh or changing the original.
- **Q11-04**: Include offline starter materials and user-saved presets in MVP.

## [Phase 12](3d_Phase_12.md)

- **Q12-01**: Directly paint Base Color, Roughness, Metallic, Emissive and Opacity in MVP. Generation of all eight and masking compatible maps remain available.
- **Q12-02**: Save editable paint layers across sessions as well as the painted texture and reusable masks. Keep source textures and masks separate.
- **Q12-03**: Include freehand viewport lasso in MVP, in addition to brush, erase, fill by component or material slot, and invert.
- **Q12-04**: Include explicit mask transfer after a UV layout change, with a preview and accept or discard review. Preserve the original mask.

## [Phase 13](3d_Phase_13.md)

- **Q13-01**: Require coordinated AI edits across multiple selected texture maps within one masked request. Preserve locked maps and protected unmasked pixels, and validate feature alignment.
- **Q13-02**: Allow one regional generation request to target multiple selected components. Preserve independent texture sets and component boundaries, and keep one coordinated reviewable result per request.
- **Q13-03**: Include hard edges, adjustable inward feathering and seam-aware blending across UV islands in MVP. Preserve masks and locked/protected pixels.
- **Q13-04**: From a partially successful regional edit, explicitly apply completed maps only if compatible with remaining maps. Flag failures and leave failed/untouched maps unchanged.

## [Phase 14](3d_Phase_14.md)

- **Q14-01**: Full humanoid preparation plus general creature inspection in MVP. Dedicated creature preparation is not MVP.
- **Q14-02**: Accept A-pose and T-pose and include user-initiated automatic conversion between them. Review the derivative before use; preserve original and check target-specific pose requirements.
- **Q14-03**: A clean base is always required. Separate eyes, teeth and tongue required only when the selected preparation workflow needs them.
- **Q14-04**: Preserve supported imported rigging and allow explicit skin-weight transfer between compatible meshes. Review the result separately and preserve originals.

## [Phase 15](3d_Phase_15.md)

- **Q15-01**: Bundle a rights-cleared automatic mapping template, plus optional import of authorized local templates. Rights verification is a prerequisite, not a claim already verified.
- **Q15-02**: Export numbered reference views and a removable guide texture when UVs can display it clearly.
- **Q15-03** (superseded): Under the no-manual-adjustments requirement, Director automatically places all 218 landmarks and flags unreliable mapping rather than asking for point placement, adjustment, or per-point approval.
- **Q15-04**: Verify the CC5 handoff with one Character Creator 5 build and the Default 218-point Body Wrap preset for MVP. Compatibility testing is required, not yet completed.

## [Phase 16](3d_Phase_16.md)

- **Q16-01**: Keep current viewing angle on Perspective/Orthographic projection switches; Front view is a separate action.
- **Q16-02**: Reset viewport framing, display mode and panel split after each session. Durable edits, including paint layers, are unaffected.
- **Q16-03**: Default to visible-surface selection. Include opt-in through-selection with preview of affected hidden surfaces before applying.
- **Q16-04**: Automatically simplify the display temporarily when navigating under resource pressure, indicate when active, restore full detail after navigation, and do not change saved mesh, measurements or exports.

## [Phase 17](3d_Phase_17.md)

- **Q17-01**: Keep approval and Add to Library separate. Approval retains the item in its project without automatically enrolling it in the reusable library.
- **Q17-02**: Pin the exact approved revision used by each assignment. Updates require explicit action and show affected assets in the existing shared-update flow.
- **Q17-03**: Only whole assets and materials get their own reusable library entries. Components and texture sets are still available through applicable parent entries.
- **Q17-04**: Include searchable tags, favorites, and flat collections in MVP. Nested collections and saved searches deferred.

## [Phase 18](3d_Phase_18.md)

- **Q18-01**: Blender is the additional tested MVP preset, alongside standard SWIFT ZIP and CC5 handoff.
- **Q18-02**: Defer direct GLB export until after MVP; canonical geometry remains FBX.
- **Q18-03**: Include required usable files, the manifest, and a short compatibility report by default. Original references and detailed generation history are opt-in.
- **Q18-04**: Permit a usable compatible subset after explicitly disclosing omissions and getting confirmation. Block an unusable export or one missing required content.
- **Q18-05**: Validate and reimport an eligible SWIFT ZIP as an editable asset, reconstructing included component relationships, material assignments and variants from the manifest. Do not invent omitted content or history; update the Phase 26 acceptance gate to verify this round trip.

## [Phase 19](3d_Phase_19.md)

- **Q19-01**: Auto selects the highest-quality qualified model for the task using role-specific evidence. Compatible manual selection remains available.
- **Q19-02**: Admin UI manages vetted integrations already set up on the ThinkStation PGX. No new provider integration installation from UI in MVP. Previously approved manual model downloads for vetted integrations remain.
- **Q19-03**: One enabled version per provider with controlled upgrades. Existing queued or running work is pinned to its original version and must reach a terminal state before switching.
- **Q19-04**: A newly installed or updated provider must pass a real PGX test producing usable output before Auto can select it.

## [Phase 20](3d_Phase_20.md)

- **Q20-01**: Qualify the ThinkStation PGX only for MVP generation. Other Tailscale-linked computers are clients, not additional generation hosts.
- **Q20-02**: Use tested PGX memory reserve defaults with advanced adjustments bounded by a hard safety minimum.
- **Q20-03**: Block GPU generation when the GPU is unavailable; no manual or automatic CPU fallback for a GPU generation job. This does not prohibit separately designed CPU-only operations.
- **Q20-04**: Queue heavy tasks such as FBX conversion and ZIP export until generation finishes. Browsing and lightweight editing remain available.

## [Phase 21](3d_Phase_21.md)

- **Q21-01**: While an accepted geometry request is outstanding, block another geometry request across tabs and computers. Unrelated work with no conflicting asset locks may wait in the queue. The PGX still runs only one AI inference job at a time.
- **Q21-02**: Start with the oldest eligible submission. Process eligible jobs that use the same loaded model consecutively, in submission order within the model group, before switching models. One active AI inference at a time. Jeremy’s intent is to avoid repeated model loads.
- **Q21-03**: Resume verified never-started waiting jobs after rechecking inputs and safe recovery. Interrupted jobs require manual retry.
- **Q21-04**: Try a graceful cancel first. If it does not stop, ask Jeremy before force-stopping the isolated worker. Keep the inference slot unavailable until the worker and GPU resources are verified free.

## [Phase 22](3d_Phase_22.md)

- **Q22-01**: Run expiry cleanup at startup and periodically; offer Clean Up Now and report aggregate space reclaimed without deleted item identities. The inherited 10-day pending period is unchanged.
- **Q22-02**: Enforce a minimum free disk space floor plus an optional Director storage budget. Block new work if the limit would be exceeded; never evict approved assets to make space.
- **Q22-03**: Offer explicit bulk replacement before deletion of an in-use material. List all affected assets, verify compatibility, require confirmation, and delete only after assignments update successfully. Do not delete on partial failure.
- **Q22-04**: Use editable SWIFT asset ZIPs for MVP recovery. Full-library approved-only local backup/restore is post-MVP.

## [Phase 23](3d_Phase_23.md)

- **Q23-01**: Use top tabs with tools under each, without imposing a sequential wizard.
- **Q23-02**: Reopen assets at the default tool with no component selected. Saved work remains intact; viewport settings reset pursuant to Q16-02.
- **Q23-03**: Full MVP authoring tested in desktop Chrome and Edge. Full tablet touch editing is post-MVP.

## [Phase 24](3d_Phase_24.md)

- **Q24-01**: “PGX and any computer I link to it through tailscale.” The PGX runs 3D Generation, and Jeremy can reach it locally or from computers he links via Tailscale. No public endpoint. This does not decide separate app sign-in.
- **Q24-02**: Allow manual downloads for setup. Models and dependencies may be downloaded when explicitly initiated. Generation stays local and can run offline.
- **Q24-03**: Require rights for commercial use of finished outputs. Redistribution of app, model weights and templates is not an MVP licensing requirement.
- **Q24-04**: Technical logs only. No asset contents, images, prompts or optional support bundle in MVP diagnostics.

## [Phase 25](3d_Phase_25.md)

- **Q25-01**: Disqualify hard failures such as invalid required formats, unauthorized or out-of-mask edits, data loss, no offline execution, and unverified required commercial rights. Permit documented warnings for usable quality/budget misses.
- **Q25-02**: Set the hard rules now, collect baseline runs on the ThinkStation PGX to establish numeric quality and performance targets, and freeze those targets before using them to qualify any model.
- **Q25-03**: Jeremy alone signs off for MVP on visual quality and documented limitations using the same written rubric for each model. No second reviewer required for MVP.

## [Phase 26](3d_Phase_26.md)

- **Q26-01**: Include character preparation in the first working demo. A clean humanoid base and separately inspectable/exportable wearable were suggested as the fixture, not explicitly selected.
- **Q26-02**: Static prop and modular humanoid are the two required MVP acceptance fixtures. A separate vehicle interior fixture is optional, not removal of that classification.
- **Q26-03**: Hold MVP release until all integrations included in agreed MVP scope pass qualification; a disabled or unqualified integration in scope does not count. This does not put explicitly post-MVP items into scope.
- **Q26-04**: Live PGX walkthrough for final sign-off in addition to the test report. No separate reusable test package required.

## Evidence still needed before MVP release

- Confirm a versioned, rights-cleared set of providers and model outputs eligible for commercial use. Verify bundling rights for the Phase 15 template separately.
- Run baseline tests on the ThinkStation PGX and freeze numerical quality and performance targets before qualifying models. Confirm resource defaults, offline operation, queue and recovery behavior, and approved Tailscale access.
- Verify the selected CC5 build and Default Body Wrap preset and the Blender preset. Confirm the editable SWIFT ZIP round trip and desktop Chrome and Edge support.
- Pass every planned MVP integration and document results. Jeremy signs off on visual quality and limitations and receives the test report and live PGX walkthrough.
