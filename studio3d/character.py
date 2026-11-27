"""Character preparation: checking that a humanoid is ready to hand on (3d_Generation_Plan Phase 14).

What this does today is inspect and record. It assigns roles to components, takes the person's word for the pose,
measures what can be measured from the file (height, where the feet are, whether the axes and units are the
studio's), lists what a person has to judge by eye, and when nothing fails it records exactly which body revision
is handed to landmark mapping. It changes no geometry.

What it does not do, because no tool for it is set up: convert between A-pose and T-pose, transfer skin weights,
reconstruct hidden anatomy, or fit clothing. Those are named as unavailable. Creatures can be inspected; they have
no preparation path (decision Q14-01).
"""
HUMANOID_ROLES = ("Base anatomy", "Eyes", "Teeth", "Tongue", "Hair", "Facial hair", "Clothing", "Armor", "Footwear", "Accessory")
CREATURE_ROLES = ("Base anatomy", "Eyes", "Teeth", "Tongue", "Horns", "Wings", "Tail", "Fur", "Equipment")
PROFILES = {"general": "General humanoid", "anatomy": "Anatomy-specific (separate eyes, teeth and tongue)"}
POSES = {"": "Not stated", "a-pose": "A-pose", "t-pose": "T-pose", "other": "Another pose"}
UNAVAILABLE = [("character.pose", "Converting between A-pose and T-pose"), ("character.weights", "Transferring skin weights"),
               ("geometry.generate", "Reconstructing hidden anatomy"), ("character.landmarks", "Placing the 218 body landmarks")]


def roles(kind):
    return list(HUMANOID_ROLES if kind == "humanoid" else CREATURE_ROLES if kind == "creature" else ())


def state(record):
    c = record.get("character") or {}
    return {"artifact": c.get("artifact"), "profile": c.get("profile") if c.get("profile") in PROFILES else "general",
            "pose": c.get("pose") if c.get("pose") in POSES else "", "stature_cm": c.get("stature_cm"), "confirmed": list(c.get("confirmed") or []), "handoff": c.get("handoff")}


def checks(record, artifact):
    """-> (checks, eligible). Each check: {id, label, status: "pass" | "warn" | "fail" | "manual" | "info", detail}.
    "manual" means only a person can judge it; it holds the hand-off back until they tick it."""
    c, out = state(record), []
    add = lambda cid, label, status, detail: out.append({"id": cid, "label": label, "status": status, "detail": detail})
    comps, report, kind = artifact["components"], artifact["report"], record["type"]
    if kind == "creature":
        add("scope", "Creature", "info", "Creatures can be inspected here. There is no creature preparation or hand-off in this version.")
    elif kind != "humanoid":
        add("scope", "Classification", "fail", "Character preparation is for assets classified as Humanoid.")
    base = [x for x in comps if x["role"] == "Base anatomy"]
    if len(base) == 1:
        add("base", "Clean base body", "pass", f"“{base[0]['name']}” is the base, with {base[0]['vertices']:,} control points.")
    elif not base:
        add("base", "Clean base body", "fail", "No component has the role Base anatomy. Give that role to the body mesh.")
    else:
        add("base", "Clean base body", "fail", f"{len(base)} components have the role Base anatomy: " + ", ".join(x["name"] for x in base) + ". There must be exactly one.")
    for role in ("Eyes", "Teeth", "Tongue"):
        have = [x for x in comps if x["role"] == role]
        if c["profile"] == "anatomy" and not have:
            add(role.lower(), f"Separate {role.lower()}", "fail", f"This profile needs a separate component with the role {role}.")
        elif len(have) > (2 if role == "Eyes" else 1):
            add(role.lower(), f"Separate {role.lower()}", "warn", f"{len(have)} components have the role {role}. Check for duplicates.")
        elif have:
            add(role.lower(), f"Separate {role.lower()}", "pass", ", ".join(x["name"] for x in have))
    unassigned = [x["name"] for x in comps if x["node"] == "mesh" and not x["role"]]
    if unassigned:
        add("roles", "Component roles", "warn", f"{len(unassigned)} mesh{'es have' if len(unassigned) > 1 else ' has'} no role: " + ", ".join(unassigned[:6]) + ("…" if len(unassigned) > 6 else "") + ".")
    conv = report["conventions"]
    add("conventions", "Axes and units", "pass" if conv["canonical"] else "fail", "+Y up, +Z forward, centimetres." if conv["canonical"] else " ".join(conv["notes"]) + " The studio cannot convert files yet, so re-export it from its source with those settings.")
    t = report["totals"]
    if t["bounds"]:
        (x0, y0, z0), (x1, y1, z1) = t["bounds"]
        unit, height = conv["unit_scale"], (y1 - y0) * conv["unit_scale"]
        off = abs(y0 * unit)
        add("ground", "Feet on the ground", "pass" if off <= max(0.5, height * 0.01) else "warn", f"The lowest point is {y0 * unit:+.1f} cm from the ground plane." + (" Measured from each part's bounding box, so treat it as a guide." if t["approximate_bounds"] else ""))
        cx, cz = (x0 + x1) / 2 * unit, (z0 + z1) / 2 * unit
        add("centre", "Centred over the origin", "pass" if max(abs(cx), abs(cz)) <= max(1.0, height * 0.03) else "warn", f"The middle of the figure is {cx:+.1f} cm sideways and {cz:+.1f} cm front-to-back from the origin.")
        if c["stature_cm"]:
            diff = height - c["stature_cm"]
            add("stature", "Height", "pass" if abs(diff) <= c["stature_cm"] * 0.02 else "warn", f"Measured {height:.1f} cm; you stated {c['stature_cm']:.1f} cm ({diff:+.1f} cm).")
        else:
            add("stature", "Height", "info", f"Measured {height:.1f} cm from the lowest to the highest point. State the intended height to have it compared.")
    faults = [d for d in report["defects"] if base and d["geometry"] == next((m["geometry"] for m in report["models"] if m["id"] == base[0]["source_model"]), None)] if len(base) == 1 else []
    worst = [d for d in faults if d["severity"] in ("technical failure", "significant defect")]
    if worst:
        add("faults", "Faults in the base mesh", "fail" if any(d["severity"] == "technical failure" for d in worst) else "warn", ", ".join(f"{d['kind']} ({d['count']})" for d in worst) + ". Nothing is repaired automatically.")
    elif len(base) == 1:
        add("faults", "Faults in the base mesh", "pass", "None found by the checks that were run.")
    if len(base) == 1:
        add("uvs", "UVs on the base", "pass" if base[0]["uv_channels"] else "warn", f"{base[0]['uv_channels']} UV channel(s)." if base[0]["uv_channels"] else "The base has no UVs, so a guide texture cannot be made for it later; numbered views still can.")
    rig = report["rigging"]
    if rig["skeleton"] or rig["skin"] or rig["blend_shapes"] or rig["animation"]:
        add("rig", "Rigging in the file", "info", f"The file carries {rig['skeleton']} bone(s), {rig['skin']} skin binding(s), {rig['blend_shapes']} blend shape set(s) and {rig['animation']} animation(s). They are kept exactly as they are; this is not a check that it deforms well.")
    add("pose", "Neutral pose", "pass" if c["pose"] in ("a-pose", "t-pose") else "fail", f"You stated: {POSES[c['pose']]}. " + ("The studio cannot see the pose in the mesh, so this rests on your statement." if c["pose"] in ("a-pose", "t-pose") else "State A-pose or T-pose. A character in another pose needs converting, which is not available yet."))
    for cid, label, detail in (("hidden", "Body complete under clothing", "Hide the clothing and look at the base on its own: no missing skin where clothing sat, and openings only where they are meant to be. Only you can judge this."),
                               ("facing", "Facing forward", "Use the Front view: the character should face you. The studio cannot tell front from back in a mesh.")):
        add(cid, label, "pass" if cid in c["confirmed"] else "manual", ("Confirmed by you. " if cid in c["confirmed"] else "") + detail)
    eligible = kind == "humanoid" and not any(x["status"] in ("fail", "manual") for x in out)
    return out, eligible


def update(studio, asset_id, artifact_id, fields):
    with studio.store.lock:
        r = studio.store.load(asset_id)
        studio._find(r, artifact_id)
        c = state(r)
        if c["artifact"] != artifact_id:
            c.update(artifact=artifact_id, handoff=None, confirmed=[])          # another body revision: earlier statements were about a different mesh
        g = fields if isinstance(fields, dict) else {}
        if g.get("profile") in PROFILES:
            c["profile"] = g["profile"]
        if "pose" in g and g["pose"] in POSES:
            if g["pose"] != c["pose"]:
                c["handoff"] = None
            c["pose"] = g["pose"]
        if "stature_cm" in g:
            try:
                c["stature_cm"] = round(float(g["stature_cm"]), 2) if g["stature_cm"] and 10 <= float(g["stature_cm"]) <= 1000 else None
            except (TypeError, ValueError):
                c["stature_cm"] = None
        if isinstance(g.get("confirmed"), list):
            c["confirmed"] = [x for x in ("hidden", "facing") if x in g["confirmed"]]
        r["character"] = c
        r["modified"] = studio.store.clock()
        studio.store.save(r)
        return c


def hand_off(studio, asset_id):
    """Record the exact body revision handed to landmark mapping. Refused unless every check passes. Nothing is mapped,
    generated or copied by this (Phase 14, CHP-010)."""
    with studio.store.lock:
        r = studio.store.load(asset_id)
        c = state(r)
        if not c["artifact"]:
            raise ValueError("Choose the body revision and fill in its preparation first.")
        art = studio._find(r, c["artifact"])
        found, eligible = checks(r, art)
        if not eligible:
            raise ValueError("Not ready to hand on: " + "; ".join(x["label"] for x in found if x["status"] in ("fail", "manual")) + ".")
        base = next(x for x in art["components"] if x["role"] == "Base anatomy")
        c["handoff"] = {"artifact": art["id"], "sha256": art["blob"], "base_component": base["id"], "base_name": base["name"], "pose": c["pose"], "uv_channels": base["uv_channels"],
                        "height_cm": round((art["report"]["totals"]["bounds"][1][1] - art["report"]["totals"]["bounds"][0][1]) * art["report"]["conventions"]["unit_scale"], 2),
                        "created": studio.store.clock(), "pending": art["state"] != "approved"}
        r["character"] = c
        r["modified"] = studio.store.clock()
        studio.store.save(r)
        return c
