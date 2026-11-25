# Phase 26: Development Roadmap and Acceptance Criteria

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 26.1 Purpose

Turn the 26-phase design into a build and verification plan. Phase numbering is the design sequence, not a mandatory build order. Approved decisions from Phases 01–10 remain binding. Phases 11–26 are the finalized design baseline. Design closure is not implementation, qualification or release. Capability spikes and tests determine provider readiness. No specific implementation or provider is approved here.

## 26.2 Delivery sequence

| Gate | Scope and dependency | Exit evidence |
|---|---|---|
| A. Design baseline | Reconcile the 26 design files, approve MVP scope and support boundaries, record the closed owner decisions and explicitly deferred scope | Decision register, phase interfaces, release matrix, clear post-MVP backlog |
| B. First working demo | Asset/lifecycle (04/22), local adapters/resources/queue (19–21), handoff (05), minimal viewport/UI (16/23), local security (24), ZIP contract (18) and demonstrable character prep (14) | From approved references or imported FBX, review a candidate, reopen it, confirm a pending export and validate package reimport. Demonstrate character preparation in this same demo, not a later milestone |
| C. Production geometry and surface | Geometry, optimization, components, UV, texturing and materials (06–11), library foundations (17) | Modular fixture with independent components, compatible UV/PNG set, reusable material and preserved source |
| D. Targeted surface editing | Shared selection, painting, masks and inpainting (12–13), related viewport checks (16) | Apply and discard candidate edits on an isolated region without changing protected maps or neighboring components |
| E. Character preparation | Actor prep and landmark mapping (14–15), selected actor export profile (18), licensing gate (24) | Clean base and a modular wearable remain independent, automatic 218-landmark output passes the rights-cleared Phase 15 handoff on the selected CC5 build and Default preset, without manual landmark placement in Director |
| F. Qualification and release | Finish evaluations (25), recovery and privacy tests, desktop acceptance (23), rights and performance verification (24) | Versioned test report, documented warnings, offline PGX evidence, successful qualification of every planned MVP integration, and a live PGX walkthrough for owner sign-off |

Build persistence, validation and fault handling with each gate. The first working demo does not require all planned integrations to be qualified. The MVP release does. Do not mark a gate done because a UI exists if its interdependent artifacts cannot yet be reviewed, reopened and exported.

## 26.3 Acceptance matrix

| ID | Scenario | Required evidence |
|---|---|---|
| REL-001 | Static asset loop | Reference IDs and roles survive handoff and reload. Local geometry run or import produces validated FBX. Approved original is unchanged. Geometry is reimported at intended scale and orientation from the package. Editable ZIP reimport reconstructs the included asset and its relationships as defined in Phase 18, not just a flattened mesh. |
| REL-002 | Modular asset loop | Replace a component or material variant without regenerating or editing unaffected components. Validate hierarchy, transforms, independent texture sets and common per-set map resolution. Reimport the editable ZIP and verify included component relationships, material assignments and variants survive. |
| REL-003 | Localized surface loop | Save a candidate paint or inpaint result. Check protected pixels, map locks, seam behavior, candidate comparison and restoration by discarding the candidate. |
| REL-004 | Actor handoff loop | A clean base, prepared wearables, automatically generated landmarks and reference artifacts retain provenance and preserve approved originals. Verify the rights-cleared template with the selected CC5 build and its Default preset. Never ship the numbered overlay as skin color. |
| REL-005 | Recovery and retention | Force an interruption between processing and commit. Reopen without corrupting approved artifacts or duplicating results. Verify 10-day pending expiry and denial cleanup, shared-content protection and explicit dependency approval. |
| REL-006 | Release boundary | Runtime passes offline after provisioning. Access, licensing, PGX generation and desktop Chrome/Edge match the release matrix. Every planned MVP integration qualifies. |
| REL-007 | Export review | Pending warning is explicit, the manifest references only valid files in the current package, and export neither approves nor extends retention. |

Required sign-off fixtures are a static prop and a modular humanoid. The Performance Stage bass drum and a clean humanoid with one separate wearable are candidate examples, not mandated files. Any existing drum GLB is a downstream comparison, not a canonical input requirement. A separate vehicle-interior fixture is optional; vehicle-interior classification remains in scope where specified. Use synthetic failure cases when real customer files are unnecessary.

## 26.4 Scope and readiness controls

- Record each capability as required, optional, deferred, or blocked by missing qualification. An in-scope integration that is disabled, unlicensed or unqualified blocks MVP release. Explicitly deferred features do not.
- Preserve the explicit post-MVP slate for generated shared/hybrid atlas layouts, atlas optimization, UDIM, direct GLB export, full tablet touch editing and full-library backup. Explicit weight transfer remains MVP, but automatic rig creation does not.
- Prioritize correct asset recovery and independent operation over throughput or batch convenience.
- State evidence rather than asserting an unrun case passed. A rights-blocked CC5 integration or unqualified provider shall not quietly become a fallback success.
- Keep checkpoints reversible. An upgrade plan must state how it protects approved assets and how old readers or exports are handled. It must not revive denied outputs.
- Trace each release gate to the closed decision register and record implementation evidence separately.

## 26.5 Application and provider responsibilities

The application team owns traceability, feature flags, reliable staging, packaging and release evidence. Providers supply pinned role capability and measured behavior under the selected local profile. An end-to-end success cannot be inferred from a provider demo or adapter mock. Deliver a versioned test report with qualification results, known limitations and what was actually exercised. Walk Jeremy through the working release live on the PGX. No separate reusable test ZIP is required. Keep acceptance evidence distinct from deliverable asset ZIPs and hold release until the required evidence exists.

Design decisions: Q26-01 through Q26-04.
