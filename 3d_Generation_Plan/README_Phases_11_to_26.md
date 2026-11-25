# SWIFT Director | 3D Generation | Phases 11–26

MVP design baseline 1.0. All 16 phase specifications reflect the closed owner review. This package is a design handoff, not a software release, and includes no code changes or repository commits. Specific model versions, numeric PGX targets and integration test results are not established by this package.

[MVP Decision Register](SWIFT_Director_3D_Decision_Register.md) lists the resolved questions, including the superseded manual-landmark question, and the evidence still required before release.

## Source of truth

- [Goose Coop Term](https://chatgpt.com/c/6b05b469-5920-83ea-b780-7cc40dc67041) records the user decisions and phase sequence.
- [Original 26-phase roadmap](https://chatgpt.com/c/6b05b469-5920-83ea-b780-7cc40dc67041?messageId=5091248d-512c-4f5e-b4ab-ac064dcff2b5).
- [SWIFT Director approved phase files](https://github.com/Streamlined-Workflows/SWIFT_Director/tree/main/3d_Generation_Plan). Later approved decisions take precedence over early draft recommendations.

## Inherited design baseline

- Local-only MVP, independently runnable stages in Asset Generation > 3D Generation. Reference imagery is authored in sibling Reference Generation.
- Geometry is canonical FBX using right-handed Y-up, +Z forward and centimeters. A future runtime derivative is not a second canonical format. Geometric vertex count is the primary geometry budget target.
- New modular texture sets are independent per component. One common resolution per texture set (512, 1024, 2048, 4096). Canonical maps are PNG and tangent-space normals use Positive Y. Per-map overrides and Leave Unmapped are excluded. Shared/hybrid atlases, atlas optimization and UDIM are post-MVP.
- Default to Preserve Existing where surface data is present, flag affected UVs/maps, and never silently rebake. Confirmed defects are red where applicable. Repair is explicit and nondestructive.
- The foundation allows multiple queued jobs with one active AI inference job per generation server. Stage-specific execution guards disallow repeated or conflicting submissions in protected scopes, with one reviewable result per request.
- Generated candidates are Pending for 10 days from successful generation. Selection, lock, use, or export is not approval. Pending export requires confirmation and does not extend retention. Approval of required pending dependencies is explicit. Denial and expiry remove exclusive files, metadata, and history while protecting content still required by a valid retained artifact.

## Phase index

| Phase | Final design specification | Decisions closed |
|---|---|---:|
| 11 | [Material Extraction and Generation](3d_Phase_11.md) | 4 |
| 12 | [Direct Surface Painting and Masking](3d_Phase_12.md) | 4 |
| 13 | [Regional Texture Generation and Inpainting](3d_Phase_13.md) | 4 |
| 14 | [Character Preparation](3d_Phase_14.md) | 4 |
| 15 | [Character Landmark Mapping and CC5 Integration](3d_Phase_15.md) | 4 |
| 16 | [3D Viewport and Editing Controls](3d_Phase_16.md) | 4 |
| 17 | [Asset and Material Libraries](3d_Phase_17.md) | 4 |
| 18 | [Export and Interoperability](3d_Phase_18.md) | 5 |
| 19 | [Model Provider Architecture](3d_Phase_19.md) | 4 |
| 20 | [Hardware and Resource Management](3d_Phase_20.md) | 4 |
| 21 | [Generation Queue and Job Management](3d_Phase_21.md) | 4 |
| 22 | [Asset Versioning and Persistence](3d_Phase_22.md) | 4 |
| 23 | [User Interface and Workspace Design](3d_Phase_23.md) | 3 |
| 24 | [Security, Privacy and Licensing](3d_Phase_24.md) | 4 |
| 25 | [Model Evaluation and Validation Framework](3d_Phase_25.md) | 3 |
| 26 | [Development Roadmap and Acceptance Criteria](3d_Phase_26.md) | 4 |

**Total: 63 decisions closed, including one superseded.**

## Start here

- Phase 26 sets the build sequence, first demo and release gate.
- Phases 19–25 cover providers, PGX resources, queueing, storage, browser workspace, access and qualification.
- Phases 11–18 cover the production workflows and editable asset export and recovery.
