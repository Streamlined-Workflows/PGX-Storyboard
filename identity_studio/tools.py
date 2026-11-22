"""What Identity Studio runs that the rest of SWIFT Director does not.

System status shows this list in its own section. Models the storyboard already lists (FLUX.2
[dev] and its turbo LoRA, which will draw concepts) are not repeated here.

Each entry reports honestly whether it is installed in the server's Python right now.
"""
import importlib.metadata
import importlib.util

CATALOG = [
    {"id": "vtracer", "name": "VTracer", "package": "vtracer", "kind": "tracing tool",
     "use": "Will trace an approved logo concept from pixels into an SVG, so it scales to any size "
            "for icons and print. Works best on flat marks with a few solid colours.",
     "needed_for": "the export step, which is not built yet",
     "note": "A small program (about 1 MB), not an AI model: it follows the edges of the shapes in a "
             "picture. It runs on the processor and does not use the GPU or the render queue."},
]

SHARED = "Concepts will be drawn with FLUX.2 [dev] and its turbo LoRA, which are listed under AI models above."


def status():
    out = []
    for item in CATALOG:
        entry = {k: item[k] for k in ("id", "name", "kind", "use", "needed_for", "note")}
        entry["installed"] = importlib.util.find_spec(item["package"]) is not None
        entry["version"] = ""
        if entry["installed"]:
            try:
                entry["version"] = importlib.metadata.version(item["package"])
            except importlib.metadata.PackageNotFoundError:
                pass
        out.append(entry)
    return {"tools": out, "shared": SHARED}
