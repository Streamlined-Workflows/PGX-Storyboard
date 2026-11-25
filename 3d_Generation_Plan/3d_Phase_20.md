# Phase 20: Hardware and Resource Management

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 20.1 Purpose and boundary

The local generation server shall admit and run GPU, CPU, storage and mixed workloads within measurable operating limits. The studio must remain usable while a job runs. It shall avoid loading every specialist model at once, and protect artifacts when a process exceeds its expected resource needs. Phase 19 defines provider declarations, Phase 21 owns user-facing job state, and Phase 25 defines validation benchmarks.

**Carried forward:** MVP runs locally. A local backend need not be the UI device. Each generation server permits one active AI inference job. Providers run sequentially and independently without required concurrent residency. Model residency can continue between eligible jobs in the same exact-model group without holding a second active inference lease. The previous attempt must no longer be executing and its per-attempt reservations must be reconciled before the next job. An idle resident model is not an active inference attempt. Resource pressure may defer or block work, but shall not substitute a lower quality, different strategy or reduced input set without user action.

## 20.2 Hardware inventory and resource accounting

Probe OS/architecture, memory topology, accelerator and driver capabilities, CPU limits, accessible disk locations and free space, and applicable runtime versions. Treat feature detection separately from qualification. The ThinkStation PGX is the sole MVP generation host for qualification and release support. Linked computers are clients, reached locally or over Tailscale as approved in Phase 24. Client access does not add a generation host. Detection on the PGX is not proof that a provider build works.

| Resource | What SWIFT shall account for |
|---|---|
| Accelerator and system memory | Dedicated and/or shared memory topology, reserved headroom, provider load/work estimates, observed peaks, and reclamation stage. Avoid summing unified memory twice. |
| CPU and host workload | Worker and thread limits, non-inference conversion/validation cost, interactive workload headroom and concurrent deterministic stages if allowed. |
| Storage | Model files, existing artifacts, estimated working-set peak, conversion/export scratch, and a protected disk floor. Count copied data as real space unless deduplicated. |
| Time and stability | Model load time, stage wall time, supported timeout, worker heartbeat, retry eligibility and device/driver resets. |

Controls display detected limits and readiness, effective resource estimates and headroom, and reasons for a blocker. Use memory reserve defaults established by PGX qualification, with advanced adjustments bounded by a hard safety minimum. Enforce the free disk floor and optional Director budget defined in Phase 22. A model's declared peak is not a guarantee. Tag estimates as measured, declared or unknown and include the qualification context.

## 20.3 Admission, execution and release

1. Validate runtime availability, exact compatibility and the requested operation. Compare estimated peak resources and scratch against current available capacity minus headroom, and return a named resource blocker before allocating if capacity is insufficient.
2. Reserve capacity with the Phase 21 inference lease. Recheck after waiting, before loading, and before high-cost conversion when conditions may change. Do not claim a GPU is ready merely because an adapter package exists. Block a GPU generation job when the GPU is unavailable. Neither an automatic switch nor a manual fallback to CPU is offered for that job. Independently designed CPU-only operations remain eligible under their own contracts.
3. Run the stage and sample resource consumption locally. Keep browsing and lightweight editing available. Queue separate heavy operations, including FBX conversion and ZIP export, until generation finishes. If an admitted request itself needs a heavy conversion to publish its output, perform that required stage sequentially after its inference work stops, never in parallel with inference. Update the interface with actionable load, execution, validation and waiting states without inventing percentages.
4. Publish validated output through Phase 22 staging. Release the lease only when the previous attempt has stopped executing and its reservations and scratch are safe for the next stage. A stalled or cancelled worker is subject to the stricter release check below. Retain only the same qualified model for its next eligible job when safe under Phase 21. Free the outgoing model allocations on switch before loading a different provider, or when pressure or failure requires reclamation. The active job's required files remain pinned until released.
5. On disk pressure, out-of-memory, timeout, cancellation or worker crash, contain failure to the active attempt. Try a graceful stop. If it does not stop, ask before force-stopping the isolated worker and hold the inference slot until the worker and GPU resources are verified free. Remove exclusive partials when safe, record a useful class, and preserve original and approved artifacts. Do not evict approved work to finish a job.

## 20.4 Functional requirements

| ID | Requirement |
|---|---|
| HRM-001 | Detect accelerator, RAM topology, runtime and disk facts locally. Mark unmeasurable sensors or estimates unavailable rather than inventing values. |
| HRM-002 | Compare each stage, including conversion and export, against supported and configured limits before allocation. |
| HRM-003 | Track execution, scratch and output headroom separately and avoid counting immutable deduplicated blobs twice. |
| HRM-004 | Enforce one active inference lease per server, including near-simultaneous requests, and verify release before starting the next provider. |
| HRM-005 | After cancellation or worker loss, reconcile or quarantine stale allocations before reuse. Surface an operator-action state if the process/device cannot be safely reclaimed. |
| HRM-006 | Distinguish unsupported hardware, temporarily busy, insufficient headroom, capacity exceeded during runtime, and out-of-disk. |
| HRM-007 | Keep telemetry local and per-resource summaries independent of deleted generation-specific history. |
| HRM-008 | Never treat transparent resource management as authorization for a different provider, input set, output specification or automatic deletion of approved assets. |
| HRM-009 | Forecast disk commitment before multi-stage work and again before journaled/atomic publication where temporary duplication can occur. |
| HRM-010 | Protect operator access and keep the UI available when capacity is too low to start new work. |
| HRM-011 | Qualify the PGX only for MVP generation. Do not interpret connected editing clients as additional execution nodes. |
| HRM-012 | Use PGX-tested memory reserve defaults and accept advanced changes only at or above the hard safety minimum. |
| HRM-013 | Block GPU generation while GPU service is unavailable and do not offer CPU fallback for that request. |
| HRM-014 | Do not overlap independent heavy operations with generation. Queue them with a visible blocker while maintaining lightweight editing. |

## 20.5 Provider constraints and SWIFT responsibilities

Providers declare hardware support, load and run estimates or measurement availability, actual driver dependencies, timeout and cancellation behavior. A separately designed CPU-only operation has its own capability and performance profile. It is not a fallback path for an admitted GPU generation job. Providers expose stop/release behavior or permit worker isolation sufficient for bounded cleanup. SWIFT enforces admission, reservations, telemetry, scheduling limits, subprocess cleanup, preflight and honest failure messaging. It measures and publishes the reference host operating envelope in Phase 25 without promising portability to untested hosts.

## 20.6 Validation and acceptance

| ID | Exercise | Expected evidence |
|---|---|---|
| HRV-001 | Run two requests against one server | At most one active inference attempt across loading, execution and teardown. |
| HRV-002 | Launch two sequential specialists on the reference target | Stage outputs persist, previous allocations are reclaimed, peak memory stays within qualified limits |
| HRV-003 | Lower free disk beneath its floor or induce mid-run pressure | Preflight blocks or fails safely without filling system storage, changing approved files, or advertising success |
| HRV-004 | Simulate OOM and an unresponsive worker | Classified failure, graceful stop attempt, explicit consent before force stop, unchanged source hashes, and verified release before subsequent work. |
| HRV-005 | Compare unified-memory reports and estimate to observed peak on representative fixtures | No double counting. Estimates are flagged and thresholds calibrated. |
| HRV-006 | Submit FBX conversion and ZIP export while generation runs, then use the editor | Heavy work waits until the generation finishes. Browsing and lightweight editing remain usable under the accepted responsiveness budget. |
| HRV-007 | Disconnect GPU availability and submit GPU generation and a separate compatible CPU-only operation | GPU generation is blocked without an offered CPU fallback. The separate CPU-only operation is evaluated on its own contract. |
| HRV-008 | Change the advanced memory reserve below and above the qualified minimum | The below-floor request is rejected. A qualifying adjustment is shown and applied locally. |

MVP acceptance requires the PGX hardware matrix, qualified memory defaults and safety minimum, local preflight and resource records, same-model reuse and verified release across model switches, safe cancellation and failure states, plus reproducible resource-pressure tests. Multi-node scheduling, secondary generation-host qualification and GPU-to-CPU generation fallback are outside MVP.

## 20.7 Finalized decisions

| ID | Approved requirement |
|---|---|
| Q20-01 | Qualify only the ThinkStation PGX for MVP generation. Linked computers are clients. |
| Q20-02 | Use tested PGX memory reserve defaults with advanced adjustments bounded by a hard safety minimum. |
| Q20-03 | Block GPU generation when the GPU is unavailable. Do not offer manual or automatic CPU fallback for that job. |
| Q20-04 | Queue heavy operations behind active generation. Browsing and lightweight editing remain available. |
