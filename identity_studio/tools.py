"""What Identity Studio runs that the rest of SWIFT Director does not.

System status shows this list in its own section. Models the storyboard already lists (FLUX.2
[dev] and its turbo LoRA, which will draw concepts) are not repeated here.

Each entry reports honestly whether it is installed in the server's Python right now.
"""
import os

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "identity")

CATALOG = [
    {"id": "imagetracer", "name": "ImageTracer", "file": os.path.join("vendor", "imagetracer_v1.2.6.js"), "version": "1.2.6", "kind": "tracing tool",
     "use": "Traces a logo concept from pixels into an SVG when you tick SVG in a concept's Download box, so it scales "
            "to any size for icons and print. Works best on flat marks with a few solid colours.",
     "needed_for": "SVG downloads",
     "note": "A small program (about 47 KB), not an AI model: it follows the edges of the shapes in a picture. It is part of "
             "SWIFT Director and runs in your browser, so it uses no server memory, no GPU and no place in the render queue."},
]

SHARED = "Concepts are drawn with FLUX.2 [dev] and its turbo LoRA, which are listed under AI models above."


def status():
    out = []
    for item in CATALOG:
        entry = {k: item[k] for k in ("id", "name", "kind", "use", "needed_for", "note", "version")}
        entry["installed"] = os.path.isfile(os.path.join(STATIC, item["file"]))
        out.append(entry)
    return {"tools": out, "shared": SHARED}
