"""Reference Generation: reference sheets for an asset, and the pictures cut out of them.

Design document: docs/Reference_Generation_Design.md. Built so far (its section 16, steps 1 to 3 and the manual half
of step 6): the workspace with its two separately started workflows, the classification registry, Simple sheet
generation with candidates, approval and ten-day retention, and Sheet Extraction by hand-drawn regions.
Not built yet: Advanced rows and views, specification panels, assembly, validation reporting, the export
profiles and the hand-over to 3D Generation.

What is kept for a SWIFT Director project (project["reference"]):
  projects   reference projects: [{id, name, parent, type, subtype, custom_subtype, mode, prompt, prompt_edited,
             sources, count, profile, aspect, at, selected, extraction: {source, regions}}]
  open       the reference project being worked on
  artifacts  one record per picture made or cut out here:
             {id, project, role: "sheet" | "view", image, state: "pending" | "approved", created, expires,
              width, height, upscaled, requires: [{id, reason}], and for a sheet {prompt, seed, sources, provider},
              and for a view {source, region, direction, section, component}}

The pictures are ordinary stills: unfinished ones are in project["image_jobs"] and finished ones in
project["generated"], both marked kind "ref" with slot = the reference project's id, so the Library can offer them
as references elsewhere. This module only reads and edits those lists; app.py does the queueing and file work.

Retention (design 2, RG-006 to RG-009): a new picture is pending and expires ten days after it was made unless it
is approved. Denying or expiring removes its record, its prompt and settings, and its entry in the Library.
Selecting, downloading or extracting from a pending picture neither approves it nor moves its expiry.
"""
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


def _project(incoming, current, new_id):
    incoming = incoming if isinstance(incoming, dict) else {}
    get = lambda k, d=None: incoming.get(k, current.get(k, d))
    kind = get("type") if get("type") in TYPES else "humanoid"
    subtype = get("subtype") if get("subtype") in TYPES[kind]["subtypes"] + [CUSTOM] else ""
    given = incoming.get("id")                               # a new project may bring its own id, if it is a plain short one
    out = {"id": current.get("id") or (given if isinstance(given, str) and re.fullmatch(r"[a-z0-9]{6,16}", given) else new_id()), "name": _text(get("name", ""), 80).strip() or "Untitled reference",
           "parent": TYPES[kind]["parent"], "type": kind, "subtype": subtype,
           "custom_subtype": _text(get("custom_subtype", ""), 60) if subtype == CUSTOM else "",
           "mode": "simple",                                      # "advanced" arrives with rows and views
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
            "artifacts": [a for a in current.get("artifacts", []) if isinstance(a, dict) and a.get("project") in seen]}


def find(state, rid):
    p = next((p for p in state["projects"] if p["id"] == rid), None)
    if not p:
        raise ValueError("That reference project is no longer there.")
    return p


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
        state["artifacts"].append({"id": g["id"], "project": g["slot"], "role": "sheet", "image": g["image"], "state": "pending",
                                   "created": made, "expires": made + RETENTION, "width": j.get("width"), "height": j.get("height"), "upscaled": False,
                                   "requires": [], "prompt": j.get("ref_prompt", ""), "seed": g.get("seed"), "sources": list(j.get("ref_sources") or []),
                                   "provider": j.get("provider", PROVIDER["name"])})
    project["reference"] = state
    expired = [a["id"] for a in state["artifacts"] if a["state"] == "pending" and a["expires"] <= now and not in_use(project, a)]
    return state, delete(project, expired)


def in_use(project, artifact):
    """Is a picture being read by a job that has not finished? Such a picture is not cleaned up until the job ends."""
    return any(j.get("kind") == "ref" and j.get("status") in ("queued", "running") and artifact["image"] in (j.get("ref_sources") or [])
               for j in project.get("image_jobs", []))


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
        for key in ("at", "selected"):
            if p[key] in ids:
                p[key] = None
    return [a["image"] for a in gone]


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
            jobs.setdefault(j.get("slot"), []).append({"id": j["id"], "status": j.get("status"), "error": j.get("error", "")})
    # Days are rounded up, so a picture made a moment ago reads "10 days", and the last day reads in hours.
    arts = [dict(a, days_left=max(0, -int(-(a["expires"] - now) // 86400)) if a["state"] == "pending" else None,
                 hours_left=max(0, int((a["expires"] - now) // 3600)) if a["state"] == "pending" else None)
            for a in sorted(state["artifacts"], key=lambda a: a["created"])]
    return {"state": {"projects": state["projects"], "open": state["open"]}, "artifacts": arts, "jobs": jobs,
            "registry": [{"key": p, "label": pl, "types": [{"key": t, "label": tl, "subtypes": list(s) + [CUSTOM]} for t, tl, s in kinds]} for p, pl, kinds in REGISTRY],
            "profiles": [{"profile": pr, "sizes": {a: {"size": list(size(pr, a)), "blocked": supported(pr, a)} for a, _, _ in ASPECTS}} for pr in PROFILES],
            "aspects": [a for a, _, _ in ASPECTS], "directions": list(DIRECTIONS), "sections": list(SECTIONS),
            "limits": {"sources": MAX_SOURCES, "count": MAX_COUNT, "regions": MAX_REGIONS, "retention_days": RETENTION // 86400},
            "prompt_limit": dict(PROMPT_LIMIT), "provider": dict(PROVIDER)}
