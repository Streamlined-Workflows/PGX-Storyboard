# Phase 13: Regional Texture Generation and Inpainting

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 13.1 Purpose and scope

Regenerate only a user-selected surface region of an existing asset. Use a reviewed Phase 12 mask to inpaint a damaged region, change a finish, or complete an eligible unseen surface while preserving approved surrounding work. This phase consumes Phase 10 maps and does not introduce geometry editing, UV repacking, global regeneration, material assignment changes, or automatic repair.

Inherited constraints include local-only execution, canonical individual PNG maps, color-space and Positive Y conventions, common resolution per component texture set, relevant locks, and explicit retention and approvals. Regional operations are independent and explicitly initiated. MVP supports coordinated AI inpainting across multiple selected maps and components in one request, with independent texture sets and one reviewable result. This phase does not choose a provider.

## 13.2 Inputs and outputs

| Direction | Record | Required detail |
|---|---|---|
| Input | Revision-frozen target list | Asset and each selected component, slot, geometry revision, UV revision/channel, texture-set revision, selected maps, and protected bindings. Each component retains its own set and common set resolution. |
| Input | Effective edit mask per target | Explicit editable pixels or surface selection resolved through Phase 12, with editable domain and protected-region exclusions for each target. |
| Input | Optional context and intent | Prompt, optional negative instructions, compatible reference crops, context width, edge behavior, and requested map method. List unsupported controls before submission. |
| Input | Original maps and lighting policy | Original map revisions are the read-only comparison baseline. Observed, inferred, and reused information remains distinct where supported. |
| Output | One regional candidate per request | Contains requested per-component map results, change coverage evidence, and source-revision and mask references. A partial result exposes completed and failed maps separately. |
| Output | Validation report | Shows effective area, requested vs produced maps, channel bounds, seams, failed outputs, and comparison with pre-edit values. |

No source view or unapproved input becomes permanently retained merely because it is consumed. Temporary files follow Phase 22, and actual operational dependencies must be described in an explicit approval prompt when needed.

## 13.3 Workflow

1. Select one or more components and choose a reviewed mask for each affected surface, or create one in Phase 12. Choose target maps per texture set, a shared replacement intent where useful, and optional references. Choose hard boundary, adjustable inward feathering, or seam-aware blending across UV islands. Preview exactly which original pixels may change for each target.
2. Validate mask compatibility and eligible coverage, material/texture locks, dimensions and channel expectations. Plot out-of-scope and ambiguous shared UV texels before submitting. A full-surface request routes to Phase 10 or requires explicit re-scoping.
3. Provide eligible local processors with their declared inputs. A context crop may include pixels outside the write region, but is read-only. Record crop-to-canonical coordinates, all map IDs, map generation methods, and provider parameters. Compatible coordinated local passes may run in sequence. Evaluate alignment on shared surface features as well as declared coordinates. The same prompt alone does not establish alignment.
4. Recompose into the canonical full-size map using the immutable source as the baseline. Any feathering stays inside the effective writable domain. Seam-aware blending uses validated correspondence across eligible UV island boundaries without writing beyond effective masks or component boundaries. Pixel equality outside the effective domain is independently enforced in native decoded sample values. Context crop, resizing, color conversion, compression, or seam padding cannot silently enlarge the write domain.
5. Review a 3D and Split View comparison, with source, result, and change overlay. Approve, deny, or request explicitly scoped repair. If some outputs fail, review the completed maps and apply a selected subset only after validating it with the remaining maps in each affected set. Failed and untouched maps remain unchanged. Applying a candidate or approved subset is separate from starting generation.

## 13.4 Functional requirements and controls

| ID | Requirement |
|---|---|
| RGI-001 | Run target-only inpainting with compatible local AI providers. Support individual maps and coordinated AI edits across multiple selected maps, not only Base Color with deterministic companion edits. One request yields one candidate group. |
| RGI-002 | Display both the editable write mask and context read region. Provide hard boundary, adjustable inward feathering, and seam-aware blending across UV islands. Keep feathers, seam processing, and any edge padding within the permitted write domain. |
| RGI-003 | Allow one request to target multiple selected components. Preserve each boundary, map binding and independent texture set. Do not merge into a common atlas or force matching set resolutions across components. Block incompatible revisions, empty masks, or unsupported requests with corrective guidance. |
| RGI-004 | Permit Phase 10's Infer Missing Surfaces or Apply Existing Surface where relevant. The latter uses a selected compatible source. Never offer intentionally leaving newly processed scope unmapped as an accepted generation mode. |
| RGI-005 | Preserve source geometry, UV assignments, topology, unrelated components, and locked or unrequested maps. Verify exact decoded sample equality outside the write mask, including hidden alpha channel data. |
| RGI-006 | Use a shared projection and effective domain for correlated output channels in the same texture set. Diagnose map misalignment and disallowed tangent-normal or color-space changes before apply. |
| RGI-007 | Report when selected and protected faces reference the same texels or incompatible tangent frames. Isolate only through a user-approved compatible upstream change, or skip/block the conflicting surface. |
| RGI-008 | Temporarily lock repeat or conflicting submissions in the active regional workflow and keep separate eligible jobs in the Phase 21 queue. Revalidate source revision and locks when a queued job starts and before applying output. |
| RGI-009 | When partial output arrives, leave valid results pending and mark missing maps. Allow explicit adoption of completed maps only after validating that they align and remain compatible with the remaining maps. Leave failed and untouched maps unchanged and never mark the group as complete. |
| RGI-010 | Show confirmed defects in red. A seam/artifact diagnostic cannot trigger extra generation, re-UV, or repair. Safe and Advanced repair remain explicit user actions. |
| RGI-011 | Show comparison by rendered region, map channel, and change domain. Provide cancel, per-request disclosure of unsupported parameters and excluded references, and capability-specific progress. |

User controls include source map(s), frozen mask, target slot and component, hard edge, adjustable inward feather, or seam-aware blend, prompt and reference controls, completion mode, local provider override if compatible, cancellation, candidate comparison, approval, and explicitly scoped full or partial apply.

## 13.5 Provider constraints and application responsibilities

| ID | Provider constraint | SWIFT responsibility |
|---|---|---|
| RPC-001 | Declare accepted mask shape, polarity, precision, channels, map types, image dimensions, and support for multiple views or correlated outputs. | Adapt and show the actual effective write domain. Do not pass an inverted or ambiguous mask. |
| RPC-002 | Enter and exit local inference from revision-pinned inputs. Return candidate maps to an isolated staging area. | Own authoritative composition, channel-correct processing, revision checks, and atomic promotion rules. |
| RPC-003 | Identify outputs that are inferred, lighting-derived, unaligned, unsupported, or partially failed. | Validate all claims independently and never interpret plausible pixels as recovered physical truth. |
| RPC-004 | Expose capability-specific limits on edit area, resolution, reference count, map coordination, repeatability, and cancellation. | Show constraints before queue admission and avoid falling back to unrequested whole-surface processing. |

## 13.6 Validation assertions and acceptance

| ID | Test | Pass condition |
|---|---|---|
| RGA-001 | Inpaint a marked patch on a 1024 fixture containing unrelated gradients, alpha, and labels | All decoded samples outside the authorized effective mask are identical, and untouched companion map hashes match. |
| RGA-002 | Let a stand-in replace a whole context crop despite a small mask | Recomposition protects the full original outside the authorized region. No provider output directly changes canonical source files. |
| RGA-003 | Edit one side of a mirrored shared-UV fixture with the other side protected | Conflict is flagged and no protected surface changes on save. |
| RGA-004 | Inpaint across an approved seam with a paired Base Color and Roughness candidate | Both keep canonical dimensions, correspond to their common surface domain, and display seam continuity for review. |
| RGA-005 | Return one valid and one corrupt requested map | The valid map is independently reviewable and the failure is visible. An explicit compatible partial map apply succeeds without replacing failed or untouched maps. An incompatible partial apply is blocked. |
| RGA-006 | Replace a source UV revision or lock a target while a job waits | Pre-start or pre-apply validation blocks the stale write and preserves the new state. |
| RGA-007 | Reject candidate, then inspect the source and another component | Approved source and sibling artifacts remain intact. Denial follows approved deletion behavior. |
| RGA-008 | Run a coordinated AI request across two components with different set resolutions and aligned feature guides for multiple maps | One candidate group contains correctly scoped, aligned per-component results. Each set retains its original resolution and unselected or locked maps remain identical. |
| RGA-009 | Compare hard edge, inward feather and seam-aware blend on a shared seam with protected neighbors | The chosen treatment appears in preview and the editable seam sides agree within the applicable Phase 25 fixture. Protected samples outside each effective mask remain exactly equal. |

Phase 13 passes when a user can run one masked AI edit over multiple selected maps and components, verify that surface features align while protected pixels and independent sets remain intact, and apply only a reviewed compatible result or subset. Each approved edge treatment must pass the same preservation gate. A local controlled-run fixture must demonstrate that application safety does not depend on the model obeying its own mask.

## 13.7 MVP boundary and decision trace

**Decisions applied:** Q13-01 coordinated AI map edits, Q13-02 multi-component requests with independent sets and one result, Q13-03 all three edge treatments, Q13-04 explicit compatible partial-map apply.
