# Phase 12: Direct Surface Painting and Masking

SWIFT Director | Asset Generation > 3D Generation | MVP design baseline 1.0

Implementation and qualification evidence pending.

## 12.1 Purpose and phase boundary

Paint on visible 3D surfaces and author masks for local texture edits, material inspection, and regional generation. The viewport is an editing surface, while renderable image data remains governed by Phase 10 and geometry remains unchanged. Painting is manual. Phase 13 consumes a frozen mask for explicitly requested generation. Phase 07 regional density priority remains post-MVP. Providing a mask for another phase does not enable an operation that phase has deferred.

Runtime work executes locally. Component texture sets remain independent and a map edit inherits the common set resolution. PNG remains canonical, with declared color spaces and Positive Y normal convention for normal maps. Locked source maps and protected source artifacts cannot be rewritten. MVP direct painting covers Base Color, Roughness, Metallic, Emissive, and Opacity. Masking remains available for compatible maps, including maps outside the direct-paint list. Phase 10 generation retains all eight map types. No brush, rasterization, or AI provider is selected here.

## 12.2 Artifact and coordinate model

| Record | Contents | Validation rule |
|---|---|---|
| Paint session | Asset/component ID, geometry and UV revisions, target texture set/map, dependent materials, transient brush state | No destructive write occurs during session preview. A changed binding is a conflict, not a retarget. |
| Editable paint layer stack | Ordered layer records, editable layer data, saved settings, and pinned source and binding revisions | Reopen as editable layers with the correct order and composite. The original source map and reusable masks remain separate artifacts. |
| Paint result | Canonical flattened derivative map with provenance, edit domain, source ID, and applicable UV association | Dimensions, precision, and channel semantics match the target set. Layered authoring data does not replace the canonical PNG output. |
| Surface mask | Selection weights, valid domain/coverage, target component and revisions, UV channel where applicable, mask provenance | Weight 0 protects a texel or selected surface. Weight 1 is fully selected. Soft weights apply only within explicitly selected coverage. |
| Consumer projection | Resolved UV mask or revision-specific surface selection for a requested consumer | Every projection cites its source mask and selection basis. Shared texels, seams, and overlap are surfaced before use. |
| UV mask transfer candidate | Original mask and source/target binding revisions, target mask, coverage and conflict report | Explicitly accepted or discarded after preview. Source and any existing target masks are unchanged unless separately replaced by user action. |

Screen-space pointing is temporary. Saved masks must be bound to a stable surface representation or an explicit target UV revision, not the camera angle that produced them. Disabled or missing UV layouts block texture writes. 3D review remains possible. A mask shared across operations is not automatically a compatible mask for a different asset revision. A stale UV mask is inspectable but cannot become a live input after a UV change without the explicit transfer workflow.

## 12.3 Workflow and controls

1. Select the asset, component, slot or map, and UV channel if applicable. Inspect intentional mirrored or repeated UV use and choose the approved target binding.
2. Choose Paint or Mask mode. Configure brush size with a clear unit, opacity, hardness, brush value or channel, and add/erase behavior. Mark protected surfaces separately where supported.
3. Point into the 3D View or use a synchronized Split View for UV inspection. Choose freehand viewport lasso, component or material-slot fill, invert, or brush selection as appropriate. Preview covered surface, seam continuity, and reflected or repeated UV effects before saving.
4. Work within the selected component and view constraints. A brush does not affect an occluded backside by default. Phase 16 opt-in through-selection previews affected hidden surfaces before applying a selection. It does not implicitly turn a brush stroke into a hidden-surface write. Review with unlit map inspection, a mask-only overlay, and lit surface context.
5. Undo or redo eligible edits within the work session. Save editable paint layers and the canonical flattened painted map as separate but linked data. Save reusable masks separately. Reopening restores layers without restoring temporary viewport framing, tool selection, or session undo history. The original map remains available.
6. If the UV layout changes, select a stale mask and explicitly request transfer to the compatible target UV revision. Inspect source, transferred result, and omissions or overlaps. Accept the new mask or discard it, preserving the original. The Phase 13 handoff passes a frozen accepted mask revision and never starts generation automatically.

## 12.4 Functional requirements

| ID | Requirement |
|---|---|
| SPM-001 | Support 3D surface painting, mask painting and erase, with a default visible-surface raycast and an explicit component/slot scope. |
| SPM-002 | Expose brush radius, strength, edge hardness, and add/erase modes. Display live brush coverage and current scope before the stroke commits. |
| SPM-003 | Support reviewable surface or UV selections, a freehand viewport lasso, fill by component or material slot, mask invert, clear, and save. Combine masks only when they share or can safely map to a validated target. Show resulting coverage before use. |
| SPM-004 | Preserve existing geometry, UVs, maps, and unrelated components. A saved map is a separate canonical artifact. No texture-set resize occurs without explicit Phase 10 action. |
| SPM-005 | Report UV overlap and material boundaries before applying affected strokes. If protected and editable faces reference the same texel, block the paint write or require an explicit compatible shared-texel decision. Do not silently duplicate or re-unwrap geometry. |
| SPM-006 | For seam crossings, paint may span both islands where the sampled surface is continuous and permitted. UV padding writes must be identified as padding, must not overwrite other islands, and must be explicitly requested or captured in the reviewed operation scope. |
| SPM-007 | Prevent edits to locked target maps. Preview a proposed independent derivative only after the user explicitly chooses that path. A lock is not bypassed by silently changing the assignment. |
| SPM-008 | Flag a mask stale when geometry or UV revisions change. For a compatible changed UV layout, support explicit mask transfer with side-by-side or overlay preview and Accept or Discard. Report lost or ambiguous coverage. Bind the accepted derivative to the target revision and preserve the original. Block unsupported geometry changes and never transfer automatically. |
| SPM-009 | Provide 3D and Split View only, with synchronized selection and distinct colors for selected, protected, affected, and confirmed defective areas. Confirmed defects display red and never trigger automatic repair. |
| SPM-010 | Save and discard are explicit. Persist pending artifacts under the approved ten-day lifecycle. Explicit approval and dependency confirmation govern retention. Brush undo is not persistent artifact version history. |
| SPM-011 | Allow a mask to be reviewed and handed off without editing any map. Manual brush actions are not AI generation requests. Phase 21 owns server scheduling, and the applicable workflow prevents repeat or conflicting generation submissions while active. |
| SPM-012 | Persist editable layers across sessions alongside the canonical painted result. Reopen their ordering and editable state and verify that compositing reproduces the saved painted map. Store source maps and reusable masks independently. |
| SPM-013 | Permit direct painting only for Base Color, Roughness, Metallic, Emissive, and Opacity. Use correct color and data semantics per map. Do not disable masking for another compatible map merely because direct painting is unavailable. |

## 12.5 Provider constraints and application responsibilities

No AI provider is required for core painting or masks. A supported local surface processing adapter must accept revision-specific surface or UV data, declare precision and supported channels, and return deterministic, bounded output for the requested brush operation or projection. It must not write outside its scope, implicitly normalize a protected source, or move geometry. Future assisted selections must first produce masks for inspection, never immediately commit edits.

The application owns selection hit testing and visibility rules, render overlays, authoritative revision checks, mask-domain and texel overlap policies, local mask transfer and its compatibility checks, color and data-map conversion, layer and compositor state, undo transactions, immutable storage, and approval. It measures edited coverage independently of a processor. It checks canonical pixels or samples, rather than relying on byte-identical PNG compression to prove semantic equality.

## 12.6 Validation assertions and acceptance

| ID | Test | Pass condition |
|---|---|---|
| SPA-001 | Brush across visible and occluded surfaces on a two-layer shell | Only visible selected surface weights or pixels change with default controls. |
| SPA-002 | Paint a seam across two UV islands without intentional overlap | Both eligible sides update. Protected neighboring islands and unselected effective pixels remain unchanged. |
| SPA-003 | Paint where editable and protected faces share a texel | Conflicting coverage is identified before commit. No protected surface is silently changed. |
| SPA-004 | Save a mask, change component or UV revision, reopen | The old mask remains inspectable and stale. No automatic remap occurs. Transfer to a compatible UV revision previews the result and reports uncovered or ambiguous faces. Accept stores a new revision and preserves the old mask, and Discard leaves all saved masks unchanged. |
| SPA-005 | Paint, undo, redo, then discard | Undo restores pre-stroke state, redo restores the stroke, discard leaves published assignment and source hashes untouched. |
| SPA-006 | Apply a channel edit to a 2048 set | Output remains at 2048 and preserves unrelated channels or separately locked maps. Source component and mesh checksums match. |
| SPA-007 | Send a mask to Phase 13 without starting a job | Consumer receives immutable mask and revision references and opens a review state. No generation or approval is triggered. |
| SPA-008 | Save distinct layers and a reusable mask, close, and reopen | All layers are editable and recomposition matches the saved PNG pixels. Source and mask checksums remain unchanged and session undo is not restored. |
| SPA-009 | Lasso a partially occluded component, fill its material slot, and invert | Coverage matches the reviewed scope. Hidden faces are excluded by default and changes remain inspectable before apply. |
| SPA-010 | Attempt direct painting on each of eight Phase 10 maps | The five approved maps accept painting. Normal, Height, and Ambient Occlusion remain maskable when compatible, with direct painting unavailable. |

Phase 12 passes when an operator can intentionally paint and mask a distinct component from the 3D view, inspect seam and overlap effects, reopen and edit saved paint layers, explicitly transfer a mask after compatible UV change, and hand off a stable mask for Phase 13 with unedited source artifacts intact.

## 12.7 MVP boundary and decision trace

**Decisions applied:** Q12-01 five directly paintable maps, Q12-02 persistent editable layers with separate output and masks, Q12-03 freehand viewport lasso plus core selection tools, Q12-04 explicit reviewed UV mask transfer.
