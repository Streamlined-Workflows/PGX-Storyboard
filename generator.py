"""Asset Generator: making pictures outside the storyboard.

Two ways of working so far:
  image   one prompt and up to four reference pictures
  depth   a background, a middle ground and a foreground are made separately, one of each is chosen,
          and a fourth run redraws the three as one picture ("Composed Output")

Every reference picture carries how it is to be used, the same four choices as Identity Studio:
  insert         the picture itself is kept, pixel for pixel, and the rest is drawn around it (one per box)
  keep exactly   followed closely, but redrawn by the model
  style guide    its style is matched, not what it shows
  inspiration    a loose nudge
The last three each add one plain sentence to the prompt, which the page shows before anything is run.

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
SIZE = (1248, 720)                               # the size every picture here is made at
USES = ("insert", "keep exactly", "style guide", "inspiration")
USE_WORDS = {"insert": "Insert as it is", "keep exactly": "Follow closely (redrawn)", "style guide": "Style guide", "inspiration": "Inspiration"}
USE_HELP = {"insert": "Your picture itself is placed in the centre, untouched, and the rest is drawn around it.",
            "keep exactly": "The model copies this picture as closely as it can, but it redraws it and may change it.",
            "style guide": "The model matches this picture's style, not its content.",
            "inspiration": "A loose nudge only."}
# The sentence each use adds to the prompt. {n} is the picture's number as the image model sees it.
USE_TEXT = {"keep exactly": "Image {n}: reproduce what it shows faithfully, with the same shape, proportions and colours.",
            "style guide": "Image {n} is a style guide: match its visual style, colour treatment and lighting, not what it shows.",
            "inspiration": "Take loose inspiration from image {n}.",
            "insert": "One element is already in the centre of the picture and must stay exactly as it is. Draw the rest of the picture around it "
                      "so it belongs in the scene. Do not draw over it and do not repeat it."}

COMPOSE_PROMPT = ("Combine the reference images into one finished picture. "
                  "Use image 1 as the background: keep its setting, layout and lighting. "
                  "Place the subject of image 2 in the middle ground, keeping it exactly as shown. "
                  "Add the elements of image 3 in the foreground, closest to the camera. "
                  "Match the lighting, colour and style across all three so it reads as a single shot.")


def _refs(listed, limit, uses):
    """Reference pictures as [{"image", "use"}]. A bare name (how they were first stored) is taken as "keep exactly".
    Only one picture in a box can be inserted; any further one falls back to being followed closely."""
    out, inserted = [], False
    for r in listed if isinstance(listed, list) else []:
        r = {"image": r} if isinstance(r, str) else r if isinstance(r, dict) else {}
        image = r.get("image")
        if not isinstance(image, str) or not image.strip():
            continue
        use = r.get("use") if r.get("use") in uses else "keep exactly"
        if use == "insert":
            use, inserted = ("keep exactly" if inserted else "insert"), True
        out.append({"image": image[:300], "use": use})
    return out[:limit]


def _box(incoming, current, refs=MAX_REFS, uses=USES):
    incoming = incoming if isinstance(incoming, dict) else {}
    out = {"prompt": str(incoming.get("prompt", current.get("prompt", "")))[:MAX_PROMPT],
           "refs": _refs(incoming.get("refs", current.get("refs", [])), refs, uses),
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
    # One free slot: the fourth reference. It cannot be inserted, because images 1 to 3 are fixed as the three layers.
    composed = _box(incoming.get("composed"), dict({"prompt": COMPOSE_PROMPT}, **was), refs=1, uses=USES[1:])
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
            "compose_prompt": COMPOSE_PROMPT, "limits": {"refs": MAX_REFS, "count": MAX_COUNT}, "size": list(SIZE),
            "uses": [{"id": u, "name": USE_WORDS[u], "help": USE_HELP[u], "adds": USE_TEXT[u]} for u in USES]}


def plan(project, box):
    """What to queue for one box. Raises ValueError with the reason if it cannot run.
    -> {"prompt": what the image model is sent, "refs": the pictures sent as images 1, 2, ... in order,
        "insert": the picture to keep unchanged or None, "count": how many to make}"""
    if box not in BOXES:
        raise ValueError("Unknown part of the Asset Generator.")
    state = view(project)["state"]
    b = state[box]
    typed = b["prompt"].strip()
    if not typed:
        raise ValueError("Write a prompt first.")
    fixed = []
    if box == "composed":
        missing = [TITLES[layer].lower() for layer in LAYERS if not b["applied"][layer]]
        if missing:
            raise ValueError("Apply a picture to the composed output for: " + ", ".join(missing) + ".")
        fixed = [b["applied"][layer] for layer in LAYERS]                # always image 1, 2, 3 in this order; the free slot is image 4
    insert = next((r["image"] for r in b["refs"] if r["use"] == "insert"), None)
    drawn = [r for r in b["refs"] if r["use"] != "insert"]
    if insert:
        drawn = drawn[:3]                                                # the kept picture takes one of the four places
    added = ([USE_TEXT["insert"]] if insert else []) + [USE_TEXT[r["use"]].format(n=len(fixed) + n) for n, r in enumerate(drawn, 1)]
    return {"prompt": " ".join([typed.rstrip()] + added), "refs": fixed + [r["image"] for r in drawn], "insert": insert, "count": b["count"]}


def apply(project, layer, image):
    """Choose one of a layer's pictures for the composed output. -> the new stored state."""
    if layer not in LAYERS:
        raise ValueError("Only the background, middle ground and foreground can be applied.")
    if image not in [r["image"] for r in results(project, layer)]:
        raise ValueError("That picture is no longer there.")
    state = clean(project.get("generator"))
    state["composed"]["applied"][layer] = image
    return state
