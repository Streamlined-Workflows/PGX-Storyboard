# Phase 22: Asset Versioning and Persistence

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 22.1 Purpose and carried-forward rules

The local persistence layer shall protect imported originals and approved artifacts, keep independently reviewable derivatives separate, preserve integrity across crashes and provide complete cleanup of denied and expired generation work. The term versioning means explicit identities, immutable content, revision-aware links and controlled replacement. It does not imply a recoverable copy of every edit, generation or deleted asset.

Phase 02 sets successful generations pending for ten days from successful generation, except when explicitly approved or denied earlier. Viewing, exporting, selecting, locking or use as an input does not approve work or renew its age. Pending exports require the established modal and remain pending. Phase 04 governs canonical artifacts, JSON `AssetManifest.json`, copy-on-edit of shared resources and complete deletion of exclusive data. Phase 17 distinguishes approval from reusable Library enrollment and pins assignments to selected approved revisions. Phase 18 defines editable SWIFT ZIP reimport, the MVP recovery path.

## 22.2 Logical records and ownership

| Record | Responsibilities |
|---|---|
| Asset and component | Stable IDs, selected revision pointers, classification and assembly links. Rename/reclassification does not change identity. |
| Revision/artifact | ID, immutable file references, typed relationships, content facts, approval status and timestamp, generation source while retained |
| Blob | Immutable local content keyed by verified content hash, size, integrity state and valid references |
| Dependency edge | Operational requirement, historical source, or non-owning association. Only required edges participate in dependency approval. |
| Active protection | Short-lived pin for a live job, read or commit. A pin protects physical availability, not approval and not an extended review period. |
| Commit and cleanup journal | Minimum crash-consistency facts necessary for atomic publication or deletion. Discard transaction details when no longer needed and never expose them as deleted generation history. |

If identical bytes appear in two artifacts, use one physical copy with separate logical IDs and approval states. Identical bytes do not imply shared edit intent. Explicit assignments are separate. Changing a shared material or texture requires a modal listing all affected assets and relevant components whether directly or indirectly referenced. Independent copy is the recommended default. An explicitly confirmed shared replacement changes the selected references only after validation and required approvals, without overwriting previous bytes. If a user requests deletion of an in-use material, offer explicit bulk replacement first. Section 22.4 defines the separate deletion workflow.

## 22.3 Lifecycle and transactional workflow

1. Write scratch output outside the published artifact collection. Check format, compatibility and integrity independently. Stage metadata, content hash, required dependencies and source references.
2. Publish content and metadata as one recoverable application transaction. Publish approved-format candidates as pending without mutating source files. Stable readers see either the prior committed state or the complete new state.
3. On explicit approval, compute the full transitive required dependency closure, show each pending requirement with reason and incremental storage, and request a single explicit confirmation before committing approvals. A refused confirmation or missing required artifact leaves all approval states unchanged. Historical intermediates without operational dependency are not silently retained.
4. On denial or expiry, remove the artifact from production selection, Library, job-linked generation history and other artifact-owned metadata. Delete exclusive files when no valid reference or active protection remains. A protected expired input may finish its active use but cannot reappear as an available user artifact or start new work. Approved dependents must not become silently broken.
5. On restart, reconcile interrupted publish and delete records, validate references and stale protections, and run expiry cleanup. Run expiry cleanup periodically as well, and expose Clean Up Now for manual invocation. Report aggregate reclaimed space without identifying deleted artifacts. Repair integrity metadata only as a reproducible recovery operation. Do not use recovery to resurrect a denial or expired generation. Surface user-facing integrity failures without concealing missing required files.
6. Enforce a minimum free-disk-space floor and an optional Director storage budget before admitting new work. Estimate required scratch and permanent growth with deduplication taken into account. Block work that would exceed either configured boundary and explain the blocker. Never evict approved assets to create headroom.
7. Recover an asset through a validated SWIFT ZIP reimport under Phase 18. Reconstruct editable components, material assignments and variants present in the package. Do not recreate omitted files, detailed history or expired local work. Full-library backup and restore are post-MVP.

Control surface: show pending deadline, logical versus physical usage, required dependency closure, checked references before removing a resource, selected revisions, replacement behavior and disk pressure. Separately display approved state, readiness and missing dependency status. Allow explicit approve, deny, delete subject to dependency constraints, create independent copy, and confirmed update of shared assignments. Provide the storage budget control, a visible disk-floor blocker, a local aggregate cleanup report and the user-initiated Clean Up Now action.

## 22.4 Bulk replacement before deleting an in-use material

1. Detect the affected materials and assignments, including pinned revisions, and list all directly and indirectly affected assets with the relevant components and slots. The user can cancel without changes.
2. Have the user choose a replacement. Verify compatibility at every affected assignment, including required maps, any required UV channel, valid revision and the operational dependency graph. Require any applicable approval as a separate explicit dependency step.
3. Present the complete impact and request explicit confirmation before staging the updates. Recheck the affected revisions and assignments at commit to prevent a newly added use from being missed.
4. Commit all assignment changes as a single recoverable operation. Delete the old material only after all assignments have updated successfully and no valid references remain. If any assignment or publication fails, leave the old material available and do not commit a partial reassignment. No physical blob is removed while another valid reference or live job still needs it.

## 22.5 Functional requirements

| ID | Requirement |
|---|---|
| AVP-001 | Preserve stable IDs and valid pointer relationships across restart, rename, import and compatible schema migration. |
| AVP-002 | Never overwrite source/approved immutable bytes during editing, optimization, generation or failed conversion. |
| AVP-003 | Verify immutable content hashes and prevent deletion of bytes still shared by valid artifacts or required by a live job. |
| AVP-004 | Keep timestamp, retention and independent approval state durable across application and server restart. |
| AVP-005 | Remove denied or expired generation bytes, owned files, metadata and job history completely when reference and worker protections permit. |
| AVP-006 | Bind retry inputs to exact earlier revisions and show unavailable historical inputs without promising restoration. |
| AVP-007 | Validate the complete dependency graph and shared-update impact before approval, replacement or deletion. |
| AVP-008 | Make publication, approval, and deletion resumable or safely reversible at the transaction level without exposing partial assets. |
| AVP-009 | Validate storage prerequisites and support migrations without losing approved assets. Refuse incompatible writes until a safe migration path exists. |
| AVP-010 | Separate local integrity diagnostics and storage metrics from generation-owned content subject to complete deletion. |
| AVP-011 | Preserve pending status and exact original deadline when export succeeds, is declined or fails. |
| AVP-012 | Run startup and periodic expiry cleanup, offer Clean Up Now, and report only aggregate reclaimed space without deleted item identifiers. |
| AVP-013 | Enforce the minimum free-disk-space floor and any configured Director budget. Reject work that would exceed either limit without evicting approved data. |
| AVP-014 | Provide an explicit compatible bulk replacement before deleting an in-use material. Show all impacts, obtain confirmation, and do not delete on partial failure. |
| AVP-015 | Provide editable asset ZIP reimport for MVP recovery and defer any full-library backup and restore implementation. |

## 22.6 Provider constraints and SWIFT responsibilities

Providers must use isolated scratch space and return artifacts and lineage metadata for SWIFT to validate. They must not write the canonical inventory, retain private copies of production artifacts outside SWIFT's policy or own deletion decisions. SWIFT implements state transitions, integrity checks, dependency confirmation, deduplication, crash recovery, migration and cleanup. No database, hash algorithm or backup technology is selected here.

## 22.7 Validation and acceptance

| ID | Exercise | Expected evidence |
|---|---|---|
| AVV-001 | Store two logical artifacts with identical bytes then deny one | Denied logical record and its own history disappear. One shared blob remains and the valid artifact opens. |
| AVV-002 | Expire the last valid reference while a live job holds the input | The deadline is unchanged. The expired artifact is unavailable for new use. Physical bytes are removed after final release. |
| AVV-003 | Attempt to approve a candidate with two pending transitive dependencies then dismiss the modal | No approval changes. All missing or pending dependency reasons are visible. |
| AVV-004 | Kill the server at each publication and deletion boundary | No partial visible asset or resurrected deletion. Exclusive orphan files are swept after reconciliation. |
| AVV-005 | Export a pending artifact, restart and advance the test clock past its original ten-day deadline | Export copy remains outside local retention authority. The local candidate and owned generation history are removed. |
| AVV-006 | Replace a material shared by two assets via independent copy and shared update paths | The impact list is correct. Copy affects only the current asset. A confirmed update changes the intended assignments and retains approved originals. |
| AVV-007 | Migrate a retained manifest and open it after migration | IDs and lineage are preserved. Approved content hashes are unchanged. |
| AVV-008 | Age pending artifacts and exercise startup, scheduled and manual cleanup | Each path cleans expired data subject to active protections. The report shows aggregate reclaimed space and no deleted artifact identifiers. |
| AVV-009 | Attempt work below the free-space floor and above the optional Director budget | Each limit blocks new work with a reason. Existing approved data is not evicted. |
| AVV-010 | Bulk-replace an in-use material, then inject an incompatible assignment and simulated commit failure | Valid confirmed replacement updates all affected assets before deletion. Failures leave the original material available and commit no partial reassignment. |
| AVV-011 | Reimport an eligible SWIFT ZIP into a clean project | Included components, materials and variants remain editable. Excluded history and missing source files are not invented. |

MVP acceptance requires retention, crash, migration, dependency, bulk replacement, budget enforcement and deduplication assertions with an isolated test store and deterministic clock, plus editable ZIP recovery. It excludes full-library backup and restore, unlimited rollback, remote synchronization and undelete for denied or expired work.

## 22.8 Finalized decisions

| ID | Approved requirement |
|---|---|
| Q22-01 | Run startup and periodic expiry cleanup. Offer Clean Up Now and report aggregate reclaimed space without deleted item identifiers. |
| Q22-02 | Enforce a minimum free-disk-space floor and any optional Director budget. Block new work rather than evicting approved assets. |
| Q22-03 | Offer confirmed, compatible bulk replacement before deleting an in-use material. Delete only after all assignments update successfully. |
| Q22-04 | Use editable SWIFT asset ZIPs for MVP recovery. Full-library approved-only local backup and restore is post-MVP. |
