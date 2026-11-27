# 3D Generation: what could make the geometry (options, not decisions)

Gate C of `3d_Generation_Plan/3d_Phase_26.md` needs something that makes and changes geometry. The plan approves no
provider, and decision Q19-04 says a provider must pass a real test on the PGX before Auto may choose it. This note
lists what looked workable on 27 November 2026 so that choice is quicker. Nothing here has been installed, downloaded
or tried on the PGX. Check every licence yourself before relying on it; this is not legal advice.

## The short version

| Job | Most promising | Why | Open questions |
| --- | --- | --- | --- |
| Geometry from a picture | **TRELLIS.2** (Microsoft, MIT) through ComfyUI | ComfyUI says it now runs it natively with no custom nodes and no compiled CUDA extensions, which is what usually breaks on the PGX's ARM64 chip. SWIFT Director already talks to ComfyUI. | Does your ComfyUI version have it? How long does a run take on the GB10? It takes one picture, not four views. |
| Same, stricter match to the picture | **Pixal3D** (MIT per reports) through the same ComfyUI workflow | Same workflow, switched by one toggle | As above |
| Geometry from several views | **Hunyuan3D 2.0 MV / 2.1** (Tencent) | People report it running on the DGX Spark, which is the same GB10 hardware; it accepts multiple views, which fits the reference sheets | Tencent's community licence, which reports say does not apply in the EU, UK or South Korea. A US user appears to be inside it, but read it. One report says the ComfyUI multi-view workflow gave meshes without textures. |
| Splitting into parts | Hunyuan3D-Part | Open weights for part segmentation | Same Tencent licence family. NVIDIA's PartPacker is non-commercial, so it is out. |
| Remeshing | AutoRemesher | One team reports using it on a DGX Spark | It needed a patch for ARM64 |
| **GLB to FBX** | **Decided 27 Nov 2026: Blender, run without a window** | Every model above writes GLB, and the studio's canonical file is FBX | Built as `convert-service/`. Not yet run on the PGX. |

## Things to know before choosing

- **Background removal is a licence trap.** The official TRELLIS.2 and Pixal3D pipelines call a background remover
  (Bria RMBG) that is non-commercial. ComfyUI's own integration says it has no non-commercial dependencies. If a
  provider is wired in any other way, the background step has to be checked separately.
- **The best results are still from hosted services** (Hunyuan 3D 3.x, Tripo, Rodin), which the plan rules out: local only.
- **These models make triangle soup at high counts.** The plan's budgets (5,000 / 20,000 / 100,000 control points) will
  need the optimisation step as well; generation alone will not hit them.
- **None of them writes FBX, a skeleton or UVs you would keep.** Phases 7 to 11 are separate tools.

## What I would do next, if you agree

1. On the PGX, check whether the installed ComfyUI lists the TRELLIS.2 nodes. If it does, download the weights by hand
   (the plan forbids silent downloads) and run ComfyUI's own image-to-model workflow once on a reference picture.
2. If that produces a usable mesh, I add a provider that queues that workflow, exactly as images are queued today, and
   brings the GLB back as a pending candidate. That needs a decision on GLB to FBX first.
3. Try Hunyuan3D multi-view the same way only if single-picture results are not good enough for characters.

## Sources

- ComfyUI, "Trellis2 and Pixal3D are now native": https://blog.comfy.org/p/trellis2-and-pixal3d-are-now-native
- NVIDIA developer forum, "DGX Spark + Hunyuan3d 2.1": https://forums.developer.nvidia.com/t/dgx-spark-hunyuan3d-2-1/353211
- NVIDIA developer forum, 3D character pipeline on DGX Spark (AutoRemesher ARM64 patch): https://forums.developer.nvidia.com/t/super-idol-master-multi-agent-driven-3d-character-asset-pipeline-on-dgx-spark/377760
- Creative AI News, licences of open 3D models and the background-remover caveat: https://www.creativeainews.com/articles/best-open-source-ai-3d-models-2026/
- Cinevva, dated list of releases and licences: https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026
