# Phase 23: User Interface and Workspace Design

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 23.1 Purpose and boundaries

Provide one studio for independently runnable workflows. Keep stage controls close to the asset they affect and make these state changes clearly different: selecting, applying to an assembly, approving for retention, and exporting. Phase 16 defines viewport behavior, Phase 21 defines execution semantics, and Phase 22 owns lifecycle. This phase defines how those contracts appear to the user. The workspace uses top tabs with tools under each; phases are independently runnable rather than steps in a wizard.

## 23.2 Navigation and state model

The established entry is **Asset Generation > 3D Generation**. **Reference Generation** remains a sibling destination for creating or editing reference imagery. From 3D Generation, open that destination with the current asset/reference context where possible. Returning within the same session shall restore the original asset and current component context without creating a mesh or changing reference approval. This is not a fresh open. Preserve the implemented artifact-ID handoff. An unavailable handed-over reference shall be shown as unavailable, not quietly substituted.

Workspace frame:

| Area | Responsibility |
|---|---|
| Header | Project, asset, active assembly configuration, stage, dirty state, and active request |
| Top tabs and tools | Group Geometry, Optimization, Components, UVs, Textures, Materials, Surface Editing, Character Tools and Export by purpose, with a default tool for a fresh open |
| Asset tree | Selected component, variant, visibility, lock, and dependency indicators |
| Work area | 3D or split view where specified by the stage. Library and job views may use a list instead |
| Inspector | Stage inputs, validation results and applicable commands |
| Job surface | Current operation, queue eligibility, stage progress, errors and cancellation |

A stage may be opened even when it cannot run. Show missing prerequisites and deep-link to the action that addresses each. An imported FBX with suitable UVs can go straight to Materials or Textures. Actor-only actions are not offered for unrelated classifications. Export remains available for whatever compatible artifacts the user has selected.

## 23.3 Requirements

| ID | Requirement |
|---|---|
| UX-001 | Bind every mutating command to a visible asset, component, and source revision. Inspecting a different component does not change a running job. |
| UX-002 | Distinguish read-only preview changes, edits that change a working selection, and persistent material, geometry, or texture operations. |
| UX-003 | Keep source and candidate visible in review. Mark locks with text and icon, and confirmed defects red with an accessible issue list. Selection highlights and heatmaps use distinct treatments. |
| UX-004 | Show Pending, Approved, and unavailable states by label. For Pending show expiration, and for a missing source show which action is blocked. |
| UX-005 | Expose Approve, Deny, and Export as separate actions. Use the inherited dependency approval and pending-export confirmations. A cancel or dismissed modal makes no changes. |
| UX-006 | Offer automatic compatible provider selection and advanced compatible override. Show rejected inputs, unsupported options, and the actual effective configuration before submission. |
| UX-007 | Enforce server-reported locks, including after reload and on a second tab. Disable the affected command with its specific reason and keep unrelated allowed inspection available. |
| UX-008 | Preserve stable keyboard navigation, readable labels, and a way to inspect results without relying on color or a pointer. Do not capture typing shortcuts in text inputs. |
| UX-009 | Warn before discarding unsaved production edits and distinguish them from durable saved work. On a fresh open, start at the default tool with no component selected. Preserve saved assets, candidates and editable paint layers. Reset viewport settings as defined in Phase 16. |
| UX-010 | A failure panel shall identify the failed step and any retained outputs and show the next valid action. Do not offer a blind Retry when prerequisites changed. |

## 23.4 Inputs, outputs and application responsibilities

Inputs are asset classification, active configuration, selected artifact and component IDs, job state, validation state, and local UI preferences. Outputs are validated command intents, review or confirmation responses, and transient session view state. The stage registry controls names, compatible inputs and controls. The client shall not infer approval, permissions, or compatibility from stale cached state.

Providers supply structured progress, diagnostics, or capability values when available. No provider controls navigation, approval modals, export decisions, keyboard interactions or display state. Normalize unknown progress to indeterminate rather than displaying a fabricated percentage. Display provider notes as data.

## 23.5 Assertions and acceptance

| ID | Test and expected result |
|---|---|
| UX-A01 | Import compatible FBX, enter Materials without running Geometry, and return from Reference Generation. Asset and component context are preserved. |
| UX-A02 | Open the same pending result in two tabs and submit a conflicting operation. The losing tab shows the lock and can still inspect the asset. |
| UX-A03 | Approve an output with pending dependencies, then cancel. The dependency list is visible and neither approval state changes. |
| UX-A04 | Export a pending item after confirming the warning. The ZIP downloads and the item remains Pending with the same deadline. |
| UX-A05 | Navigate the core flow with a keyboard. Focus is visible, dialogs restore it, and defects can be identified without color alone. |
| UX-A06 | Return to an asset after a failed job. The previous approved output remains usable and the current failure and next action are distinguishable. |
| UX-A07 | Reopen a saved asset in a new session in desktop Chrome and Edge. The default tool opens with no component selected, viewport settings reset, and saved edits still exist. |

MVP acceptance requires all inherited workflows to be discoverable without imposing a linear wizard, all approval/export/lock state to agree with the server, and core review and recovery to pass in desktop Chrome and Edge. Record the versions tested. Full tablet touch editing is post-MVP. Customizable docks and multi-monitor layouts are not required for MVP.

Design decisions: Q23-01 through Q23-03.
