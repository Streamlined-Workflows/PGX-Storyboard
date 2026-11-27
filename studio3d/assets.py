"""3D assets: what they are, what they hold, and what happens to them (3d_Generation_Plan Phases 3, 4, 5, 6 and 22).

An asset is a record, not a model file (Phase 4, 4.1). It has an identity that survives renaming and
reclassifying, a classification, and a list of artifacts: independently identified files with their own approval
state. Geometry is canonical FBX, stored exactly as it arrived and never rewritten.

    asset    {id, project, name, description, parent, type, subtype, structural_profile, generation_mode,
              production, quality, target_vertices, dimensions {width, height, length} (cm, or None), origin,
              tags, created, modified, selected {geometry}, artifacts [...], references [...], character {...}}
    artifact {id, category: "geometry", format: "fbx", name, blob, size, state: "pending" | "approved",
              created, expires, origin: "imported" | "reimported", requires [{id, reason}], report, components [...]}
    component {id, name, parent, node: "mesh" | "group", source_model, role, side, visible, locked,
               transform {position, rotation, scale}, vertices, faces, triangles}
    reference {id, artifact (a Reference Generation picture's id), roles, direction, component, included}

Lifecycle (Phase 2, 4.11 and 22): a new artifact is pending and is deleted ten days after it was made unless it is
approved. Denying deletes it at once. Deleting removes the record's entry and, when nothing else uses the same
bytes, the file. Selecting, exporting, locking or using an artifact never approves it and never moves its expiry.
An imported file comes in as a pending candidate to review unless the person ticks "approve on import"; their own
file outside the studio is never touched.

Every function that changes something takes the store's lock, loads the record, changes it, and saves it: the save
is the commit (see store.py).
"""
import re
import time

import reference as registry          # the classification registry shared with Reference Generation (Phase 3)

from . import fbx
from .store import Blocked

RETENTION = 10 * 24 * 3600
SCHEMA = "1.0"
MODES = ("unified", "automatic modular", "directed modular")
PRODUCTION = ("draft", "in progress", "ready for review", "validated", "archived")
QUALITY = {"low": (500, 10_000, 5_000), "mid": (10_001, 30_000, 20_000), "high": (30_001, 500_000, 100_000)}     # min, max, proposed preset (Phase 6, 6.4)
STRUCTURAL = {"vehicle": ("exterior",), "vehicle_interior": ("interior",), "scenery": ("exterior", "interior")}   # Phase 3, 3.8
ORIGINS = ("ground center", "floor center", "bounding center", "custom")
DEFAULT_ORIGIN = {"humanoid": "ground center", "creature": "ground center", "scene_prop": "ground center", "vehicle": "ground center",
                  "held_prop": "bounding center", "interactive_prop": "bounding center", "vehicle_interior": "floor center", "scenery": "ground center"}
REFERENCE_ROLES = ("primary", "directional", "detail", "component", "material", "style", "scale", "layout", "configuration variant")
DIRECTIONS = ("front", "left", "right", "rear", "top", "bottom")
SIDES = ("", "left", "right", "center")
MAX_IMPORT = 512 * 1024 * 1024


def _text(value, limit):
    return (value if isinstance(value, str) else "")[:limit].strip()


def _cm(value):
    try:
        return round(float(value), 3) if value is not None and 0 < float(value) < 10_000_000 else None
    except (TypeError, ValueError):
        return None


class Studio:
    def __init__(self, store, resolve_reference=None):
        self.store = store
        self.resolve_reference = resolve_reference or (lambda project, artifact: None)     # -> {image, state, expires, what} or None

    # ---------- reading ----------
    def _find(self, record, artifact_id):
        a = next((a for a in record["artifacts"] if a["id"] == artifact_id), None)
        if not a:
            raise LookupError("That file is no longer there. It may have been denied or have expired.")
        return a

    def summary(self, r, now=None):
        now = now or self.store.clock()
        geo = next((a for a in r["artifacts"] if a["id"] == r["selected"].get("geometry")), None)
        pending = [a for a in r["artifacts"] if a["state"] == "pending"]
        return {"id": r["id"], "name": r["name"], "parent": r["parent"], "type": r["type"], "subtype": r["subtype"], "production": r["production"],
                "modified": r["modified"], "candidates": len([a for a in r["artifacts"] if a["category"] == "geometry"]),
                "pending": len(pending), "soonest": min((a["expires"] for a in pending), default=None),
                "vertices": geo["report"]["totals"]["vertices"] if geo else None}

    def list(self, project):
        with self.store.lock:
            return [self.summary(r) for r in self.store.records() if r.get("project") == project]

    def view(self, asset_id, now=None):
        """One asset with everything the page shows worked out: time left, counts against the target, and each
        reference looked up as it is now."""
        now = now or self.store.clock()
        with self.store.lock:
            r = self.store.load(asset_id)
        t = registry.TYPES[r["type"]]
        out = dict(r, type_label=t["label"], parent_label=t["parent_label"])
        out["artifacts"] = [dict(a, hours_left=max(0, int((a["expires"] - now) // 3600)) if a["state"] == "pending" else None,
                                 days_left=max(0, -int(-(a["expires"] - now) // 86400)) if a["state"] == "pending" else None) for a in r["artifacts"]]
        geo = next((a for a in r["artifacts"] if a["id"] == r["selected"].get("geometry")), None)
        out["budget"] = self.budget(r, geo)
        refs = []
        for ref in r["references"]:
            live = self.resolve_reference(r["project"], ref["artifact"])
            refs.append(dict(ref, image=live["image"] if live else None, state=live["state"] if live else "unavailable", what=live.get("what", "") if live else ""))
        out["references"] = refs
        return out

    def budget(self, r, geo):
        """Requested against measured control points (Phase 6, GPB-004): shown, never enforced."""
        lo, hi, _ = QUALITY[r["quality"]]
        if not geo:
            return {"profile": r["quality"], "range": [lo, hi], "target": r["target_vertices"], "measured": None}
        measured = geo["report"]["totals"]["vertices"]
        return {"profile": r["quality"], "range": [lo, hi], "target": r["target_vertices"], "measured": measured, "difference": measured - r["target_vertices"],
                "measured_profile": fbx.profile(measured), "within_profile": lo <= measured <= hi}

    # ---------- making and changing assets ----------
    def _fields(self, record, given):
        """Apply the fields the page may set. Identity never changes here (ADS-002, ADS-003)."""
        g = given if isinstance(given, dict) else {}
        if "name" in g:
            record["name"] = _text(g["name"], 80) or record.get("name") or "Untitled asset"
        if "description" in g:
            record["description"] = _text(g["description"], 600)
        if g.get("type") in registry.TYPES:
            if g["type"] != record.get("type"):
                record["subtype"], record["custom_subtype"] = "", ""
                record["origin"] = DEFAULT_ORIGIN[g["type"]]
            record["type"], record["parent"] = g["type"], registry.TYPES[g["type"]]["parent"]
        kind = record["type"]
        if "subtype" in g:
            record["subtype"] = g["subtype"] if g["subtype"] in registry.TYPES[kind]["subtypes"] + [registry.CUSTOM] else ""
        if "custom_subtype" in g:
            record["custom_subtype"] = _text(g["custom_subtype"], 60) if record["subtype"] == registry.CUSTOM else ""
        allowed = STRUCTURAL.get(kind, ("object",))
        if g.get("structural_profile") in allowed or record.get("structural_profile") not in allowed:
            record["structural_profile"] = g["structural_profile"] if g.get("structural_profile") in allowed else allowed[0]
        if g.get("generation_mode") in MODES:
            record["generation_mode"] = g["generation_mode"]
        if g.get("production") in PRODUCTION:
            record["production"] = g["production"]
        if g.get("quality") in QUALITY and g["quality"] != record.get("quality"):
            record["quality"], record["target_vertices"] = g["quality"], QUALITY[g["quality"]][2]
        if "target_vertices" in g:
            lo, hi, preset = QUALITY[record["quality"]]
            try:
                record["target_vertices"] = max(lo, min(hi, int(g["target_vertices"])))
            except (TypeError, ValueError):
                record["target_vertices"] = preset
        if isinstance(g.get("dimensions"), dict):
            record["dimensions"] = {k: _cm(g["dimensions"].get(k)) for k in ("width", "height", "length")}
        if g.get("origin") in ORIGINS:
            record["origin"] = g["origin"]
        if isinstance(g.get("tags"), list):
            record["tags"] = list(dict.fromkeys(_text(t, 30) for t in g["tags"] if _text(t, 30)))[:20]
        return record

    def create(self, project, fields=None):
        now = self.store.clock()
        record = {"schema": SCHEMA, "id": self.store.new_id("asset"), "project": project, "name": "Untitled asset", "description": "", "type": "scene_prop",
                  "parent": "scene_assets", "subtype": "", "custom_subtype": "", "structural_profile": "object", "generation_mode": "unified", "production": "draft",
                  "quality": "mid", "target_vertices": QUALITY["mid"][2], "dimensions": {"width": None, "height": None, "length": None},
                  "origin": DEFAULT_ORIGIN["scene_prop"], "tags": [], "created": now, "modified": now, "selected": {"geometry": None},
                  "artifacts": [], "references": [], "character": None}
        with self.store.lock:
            return self.store.save(self._fields(record, fields))

    def update(self, asset_id, fields):
        with self.store.lock:
            r = self.store.load(asset_id)
            self._fields(r, fields)
            r["modified"] = self.store.clock()
            return self.store.save(r)

    def copy(self, asset_id):
        """A new asset with its own identity that points at the same files; nothing is duplicated on disk (ADS-008).
        The copy's artifacts are new logical records, pending again from now, each with its own approval state."""
        now = self.store.clock()
        with self.store.lock:
            r = self.store.load(asset_id)
            new = dict(r, id=self.store.new_id("asset"), name=(r["name"] + " copy")[:80], created=now, modified=now, artifacts=[], references=[dict(x, id=self.store.new_id("ref")) for x in r["references"]], character=None)
            ids = {}
            for a in r["artifacts"]:
                ids[a["id"]] = self.store.new_id("art")
                new["artifacts"].append(dict(a, id=ids[a["id"]], components=[dict(c) for c in a.get("components", [])]))
            for a in new["artifacts"]:
                a["requires"] = [dict(x, id=ids.get(x["id"], x["id"])) for x in a.get("requires", [])]
            new["selected"] = {"geometry": ids.get(r["selected"].get("geometry"))}
            return self.store.save(new)

    def delete(self, asset_id):
        """Remove a whole asset, approved files included. Files other assets still use stay. -> bytes reclaimed"""
        with self.store.lock:
            r = self.store.load(asset_id)
            self.store.remove_record(asset_id)
            return self.store.drop([a["blob"] for a in r["artifacts"] if a.get("blob")])

    # ---------- geometry ----------
    def _components(self, report):
        """One component for each model node in the file that is a mesh or a group; bones are left out."""
        ids, out = {}, []
        geo = {g["id"]: g for g in report["geometries"]}
        for m in report["models"]:
            if m["kind"] in ("LimbNode", "Limb", "Root", "Camera", "Light"):
                continue
            ids[m["id"]] = self.store.new_id("cmp")
            g = geo.get(m["geometry"])
            out.append({"id": ids[m["id"]], "name": m["name"], "source_model": m["id"], "source_parent": m["parent"], "node": "mesh" if g else "group", "role": "", "side": "",
                        "visible": True, "locked": False, "transform": {"position": m["translation"], "rotation": m["rotation"], "scale": m["scale"]},
                        "vertices": g["vertices"] if g else 0, "faces": g["faces"] if g else 0, "triangles": g["triangles"] if g else 0,
                        "uv_channels": len(g["uv_channels"]) if g else 0, "material_slots": g["material_slots"] if g else 0})
        for c in out:
            c["parent"] = ids.get(c.pop("source_parent"))
        return out

    def import_geometry(self, project, asset_id, data, filename, approve=False, fields=None, origin="imported"):
        """Take an FBX file in as a new geometry candidate, on an existing asset or a new one. The file is read and
        measured first; one that cannot be read is refused and nothing is stored. -> (asset record, artifact)"""
        if len(data) > MAX_IMPORT:
            raise ValueError("That file is larger than the studio imports (512 MB).")
        report = fbx.analyse(data)                      # raises FBXError with the reason
        if not report["geometries"]:
            raise ValueError("The FBX file has no mesh in it.")
        with self.store.lock:
            self.store.admit(len(data) * 2)
            r = self.store.load(asset_id) if asset_id else None
            if r and r["project"] != project:
                raise LookupError("That asset belongs to another project.")
            now = self.store.clock()
            digest, size = self.store.put(data)
            name = re.sub(r"[^A-Za-z0-9 ._-]+", "_", _text(filename, 120)) or "geometry.fbx"
            if not r:
                base = dict({"name": re.sub(r"\.fbx$", "", name, flags=re.I)[:80]}, **(fields or {}))
                r = self.create(project, base)
            art = {"id": self.store.new_id("art"), "category": "geometry", "format": "fbx", "name": name, "blob": digest, "size": size,
                   "state": "approved" if approve else "pending", "created": now, "expires": now + RETENTION, "origin": origin, "requires": [],
                   "report": report, "components": self._components(report), "provider": "Director FBX reader"}
            r["artifacts"].append(art)
            if not r["selected"].get("geometry"):
                r["selected"]["geometry"] = art["id"]
            if r["production"] == "draft":
                r["production"] = "in progress"
            r["modified"] = now
            self.store.save(r)
            return r, art

    def select(self, asset_id, artifact_id):
        """Make a candidate the asset's current geometry. This is not approval and does not move any expiry."""
        with self.store.lock:
            r = self.store.load(asset_id)
            self._find(r, artifact_id)
            r["selected"]["geometry"] = artifact_id
            r["modified"] = self.store.clock()
            return self.store.save(r)

    def component(self, asset_id, artifact_id, component_id, fields):
        with self.store.lock:
            r = self.store.load(asset_id)
            a = self._find(r, artifact_id)
            c = next((c for c in a["components"] if c["id"] == component_id), None)
            if not c:
                raise LookupError("That component is no longer there.")
            g = fields if isinstance(fields, dict) else {}
            if c["locked"] and not ("locked" in g and not g["locked"]) and any(k in g for k in ("name", "role", "side")):
                raise Blocked("That component is locked. Unlock it to change it.")
            if "name" in g:
                c["name"] = _text(g["name"], 80) or c["name"]
            if "role" in g:
                c["role"] = _text(g["role"], 40)
            if g.get("side") in SIDES:
                c["side"] = g["side"]
            for key in ("visible", "locked"):
                if key in g:
                    c[key] = bool(g[key])
            r["modified"] = self.store.clock()
            self.store.save(r)
            return c

    # ---------- approval, denial, expiry ----------
    def approve(self, asset_id, ids, confirmed=False):
        """Approve artifacts for keeping. If they need others that are still pending, nothing changes and those are
        returned with the reason and the space they take, unless `confirmed`: then all are approved together.
        -> {"approved": [...]} or {"needs": [...], "bytes": n}"""
        with self.store.lock:
            r = self.store.load(asset_id)
            by = {a["id"]: a for a in r["artifacts"]}
            want = [i for i in dict.fromkeys(ids if isinstance(ids, list) else []) if i in by]
            if not want:
                raise LookupError("That file is no longer there.")
            needs, queue, seen = [], list(want), set(want)
            while queue:
                a = by[queue.pop(0)]
                for req in a.get("requires", []):
                    dep = by.get(req["id"])
                    if not dep or not self.store.has(dep.get("blob", "")):
                        raise ValueError("Something this needs is missing, so it cannot be approved: " + (req.get("reason") or req["id"]))
                    if dep["state"] != "approved" and dep["id"] not in seen:
                        seen.add(dep["id"])
                        queue.append(dep["id"])
                        needs.append({"id": dep["id"], "name": dep["name"], "category": dep["category"], "reason": req.get("reason", ""), "size": dep["size"], "for": a["id"]})
            if needs and not confirmed:
                return {"needs": needs, "bytes": sum(n["size"] for n in needs)}
            for i in seen:
                by[i]["state"] = "approved"
            r["modified"] = self.store.clock()
            self.store.save(r)
            return {"approved": sorted(seen)}

    def _protected(self, r, ids):
        going = set(ids)
        while True:
            needed = {x["id"] for a in r["artifacts"] if a["state"] == "approved" and a["id"] not in going for x in a.get("requires", [])}
            if not needed & going:
                return [i for i in ids if i not in going]
            going -= needed

    def _remove(self, r, ids):
        """Take artifacts out of a record completely: the entries, anything that pointed at them, and (by the caller)
        their files. Artifacts an approved one needs are kept. -> (blobs to drop, ids kept back)"""
        held = self._protected(r, list(ids))
        ids = set(ids) - set(held)
        gone = [a for a in r["artifacts"] if a["id"] in ids]
        r["artifacts"] = [a for a in r["artifacts"] if a["id"] not in ids]
        if r["selected"].get("geometry") in ids:
            left = [a for a in r["artifacts"] if a["category"] == "geometry"]
            r["selected"]["geometry"] = left[-1]["id"] if left else None
        if r.get("character") and r["character"].get("artifact") in ids:
            r["character"] = None
        return [a["blob"] for a in gone if a.get("blob")], held

    def deny(self, asset_id, ids):
        """Reject artifacts: they are deleted now, with their reports and components. -> {"denied", "held", "freed"}"""
        with self.store.lock:
            r = self.store.load(asset_id)
            ids = [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []
            before = len(r["artifacts"])
            blobs, held = self._remove(r, ids)
            r["modified"] = self.store.clock()
            self.store.save(r)                                       # the commit: from here the artifacts are gone
            return {"denied": before - len(r["artifacts"]), "held": held, "freed": self.store.drop(blobs)}

    def cleanup(self, now=None):
        """Delete pending artifacts whose ten days have run out, in every asset, then clear files nothing points at.
        Reports totals only, never which items went (Phase 22, AVP-012). A file a live job is reading is left for the
        next pass; its time is not extended. -> {"expired": n, "freed": bytes}"""
        now = now or self.store.clock()
        expired, blobs = 0, []
        with self.store.lock:
            for r in self.store.records():
                due = [a["id"] for a in r["artifacts"] if a["state"] == "pending" and a["expires"] <= now and a.get("blob") not in self.store.pins]
                if not due:
                    continue
                before = len(r["artifacts"])
                gone, _ = self._remove(r, due)
                if len(r["artifacts"]) != before:
                    expired += before - len(r["artifacts"])
                    blobs += gone
                    self.store.save(r)
            freed = self.store.drop(blobs) + self.store.sweep(now=now)
        return {"expired": expired, "freed": freed}

    # ---------- reference pictures (Phase 5) ----------
    def assign_references(self, asset_id, items):
        """Attach Reference Generation pictures to an asset by id. Nothing is copied and nothing is approved; a
        picture already attached is not attached twice. items: [{artifact, role, direction, component}]"""
        with self.store.lock:
            r = self.store.load(asset_id)
            have = {x["artifact"] for x in r["references"]}
            for it in items if isinstance(items, list) else []:
                if not isinstance(it, dict) or not isinstance(it.get("artifact"), str) or it["artifact"] in have or len(r["references"]) >= 200:
                    continue
                have.add(it["artifact"])
                direction = it.get("direction") if it.get("direction") in DIRECTIONS else ""
                role = it.get("role") if it.get("role") in REFERENCE_ROLES else ("directional" if direction else "detail")
                r["references"].append({"id": self.store.new_id("ref"), "artifact": it["artifact"], "roles": [role], "direction": direction,
                                        "component": _text(it.get("component"), 60), "included": True, "source": {k: _text(it.get(k), 40) for k in ("reference_project", "row") if it.get(k)}})
            r["modified"] = self.store.clock()
            return self.store.save(r)

    def reference(self, asset_id, ref_id, fields=None, remove=False):
        with self.store.lock:
            r = self.store.load(asset_id)
            ref = next((x for x in r["references"] if x["id"] == ref_id), None)
            if not ref:
                raise LookupError("That reference is no longer attached.")
            if remove:
                r["references"].remove(ref)
            else:
                g = fields if isinstance(fields, dict) else {}
                if isinstance(g.get("roles"), list):
                    ref["roles"] = [x for x in dict.fromkeys(g["roles"]) if x in REFERENCE_ROLES] or ref["roles"]
                    if "primary" in ref["roles"]:                      # one primary per asset; taking it leaves the others as they were (REF-004)
                        for other in r["references"]:
                            if other is not ref and "primary" in other["roles"]:
                                other["roles"] = [x for x in other["roles"] if x != "primary"] or ["detail"]
                if "direction" in g:
                    ref["direction"] = g["direction"] if g["direction"] in DIRECTIONS else ""
                if "component" in g:
                    ref["component"] = _text(g["component"], 60)
                if "included" in g:
                    ref["included"] = bool(g["included"])
            r["modified"] = self.store.clock()
            return self.store.save(r)

    # ---------- the manifest (Phase 4, 4.4) ----------
    def manifest(self, r, artifacts=None, paths=None):
        """AssetManifest.json for an asset: portable, with no storage paths in it. `artifacts` limits it to those ids;
        `paths` maps artifact id -> the file's path inside a package."""
        t = registry.TYPES[r["type"]]
        keep = [a for a in r["artifacts"] if artifacts is None or a["id"] in artifacts]
        geo = next((a for a in keep if a["id"] == r["selected"].get("geometry")), keep[0] if keep else None)
        return {"schemaVersion": SCHEMA, "assetId": r["id"], "name": r["name"], "description": r["description"],
                "classification": {"parent": t["parent_label"], "type": t["label"], "subtype": r["custom_subtype"] if r["subtype"] == registry.CUSTOM else r["subtype"],
                                   "typeKey": r["type"], "structuralProfile": r["structural_profile"]},
                "generationMode": r["generation_mode"], "status": {"production": r["production"]},
                "coordinates": {"handedness": "right", "up": "+Y", "forward": "+Z", "unit": "cm"},
                "dimensions": dict(r["dimensions"], unit="cm"), "origin": r["origin"],
                "geometry": {"qualityProfile": r["quality"], "targetVertices": r["target_vertices"], "selectedArtifactId": geo["id"] if geo else None,
                             "measured": {k: geo["report"]["totals"][k] for k in ("vertices", "faces", "triangles", "edges", "rendering_vertices")} if geo else None},
                "artifacts": [{"artifactId": a["id"], "category": a["category"], "format": a["format"], "name": a["name"], "path": (paths or {}).get(a["id"]), "sha256": a["blob"], "size": a["size"],
                               "approval": a["state"], "expires": None if a["state"] == "approved" else a["expires"], "origin": a["origin"], "requires": a.get("requires", []),
                               "conventions": a["report"]["conventions"], "statistics": a["report"]["totals"], "rigging": a["report"]["rigging"],
                               "components": [{k: c[k] for k in ("id", "name", "parent", "node", "role", "side", "visible", "locked", "transform", "vertices", "faces", "triangles", "source_model")} for c in a["components"]]}
                              for a in keep],
                "references": [{"referenceId": x["id"], "artifactId": x["artifact"], "roles": x["roles"], "direction": x["direction"], "component": x["component"], "included": x["included"]} for x in r["references"]],
                "character": r.get("character"), "metadata": {"tags": r["tags"], "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["created"]))}}
