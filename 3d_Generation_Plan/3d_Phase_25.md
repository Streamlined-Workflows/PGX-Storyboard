# Phase 25: Model Evaluation and Validation Framework

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 25.1 Purpose

Turn each phase's provider constraints and assertions into comparable, repeatable evidence. Evaluate providers by role, configuration and hardware, then test the composed local workflow separately. A provider may qualify for one role or one quality profile without qualifying for another. No model or provider is selected or qualified by this design. Numeric quality and performance targets are not yet measured.

## 25.2 Evaluation contract

A benchmark case shall record a stable fixture ID and version, rights and source, exact inputs and settings, seed where meaningful, expected outputs, applicable assertion IDs, per-check metric with units, and a rubric for human inspection. An evaluation run shall include adapter, provider build and model identifiers, host configuration, failures, normalized artifact lineage, and whether a result came from a cold or warm run. Keep incompatible, not run, failed and passed distinct.

| Layer | Example checks | Evidence |
|---|---|---|
| Eligibility | local inference after provisioning, license/profile suitability, supported role and package format | Offline execution and provenance records |
| Contract | schema, declared inputs, error/cancel behavior, no changes to approved sources | Adapter conformance tests |
| Deterministic artifact validation | FBX axes/scale/hierarchy; geometry counts; UV/PNG contracts; references and package completeness | Validator runs independent of the provider |
| Output quality | visible silhouette and asymmetry, component boundaries, UV distortion, seams, mask bleed, landmark placement | Measured checks and manual review with versioned rubric |
| Runtime | cold load, warm latency, memory peaks, cancellation and release | Host measurements with workload context |
| Integration | restart, failure handling, dependency approval, pending retention and reimport | End-to-end run plus state evidence |

## 25.3 Requirements

| ID | Requirement |
|---|---|
| EVA-001 | Map each applicable assertion to a fixture, method, expected state, evidence and blocking tier. Do not hide failures by averaging across unrelated checks. |
| EVA-002 | Use deterministic validation where reliable, seeded or repeated generation for stochastic output, and human review where visual quality cannot be measured adequately. |
| EVA-003 | Record geometric vertices separately from rendering vertices, triangles, polygons and edges. Evaluate target deviation without treating the target itself as a universally exact limit. |
| EVA-004 | Measure alignment, leakage and deformation only against a comparable baseline. For masked outputs, report protected-region changes separately from intentional feather-region effects. |
| EVA-005 | Record fixture classification, stage and package variant. A missing stage input is not a provider quality failure. |
| EVA-006 | Require an end-to-end offline run on each supported primary profile before claiming support, including a cold setup path after provisioning. |
| EVA-007 | Re-evaluate affected assertions after provider, adapter, runtime or validation rubric changes. Mark prior evidence stale when applicable. |
| EVA-008 | Use only rights-cleared fixture assets. Do not bypass normal pending retention for assets from an actual user project. Preserve benchmark evidence without retaining denied or expired production history. |
| EVA-009 | Publish a capability decision per role: qualified, explicitly limited, or unavailable. Keep license failures, hard contract failures and reviewed quality deviations separate. |

## 25.4 Qualification policy

1. **Hard fail:** Disqualify a provider for the affected role if required files or formats are invalid, protected data changes (including changes outside the declared mask and allowed feather zone), approved or retained work is lost, authorization fails, local offline runtime fails, or commercial-use eligibility is unverified. Hard failures cannot be waived by a good visual score.
2. **Quality warning:** A usable result may qualify with a documented limitation for a non-blocking quality or budget miss. Describe the fixture, observed deviation, impact and any affected role or use case. A warning does not convert an unusable result into a pass.
3. **PGX baseline:** Fix the hard invariants now. Measure representative cold and warm runs on the ThinkStation PGX, then set numeric quality and performance targets, comparison methods and repeat expectations. Freeze and version those targets before qualifying any model. Reassess affected qualifications if the versioned criteria change.
4. **Visual sign-off:** Jeremy is the sole MVP reviewer for visual quality and documented limitations. Use the same versioned rubric for all models within a role. Record the fixture and rubric versions, reviewer decision, and accepted warnings. A second reviewer is not an MVP requirement. Model sign-off does not approve individual production assets.

## 25.5 Fixtures and test strategy

Use the static prop and modular humanoid from Phase 26. A separate interior scene or compartment is optional. Add a controlled invalid package, a locked-component case, a texture mismatch case and a locally controlled job interruption. Do not require exact bit-for-bit identity from stochastic inference. For deterministic validation of artifacts such as protected pixels, a fixture may require byte or value equality according to a declared comparison method.

Providers shall disclose deterministic options, supported ranges, native output semantics, and failure modes. The application shall normalize formats, measure and validate independently, correlate runs with chosen inputs, and provide a scorecard without letting the provider grade its own output. Human reviewers shall see the relevant references, output and rationale. Do not combine model ranking with user artifact approval.

## 25.6 Assertions and acceptance

| ID | Test and expected result |
|---|---|
| EVA-A01 | Two comparable runs against versions of the same role report fixture version, settings, metrics and hardware. Incompatible settings remain visibly separate. |
| EVA-A02 | Inject a valid-looking provider output with an invalid canonical transform or missing attachment. A contract gate fails before recommendation or export. |
| EVA-A03 | Run a regional edit fixture. The report separates painted intent, approved feather margin and out-of-mask changes. |
| EVA-A04 | Run with provider output missing a proof or required role. The capability card shows exactly what is not qualified. |
| EVA-A05 | Run offline with a real cold launch after provisioning, then cancel a job. Record terminal state and resource recovery without corrupting the approved asset. |
| EVA-A06 | Change adapter or fixture version. Previously recorded evidence is not silently reported as current. |
| EVA-A07 | Compare a hard format failure with a usable result that misses a quality target. The first fails qualification; the second can qualify only with documented warnings and Jeremy’s sign-off. |
| EVA-A08 | Inspect the evidence for a proposed qualification. The recorded baseline, approved rubric and frozen numeric targets predate qualification. |

MVP acceptance requires traceable role-level checks, conformance and offline evidence, repeatable human review, independently validated exports, and a defensible threshold policy recorded before qualification. This document supplies design assertions, not results.

Design decisions: Q25-01 through Q25-03.
