"""Asset Generator: making pictures outside the storyboard.

Two ways of working so far:
  image   one prompt and up to four reference pictures
  depth   a background, a middle ground and a foreground are made separately, one of each is chosen,
          and a fourth run redraws the three as one picture ("Composed Output")

Every reference picture carries how it is to be used:
  insert         the picture itself is kept, pixel for pixel, and the rest is drawn around it (one per box)
  keep exactly   the picture is sent to the image model, which follows it closely but redraws it
  style guide    the picture is NOT sent. The language model describes its look in words (Apply), and those words go
                 at the start of the prompt
  inspiration    the picture is NOT sent. The language model describes its general idea in words (Apply), likewise
An attached picture outweighs any sentence about it, so "match the style only" cannot be asked for while the picture
is attached: the image model copies it. Describing it in words is what makes the last two different from the second.

Each reference has a number from 1 to 4 that it keeps for as long as it is there, and a colour that goes with the
number. Words a reference added to the prompt are remembered as ranges of the prompt (`marks`), so the page can show
them in that reference's colour; anything the person types or changes is outside those ranges.

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
import workflows

PROMPT_LIMIT = workflows.PROMPT_LIMITS["image"]         # what the count beside each prompt box is measured against
SIZE = (1248, 720)                               # the size every picture here is made at
USES = ("insert", "keep exactly", "style guide", "inspiration")
USE_WORDS = {"insert": "Insert as it is", "keep exactly": "Follow closely (redrawn)", "style guide": "Style guide", "inspiration": "Inspiration"}
USE_HELP = {"insert": "Your picture itself is placed in the centre, untouched, and the rest is drawn around it.",
            "keep exactly": "The picture is sent to the image model, which copies it as closely as it can but redraws it.",
            "style guide": "The picture is not sent to the image model. Apply has the language model describe its look only, in up to 300 characters, and puts that at the start of your prompt.",
            "inspiration": "The picture is not sent to the image model. Apply has the language model describe its general idea, in up to 300 characters, and puts that at the start of your prompt."}
DESCRIBED = ("style guide", "inspiration")           # used as words in the prompt, never attached
TEXT_LIMIT = 300
MAX_MARKS = 200
# The sentence a use adds after the prompt. {n} is the picture's number as the image model sees it.
USE_TEXT = {"keep exactly": "Image {n}: reproduce what it shows faithfully, with the same shape, proportions and colours.",
            "insert": "One element is already in the centre of the picture and must stay exactly as it is. Draw the rest of the picture around it "
                      "so it belongs in the scene. Do not draw over it and do not repeat it."}

# ---- Asset Configuration: one per generator mode, shown in the box at the top of that mode ----
MODES = ("image", "character", "depth", "3d")
RATINGS = ("E", "PG-13", "R", "M", "X")          # the same list as the project's own rating, so one filtering rule can cover both later
TYPES = (("actor", "Actor"), ("scene", "Scene"), ("prop", "Prop"), ("world", "World"))
MODE_TYPE = {"image": "scene", "character": "actor", "depth": "scene", "3d": "prop"}       # what each mode starts as
MODEL_ROLES = (("prompting", "Prompting Model"), ("image", "Image Model"), ("image_lora", "Image Model LoRA"),
               ("background_removal", "Background Removal Model"), ("upscale", "Upscale Model"))
WORKFLOW = (("confirm_before_run", "Ask me before running generations", False),
            ("approve_before_save", "Only pictures I approve can be saved to Assets", False),
            ("keep_alternatives", "Keep the other pictures when one is saved", True),
            ("keep_history", "Keep each picture's prompt with it", True),
            ("auto_model_recommendations", "Allow automatic model recommendations", True))
# The settings that change what the Asset Generator does today. Everything else is stored for the update that will act on it.
USED = ("name", "type", "workflow.confirm_before_run", "workflow.approve_before_save")
MAX_APPROVED = 2000


def _config(incoming, current, mode, rating):
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda key, fallback: incoming.get(key, current.get(key, fallback))
    out = {"name": str(get("name", "") or "").strip()[:80],
           "rating": get("rating", rating) if get("rating", rating) in RATINGS else (rating if rating in RATINGS else "PG-13"),
           "type": get("type", MODE_TYPE[mode]) if get("type", MODE_TYPE[mode]) in [k for k, _ in TYPES] else MODE_TYPE[mode]}
    was, now = current.get("models") or {}, incoming.get("models") if isinstance(incoming.get("models"), dict) else {}
    out["models"] = {}
    for role, _ in MODEL_ROLES:                              # "auto", or "<where it runs>:<which one>" once there is more than one to choose from
        value = now.get(role, was.get(role, "auto"))
        out["models"][role] = value if value == "auto" or (isinstance(value, str) and ":" in value and len(value) <= 200) else "auto"
    was, now = current.get("workflow") or {}, incoming.get("workflow") if isinstance(incoming.get("workflow"), dict) else {}
    out["workflow"] = {key: now[key] if isinstance(now.get(key), bool) else was[key] if isinstance(was.get(key), bool) else default for key, _, default in WORKFLOW}
    return out


COMPOSE_PROMPT = ("Combine the reference images into one finished picture. "
                  "Use image 1 as the background: keep its setting, layout and lighting. "
                  "Place the subject of image 2 in the middle ground, keeping it exactly as shown. "
                  "Add the elements of image 3 in the foreground, closest to the camera. "
                  "Match the lighting, colour and style across all three so it reads as a single shot.")


def _refs(listed, limit, uses, fixed=None):
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
        # `text` is what the language model wrote for it, kept so it can be shown under the picture. Only described uses have one.
        text = str(r.get("text") or "")[:TEXT_LIMIT] if use in DESCRIBED and isinstance(r.get("text"), str) else ""
        out.append({"image": image[:300], "use": use, "slot": r.get("slot"), "text": text})
    out = out[:limit]
    numbers = [fixed] if fixed else list(range(1, MAX_REFS + 1))
    taken = set()
    for r in out:                                            # a number is kept if it is valid and free; otherwise the lowest free one
        if r["slot"] in numbers and r["slot"] not in taken and not isinstance(r["slot"], bool):
            taken.add(r["slot"])
        else:
            r["slot"] = None
    for r in out:
        if r["slot"] is None:
            r["slot"] = next(n for n in numbers if n not in taken)
            taken.add(r["slot"])
    return out


def _marks(listed, length):
    """Ranges of the prompt that a reference's description put there: [[start, end, reference number], ...], in order,
    inside the prompt and not overlapping. Anything else is dropped."""
    out, last = [], 0
    for m in sorted((m for m in listed if isinstance(m, (list, tuple)) and len(m) == 3 and all(isinstance(v, int) and not isinstance(v, bool) for v in m)),
                    key=lambda m: m[0]) if isinstance(listed, list) else []:
        start, end, slot = m
        if last <= start < end <= length and 1 <= slot <= MAX_REFS:
            out.append([start, end, slot])
            last = end
    return out[:MAX_MARKS]


def _box(incoming, current, refs=MAX_REFS, uses=USES, fixed=None):
    incoming = incoming if isinstance(incoming, dict) else {}
    out = {"prompt": str(incoming.get("prompt", current.get("prompt", "")))[:MAX_PROMPT],
           "refs": _refs(incoming.get("refs", current.get("refs", [])), refs, uses, fixed),
           "at": incoming.get("at", current.get("at")) if isinstance(incoming.get("at", current.get("at")), str) else None}
    # Marks describe the prompt they came with. A prompt sent without marks has none; a save that leaves the prompt out keeps both.
    out["marks"] = _marks(incoming.get("marks") if "prompt" in incoming else current.get("marks"), len(out["prompt"]))
    try:
        out["count"] = max(1, min(MAX_COUNT, int(incoming.get("count", current.get("count", 1)))))
    except (TypeError, ValueError):
        out["count"] = current.get("count", 1)
    return out


def clean(incoming, current=None, rating="PG-13"):
    """What the browser sent, limited to what may be stored. Anything missing keeps its stored value.
    `rating` is the project's own rating, which a mode's asset configuration starts from."""
    incoming = incoming if isinstance(incoming, dict) else {}
    current = current if isinstance(current, dict) else {}
    out = {name: _box(incoming.get(name), current.get(name) or {}) for name in ("image",) + LAYERS}
    was = current.get("composed") or {}
    # One free slot: the fourth reference. It cannot be inserted, because images 1 to 3 are fixed as the three layers.
    composed = _box(incoming.get("composed"), dict({"prompt": COMPOSE_PROMPT}, **was), refs=1, uses=USES[1:], fixed=MAX_REFS)
    applied = (incoming.get("composed") or {}).get("applied") if isinstance(incoming.get("composed"), dict) else None
    applied = applied if isinstance(applied, dict) else was.get("applied") or {}
    composed["applied"] = {layer: applied.get(layer) if isinstance(applied.get(layer), str) and applied.get(layer) else None for layer in LAYERS}
    out["composed"] = composed
    given, kept = incoming.get("config") if isinstance(incoming.get("config"), dict) else {}, current.get("config") if isinstance(current.get("config"), dict) else {}
    out["config"] = {mode: _config(given.get(mode), kept.get(mode) or {}, mode, rating) for mode in MODES}
    approved = incoming.get("approved") if isinstance(incoming.get("approved"), list) else current.get("approved") or []
    out["approved"] = list(dict.fromkeys(a for a in approved if isinstance(a, str) and a))[-MAX_APPROVED:]
    return out


def results(project, box):
    """The finished pictures of one box, oldest first."""
    return sorted(({"id": g["id"], "image": g["image"], "created": g.get("created") or 0}
                   for g in project.get("generated", []) if g.get("kind") == "gen" and g.get("slot") == box and g.get("image")),
                  key=lambda g: g["created"])


def jobs(project, box):
    return [{"id": j["id"], "status": j.get("status"), "error": j.get("error", "")}
            for j in project.get("image_jobs", []) if j.get("kind") == "gen" and j.get("slot") == box and j.get("status") != "done"]


def view(project, in_use=None):
    """Everything the page needs to draw the Asset Generator. `in_use` says what performs each model role today."""
    state = clean(project.get("generator"))
    made = {g["id"] for g in project.get("generated", []) if g.get("kind") == "gen"}
    state["approved"] = [a for a in state["approved"] if a in made]      # a picture that was removed is no longer approved
    for layer in LAYERS:                                 # a picture that was removed can no longer be the applied one
        if state["composed"]["applied"][layer] not in [r["image"] for r in results(project, layer)]:
            state["composed"]["applied"][layer] = None
    return {"state": state, "boxes": {b: {"results": results(project, b), "jobs": jobs(project, b)} for b in BOXES},
            "options": {"ratings": list(RATINGS), "types": [{"key": k, "label": l} for k, l in TYPES], "roles": [{"key": k, "label": l} for k, l in MODEL_ROLES],
                        "workflow": [{"key": k, "label": l} for k, l, _ in WORKFLOW], "used": list(USED), "in_use": in_use or {}},
            "compose_prompt": COMPOSE_PROMPT, "limits": {"refs": MAX_REFS, "count": MAX_COUNT}, "prompt_limit": dict(PROMPT_LIMIT), "size": list(SIZE),
            "uses": [{"id": u, "name": USE_WORDS[u], "help": USE_HELP[u], "adds": USE_TEXT.get(u, ""), "described": u in DESCRIBED} for u in USES],
            "text_limit": TEXT_LIMIT}


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
    drawn = [r for r in b["refs"] if r["use"] == "keep exactly"]         # a style guide or inspiration is words in the prompt, never attached
    if insert:
        drawn = drawn[:3]                                                # the kept picture takes one of the four places
    added = ([USE_TEXT["insert"]] if insert else []) + [USE_TEXT[r["use"]].format(n=len(fixed) + n) for n, r in enumerate(drawn, 1)]
    return {"prompt": " ".join([typed.rstrip()] + added), "refs": fixed + [r["image"] for r in drawn], "insert": insert, "count": b["count"]}


MODE_BOXES = {"image": ("image",), "depth": LAYERS + ("composed",), "character": (), "3d": ()}


def reset(project, mode, rating="PG-13"):
    """Put one generator mode back to how a new project has it: empty prompts, no references, one generation, nothing
    applied, and its Asset Configuration at the defaults. Changes `project` in place.

    The pictures it made are not deleted. They leave the mode's boxes but stay in the project's Library, where
    "Apply from Library" can still reach them. Refused while that mode is still generating, so no picture arrives in a box
    that was just emptied."""
    if mode not in MODES:
        raise ValueError("Unknown part of the Asset Generator.")
    boxes = MODE_BOXES[mode]
    if any(j.get("status") in ("queued", "running") for b in boxes for j in project.get("image_jobs", []) if j.get("kind") == "gen" and j.get("slot") == b):
        raise ValueError("Pictures are still being generated here. Reset when they have finished.")
    state, fresh = clean(project.get("generator")), clean(None, None, rating)
    for b in boxes:
        state[b] = fresh[b]
    state["config"][mode] = fresh["config"][mode]
    gone = {g["id"] for g in project.get("generated", []) if g.get("kind") == "gen" and g.get("slot") in boxes}
    for g in project.get("generated", []):
        if g["id"] in gone:
            g["slot"] = None                                     # no longer in a box; still a picture of this project
    state["approved"] = [a for a in state["approved"] if a not in gone]
    project["image_jobs"] = [j for j in project.get("image_jobs", []) if not (j.get("kind") == "gen" and j.get("slot") in boxes)]
    project["generator"] = state
    return len(gone)


def apply(project, layer, image):
    """Choose one of a layer's pictures for the composed output. -> the new stored state."""
    if layer not in LAYERS:
        raise ValueError("Only the background, middle ground and foreground can be applied.")
    if image not in [r["image"] for r in results(project, layer)]:
        raise ValueError("That picture is no longer there.")
    state = clean(project.get("generator"))
    state["composed"]["applied"][layer] = image
    return state
