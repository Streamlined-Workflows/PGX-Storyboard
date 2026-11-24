"""Reference Generation: reference sheets for an asset, and the pictures cut out of them.

Design document: docs/Reference_Generation_Design.md. Built so far (its section 16, steps 1 to 5 and the manual half
of step 6): the workspace with its two separately started workflows, the classification registry, Simple sheet
generation with candidates, approval and ten-day retention, Advanced rows with six directional slots (generate,
upload, lock, disable, inherit from other rows, row classification), specification panels, assembling the rows
into one sheet, and Sheet Extraction by hand-drawn regions.
Also built (step 7): consistency checks on a row's views, the four export profiles, and the hand-over of chosen
pictures to 3D Generation. Not built yet: choosing between providers (there is one) and detection that tells
which way a view faces.

Assembly is done by the page (static/generator/reference-assembly.js): it lays the chosen pictures out on a canvas,
never asking a model to redraw anything, and sends the finished PNG here to be stored as a new pending sheet that
records which pictures it was made from.

What is kept for a SWIFT Director project (project["reference"]):
  projects   reference projects: [{id, name, parent, type, subtype, custom_subtype, mode, prompt, prompt_edited,
             sources, count, profile, aspect, at, selected, extraction: {source, regions}, rows}]
             rows (Advanced mode): [{id, section, label, role, type, subtype, prompt, prompt_edited, sources, count,
             profile, aspect, locked, at, selected, slots: {front|left|right|rear|top|bottom: {enabled, locked, at, selected}}}]
             A row source is {"image": name} or {"row": id, "direction": d}: the picture another row has chosen for
             that view, looked up each time it is used, so nothing is copied.
  open       the reference project being worked on
  handover   what has been sent to 3D Generation: [{id, reference, name, parent, type, subtype, created, updated,
             items: [{artifact, role, row, component}]}]. Only ids are kept, so nothing is copied and nothing is approved.
  artifacts  one record per picture made or cut out here:
             {id, project, role: "sheet" | "view", image, state: "pending" | "approved", created, expires,
              width, height, upscaled, requires: [{id, reason}], origin: "generated" | "extracted" | "uploaded",
              and for a sheet {prompt, seed, sources, provider}, for an extracted view {source, region, direction,
              section, component}, for a row's view {row, direction, component, type, subtype, prompt, seed, sources},
              and role "row" for a complete row picture that was uploaded {row}}

The pictures are ordinary stills: unfinished ones are in project["image_jobs"] and finished ones in
project["generated"], both marked kind "ref" with slot = the reference project's id, so the Library can offer them
as references elsewhere. This module only reads and edits those lists; app.py does the queueing and file work.

Retention (design 2, RG-006 to RG-009): a new picture is pending and expires ten days after it was made unless it
is approved. Denying or expiring removes its record, its prompt and settings, and its entry in the Library.
Selecting, downloading or extracting from a pending picture neither approves it nor moves its expiry.
"""
import json
import re
import time

import workflows

RETENTION = 10 * 24 * 3600
MAX_PROJECTS, MAX_SOURCES, MAX_COUNT, MAX_PROMPT, MAX_REGIONS = 40, 4, 10, 3000, 60
PROMPT_LIMIT = workflows.PROMPT_LIMITS["image"]

# The classification registry (3d_Generation_Plan/3d_Phase_3.md, 3.2). Every type also allows a Custom subtype.
REGISTRY = (
    ("actors", "Actors", (("humanoid", "Humanoid", ("Organic", "Mechanical", "Hybrid")),
                          ("creature", "Creature", ("Quadruped", "Bipedal", "Winged", "Aquatic", "Serpentine", "Insectoid")))),
    ("scene_assets", "Scene Assets", (("scene_prop", "Scene Prop", ("Furniture", "Container", "Machinery", "Decoration", "Fixture")),
                                      ("vehicle", "Vehicle", ("Ground", "Water", "Aircraft", "Spacecraft", "Hybrid")))),
    ("props", "Props", (("held_prop", "Held Prop", ("Tool", "Instrument", "Equipment", "Weapon", "Container")),
                        ("interactive_prop", "Interactive Prop", ("Door", "Window", "Container", "Switch", "Lever", "Mechanism", "Furniture")))),
    ("world_assets", "World Assets", (("vehicle_interior", "Vehicle Interior", ("Cockpit", "Cabin", "Cargo Hold", "Passenger Compartment", "Engineering Compartment", "Complete Interior")),
                                      ("scenery", "Scenery", ("Architecture", "Vegetation", "Terrain", "Natural Formation", "Modular Structure")))),
)
TYPES = {t: {"key": t, "label": label, "parent": p, "parent_label": plabel, "subtypes": list(subs)} for p, plabel, kinds in REGISTRY for t, label, subs in kinds}
CUSTOM = "Custom"

# Recommended content of a sheet for each type (design 3.1): what the upper (Base) and lower (Detail) parts show.
# These are starting points for the prompt, which the person can rewrite.
TEMPLATES = {
    "humanoid": ("the complete character standing in a consistent neutral A-pose, shown from the front, right side, rear and left side",
                 "close-ups of the head from the front and side, the hands, the feet, the eyes, the hair, and the clothing, footwear and accessories"),
    "creature": ("the complete creature in a consistent neutral standing pose that suits its anatomy, shown from the front, right side, rear and left side",
                 "close-ups of the head, paws or claws, teeth, tail, and any wings, horns, fur or scales"),
    "scene_prop": ("the complete object on its own, shown from the front, right side, rear and left side",
                   "close-ups of its materials, structural features, openings and removable parts"),
    "vehicle": ("the exterior of the complete vehicle, shown from the front, right side, rear, left side and top",
                "close-ups of the hull, engines, glass, landing gear or wheels, and doors"),
    "held_prop": ("the complete object on its own with no hand holding it, shown from the front, right side, rear and left side",
                  "close-ups of the grip, the working parts, the materials and any removable parts"),
    "interactive_prop": ("the complete object, shown closed and shown open as two clearly separate states, from the front and side",
                         "close-ups of the moving parts, hinges, handles, openings and the surfaces where parts attach"),
    "vehicle_interior": ("the interior with nobody in it, looking forward, rearward, left and right",
                         "close-ups of the fixtures, controls, seats, doors and structural surfaces"),
    "scenery": ("the complete structure or landscape piece, shown from the front, right side, rear and left side",
                "close-ups of the roof, walls, foundations, vegetation, architectural parts and materials"),
}
NOUN = {"humanoid": "character", "creature": "creature", "scene_prop": "prop", "vehicle": "vehicle", "held_prop": "prop",
        "interactive_prop": "prop", "vehicle_interior": "interior", "scenery": "scenery"}

# What the picture-making provider can do (design 10). One provider today: the FLUX.2 [dev] setup the rest of the app uses.
# The size limit is the one its makers publish (about four megapixels); it has not been measured on this machine.
PROVIDER = {"name": "FLUX.2 [dev] + Turbo LoRA", "local": True, "inputs": 4, "outputs_per_job": 1, "formats": ["png"],
            "max_side": 2048, "max_pixels": 4_200_000, "multiple": 16}
PROFILES = (512, 1024, 2048, 4096)                       # the longer side, in pixels
ASPECTS = (("16:9", 16, 9), ("3:2", 3, 2), ("4:3", 4, 3), ("1:1", 1, 1), ("3:4", 3, 4), ("2:3", 2, 3), ("9:16", 9, 16))
DIRECTIONS = ("front", "left", "right", "rear", "top", "bottom")
SECTIONS = ("base", "detail")
MAX_ROWS, ROW_SOURCES = 24, 6
ROLES = ("Complete asset", "Base anatomy", "Head", "Hair", "Headwear", "Clothing", "Footwear", "Armor", "Accessory", "Equipment", "Component", "Configuration state")
# What is added to a row's prompt for each view.
DIRECTION_WORDS = {"front": "Front view: seen straight on from the front.", "left": "Left side view: the subject's left side faces the camera, in full profile.",
                   "right": "Right side view: the subject's right side faces the camera, in full profile.", "rear": "Rear view: seen from directly behind.",
                   "top": "Top view: seen from directly above, looking straight down.", "bottom": "Bottom view: seen from directly below, looking straight up."}
ROW_SHAPE = {"humanoid": "2:3", "creature": "3:2", "vehicle": "3:2", "vehicle_interior": "3:2", "scenery": "3:2"}       # others start square
# Which views a new row starts with, by type (design 3.1). Any of the six can be switched on or off afterwards.
ROW_VIEWS = {"vehicle": ("front", "left", "right", "rear", "top", "bottom"), "vehicle_interior": ("front", "left", "right", "rear", "top", "bottom")}


def row_prompt(kind, name, label, role, section):
    """The recommended prompt for one row. Each view adds its own direction sentence to it when it is generated."""
    whole = section == "base" and role in ("", "Complete asset")
    subject = (name.strip() or f"the {NOUN[kind]}") if whole else f"{(label or role or 'the component').strip()} of {name.strip() or 'the ' + NOUN[kind]}, shown on its own with nothing else in the picture"
    pose = {"humanoid": " standing in a neutral A-pose", "creature": " in a neutral standing pose"}.get(kind, "") if whole or role == "Base anatomy" else ""
    return (f"{subject}{pose}, the whole subject in frame and centred, on a plain light grey background. "
            "Flat, even, shadowless studio lighting. Orthographic-style reference view with no perspective distortion. No text, no labels.")


def size(profile, aspect):
    """Pixel size for a profile and aspect ratio: the longer side is the profile, both sides a multiple of 16."""
    w, h = next(((a, b) for name, a, b in ASPECTS if name == aspect), (16, 9))
    m = PROVIDER["multiple"]
    long_side, short = profile, max(m, round(profile * min(w, h) / max(w, h) / m) * m)
    return (long_side, short) if w >= h else (short, long_side)


def supported(profile, aspect):
    """-> "" if the provider can make this size, otherwise the reason, in words for the person."""
    w, h = size(profile, aspect)
    if max(w, h) > PROVIDER["max_side"] or w * h > PROVIDER["max_pixels"]:
        return (f"{PROVIDER['name']} cannot make a {w} × {h} picture directly (its limit is {PROVIDER['max_side']} pixels on the longer side). "
                "A larger sheet needs an upscale model, and none is installed.")
    return ""


def default_prompt(kind, name="", subtype=""):
    base, detail = TEMPLATES[kind]
    who = (name.strip() or f"the {NOUN[kind]}") + (f" ({subtype.lower()} {TYPES[kind]['label'].lower()})" if subtype else "")
    return (f"A {NOUN[kind]} reference sheet of {who} on a plain light grey background. "
            f"Upper part of the sheet: {base}. Lower part of the sheet: {detail}. "
            "The same subject in every view, with identical proportions, colours and materials. "
            "Even, shadowless studio lighting. Each view separate and fully visible, nothing overlapping. No text, no labels, no captions.")


def _text(value, limit):
    return str(value if isinstance(value, str) else "")[:limit]


def _region(r):
    """One hand-drawn region of a sheet: where it is (in the sheet's own pixels) and what it shows."""
    try:
        x, y, w, h = (max(0, int(round(float(r.get(k))))) for k in ("x", "y", "w", "h"))
    except (TypeError, ValueError, AttributeError):
        return None
    if w < 8 or h < 8:
        return None
    return {"id": _text(r.get("id"), 40) or f"r{x}_{y}_{w}_{h}", "x": x, "y": y, "w": w, "h": h,
            "direction": r.get("direction") if r.get("direction") in DIRECTIONS else "",       # "" = not a directional view
            "section": r.get("section") if r.get("section") in SECTIONS else "base",
            "component": _text(r.get("component"), 60), "detected": bool(r.get("detected"))}


PANEL_FIELDS, FIELD_NAME, FIELD_VALUE = 16, 40, 300
DEFAULT_FIELDS = ("Build", "Materials", "Colours", "Style", "Notes")
WIDTHS = ("full", "half", "custom")
LAYOUT = {"orientation": ("landscape", "portrait"), "background": ("solid", "transparent"), "align": ("left", "center", "right"),
          "panel_style": ("boxed", "plain"), "units": ("metric", "imperial")}
LAYOUT_DEFAULT = {"orientation": "landscape", "resolution": 2048, "height": 0, "background": "solid", "colour": "#e6e6e6", "labels": True, "title": True,
                  "spacing": 24, "margin": 48, "align": "center", "panel_style": "boxed", "units": "metric"}


def _panel(incoming, current):
    """A specification panel: a Label, a Sub Label, optional dimensions (kept in centimetres whatever units are shown) and
    any number of named lines. `include` only says whether it is drawn on the sheet; switching it off keeps everything.
    A Label or Sub Label left empty is drawn as the name and role of what the panel belongs to, so it follows a rename."""
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda k, d=None: incoming.get(k, current.get(k, d))
    fields = get("fields")
    if not isinstance(fields, list):
        fields = [{"name": n, "value": ""} for n in DEFAULT_FIELDS]
    dims = get("dims") if isinstance(get("dims"), dict) else {}
    def cm(v):
        try:
            return round(min(1_000_000.0, float(v)), 2) if v is not None and float(v) > 0 else None
        except (TypeError, ValueError):
            return None
    return {"include": bool(get("include", False)), "label": _text(get("label", ""), 60), "sub_label": _text(get("sub_label", ""), 60),
            "dims": {k: cm(dims.get(k)) for k in ("height", "width", "depth")},
            "fields": [{"name": _text(f.get("name"), FIELD_NAME), "value": _text(f.get("value"), FIELD_VALUE)} for f in fields[:PANEL_FIELDS] if isinstance(f, dict)]}


def _layout(incoming, current):
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda k: incoming.get(k, current.get(k, LAYOUT_DEFAULT[k]))
    out = {k: get(k) if get(k) in allowed else LAYOUT_DEFAULT[k] for k, allowed in LAYOUT.items()}
    out["resolution"] = get("resolution") if get("resolution") in PROFILES else LAYOUT_DEFAULT["resolution"]
    out["colour"] = get("colour") if isinstance(get("colour"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", get("colour")) else LAYOUT_DEFAULT["colour"]
    out["labels"], out["title"] = bool(get("labels")), bool(get("title"))
    for key, low, high in (("spacing", 0, 200), ("margin", 0, 400), ("height", 0, 16384)):      # height 0 = as tall as the content needs
        try:
            out[key] = max(low, min(high, int(get(key))))
        except (TypeError, ValueError):
            out[key] = LAYOUT_DEFAULT[key]
    return out


def _row(incoming, current, project_type, name, known):
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda k, d=None: incoming.get(k, current.get(k, d))
    given = incoming.get("id")
    kind = get("type") if get("type") in TYPES else ""               # "" = the project's own classification
    real = kind or project_type
    out = {"id": current.get("id") or (given if isinstance(given, str) and re.fullmatch(r"[a-z0-9]{6,16}", given) else None),
           "section": get("section") if get("section") in SECTIONS else "base", "label": _text(get("label", ""), 60).strip(), "role": _text(get("role", ""), 40).strip(),
           "type": kind, "subtype": get("subtype") if kind and get("subtype") in TYPES[kind]["subtypes"] else "", "locked": bool(get("locked", False)),
           "prompt_edited": bool(get("prompt_edited", False))}
    if not out["id"]:
        return None
    out["prompt"] = _text(get("prompt", ""), MAX_PROMPT) if out["prompt_edited"] else row_prompt(real, name, out["label"], out["role"], out["section"])
    sources = []
    for src in get("sources", []) if isinstance(get("sources", []), list) else []:
        if isinstance(src, dict) and isinstance(src.get("image"), str) and src["image"].strip():
            src = {"image": src["image"][:300]}
        elif isinstance(src, dict) and src.get("row") in known and src.get("row") != out["id"] and src.get("direction") in DIRECTIONS:
            src = {"row": src["row"], "direction": src["direction"]}
        else:
            continue
        if src not in sources:
            sources.append(src)
    out["sources"] = sources[:ROW_SOURCES]
    try:
        out["count"] = max(1, min(MAX_COUNT, int(get("count", 1))))
    except (TypeError, ValueError):
        out["count"] = 1
    out["profile"] = get("profile") if get("profile") in PROFILES else 1024
    out["aspect"] = get("aspect") if get("aspect") in [a for a, _, _ in ASPECTS] else ROW_SHAPE.get(real, "1:1")
    out["at"] = get("at") if isinstance(get("at"), str) else None             # the complete-row picture on show
    out["selected"] = get("selected") if isinstance(get("selected"), str) else None
    out["width"] = get("width") if get("width") in WIDTHS else "full"         # how much of the sheet's width the row takes when assembled
    try:
        out["width_pct"] = max(20, min(100, int(get("width_pct", 50))))
    except (TypeError, ValueError):
        out["width_pct"] = 50
    out["assemble"] = get("assemble") if get("assemble") in ("views", "whole") else "views"      # which of its pictures go on the sheet
    out["validation"] = current.get("validation") if isinstance(current.get("validation"), dict) else None      # written by check(), never by the page
    out["panel"] = _panel(get("panel"), current.get("panel") or {})
    slots, was, starts = get("slots") if isinstance(get("slots"), dict) else {}, current.get("slots") or {}, ROW_VIEWS.get(real, DIRECTIONS[:4])
    out["slots"] = {}
    for d in DIRECTIONS:
        sl = slots.get(d) if isinstance(slots.get(d), dict) else was.get(d) or {}
        out["slots"][d] = {"enabled": bool(sl.get("enabled", d in starts)), "locked": bool(sl.get("locked", False)),
                           "at": sl.get("at") if isinstance(sl.get("at"), str) else None, "selected": sl.get("selected") if isinstance(sl.get("selected"), str) else None}
    return out


def _uncycle(rows):
    """Drop inherited sources that would make rows depend on each other in a circle (design RIN-006)."""
    def reaches(start, target, seen=()):
        row = next((r for r in rows if r["id"] == start), None)
        return bool(row) and any(s.get("row") == target or (s.get("row") and s["row"] not in seen and reaches(s["row"], target, seen + (start,))) for s in row["sources"])
    for r in rows:
        for s in list(r["sources"]):
            if s.get("row") and reaches(s["row"], r["id"]):
                r["sources"].remove(s)


def _project(incoming, current, new_id):
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda k, d=None: incoming.get(k, current.get(k, d))
    kind = get("type") if get("type") in TYPES else "humanoid"
    subtype = get("subtype") if get("subtype") in TYPES[kind]["subtypes"] + [CUSTOM] else ""
    given = incoming.get("id")                               # a new project may bring its own id, if it is a plain short one
    out = {"id": current.get("id") or (given if isinstance(given, str) and re.fullmatch(r"[a-z0-9]{6,16}", given) else new_id()), "name": _text(get("name", ""), 80).strip() or "Untitled reference",
           "parent": TYPES[kind]["parent"], "type": kind, "subtype": subtype,
           "custom_subtype": _text(get("custom_subtype", ""), 60) if subtype == CUSTOM else "",
           "mode": get("mode") if get("mode") in ("simple", "advanced") else "simple",
           "created": current.get("created") or time.time()}
    words = out["custom_subtype"] if subtype == CUSTOM else subtype
    out["prompt_edited"] = bool(get("prompt_edited", False))
    # Until the person rewrites the prompt it follows the classification and name.
    out["prompt"] = _text(get("prompt", ""), MAX_PROMPT) if out["prompt_edited"] else default_prompt(kind, out["name"] if out["name"] != "Untitled reference" else "", words)
    sources = get("sources", [])
    out["sources"] = list(dict.fromkeys(s[:300] for s in sources if isinstance(s, str) and s.strip()))[:MAX_SOURCES] if isinstance(sources, list) else []
    try:
        out["count"] = max(1, min(MAX_COUNT, int(get("count", 1))))
    except (TypeError, ValueError):
        out["count"] = 1
    out["profile"] = get("profile") if get("profile") in PROFILES else 1024
    out["aspect"] = get("aspect") if get("aspect") in [a for a, _, _ in ASPECTS] else "16:9"
    out["at"] = get("at") if isinstance(get("at"), str) else None                   # the candidate on show
    out["selected"] = get("selected") if isinstance(get("selected"), str) else None  # the candidate chosen as the sheet
    ex = get("extraction") if isinstance(get("extraction"), dict) else {}
    regions = [r for r in (_region(r) for r in ex.get("regions", []) if isinstance(r, dict)) if r][:MAX_REGIONS] if isinstance(ex.get("regions"), list) else []
    out["extraction"] = {"source": _text(ex.get("source"), 300), "regions": regions}
    listed = get("rows") if isinstance(get("rows"), list) else []
    was = {r["id"]: r for r in current.get("rows", []) if isinstance(r, dict) and r.get("id")}
    known = {r.get("id") for r in listed if isinstance(r, dict)}
    plain = out["name"] if out["name"] != "Untitled reference" else ""
    rows = [r for r in (_row(r, was.get(r.get("id")) or {}, kind, plain, known) for r in listed[:MAX_ROWS] if isinstance(r, dict)) if r]
    out["rows"] = list({r["id"]: r for r in rows}.values())
    _uncycle(out["rows"])
    out["panel"] = _panel(get("panel"), current.get("panel") or {})       # the Base section's panel
    out["layout"] = _layout(get("layout"), current.get("layout") or {})
    return out


def clean(incoming, current=None, new_id=None):
    """What the browser sent, limited to what may be stored. Artifacts are never taken from the browser."""
    incoming = incoming if isinstance(incoming, dict) else {}
    current = current if isinstance(current, dict) else {}
    new_id = new_id or (lambda: f"rp{int(time.time() * 1000):x}")
    was = {p["id"]: p for p in current.get("projects", []) if isinstance(p, dict) and p.get("id")}
    listed = incoming.get("projects") if isinstance(incoming.get("projects"), list) else list(was.values())
    projects, seen = [], set()
    for p in listed[:MAX_PROJECTS]:
        if not isinstance(p, dict):
            continue
        done = _project(p, was.get(p.get("id")) or {}, new_id)
        if done["id"] not in seen:
            seen.add(done["id"])
            projects.append(done)
    opened = incoming.get("open", current.get("open"))
    return {"projects": projects, "open": opened if opened in seen else (projects[0]["id"] if projects else None),
            "artifacts": [a for a in current.get("artifacts", []) if isinstance(a, dict) and a.get("project") in seen],
            "handover": [h for h in current.get("handover", []) if isinstance(h, dict) and h.get("reference") in seen]}


def find(state, rid):
    p = next((p for p in state["projects"] if p["id"] == rid), None)
    if not p:
        raise ValueError("That reference project is no longer there.")
    return p


def candidates(state, row_id, direction):
    """A view slot's pictures, oldest first. `direction` None gives the row's complete-row pictures."""
    role = "view" if direction else "row"
    return sorted((a for a in state["artifacts"] if a["role"] == role and a.get("row") == row_id and (not direction or a.get("direction") == direction)),
                  key=lambda a: a["created"])


def chosen(state, row, direction):
    """The picture a slot uses: the one the person selected, otherwise the first one made for it. None if it is empty."""
    made = candidates(state, row["id"], direction)
    want = row["slots"][direction]["selected"] if direction else row["selected"]
    return next((a for a in made if a["id"] == want), made[0] if made else None)


def find_row(p, row_id):
    row = next((r for r in p["rows"] if r["id"] == row_id), None)
    if not row:
        raise ValueError("That row is no longer there.")
    return row


def targets(state, row, what):
    """Which views a request would generate (design 5.3). `what`: "row" = every enabled, unlocked view;
    "missing" = enabled views that have no picture yet; or one direction. -> {"make": [...], "locked": [...], "disabled": [...]}"""
    asked = list(DIRECTIONS) if what in ("row", "missing") else [what] if what in DIRECTIONS else []
    out = {"make": [], "locked": [], "disabled": []}
    for d in asked:
        sl = row["slots"][d]
        if not sl["enabled"]:
            out["disabled"].append(d)
        elif row["locked"] or (sl["locked"] and chosen(state, row, d)):
            out["locked"].append(d)
        elif what != "missing" or not chosen(state, row, d):
            out["make"].append(d)
    return out


def conditioning(state, p, row, direction):
    """The pictures sent to the image model for one view, in order, and the ones left out because it takes only so many
    (design 10: say which are used). First the row's own sources, then this row's locked views. A view that is not
    locked is never sent: it may be the very picture the person is trying to replace, and sending it would pull the
    new one towards it.
    -> {"used": [{"image", "what"}], "unused": [...], "unavailable": [what...]}"""
    listed, missing = [], []
    for n, src in enumerate(row["sources"], 1):
        if "image" in src:
            listed.append({"image": src["image"], "what": f"source {n}"})
            continue
        other = next((r for r in p["rows"] if r["id"] == src["row"]), None)
        got = chosen(state, other, src["direction"]) if other else None
        name = f"source {n} (the {src['direction']} view of {(other['label'] or other['role'] or 'another row') if other else 'a row that was removed'})"
        (listed.append({"image": got["image"], "what": name}) if got else missing.append(name))
    for d in DIRECTIONS:
        a = chosen(state, row, d) if d != direction and row["slots"][d]["enabled"] and (row["slots"][d]["locked"] or row["locked"]) else None
        if a:
            listed.append({"image": a["image"], "what": f"this row's locked {d} view"})
    seen, unique = set(), []
    for x in listed:
        if x["image"] not in seen:
            seen.add(x["image"])
            unique.append(x)
    return {"used": unique[:PROVIDER["inputs"]], "unused": unique[PROVIDER["inputs"]:], "unavailable": missing}


def plan_views(project, rid, row_id, what):
    """What to queue for a row's views. Raises ValueError with the reason if it cannot run.
    -> [{"direction", "prompt", "sources", "used", "unused", "width", "height", "count"}]"""
    state = project["reference"]
    p = find(state, rid)
    row = find_row(p, row_id)
    aim = targets(state, row, what)
    if not aim["make"]:
        raise ValueError("The row is locked." if row["locked"] else "There is nothing to generate: " + (
            "every enabled view already has a picture." if what == "missing" and not aim["locked"] else "the views asked for are locked or switched off."))
    if not row["prompt"].strip():
        raise ValueError("Write a prompt for the row first.")
    why = supported(row["profile"], row["aspect"])
    if why:
        raise ValueError(why)
    w, h = size(row["profile"], row["aspect"])
    out = []
    for d in aim["make"]:
        c = conditioning(state, p, row, d)
        prompt = row["prompt"].strip() + " " + DIRECTION_WORDS[d]
        if c["used"]:
            prompt += " The subject is the one shown in the reference image" + ("s" if len(c["used"]) > 1 else "") + ": keep its identity, proportions, colours and materials exactly."
        out.append({"direction": d, "prompt": prompt, "sources": [x["image"] for x in c["used"]], "used": c["used"], "unused": c["unused"], "unavailable": c["unavailable"],
                    "width": w, "height": h, "count": row["count"]})
    return out


def place(project, rid, row_id, direction, image, new_id, now=None):
    """Put an existing picture (an upload, or one from the Library) into a view slot, or into the row as its complete-row
    picture when `direction` is None. No file is copied: the new record points at the same picture. A picture that is
    still pending elsewhere stays pending here with the same expiry; anything else the person supplied is kept.
    -> the new artifact"""
    now = now or time.time()
    state = project["reference"]
    p = find(state, rid)
    row = find_row(p, row_id)
    if not isinstance(image, str) or not image.strip():
        raise ValueError("Choose a picture first.")
    if direction is not None and direction not in DIRECTIONS:
        raise ValueError("Unknown view.")
    if row["locked"] or (direction and row["slots"][direction]["locked"] and chosen(state, row, direction)):
        raise ValueError("That view is locked. Unlock it to replace its picture.")
    same = next((a for a in state["artifacts"] if a["image"] == image), None)
    art = {"id": new_id(), "project": rid, "role": "view" if direction else "row", "image": image[:300], "row": row_id, "direction": direction or "",
           "state": same["state"] if same else "approved", "created": now, "expires": same["expires"] if same else now + RETENTION,
           "width": same.get("width") if same else None, "height": same.get("height") if same else None, "upscaled": False, "requires": [], "origin": "uploaded",
           "component": row["role"], "type": row["type"] or p["type"], "subtype": row["subtype"] if row["type"] else p["subtype"]}
    state["artifacts"].append(art)
    if direction:
        row["slots"][direction].update(selected=art["id"], at=art["id"])        # an upload is put there to be used
    else:
        row.update(selected=art["id"], at=art["id"])
    return art


def assembled(project, rid, image, width, height, used, new_id, now=None):
    """Record a sheet the page assembled from chosen pictures. It is a new pending picture of its own, and it needs the
    pictures it was made from: approving it asks about any of those that are still pending.
    `used` is the ids of the pictures on it. -> the new artifact"""
    now = now or time.time()
    state = project["reference"]
    p = find(state, rid)
    by = {a["id"]: a for a in state["artifacts"] if a["project"] == rid}
    ids = [i for i in dict.fromkeys(used if isinstance(used, list) else []) if i in by]
    if not ids:
        raise ValueError("There is nothing to assemble: no row has a picture yet.")
    rows = {r["id"]: r for r in p["rows"]}
    def why(a):
        row = rows.get(a.get("row"), {})
        where = f"the row “{row.get('label') or row.get('role') or 'unnamed'}”"
        return f"The {a['direction']} view of {where}, shown on this sheet." if a["role"] == "view" else f"The complete picture of {where}, shown on this sheet."
    art = {"id": new_id(), "project": rid, "role": "sheet", "image": image, "state": "pending", "created": now, "expires": now + RETENTION,
           "width": width, "height": height, "upscaled": False, "origin": "assembled", "requires": [{"id": i, "reason": why(by[i])} for i in ids],
           "prompt": "", "seed": None, "sources": [by[i]["image"] for i in ids], "provider": "Assembled by SWIFT Director"}
    state["artifacts"].append(art)
    return art


# ---- checking a row's views against each other (design 10) ----
ASPECTS_CHECKED = ("identity", "proportions", "components", "anatomy", "pose", "materials", "colour", "orientation", "asymmetry", "isolation", "projection", "configuration")


def notes(state, p, row):
    """What can be said about a row without a model: plain facts, never a reason to stop. -> [{"views", "aspect", "description"}]"""
    out, used = [], [(d, chosen(state, row, d)) for d in DIRECTIONS if row["slots"][d]["enabled"]]
    empty = [d for d, a in used if not a]
    have = [(d, a) for d, a in used if a]
    if empty and have:
        out.append({"views": empty, "aspect": "completeness", "description": "Switched on but empty: " + ", ".join(empty) + "."})
    shapes = {}
    for d, a in have:
        if a.get("width") and a.get("height"):
            shapes.setdefault(round(a["width"] / a["height"], 2), []).append(d)
    if len(shapes) > 1:
        out.append({"views": [d for ds in shapes.values() for d in ds], "aspect": "projection",
                    "description": "The views are not all the same shape (" + "; ".join(f"{', '.join(ds)} at {k}:1" for k, ds in shapes.items()) + "), so the subject may not be the same size in each."})
    for n, src in enumerate(row["sources"], 1):
        other = next((r for r in p["rows"] if r["id"] == src.get("row")), None) if "row" in src else None
        if "row" in src and not (other and chosen(state, other, src["direction"])):
            out.append({"views": [], "aspect": "sources", "description": f"Source {n} points at a view in another row that has no picture, so it is not sent."})
    return out


def checked(project, rid, row_id, findings, model, now=None):
    """Store what the language model found when it compared a row's views. Findings are advice only: nothing is blocked
    or changed because of them. Each: {"views": [direction...], "aspect", "description", "certain": bool}."""
    state = project["reference"]
    p = find(state, rid)
    row = find_row(p, row_id)
    kept = []
    for f in findings if isinstance(findings, list) else []:
        if isinstance(f, dict) and str(f.get("description") or "").strip():
            kept.append({"views": [v for v in f.get("views", []) if v in DIRECTIONS] if isinstance(f.get("views"), list) else [],
                         "aspect": f.get("aspect") if f.get("aspect") in ASPECTS_CHECKED else "identity",
                         "description": _text(f["description"], 400).strip(), "certain": bool(f.get("certain", False))})
    row["validation"] = {"checked": now or time.time(), "model": _text(model, 80), "findings": kept[:20],
                         "pictures": {d: chosen(state, row, d)["id"] for d in DIRECTIONS if row["slots"][d]["enabled"] and chosen(state, row, d)}}
    return row["validation"]


def to_check(project, rid, row_id):
    """The pictures a consistency check compares: the row's views in use. -> (reference project, row, [(direction, artifact)])"""
    state = project["reference"]
    p = find(state, rid)
    row = find_row(p, row_id)
    views = [(d, chosen(state, row, d)) for d in DIRECTIONS if row["slots"][d]["enabled"] and chosen(state, row, d)]
    if len(views) < 2:
        raise ValueError("A check compares views with each other, so the row needs at least two views with pictures.")
    return p, row, views


# ---- export (design 11) and the hand-over to 3D Generation (design 12) ----
PROFILES_OUT = {"sheet": "Sheet Only", "views": "Individual Views", "package": "Complete Reference Package", "components": "Component Reference Sheets"}


def _safe(text, fallback):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_")[:50] or fallback


def _unique(path, taken):
    stem, dot, ext = path.rpartition(".")
    n, out = 2, path
    while out.lower() in taken:
        out, n = f"{stem}_{n}{dot}{ext}", n + 1
    taken.add(out.lower())
    return out


def export_plan(project, rid, profile, now=None):
    """What an export contains (design 11). Nothing is generated, extracted or approved by exporting: only pictures that
    already exist are listed. The page fetches the files and makes the ZIP; for component sheets it also assembles one
    sheet per row from that row's pictures.
    -> {"profile", "zip", "name", "files": [{"path", "image", "id"}], "components": [{"row", "path"}], "manifest", "pending": [...]}"""
    now = now or time.time()
    if profile not in PROFILES_OUT:
        raise ValueError("Unknown export.")
    state = project["reference"]
    p = find(state, rid)
    by = {a["id"]: a for a in state["artifacts"] if a["project"] == rid}
    stem, taken, files, components, used = _safe(p["name"], "Reference"), set(), [], [], []
    def add(a, path, **more):
        path = _unique(path, taken)
        files.append({"path": path, "image": a["image"], "id": a["id"]})
        used.append(dict({"path": path, "artifact": a["id"], "role": a["role"], "origin": a.get("origin", ""), "width": a.get("width"), "height": a.get("height"),
                          "upscaled": bool(a.get("upscaled")), "approval": a["state"], "expires": None if a["state"] == "approved" else a["expires"]}, **more))
    sheet = by.get(p["selected"]) if by.get(p["selected"], {}).get("role") == "sheet" else None
    if profile in ("sheet", "package"):
        if sheet:
            add(sheet, f"{stem}_Reference_Sheet.png")
        elif profile == "sheet":
            raise ValueError("Select a sheet first: use “Select as the sheet” on the one to export.")
    if profile in ("views", "package"):
        for row in p["rows"]:
            for d in DIRECTIONS:
                a = chosen(state, row, d) if row["slots"][d]["enabled"] else None
                if a:
                    add(a, f"Views/{_safe(row['label'] or row['role'], 'Row')}/{d.capitalize()}.png", row=row["id"], direction=d, component=row["role"],
                        classification={"type": row["type"] or p["type"], "subtype": row["subtype"] if row["type"] else p["subtype"]})
        for a in sorted((a for a in by.values() if a["role"] == "view" and a.get("region")), key=lambda a: a["created"]):
            add(a, f"Views/Extracted/{_safe(a.get('direction') or a.get('component'), 'Detail').capitalize()}.png", direction=a.get("direction", ""), component=a.get("component", ""),
                section=a.get("section", ""), source=a.get("source", ""), region=a.get("region"))
    if profile == "components":
        for row in p["rows"]:
            views = [chosen(state, row, d) for d in DIRECTIONS if row["slots"][d]["enabled"] and chosen(state, row, d)]
            whole = chosen(state, row, None)
            shown = [whole] if whole and (row["assemble"] == "whole" or not views) else views
            if not shown:
                continue
            path = _unique(f"{_safe(row['role'], 'Components')}/{_safe(row['label'] or row['role'], 'Component')}_Reference.png", taken)
            components.append({"row": row["id"], "path": path, "pictures": [a["id"] for a in shown]})
            panel = row["panel"] if row["section"] == "detail" else p["panel"]
            used.append({"path": path, "role": "component sheet", "row": row["id"], "component": row["role"], "made_from": [a["id"] for a in shown],
                         "classification": {"type": row["type"] or p["type"], "subtype": row["subtype"] if row["type"] else p["subtype"]},
                         "panel_included": bool(panel["include"]), "approval": "approved" if all(a["state"] == "approved" for a in shown) else "pending"})
    if not files and not components:
        raise ValueError({"views": "There are no individual views yet. A view exists once a row's slot has a picture or a region has been extracted; a complete sheet is not split automatically.",
                          "components": "No row has pictures yet, so there are no component sheets to make."}.get(profile, "There is nothing to export yet."))
    touched = {f["id"] for f in files} | {i for c in components for i in c["pictures"]}
    pending = [{"id": a["id"], "image": a["image"], "expires": a["expires"], "hours_left": max(0, int((a["expires"] - now) // 3600)),
                "what": ("Sheet" if a["role"] == "sheet" else f"{(a.get('direction') or a.get('component') or 'Detail').capitalize()} view" if a["role"] == "view" else "Complete row picture")}
               for a in by.values() if a["id"] in touched and a["state"] != "approved"]
    manifest = {"format": "SWIFT Director reference export", "version": 1, "profile": PROFILES_OUT[profile], "exported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "reference": {"id": p["id"], "name": p["name"], "parent": p["parent"], "type": p["type"], "subtype": p["custom_subtype"] if p["subtype"] == CUSTOM else p["subtype"], "mode": p["mode"]},
                "units": {"stored": "centimetres", "shown": p["layout"]["units"]},
                "rows": [{"id": r["id"], "section": r["section"], "label": r["label"], "component_role": r["role"],
                          "classification": {"type": r["type"] or p["type"], "subtype": r["subtype"] if r["type"] else p["subtype"], "inherited": not r["type"]},
                          "locked": r["locked"], "panel": r["panel"] if r["section"] == "detail" else None} for r in p["rows"]],
                "base_panel": p["panel"], "files": used,
                "note": "Exporting does not approve pending pictures or change when they expire. This copy is not affected when a local picture is deleted."}
    single = profile == "sheet"
    return {"profile": profile, "zip": not single, "name": f"{stem}_Reference_Sheet.png" if single else f"{stem}_{_safe(PROFILES_OUT[profile], 'Export')}.zip",
            "files": files, "components": components, "manifest": manifest, "pending": pending}


def send_to_3d(project, rid, new_id, now=None):
    """Hand the reference's chosen pictures to 3D Generation: the selected sheet, each row's views in use, and the
    extracted views. Only their ids are recorded, so no file is copied and nothing is approved or given more time.
    Sending again replaces what was sent before for the same reference. -> the hand-over entry"""
    now = now or time.time()
    state = project["reference"]
    p = find(state, rid)
    by = {a["id"]: a for a in state["artifacts"] if a["project"] == rid}
    items = []
    if by.get(p["selected"], {}).get("role") == "sheet":
        items.append({"artifact": p["selected"], "role": "sheet", "row": "", "component": ""})
    for row in p["rows"]:
        for d in DIRECTIONS:
            a = chosen(state, row, d) if row["slots"][d]["enabled"] else None
            if a:
                items.append({"artifact": a["id"], "role": d, "row": row["id"], "component": row["role"]})
    for a in sorted((a for a in by.values() if a["role"] == "view" and a.get("region")), key=lambda a: a["created"]):
        items.append({"artifact": a["id"], "role": a.get("direction") or "detail", "row": "", "component": a.get("component", "")})
    if not items:
        raise ValueError("There is nothing to send yet: select a sheet, or give a row's view a picture.")
    entry = next((h for h in state["handover"] if h["reference"] == rid), None)
    if not entry:
        entry = {"id": new_id(), "reference": rid, "created": now}
        state["handover"].append(entry)
    entry.update(name=p["name"], parent=p["parent"], type=p["type"], subtype=p["custom_subtype"] if p["subtype"] == CUSTOM else p["subtype"], updated=now, items=items)
    return entry


def handed_over(state):
    """The hand-overs with each picture looked up as it is now, so one that was denied or expired shows as gone."""
    by = {a["id"]: a for a in state["artifacts"]}
    rows = {r["id"]: r for p in state["projects"] for r in p["rows"]}
    out = []
    for h in state.get("handover", []):
        items = [dict(i, image=by[i["artifact"]]["image"] if i["artifact"] in by else None, state=by[i["artifact"]]["state"] if i["artifact"] in by else "gone",
                      row_label=(rows.get(i["row"]) or {}).get("label", "")) for i in h["items"]]
        out.append(dict(h, items=items, type_label=TYPES[h["type"]]["label"] if h.get("type") in TYPES else "", parent_label=TYPES[h["type"]]["parent_label"] if h.get("type") in TYPES else ""))
    return out


def sync(project, now=None):
    """Bring the artifact list in step with the pictures: record newly finished sheets as pending, and delete the ones
    whose ten days have run out. -> (state, the picture names whose records were deleted). Changes `project` in place."""
    now = now or time.time()
    state = clean(project.get("reference"), project.get("reference"))
    known = {a["id"] for a in state["artifacts"]}
    jobs = {j["id"]: j for j in project.get("image_jobs", []) if j.get("kind") == "ref"}
    for g in project.get("generated", []):
        if g.get("kind") != "ref" or g["id"] in known or not g.get("image") or g.get("slot") not in {p["id"] for p in state["projects"]}:
            continue
        j = jobs.get(g["id"], {})
        made = g.get("created") or now
        art = {"id": g["id"], "project": g["slot"], "role": "sheet", "image": g["image"], "state": "pending",
               "created": made, "expires": made + RETENTION, "width": j.get("width"), "height": j.get("height"), "upscaled": False, "origin": "generated",
               "requires": [], "prompt": j.get("ref_prompt", ""), "seed": g.get("seed"), "sources": list(j.get("ref_sources") or []),
               "provider": j.get("provider", PROVIDER["name"])}
        if j.get("row"):                                         # one view of an Advanced row
            art.update(role="view", row=j["row"], direction=j.get("direction", ""), component=j.get("component", ""), type=j.get("type", ""), subtype=j.get("subtype", ""))
        state["artifacts"].append(art)
    project["reference"] = state
    expired = [a["id"] for a in state["artifacts"] if a["state"] == "pending" and a["expires"] <= now and not in_use(project, a)]
    return state, delete(project, expired)


def in_use(project, artifact):
    """Is a picture being read by a job that has not finished? Such a picture is not cleaned up until the job ends."""
    return any(j.get("kind") == "ref" and j.get("status") in ("queued", "running") and artifact["image"] in (j.get("ref_sources") or [])
               for j in project.get("image_jobs", []))


def locked_pictures(state):
    """The pictures that locked views are holding: the one in use in each locked slot, and in every slot of a locked row.
    They cannot be denied until the view is unlocked."""
    return {a["id"] for p in state["projects"] for r in p["rows"] for d in DIRECTIONS
            if (r["locked"] or r["slots"][d]["locked"]) for a in [chosen(state, r, d)] if a}


def protected(state, ids):
    """Artifacts among `ids` that an approved artifact outside the set needs. They cannot be deleted while it is kept.
    Worked out in rounds, because keeping one may mean keeping what that one needs in turn."""
    going = set(ids)
    while True:
        needed = {r["id"] for a in state["artifacts"] if a["state"] == "approved" and a["id"] not in going for r in a.get("requires", [])}
        if not needed & going:
            return [i for i in ids if i not in going]
        going -= needed


def delete(project, ids):
    """Remove artifacts completely: their records here, their Library entries and the jobs that hold their prompts and
    settings. An artifact that an approved one still needs is left alone. -> the picture names no longer referenced,
    which app.py may delete from disk."""
    state = project["reference"]
    ids = set(ids) - set(protected(state, list(ids)))
    gone = [a for a in state["artifacts"] if a["id"] in ids]
    if not gone:
        return []
    state["artifacts"] = [a for a in state["artifacts"] if a["id"] not in ids]
    project["generated"] = [g for g in project.get("generated", []) if not (g.get("kind") == "ref" and g.get("id") in ids)]
    project["image_jobs"] = [j for j in project.get("image_jobs", []) if not (j.get("kind") == "ref" and j.get("id") in ids)]
    for p in state["projects"]:
        for holder in [p] + p["rows"] + [sl for r in p["rows"] for sl in r["slots"].values()]:
            for key in ("at", "selected"):
                if holder[key] in ids:
                    holder[key] = None
    for r in (r for p in state["projects"] for r in p["rows"]):
        for d in DIRECTIONS:                                     # an emptied slot is no longer locked: there is nothing left to protect
            if r["slots"][d]["locked"] and not candidates(state, r["id"], d):
                r["slots"][d]["locked"] = False
    kept = {a["image"] for a in state["artifacts"]}              # a file another record still points at is not given up
    return list(dict.fromkeys(a["image"] for a in gone if a["image"] not in kept))


def approve(project, ids, confirmed=False):
    """Approve artifacts for permanent keeping. If any of them needs other pictures that are still pending, nothing is
    changed and those are returned with the reason each is needed, unless `confirmed`: then the whole set is approved
    together. Raises ValueError if something needed is missing.
    -> {"approved": [...]} or {"needs": [{id, image, reason, for}]}"""
    state = project["reference"]
    by = {a["id"]: a for a in state["artifacts"]}
    want = [i for i in dict.fromkeys(ids) if i in by]
    if not want:
        raise ValueError("That picture is no longer there.")
    needs, queue, seen = [], list(want), set(want)
    while queue:                                             # follow what each needs, and what those need in turn
        a = by[queue.pop(0)]
        for r in a.get("requires", []):
            dep = by.get(r["id"])
            if not dep:
                raise ValueError("A picture this one depends on is missing, so it cannot be approved: " + r.get("reason", r["id"]))
            if dep["state"] != "approved" and dep["id"] not in seen:
                seen.add(dep["id"])
                queue.append(dep["id"])
                needs.append({"id": dep["id"], "image": dep["image"], "reason": r.get("reason", ""), "for": a["id"]})
    if needs and not confirmed:
        return {"needs": needs}
    for i in seen:                                           # all together: nothing above can fail past this point
        by[i]["state"] = "approved"
    return {"approved": sorted(seen)}


def plan(project, rid):
    """What to queue for a Simple sheet run. Raises ValueError with the reason if it cannot run."""
    state = project["reference"]
    p = find(state, rid)
    prompt = p["prompt"].strip()
    if not prompt:
        raise ValueError("Write a prompt first.")
    why = supported(p["profile"], p["aspect"])
    if why:
        raise ValueError(why)
    w, h = size(p["profile"], p["aspect"])
    sources = p["sources"][:PROVIDER["inputs"]]
    if sources:
        prompt += " The subject is the one shown in the reference image" + ("s" if len(sources) > 1 else "") + ": keep its identity, proportions, colours and materials."
    return {"prompt": prompt, "sources": sources, "unused": p["sources"][len(sources):], "count": p["count"], "width": w, "height": h}


def view(project, now=None):
    """Everything the page needs. Call after sync()."""
    now = now or time.time()
    state = project["reference"]
    jobs = {}
    for j in project.get("image_jobs", []):
        if j.get("kind") == "ref" and j.get("status") != "done":
            jobs.setdefault(j.get("slot"), []).append({"id": j["id"], "status": j.get("status"), "error": j.get("error", ""), "row": j.get("row"), "direction": j.get("direction")})
    # Days are rounded up, so a picture made a moment ago reads "10 days", and the last day reads in hours.
    arts = [dict(a, days_left=max(0, -int(-(a["expires"] - now) // 86400)) if a["state"] == "pending" else None,
                 hours_left=max(0, int((a["expires"] - now) // 3600)) if a["state"] == "pending" else None)
            for a in sorted(state["artifacts"], key=lambda a: a["created"])]
    shown = json.loads(json.dumps(state["projects"]))           # a copy: what is added below is for the page, not for storing
    for p in shown:                                             # plain facts about each row, worked out fresh each time
        for r in p["rows"]:
            r["notes"] = notes(state, p, r)
            if r["validation"]:
                r["validation"]["stale"] = r["validation"]["pictures"] != {d: chosen(state, r, d)["id"] for d in DIRECTIONS if r["slots"][d]["enabled"] and chosen(state, r, d)}
    return {"state": {"projects": shown, "open": state["open"]}, "artifacts": arts, "jobs": jobs, "handover": handed_over(state),
            "exports": [{"key": k, "label": v} for k, v in PROFILES_OUT.items()],
            "registry": [{"key": p, "label": pl, "types": [{"key": t, "label": tl, "subtypes": list(s) + [CUSTOM]} for t, tl, s in kinds]} for p, pl, kinds in REGISTRY],
            "profiles": [{"profile": pr, "sizes": {a: {"size": list(size(pr, a)), "blocked": supported(pr, a)} for a, _, _ in ASPECTS}} for pr in PROFILES],
            "aspects": [a for a, _, _ in ASPECTS], "directions": list(DIRECTIONS), "sections": list(SECTIONS),
            "limits": {"sources": MAX_SOURCES, "count": MAX_COUNT, "regions": MAX_REGIONS, "retention_days": RETENTION // 86400, "rows": MAX_ROWS, "row_sources": ROW_SOURCES},
            "roles": list(ROLES), "direction_words": dict(DIRECTION_WORDS), "layout_options": {k: list(v) for k, v in LAYOUT.items()},
            "prompt_limit": dict(PROMPT_LIMIT), "provider": dict(PROVIDER)}
