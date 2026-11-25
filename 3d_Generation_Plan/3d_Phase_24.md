# Phase 24: Security, Privacy and Licensing

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 24.1 Purpose and threat boundaries

Keep uploaded reference imagery, character packages, intermediate artifacts, prompts and logs local in MVP. Protect the host from unsafe imports or provider behavior, and verify commercial rights for finished outputs before enabling a provider, and verify separate permissions before bundling any third-party template. The ThinkStation PGX hosts the app. Access is restricted to the PGX itself and computers Jeremy authorizes through Tailscale. No public endpoint or general LAN access is in scope. Provisioning, inference and user-initiated exports are distinct operations. This phase does not authorize public deployment or any asset transfer.

| Boundary | Risks to control |
|---|---|
| Browser to Director | Unauthorized requests, cross-origin writes, wrong workspace access and stale approval |
| Director to providers | Provider egress, broad file access, unsafe plugins and leaked credentials |
| Import and conversion | Malformed FBX or PNG, oversized images or archives, unexpected paths or embedded files |
| Storage and logs | Unapproved artifact recovery, secrets, references exposing personal likeness and leftover scratch files |
| Export and distribution | Accidental inclusion of private sources, license incompatibility and redistribution of third-party assets |

## 24.2 Requirements and controls

| ID | Requirement |
|---|---|
| SEC-001 | Explicit, manually initiated setup downloads are allowed for selected providers, models and dependencies. Record exact versions and verify integrity. After provisioning, inference, conversion, validation, preview and normal storage can run on the PGX without internet access. Remote access may depend on Tailscale connectivity; inference may not. No automatic external fallback or asset upload. |
| SEC-002 | Restrict access to local PGX operation and Jeremy-authorized Tailscale computers. Deny unapproved devices, other LAN clients and public access. Provider workers remain inaccessible directly from browser clients. |
| SEC-003 | Validate server-side request authorization, input ownership, mutation scope and origin protections for the selected deployment profile. Enforce the same rules on API and UI flows. The design does not decide whether a separate app sign-in is required; implementation must still prove the approved access boundary. |
| SEC-004 | Treat imported files and provider results as untrusted. Check allowed formats, paths and size/complexity limits. Isolate parsers and reject malformed or excessive input cleanly without changing source files. |
| SEC-005 | Give workers access only to their declared inputs, model cache and scoped job workspace. Do not mount the entire asset library, browser credentials or host secrets by default. Restrict network access and clean job scratch data. |
| SEC-006 | Retain technical logs only, such as job state, timing, provider/version and sanitized fault codes. Exclude assets, references, images, prompt text, secrets and support bundles. Provider-supplied strings are untrusted display data and must not leak private input into diagnostics. No outbound project telemetry. |
| SEC-007 | Honor Phase 22 cleanup across scratch files, lost jobs, retained indexes and any app-managed backups. Do not promise forensic erasure or deletion of files a user previously exported. |
| SEC-008 | Track license and usage metadata for providers, model weights, dependencies and templates separately. Record source, version, permitted purpose, redistribution status, required notices and verification state. |
| SEC-009 | Require verified commercial use of finished outputs. General redistribution rights for the app, weights and templates are not an MVP eligibility requirement. Anything actually bundled still needs affirmative bundling rights, including the required Phase 15 template. Do not assume rights to vendor files, marks or landmark templates. |
| SEC-010 | Keep source reference imagery, prompt text and optional provenance out of deliverable packages unless selected and appropriate for the export profile. Warnings shall state what the package actually contains. |

The admin surfaces enabled deployment profile, provisioning state and license eligibility. The user can inspect included sources before export. Where Phase 15 handles identifiable reference images, preview and project checks shall make the source and owner responsibility visible without storing extra likeness copies solely for review.

## 24.3 Provider obligations and application responsibilities

Providers shall expose local runtime requirements, required resources and artifact outputs. Providers shall tolerate denied network access after provisioning, or be marked incompatible. The application controls authorization, filesystem isolation, package allowlists, offline checks and policy enforcement. Do not infer model rights from a repository's software license, infer third-party consent from an upload, or represent license flags as legal clearance.

Inputs: the deployment profile, approved provider provenance, import data, runtime capabilities, and export selections. Outputs: compatibility status, local policy decisions, bounded diagnostics, export notices and validation evidence. Where the design depends on legal interpretation, collect separately verified evidence before shipping rather than deciding in this specification.

## 24.4 Assertions and acceptance

| ID | Test and expected result |
|---|---|
| SEC-A01 | Run the MVP fixture path with network egress blocked after provisioning. Processing completes locally and no cloud fallback is attempted. |
| SEC-A02 | Verify the PGX and authorized Tailscale clients can connect. Unapproved Tailscale, other LAN and public clients cannot read or change data. |
| SEC-A03 | Import invalid, oversized or path-escaping test fixtures. The application rejects them with bounded errors and creates no files outside its job directory. |
| SEC-A04 | Select a provider with missing verification for the active distribution profile. It is not eligible and the missing evidence is named. |
| SEC-A05 | Inspect normal export and logs. The export excludes unselected private inputs and secrets. Logs are technical only, and there is no support-bundle workflow. |
| SEC-A06 | Deny a pending output, then reopen and reindex. No denied metadata or exclusive bytes reappear through app-managed storage. |

MVP acceptance requires a tested deployment policy, import isolation, runtime offline proof, verified provider eligibility for commercial use of finished outputs, and a documented removal boundary. Public hosting and automatic third-party publication are outside MVP. Security testing shall use defensive fixtures and report behavior without distributing exploit reproductions.

Design decisions: Q24-01 through Q24-04.
