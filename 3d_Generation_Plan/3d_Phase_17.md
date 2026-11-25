# Phase 17: Asset and Material Libraries

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 17.1 Purpose and scope

Make approved whole assets and materials reusable across local projects without duplicating immutable files or conflating a library entry with project-specific assignments. Components and texture sets are available through applicable parent entries and do not receive standalone catalog entries. The library is an index and reuse workflow over the Phase 04 artifact graph and Phase 22 persistence rules. It does not add a remote service, marketplace, recovery archive for denied outputs, or permissions that could bypass lifecycle rules.

| Entity | Responsibility |
| --- | --- |
| Library item | Stable identity, user-readable name, classification, searchable tags, optional favorite flag and thumbnail, and a resolvable selection of approved content. |
| Physical blob | Immutable content, addressed or deduplicated by verified content identity. It has no independent product approval state. |
| Usage | Reference from an asset, component, named assembly, or material assignment to the applicable logical artifact/revision. |
| Collection | A flat user-defined grouping of library references, not a second storage or ownership system. |
| Project Work | Project review of Pending artifacts. Reusing or indexing an artifact does not authorize its retention. |

## 17.2 Workflow and controls

1. **Approve, then catalog.** Approval retains content in its project and does not enroll it. Show required dependencies, reasons, and affected storage when approving a pending item. The separate Add to Library action accepts eligible approved whole assets and materials. Classify or add metadata only through explicit editing. A thumbnail missing or invalid shall not prevent browsing the underlying retained item.
2. **Find.** Search names, tags and approved classifications. Use favorites and flat collections. Filter entries by asset or material type, compatibility, and archive status. Browse applicable components and texture sets within their parents. Show thumbnails when available, the artifact's origin or source where retained, and content metadata such as dimensions, vertex counts, material semantics, and applicable UV dependencies.
3. **Inspect before assigning.** View a material swatch or asset/assembly preview and a usage list. Determine which texture sets, material slots, UV channels and geometry revisions are required. Do not auto-convert incompatible assets or silently map a material to an arbitrary slot.
4. **Use.** Pick a compatible item and assign it to a project target deliberately. Pin the exact approved revision used by every assignment. Distinguish shared item assignment from creating an independent logical copy. Both may reuse identical blob bytes; only intentional shared updates may alter multiple current assignments.
5. **Modify or retire.** Before a shared material or texture edit, list all current direct and indirect consuming assets with affected components and assignments. Offer Create Independent Copy, Update Shared Resource, and Cancel. Preserve the original until an approved replacement and explicit application are ready. Archive, delete, and remove from collection are distinct actions. Phase 22 governs explicit compatible bulk replacements before deleting an in-use material.

## 17.3 Requirements

| ID | Requirement |
| --- | --- |
| LIB-001 | Enroll only approved whole assets and materials through separate Add to Library. Use stable IDs independent of filenames, display names and storage paths. Expose usable components and texture sets through their parent entries, not as standalone entries. |
| LIB-002 | Pending review and Approved reuse shall remain distinct. Pending items are visible in their project context, do not appear as approved catalog assets, and still expire ten days after successful generation unless explicitly approved. |
| LIB-003 | Searching and filtering shall be synchronous with accuracy expectations for persisted state or show when indexing is catching up. Index results shall not reintroduce inaccessible or expired items. A rebuild shall derive the index from valid records, not resurrect exclusive history. |
| LIB-004 | Present direct and transitive required usage, including project, asset, component or assembly, and affected material slot where applicable. Distinguish currently assigned, archived, approved dependency, and merely historical references. |
| LIB-005 | Copy-on-edit preserves other assignments unless the user deliberately selects Update Shared Resource. New bytes and assignments are reviewed, validated and stored without overwriting retained files. Physically identical valid artifacts may share storage; every logical item retains its own identity and applicable approval state. |
| LIB-006 | Every assignment shall pin its exact approved revision. Changes to the pin require explicit action, and a shared update shall require confirmation against the usage set. If that set changes before commit, refresh the affected list. Reject an update that would leave an approved dependency invalid, and identify the conflict. |
| LIB-007 | Reuse must preserve independent component texture sets and the common resolution of each set. Historical provenance shall not be converted into a required dependency unless the artifact needs it to operate. |
| LIB-008 | Archive shall hide an item from active results by default while retaining its files and dependencies. Delete shall be explicit and dependency-aware, with Phase 22 safeguards for replacement of an in-use material. No removal from a collection shall delete an underlying artifact. |
| LIB-009 | Denied and expired outputs shall leave no exclusive files, preview artifacts, index entries or generation metadata. Live dependents and active operations shall only protect the data required by existing rules. |
| LIB-010 | A library item that references unavailable historical input shall show the input as unavailable. Missing operational dependencies shall mark the item incomplete and prevent affected reuse until resolved. |
| LIB-011 | Expose actual and projected local storage impact where possible. Do not add together shared blob sizes as if every item had its own file. Distinguish cache, pending and approved usage. |
| LIB-012 | Bulk actions shall not silently approve, delete, replace, or publish artifacts. Review of affected items and dependencies shall precede irreversible operations. |
| LIB-013 | Support searchable tags, favorites and flat collections. Nested collections and saved searches are post-MVP. |

## 17.4 Inputs, outputs, and responsibilities

**Inputs:** Validated local manifests and artifacts, approval states, revision/usage graph, material slots and surface contracts, and user-provided metadata.  
**Outputs:** Search and filter results, portable assignments by artifact identity, favorites, local flat collections, or archive state, compatibility diagnostics, and approved resource revisions when explicitly produced.

Director rather than a model owns indexing, compatibility enforcement, reuse, identity, shared usage lookup, bytes accounting, and lifecycle checks. Optional metadata or thumbnail generation can consume only declared local inputs, return proposals or derived previews, and cannot write or update production assignments. Manual metadata and deterministic previews remain available independently.

The shared-library contract must not sort one item's physical storage into multiple deletable copies. A single valid reference can keep bytes in local storage after a different logical item is deleted. The UI should distinguish freeing an item in the catalog from actually reclaiming physical bytes.

## 17.5 Validation assertions

| ID | Test | Expected result |
| --- | --- | --- |
| LIB-A01 | Reuse one material in two projects with different component IDs. | Both usages resolve to valid assignments, library usage enumerates both, and identical immutable files remain stored once. |
| LIB-A02 | Edit in Project A using Create Independent Copy. | A changes only after explicit application; B and the original approved artifact are unchanged. |
| LIB-A03 | Open a shared update, then add another usage before confirming. | Confirmation requires a fresh affected list or aborts; no stale approval updates the new consumer. |
| LIB-A04 | Assign a UV-bound texture set to incompatible UV geometry. | Affected set is flagged with reason; current valid assignment remains intact. |
| LIB-A05 | Archive an approved shared item, then remove its last collection entry. | Item stays retained, existing approved consumers function, and neither action deletes its bytes. |
| LIB-A06 | Deny an item sharing bytes with approved content and expire another with exclusive bytes. | Denied/expired records and their exclusive metadata disappear; approved content remains intact and exclusive orphan bytes are reclaimed. |
| LIB-A07 | Rebuild library index from valid records after interrupted cleanup. | Expired, denied, and inaccessible entries are absent; approved items and browse metadata remain accurate. |
| LIB-A08 | Approve a project asset and its dependencies but take no library action. Then explicitly enroll the asset. | Approval alone does not add entries. Add to Library creates one whole-asset entry; components and texture sets remain discoverable through their parent. |
| LIB-A09 | Approve a newer material revision with two existing library usages. | Both existing usages remain pinned until the user completes an explicit update with an affected-assets review. |
| LIB-A10 | Tag, favorite and collect an eligible item, then reopen the library. | Assigned tags are searchable and favorite and flat collection membership persist without duplicating the item. |

## 17.6 MVP acceptance

An artist can explicitly add approved whole assets and materials to the library, then find, inspect and reuse them locally with pinned revisions. Tags, favorites and flat collections are functional, and components and sets remain available through their parents. At least two projects can reuse one shared material without duplicate bytes, and a subsequent independent edit or confirmed shared update affects exactly the intended usages. Operations never conflate catalog metadata, approval, dependencies, or physical file retention.

## 17.7 Approved decisions and boundaries

- **Q17-01:** Approval retains an artifact. Separate Add to Library enrolls it.
- **Q17-02:** Assignments pin exact approved revisions. Changes are explicit. Shared-update confirmation lists all affected assets.
- **Q17-03:** Only whole assets and materials are standalone entries. Components, texture sets and their maps are available through applicable parent entries.
- **Q17-04:** Searchable tags, favorites and flat collections are in MVP. Nested collections and saved searches are post-MVP.
