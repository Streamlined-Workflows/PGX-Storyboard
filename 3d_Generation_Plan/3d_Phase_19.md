# Phase 19: Model Provider Architecture

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 19.1 Purpose and boundary

The provider layer shall let independently runnable local inference and deterministic processing tools exchange validated artifacts through SWIFT. It shall let users replace a capability implementation without redesigning the studio or losing access to approved work. It does not select models, build tools, runtimes, or serving frameworks. Phase 20 owns resource admission, Phase 21 owns orchestration, Phase 24 owns trust and rights, and Phase 25 owns qualification.

**Carried forward from Phases 02, 04, and 06 through 10:** local-only execution after provisioning, independently runnable stages, automatic compatible selection with advanced compatible override, no silent downgrade, SWIFT-managed validation, and canonical interchange. Geometry accepted into the studio is FBX, right-handed with Y up, +Z forward and centimeters. Canonical texture maps are PNG, with Phase 10 color and Normal conventions. A provider-native file can be temporary without becoming a second canonical format.

## 19.2 Provider contract and workflow

1. The application translates the selected operation into a versioned capability request. It resolves committed artifact IDs, confirms their compatibility, and separates the user's constraints from preferences. A geometry strategy or a locked map is a constraint. An optional seed is a control only if the capability supports it.
2. The registry excludes disabled, incompatible, unqualified or disallowed providers. Auto selects the highest-quality qualified model for the requested task using role-specific evidence from Phase 25. It exposes the task, assessment basis, selected model and any qualification warnings. Advanced Override shows other compatible choices and explains exclusions.
3. A request snapshot pins the adapter, provider and model revision or digest, capabilities, effective settings, consumed artifacts, and canonical output expectations. Any required change to the requested operation returns to the user before execution. A request may not be silently rewritten to use a newer revision.
4. The stage runs locally with isolated working files and bounded progress/error reporting. It returns native outputs or typed failures, then SWIFT normalizes, measures and validates output before publication.
5. SWIFT writes approved-format candidates to the lifecycle store, with their own approval status, and releases the inference lease when stage work stops. A qualified same-model batch may retain the model in memory between sequential jobs under Phases 20 and 21. Valid intermediates can feed the next sequential stage without retaining every intermediate permanently.

| Contract | Required information |
|---|---|
| Capability descriptor | Stable capability ID and version, accepted input cardinality and roles, output types, supported controls, native and canonical constraints, known limitations, compatible adapter version and validation evidence |
| Runtime descriptor | Exact implementation identity and versions, platform prerequisites, estimated resource envelope, preflight method, launch/stop and health behavior, offline operation, local paths and approved provisioning source |
| Invocation | Request, stage and attempt IDs, versioned operation, immutable input handles, selected parameters and constraints, output directory, and progress and cancellation contract |
| Result | Failure class or candidate outputs, actual parameters and consumed inputs, produced file descriptors, diagnostics, available timing and resource measurements, and reproducibility caveats |

The administrator can inspect, enable, disable, and control upgrades for vetted provider integrations already set up on the ThinkStation PGX. Installing a new provider integration from the admin UI is outside MVP. Explicitly initiated model downloads for vetted integrations remain allowed as setup under Phase 24. A newly installed or updated provider cannot enter Auto selection until an actual PGX validation run produces usable output for its declared role. Descriptor and environment checks alone do not qualify it. To switch enabled versions, stop new admission for the affected version and let already admitted requests reach a terminal state before changing the enabled pointer. Only one version of a provider is enabled at a time. The adapter shall expose Unsupported, Unavailable, Invalid Input, Resource Unavailable, Failed, and Cancelled as distinguishable outcomes even if vendor errors must be translated.

## 19.3 Functional requirements

| ID | Requirement |
|---|---|
| MPA-001 | Separate capability IDs from provider IDs and installed revisions. One provider may declare several roles, and one role may have multiple providers. |
| MPA-002 | Allow AI and deterministic stages to use the same job and artifact contracts while clearly identifying which type performed the work. |
| MPA-003 | Preflight against actual requested capabilities, asset inputs, runtime readiness and policy. Show excluded inputs and require confirmation if the approved request would otherwise be changed. |
| MPA-004 | Never select an incompatible override or silently substitute a different provider after an admitted request is pinned. |
| MPA-005 | Validate adapter schemas at registration and independently validate actual outputs at runtime. Treat provider-declared metrics as estimates or supplemental facts. |
| MPA-006 | Normalize supported native output into independent, validated canonical artifacts. Report loss. Reject conversion when it cannot preserve a required feature. |
| MPA-007 | Protect source/approved files and unrelated projects. Providers shall never directly commit production manifests or decide approval and retention. |
| MPA-008 | Maintain compatibility, provenance and readability across provider disablement and upgrade. Expose whether an old request is reproducible, replaceable only by new submission, or unavailable. |
| MPA-009 | Record request intent and effective execution separately. Never present a seed as a cross-provider or cross-hardware reproducibility guarantee. |
| MPA-010 | Reject network-dependent inference from MVP. A registered local endpoint alone does not prove the provider can run offline. |
| MPA-011 | In Auto, select the highest-quality qualified model for the task using the published role-specific rubric. Do not substitute speed or queue affinity for the qualification ranking. |
| MPA-012 | Restrict MVP admin controls to vetted integrations already provisioned on the PGX. Distinguish a manual model download from installation of a new provider integration. |
| MPA-013 | Permit only one enabled version per provider and defer switching while any admitted request is pinned to the original version. |
| MPA-014 | Exclude newly installed or updated providers from Auto until real PGX evaluation demonstrates a usable output in the applicable role. |

## 19.4 Provider constraints and SWIFT responsibilities

A candidate implementation must run the declared stage independently after provisioning, accept only supported operation inputs, surface unsupported parameters, report progress where possible, close per-attempt resources on completion, support controlled unload, and produce safely readable files within its approved output boundary. Where cooperative cancellation is unavailable, the adapter must expose that fact and support bounded escalation through Phases 20 and 21. The provider must not require unrelated providers to remain loaded. SWIFT owns preflight, ranking, request pinning, resource and file isolation, canonical conversion, independent validation, status reporting, lifecycle and policy enforcement. A sandbox or fallback method is not presumed proven merely by implementing the API.

## 19.5 Validation and acceptance

| ID | Exercise | Expected evidence |
|---|---|---|
| MPV-001 | Disable networking after provisioning and run a representative operation | Output or a typed local failure with no remote inference attempt |
| MPV-002 | Register two candidates with different view and lock support, then exercise automatic and manual selection | The highest-quality eligible candidate for the role is selected automatically. A lower-ranked compatible candidate can be selected manually. The unsupported override is denied before launch. |
| MPV-003 | Request an upgrade while one job runs and another waits on the same provider version | Both remain pinned to the original version. The switch waits until both are terminal. Retained output opens without the original provider active. |
| MPV-004 | Submit invalid native output or output missing a requested required property | Canonical publication is blocked or marked failed. Prior selection and source hashes remain unchanged. |
| MPV-005 | Hand validated output from one provider to another after releasing the first | Both stages run independently and share only normalized artifacts |
| MPV-006 | Simulate a stale provider reporting unsupported progress or ignoring stop | Honest status and a graceful stop attempt. Before forced termination, the application asks the user and holds the slot until resources are verified free. |
| MPV-007 | Install or update a vetted integration and pass descriptor checks but skip the real PGX test | Auto excludes the revision. Following a real PGX pass that produces usable output and satisfies applicable qualification gates, Auto may select it. |
| MPV-008 | Inspect the admin UI and request an allowed manual model download for a vetted integration | No new provider integration install is offered. The download is explicitly initiated and is not needed during offline inference. |

MVP acceptance requires the contract, mock and real qualification suites, quality-ranked Auto selection, compatible manual selection, verifiable local execution, validated interchange, and safe behavior during provider replacement or failure. Provider marketplace, arbitrary UI installation, remote inference, and live version switching during admitted work are outside MVP.

## 19.6 Finalized decisions

| ID | Approved requirement |
|---|---|
| Q19-01 | Auto selects the highest-quality qualified model per task. Compatible manual override remains available. |
| Q19-02 | Manage vetted PGX integrations in the admin UI. Do not install new integrations there. Explicit manual model downloads remain allowed. |
| Q19-03 | One enabled version per provider. Keep admitted requests on their exact pins until terminal before switching versions. |
| Q19-04 | Require a real PGX test with usable output before a new or updated provider is eligible for Auto. |
