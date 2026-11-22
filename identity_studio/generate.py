"""Turning a brief and its reference images into concept jobs, and collecting what comes back.

This file knows what to ask for; it does not know how FLUX.2 is wired. The host hands in its own
graph builders with configure(), so Identity Studio uses the same models and settings as the rest
of SWIFT Director and never keeps a second copy of that configuration.

What a reference can and cannot do here: FLUX.2 treats a reference image as strong guidance. It
usually keeps a mark's shape and colour, but it redraws it, so "keep exactly" is a request, not a
guarantee. Exact placement of an uploaded vector belongs to a later composition step.
"""
import random
import struct

from . import references, schemas

MAX_REFS = 4                    # the FLUX.2 graph takes up to four reference images
SIZES = {"icon only": (1024, 1024), "icon and text": (1536, 768)}

_build = {"image": None, "fix": None, "before": None}


def configure(build_image=None, build_fix=None, before=None):
    """Called once by the host. build_image(prompt, refs, seed, width=, height=, prefix=) and
    build_fix(image, mask, prompt, seed, width, height, prefix) return ComfyUI graphs.
    `before` runs just before jobs are queued (the host uses it to free the language model's memory)."""
    _build.update(image=build_image, fix=build_fix, before=before)


def ready():
    return bool(_build["image"])


def can_fix():
    return bool(_build["fix"])


def png_size(data):
    """-> (width, height) of a PNG, or None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None


def concept_prompt(settings, refs, direction=""):
    """The words sent to the image model for one brief. `refs` are the references in use, in order."""
    s = settings
    subject = s["app_name"] or "a software product"
    parts = [f"A logo design for {subject}."]
    if s["purpose"]:
        parts.append(f"{subject} is: {s['purpose'].rstrip('.')}.")
    if s["description"]:
        parts.append(f"The logo shows: {s['description'].rstrip('.')}.")
    if direction:
        parts.append(f"For this version: {direction.rstrip('.')}.")
    for i, ref in enumerate(refs, 1):
        how = {"keep exactly": f"Reference image {i} is an existing mark. Reproduce that mark faithfully: the same shape, proportions and colours, not redesigned.",
               "style guide": f"Match the visual style of reference image {i}: its line weight, shapes and colour treatment.",
               "inspiration": f"Take loose inspiration from reference image {i}."}[ref.get("use") if ref.get("use") in references.USES else "inspiration"]
        parts.append(how + (f" Note: {ref['note'].rstrip('.')}." if ref.get("note") else ""))
    style = s["style_notes"] or ("" if s["style"] == "custom" else s["style"])
    if style:
        parts.append(f"Style: {style.rstrip('.')}.")
    if s["palette"]:
        parts.append("Use only these colours: " + ", ".join(s["palette"]) + ".")
    if s["layout"] == "icon only":
        parts.append("A single icon mark, centred, with generous empty margin around it. No text, no letters, no words.")
    else:
        text = f'the name "{s["app_name"]}"' if s["app_name"] else "the product name"
        tag = f' and, smaller, the tagline "{s["tagline"]}"' if s["tagline"] else ""
        parts.append(f"An icon mark on the left with {text}{tag} set beside it in clean, correctly spelled lettering.")
    back = {"dark": "a plain solid black background", "light": "a plain solid white background"}.get(s["background"], "a plain solid white background")
    parts.append(f"Flat vector-style artwork with crisp clean edges and solid fills, on {back}. "
                 "One logo only, shown straight on. No mockup, no photograph, no shadow, no frame, no watermark, no extra objects.")
    return " ".join(parts)


def plan(project, direction=""):
    """-> (prompt, refs in use, notes for the person). Raises ValueError if there is nothing to go on."""
    s = project["settings"]
    if not (s["app_name"] or s["description"] or s["purpose"]):
        raise ValueError("Fill in the brief first: at least the application name or what the logo should show.")
    on = [r for r in project["references"] if isinstance(r, dict) and r.get("enabled", True)]
    notes = []
    if len(on) > MAX_REFS:
        notes.append(f"{len(on)} references are switched on; the first {MAX_REFS} are used. Switch some off to choose which.")
    refs = on[:MAX_REFS]
    if s["background"] == "transparent":
        notes.append("Concepts are drawn on a plain white background. A transparent background comes with the export step.")
    if s["layout"] != "icon only":
        notes.append("Lettering from the image model is often misspelled. Treat any text as a sketch.")
    if any(r.get("use") == "keep exactly" for r in refs):
        notes.append("A reference marked \"keep exactly\" is followed closely but redrawn, so check its shape in each concept.")
    return concept_prompt(s, refs, str(direction or "").strip()[:500]), refs, notes


def queue_concepts(store, jobs, pid, direction=""):
    """Queue one job per concept in the brief's "concepts per round". -> {concepts, notes}."""
    if not ready():
        raise ValueError("Concept generation is not connected on this server.")
    project = store.load(pid)
    prompt, refs, notes = plan(project, direction)
    names = []
    for ref in refs:                                   # put each reference where ComfyUI can load it
        data, missing = store.reference_for_model(pid, ref["id"])
        if missing:
            raise ValueError(f"\"{ref['name']}\" has not been prepared for generation yet. Open the project page, wait a moment, and try again.")
        names.append(jobs.comfy.upload(f"identity_{pid}_{ref['id']}.png", data))
    width, height = SIZES.get(project["settings"]["layout"], (1024, 1024))
    if _build["before"]:
        try:
            _build["before"]()
        except Exception:
            pass                                       # freeing memory is a courtesy, never a reason to fail
    made = []
    for _ in range(project["settings"]["concept_count"]):
        cid, seed = schemas.new_id(), random.randint(1, 2**31 - 1)
        graph = _build["image"](prompt, names, seed, width=width, height=height, prefix=f"identity/{pid}/{cid}")
        concept = {"id": cid, "kind": "concept", "state": "waiting", "prompt": prompt, "direction": str(direction or "").strip()[:500],
                   "seed": seed, "width": width, "height": height, "references": [r["id"] for r in refs], "parent": None, "error": ""}
        store.add_concept(pid, concept)
        job = jobs.add(pid, "concept", (project["settings"]["app_name"] or project["name"]) + " concept", graph, meta={"concept": cid})
        store.update_concept(pid, cid, job=job["id"])
        made.append(cid)
    return {"queued": len(made), "concepts": made, "notes": notes}


def queue_fix(store, jobs, pid, cid, mask, text):
    """Repaint the painted area of one concept. The original is kept; the result is a new concept."""
    if not can_fix():
        raise ValueError("Fixing an area is not connected on this server.")
    text = str(text or "").strip()[:800]
    if not text:
        raise ValueError("Describe what the painted area should look like.")
    if references.sniff(mask or b"") != "png" or len(mask) > references.MAX_BYTES:
        raise ValueError("Paint over the area to fix first.")
    path = store.concept_file(pid, cid)[0]
    with open(path, "rb") as f:
        picture = f.read()
    width, height = png_size(picture) or (1024, 1024)
    new = schemas.new_id()
    image = jobs.comfy.upload(f"identity_{pid}_{cid}.png", picture)
    mask_name = jobs.comfy.upload(f"identity_{pid}_{new}_mask.png", mask)
    prompt = (f"{text.rstrip('.')}. Only this part of the picture changes. It blends seamlessly with the rest of the logo: "
              "the same flat style, line weight and colours as the reference image, no visible seam.")
    seed = random.randint(1, 2**31 - 1)
    graph = _build["fix"](image, mask_name, prompt, seed, int(width), int(height), f"identity/{pid}/{new}")
    store.add_concept(pid, {"id": new, "kind": "fix", "state": "waiting", "prompt": prompt, "direction": text, "seed": seed,
                            "width": int(width), "height": int(height), "references": [], "parent": cid, "error": ""})
    job = jobs.add(pid, "fix", "Fix: " + text[:60], graph, meta={"concept": new})
    store.update_concept(pid, new, job=job["id"])
    return {"queued": 1, "concepts": [new], "notes": []}


def on_job_change(store, jobs, job):
    """Keep a concept in step with its job, and bring the finished picture into the project's own folder."""
    cid = (job.get("meta") or {}).get("concept")
    if not cid:
        return
    try:
        if job["state"] == "done":
            if not job.get("outputs"):
                return store.update_concept(job["project_id"], cid, state="failed", error="The job finished without a picture.")
            data = jobs.comfy.view(job["outputs"][0])
            if references.sniff(data) != "png":
                return store.update_concept(job["project_id"], cid, state="failed", error="ComfyUI returned something that is not a PNG picture.")
            size = png_size(data) or (0, 0)
            store.save_concept_file(job["project_id"], cid, data)
            store.update_concept(job["project_id"], cid, state="done", error="", width=size[0], height=size[1])
        elif job["state"] in ("failed", "stopped", "cancelled"):
            store.update_concept(job["project_id"], cid, state=job["state"], error=job.get("error", ""))
        else:
            store.update_concept(job["project_id"], cid, state="waiting", error="")
    except ValueError:
        pass                                           # the project or concept was removed meanwhile
