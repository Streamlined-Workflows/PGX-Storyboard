# Phase 21: Generation Queue and Job Management

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 21.1 Purpose and carried-forward rules

The local queue shall make generation observable, cancellable, and independently retryable where inputs remain available. The queue shall enforce admission rules separately from scheduling and keep user submissions separate from internal stages.

Phase 02 permits multiple eligible waiting jobs and limits each generation server to one active AI inference job. Phase 06 narrows admission for geometry-producing requests: one candidate per user request, and no additional geometry submission while the accepted request is waiting, running or in required internal stages. The geometry admission lock is PGX-wide across projects, browser tabs and client computers. Geometry-producing refinement, regeneration and component work use that same lock. Phase 08 prevents duplicate and conflicting component work on the affected asset and processes its components sequentially. Phase 10 prevents additional texture generation submissions during active texture execution at the frontend and backend. Unrelated work with no conflicting asset locks may wait in the queue while geometry is outstanding. Independent heavy work waits until generation finishes under Phase 20. A single coordinated texture-set request may produce several requested maps. A geometry-with-texture or Master Mesh request may require sequential child stages. Neither exception allows submission of multiple user candidates. The generic queue remains available for other eligible work.

## 21.2 Objects, states and controls

| Object | Meaning |
|---|---|
| Request | One authorized intent with a stable ID, idempotency key, operation, immutable input handles and effective configuration |
| Stage | A declared node within the request plan, with input/output contracts and declared prerequisites |
| Attempt | A bounded execution of one stage with an exact provider/runtime, start/end timestamps and outcome |
| Resource lease | Exclusive claim on the inference slot for one stage, including loading and teardown |
| Admission lock | Prevents new submissions within the workflow-specific scope while an accepted request remains outstanding |

The following are logical states: Waiting, Running, Validating, Publishing, Cancelling, Awaiting Force-Stop Confirmation, Succeeded, Partially Succeeded, Failed, Cancelled and Interrupted. An outstanding lock survives browser or client disconnect. A waiting request may be admitted without holding an active inference lease. A resource- or prerequisite-blocked waiting job has a visible reason. Partial success is used only when the workflow allows independently valid reviewable outputs. A request cannot be called successful until its required outputs are durably published. Job outcome is independent of artifact approval. An outcome does not mark a generated artifact approved or reset its expiration.

The queue view shall provide operation, asset or component, stage, honest progress or indeterminate state, time and blocker, stable request ID, and authorized actions. Users may view details, cancel waiting or active work, and explicitly retry an eligible failed stage where unchanged inputs exist. Retry rechecks dependencies, admission and resource capacity. If the effective inputs or configuration must change, submit a new request instead. The queue shows submission order and explains when loaded-model grouping changes the next eligible inference job. Manual reprioritization is outside MVP.

## 21.3 Execution workflow

1. Resolve and validate the request and then atomically claim its scoped admission lock and persist the request. Repeated submission with the same idempotency key shall return or point to the same request. A different submission blocked by the active lock shall not enter the queue.
2. Snapshot input revisions, provider and settings. Acquire active input protections only for live use as defined in Phase 22. Waiting records do not prevent their pending inputs from expiring. Reject a dangling prerequisite rather than silently using a replacement.
3. Apply the oldest-eligible and loaded-model scheduling rules in Section 21.4. Revalidate runtime, artifact prerequisites and capacity before acquiring the Phase 20 lease where applicable.
4. Run, validate, stage and publish the result under Phase 22. Use request/stage/attempt identity to make final publication idempotent if completion is repeated.
5. Release the active inference lease only when execution stops and Phase 20 verifies the resources are safe. Keep workflow-specific admission locked until the request reaches its terminal state. Try graceful cancellation first. If it does not stop, ask Jeremy before force-stopping the isolated worker. Do not unlock the slot or admit conflicting work until the worker is stopped and its GPU resources are verified free. Declining or leaving confirmation unanswered shall not force-stop the worker.
6. On restart, reconcile the persisted ledger against leases, workers and staged outputs. Do not start a second worker while a previous worker is unaccounted for. Resume a verified never-started waiting request only after rechecking its inputs, locks, exact provider and safe recovery. If execution began and cannot be reconciled to a committed terminal result, mark it Interrupted and require manual retry. Do not restart inference or create a replacement generation automatically.

## 21.4 Scheduling policy

Start with the oldest eligible submission when no usable model group is active. After an inference attempt, prefer the oldest otherwise eligible request whose next inference step uses the same exact loaded model and revision. Continue that group in original submission order before switching to a different model. A blocked or conflicting request does not keep its group running or block another eligible job. When no eligible same-model work remains, return to the oldest eligible submission. If its model differs, release the outgoing model allocations before loading the next one.

Eligibility requires intact pinned inputs, satisfied prerequisites, applicable asset and workflow locks, and sufficient resources. A group changes scheduling order only. It cannot change Auto provider selection, a request pin, required stage ordering, or the one-active-inference limit. For example, with otherwise eligible, nonconflicting A1, B1, A2 submitted in that order, run A1, A2, then B1 and perform a single A-to-B switch. Independent heavy CPU work waits during active generation. A required conversion inside the admitted request follows its own stage dependencies and shall not overlap inference.

## 21.5 Functional requirements

| ID | Requirement |
|---|---|
| GQM-001 | Separate job scheduling from user admission, with backend atomicity and matching interface states. |
| GQM-002 | Persist allowed waiting requests, exact snapshots, blockers and stage transitions across restart subject to retention. |
| GQM-003 | Enforce one live AI inference lease per generation server across workspaces. |
| GQM-004 | Enforce applicable geometry, component and texture locks without discarding the generic eligible queue. |
| GQM-005 | Never silently consume deleted, changed or unauthorized inputs. Expose blocked or interrupted status and recovery options. |
| GQM-006 | Preserve compatible completed artifacts when a later stage fails, subject to normal retention. Do not display failed partial files as published artifacts. |
| GQM-007 | Classify and expose capacity, incompatibility, provider, validation, interruption and user cancellation outcomes. |
| GQM-008 | Quarantine late or duplicate output after cancellation or retry. Commit only from the authorized active attempt. |
| GQM-009 | Release all locks and input protections once safely terminal. Clean up denied and expired generation history under Phase 22. |
| GQM-010 | Protect prior approved selections and unrelated assets regardless of job outcome. |
| GQM-011 | Enforce the PGX-wide geometry lock across all sessions and allow unrelated nonconflicting work to wait. |
| GQM-012 | Dispatch oldest eligible first when starting or switching groups and process eligible requests that use the exact loaded model in submission order within its group. |
| GQM-013 | Automatically resume only verified never-started waiting work after safe reconciliation and preflight. Require explicit retry for interrupted work. |
| GQM-014 | Attempt graceful cancellation and request explicit confirmation before forced termination. Keep the inference slot unavailable until worker and GPU resource release are verified. |

Providers shall expose or support adapter-level handles for stage start, status, result and stop. A provider without cooperative cancellation must allow safe isolation and report when no graceful stop is available. Forced termination is an application-controlled action that requires confirmation after graceful stop does not succeed. The lease is never freed merely because the cancellation timer expired. SWIFT owns request admission, orchestration, progress reporting, atomicity, reconciliation, publication authorization, retry policy and retention. Providers shall not insert queue entries or approve artifacts directly.

## 21.6 Validation and acceptance

| ID | Exercise | Expected evidence |
|---|---|---|
| GQV-001 | Submit the same geometry request twice, then a different one from another tab and another linked computer | One admitted geometry request and one candidate. No duplicate enqueue and no bypass while waiting or running. |
| GQV-002 | Queue eligible jobs from independent workflows and run a multi-stage geometry request | Unrelated nonconflicting work can wait. Dependent stages do not create extra submissions or overlap active inference. Independent heavy jobs wait until generation finishes. |
| GQV-003 | Cancel one waiting job and one mid-run job | The waiting job never launches. The running job receives a graceful cancel first. Prior assets are unchanged. |
| GQV-004 | Kill the server before and after the publish commit | After reconciliation, verified never-started jobs resume only after input and resource checks, interrupted jobs await retry, and committed jobs stay terminal. No duplicate publication or second live lease. |
| GQV-005 | Retry a failed stage with intact then removed input | The first succeeds if still compatible. The second is blocked with the exact missing-input reason. |
| GQV-006 | Simulate late output after cancellation and a partial coordinated texture-set failure | Late output is discarded. Only permitted complete maps remain reviewable, and none are auto-approved. |
| GQV-007 | Submit eligible A1, B1, A2 with distinct pinned model groups A and B | Dispatch order is A1, A2, B1. Only one A-to-B switch and at most one active inference. A2 is skipped when blocked. |
| GQV-008 | Hold an isolated worker after graceful cancel times out and exercise decline and confirmation | No force-stop occurs before explicit confirmation. The slot remains unavailable until the worker and GPU resources are verified free. |

MVP acceptance requires all applicable admission, loaded-model scheduling, interruption, cancellation and deletion assertions to pass on the instrumented PGX. Scheduled recurring runs, distributed scheduling, manual reprioritization and unattended retry loops are outside MVP.

## 21.7 Finalized decisions

| ID | Approved requirement |
|---|---|
| Q21-01 | Block repeat geometry submission across tabs and computers during the accepted request. Permit unrelated nonconflicting work to wait. One active AI inference per PGX. |
| Q21-02 | Start oldest eligible. Complete eligible work using the exact loaded model in submission order within that group before switching. |
| Q21-03 | Resume verified never-started waiting jobs after recheck and safe recovery. Interrupted jobs require explicit retry. |
| Q21-04 | Try graceful cancellation and ask before force-stopping the isolated worker. Hold the inference slot until worker and GPU resources are verified free. |
