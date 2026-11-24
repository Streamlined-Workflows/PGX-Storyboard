"""Asset Generator: making pictures outside the storyboard.

Two ways of working so far:
  image   one prompt and up to four reference pictures
  depth   a background, a middle ground and a foreground are made separately, one of each is chosen,
          and a fourth run redraws the three as one picture ("Composed Output")

What is kept for a project (project["generator"]) is only what the person typed and chose: each box's
prompt, reference pictures and how many to make; which picture is showing; and which three pictures are
applied to the composed output. The pictures themselves are ordinary generated stills: finished ones
are in project["generated"] and unfinished ones in project["image_jobs"], each marked kind "gen" with
the box it belongs to. This module only reads those lists; app.py does the queueing.
"""

LAYERS = ("background", "middle", "foreground")
BOXES = ("image",) + LAYERS + ("composed",)
TITLES = {"image": "Image", "background": "Background", "middle": "Middle ground", "foreground": "Foreground", "composed": "Composed output"}
MAX_PROMPT, MAX_REFS, MAX_COUNT = 3000, 4, 10

COMPOSE_PROMPT = ("Combine the reference images into one finished picture. "
                  "Use image 1 as the background: keep its setting, layout and lighting. "
                  "Place the subject of image 2 in the middle ground, keeping it exactly as shown. "
                  "Add the elements of image 3 in the foreground, closest to the camera. "
                  "Match the lighting, colour and style across all three so it reads as a single shot.")


def _box(incoming, current, refs=MAX_REFS):
    incoming = incoming if isinstance(incoming, dict) else {}
    out = {"prompt": str(incoming.get("prompt", current.get("prompt", "")))[:MAX_PROMPT],
           "refs": [str(r)[:300] for r in incoming.get("refs", current.get("refs", [])) if isinstance(r, str) and r.strip()][:refs],
           "at": incoming.get("at", current.get("at")) if isinstance(incoming.get("at", current.get("at")), str) else None}
    try:
        out["count"] = max(1, min(MAX_COUNT, int(incoming.get("count", current.get("count", 1)))))
    except (TypeError, ValueError):
        out["count"] = current.get("count", 1)
    return out


def clean(incoming, current=None):
    """What the browser sent, limited to what may be stored. Anything missing keeps its stored value."""
    incoming = incoming if isinstance(incoming, dict) else {}
    current = current if isinstance(current, dict) else {}
    out = {name: _box(incoming.get(name), current.get(name) or {}) for name in ("image",) + LAYERS}
    was = current.get("composed") or {}
    composed = _box(incoming.get("composed"), dict({"prompt": COMPOSE_PROMPT}, **was), refs=1)      # one free slot: the fourth reference
    applied = (incoming.get("composed") or {}).get("applied") if isinstance(incoming.get("composed"), dict) else None
    applied = applied if isinstance(applied, dict) else was.get("applied") or {}
    composed["applied"] = {layer: applied.get(layer) if isinstance(applied.get(layer), str) and applied.get(layer) else None for layer in LAYERS}
    out["composed"] = composed
    return out


def results(project, box):
    """The finished pictures of one box, oldest first."""
    return sorted(({"id": g["id"], "image": g["image"], "created": g.get("created") or 0}
                   for g in project.get("generated", []) if g.get("kind") == "gen" and g.get("slot") == box and g.get("image")),
                  key=lambda g: g["created"])


def jobs(project, box):
    return [{"id": j["id"], "status": j.get("status"), "error": j.get("error", "")}
            for j in project.get("image_jobs", []) if j.get("kind") == "gen" and j.get("slot") == box and j.get("status") != "done"]


def view(project):
    """Everything the page needs to draw the Asset Generator."""
    state = clean(project.get("generator"))
    for layer in LAYERS:                                 # a picture that was removed can no longer be the applied one
        if state["composed"]["applied"][layer] not in [r["image"] for r in results(project, layer)]:
            state["composed"]["applied"][layer] = None
    return {"state": state, "boxes": {b: {"results": results(project, b), "jobs": jobs(project, b)} for b in BOXES},
            "compose_prompt": COMPOSE_PROMPT, "limits": {"refs": MAX_REFS, "count": MAX_COUNT}}


def plan(project, box):
    """What to queue for one box: (prompt, reference pictures, how many). Raises ValueError with the reason if it cannot run."""
    if box not in BOXES:
        raise ValueError("Unknown part of the Asset Generator.")
    state = view(project)["state"]
    b = state[box]
    prompt = b["prompt"].strip()
    if not prompt:
        raise ValueError("Write a prompt first.")
    refs = list(b["refs"])
    if box == "composed":
        missing = [TITLES[layer].lower() for layer in LAYERS if not b["applied"][layer]]
        if missing:
            raise ValueError("Apply a picture to the composed output for: " + ", ".join(missing) + ".")
        refs = [b["applied"][layer] for layer in LAYERS] + refs[:1]      # always image 1, 2, 3 in this order; the free slot is image 4
    return prompt, refs, b["count"]


def apply(project, layer, image):
    """Choose one of a layer's pictures for the composed output. -> the new stored state."""
    if layer not in LAYERS:
        raise ValueError("Only the background, middle ground and foreground can be applied.")
    if image not in [r["image"] for r in results(project, layer)]:
        raise ValueError("That picture is no longer there.")
    state = clean(project.get("generator"))
    state["composed"]["applied"][layer] = image
    return state
