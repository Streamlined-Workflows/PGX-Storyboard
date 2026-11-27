"""Exporting an asset as a SWIFT ZIP and bringing one back in (3d_Generation_Plan Phase 18; Phase 22 for recovery).

    AssetName.zip
      AssetManifest.json            identities, classification, conventions, statistics, components, checksums
      Geometry/                     the FBX files, byte for byte as stored
      References/                   reference pictures, only when asked for
      Documentation/Compatibility_Report.md

An export contains the selected geometry and what it needs, not the whole history. It is written to a staging file,
checked by reading it back, and only then moved into place, so a failed export leaves nothing that looks finished.
Exporting never approves anything and never moves an expiry; the caller asks the person to confirm when anything in
the package is pending.

A reimport is checked completely before anything is stored: safe relative paths, no duplicate names, sizes within
bounds, a manifest of a known schema, and every file matching its checksum and readable as FBX. It then becomes an
editable asset with the manifest's classification, settings, component names, roles and locks. Nothing that the
package does not contain is invented, and an asset already here is never overwritten.
"""
import hashlib
import io
import json
import os
import re
import time
import zipfile

from . import fbx

SCHEMA_MAJOR = "1"
MAX_ZIP = 2 * 1024 ** 3
MAX_ENTRIES = 2000
MAX_UNPACKED = 4 * 1024 ** 3
PROFILES = {"standard": "Standard SWIFT ZIP", "geometry": "Geometry only (FBX file)"}


def safe_name(text, fallback="Asset"):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_")[:60] or fallback


def plan(studio, asset_id, profile="standard", artifacts=None, references=False, now=None):
    """What an export would contain, and what stands in its way. Reading this changes nothing.
    -> {"profile", "name", "files": [{path, artifact, size}], "pending": [...], "warnings": [...], "blocked": reason or ""}"""
    if profile not in PROFILES:
        raise ValueError("Unknown export.")
    now = now or studio.store.clock()
    r = studio.store.load(asset_id)
    chosen = [a for a in r["artifacts"] if a["category"] == "geometry" and (a["id"] in artifacts if artifacts else a["id"] == r["selected"].get("geometry"))]
    out = {"profile": profile, "name": "", "files": [], "pending": [], "warnings": [], "blocked": "", "references": []}
    if not chosen:
        out["blocked"] = "There is no geometry to export. Import an FBX or select a candidate first."
        return out
    stem, taken = safe_name(r["name"]), set()
    for a in chosen:
        if not studio.store.has(a["blob"]):
            out["blocked"] = f"The file for “{a['name']}” is missing from storage, so it cannot be exported."
            return out
        path = f"Geometry/{safe_name(re.sub(r'[.]fbx$', '', a['name'], flags=re.I), stem)}.fbx"
        n = 2
        while path.lower() in taken:
            path, n = re.sub(r"(_\d+)?\.fbx$", f"_{n}.fbx", path), n + 1
        taken.add(path.lower())
        out["files"].append({"path": path, "artifact": a["id"], "size": a["size"]})
        if a["state"] != "approved":
            out["pending"].append({"id": a["id"], "name": a["name"], "hours_left": max(0, int((a["expires"] - now) // 3600))})
        if not a["report"]["conventions"]["canonical"]:
            out["warnings"].append(f"“{a['name']}” is exported exactly as it was imported. " + " ".join(a["report"]["conventions"]["notes"]) + " The studio does not convert files yet.")
        bad = [d for d in a["report"]["defects"] if d["severity"] in ("technical failure", "significant defect")]
        if bad:
            out["warnings"].append(f"“{a['name']}” has known faults that are exported as they are: " + ", ".join(sorted({d['kind'] for d in bad})) + ".")
    if references and profile == "standard":
        for ref in studio.view(asset_id, now)["references"]:
            if ref["included"] and ref["image"]:
                out["references"].append({"artifact": ref["artifact"], "image": ref["image"], "state": ref["state"], "path": f"References/{safe_name(ref['direction'] or ref['component'] or 'Reference')}_{len(out['references']) + 1}.png"})
                if ref["state"] == "pending":
                    out["pending"].append({"id": ref["artifact"], "name": "Reference picture: " + (ref["what"] or ref["direction"] or "detail"), "hours_left": None})
            elif ref["included"]:
                out["warnings"].append("A reference picture attached to this asset is no longer available and is left out.")
    if profile == "geometry":
        out["name"] = f"{stem}.fbx"
        out["files"] = out["files"][:1]
        out["files"][0]["path"] = out["name"]
    else:
        out["name"] = f"{stem}.zip"
    return out


def report_text(r, pl, manifest):
    geo = manifest["artifacts"][0] if manifest["artifacts"] else None
    lines = [f"# {r['name']}: compatibility report", "",
             f"Exported from SWIFT Director on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. Profile: {PROFILES[pl['profile']]}.", "",
             "## What is in this package", ""]
    lines += [f"- `{f['path']}`" for f in pl["files"]] + [f"- `{x['path']}` (reference picture)" for x in pl["references"]] + ["- `AssetManifest.json`", ""]
    lines += ["## Geometry", "", "FBX, binary, exactly as stored. Nothing was converted, repaired or re-saved on export.", ""]
    if geo:
        c, s = geo["conventions"], geo["statistics"]
        lines += [f"- Axes in the file: {c['up']} up, {c['front']} front. One unit is {c['unit_scale']:g} cm.",
                  f"- Control points {s['vertices']:,}; faces {s['faces']:,}; triangles {s['triangles']:,}" + (f"; edges {s['edges']:,}" if s.get("edges") is not None else "") + ".",
                  f"- Matches the studio's conventions (+Y up, +Z forward, centimetres): {'yes' if c['canonical'] else 'no'}.", ""]
    lines += ["## Tested with", "", "- SWIFT Director reimport: this package is read back and checked before it is offered for download.",
              "- Blender, Character Creator 5 and other tools: **not tested**. No compatibility is claimed.", ""]
    if pl["warnings"]:
        lines += ["## Things to know", ""] + [f"- {w}" for w in pl["warnings"]] + [""]
    if pl["pending"]:
        lines += ["## Not approved", "", "Some contents were not approved for keeping when this was exported. The copies inside SWIFT Director are deleted when their time runs out; this package is not affected.", ""]
    lines += ["## Left out", "", "Textures, materials, UV layouts as separate files, landmarks and generation history are not part of this export" + ("" if pl["references"] else ", and neither are reference pictures") + "."]
    return "\n".join(lines) + "\n"


def build(studio, asset_id, profile="standard", artifacts=None, references=False, read_reference=None):
    """Write the export and return (path on disk, download name, plan). Raises ValueError if the plan is blocked.
    The caller has already had the person confirm anything pending."""
    store = studio.store
    with store.lock:
        pl = plan(studio, asset_id, profile, artifacts, references)
        if pl["blocked"]:
            raise ValueError(pl["blocked"])
        r = store.load(asset_id)
        blobs = {f["artifact"]: next(a["blob"] for a in r["artifacts"] if a["id"] == f["artifact"]) for f in pl["files"]}
        for b in blobs.values():
            store.pin(b)                                # held only while the export reads them
    out_dir = os.path.join(store.root, "exports")
    final = os.path.join(out_dir, f"{store.new_id('export')}_{pl['name']}")
    staging = os.path.join(store.root, "staging", os.path.basename(final) + ".part")
    try:
        store.admit(sum(f["size"] for f in pl["files"]) * 2)
        if profile == "geometry":
            data = store.read(blobs[pl["files"][0]["artifact"]])
            with open(staging, "wb") as f:
                f.write(data)
        else:
            manifest = studio.manifest(r, artifacts=set(blobs), paths={f["artifact"]: f["path"] for f in pl["files"]})
            manifest["package"] = {"profile": PROFILES[profile], "profileVersion": "1.0", "exported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                   "coordinateMode": "asset-space", "files": [], "omitted": ["textures", "materials", "landmarks", "generation history"] + ([] if pl["references"] else ["reference pictures"])}
            with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as z:
                for f in pl["files"]:
                    data = store.read(blobs[f["artifact"]])
                    z.writestr(f["path"], data)
                    manifest["package"]["files"].append({"path": f["path"], "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "role": "geometry", "required": True})
                for x in pl["references"]:
                    data = read_reference(r["project"], x["image"]) if read_reference else None
                    if data:
                        z.writestr(x["path"], data)
                        manifest["package"]["files"].append({"path": x["path"], "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "role": "reference", "required": False, "referenceArtifactId": x["artifact"]})
                z.writestr("Documentation/Compatibility_Report.md", report_text(r, pl, manifest))
                z.writestr("AssetManifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            with open(staging, "rb") as f:
                check(f.read())                         # read back what was written before calling it done
        os.replace(staging, final)
        return final, pl["name"], pl
    finally:
        for b in blobs.values():
            store.unpin(b)
        if os.path.exists(staging):
            os.remove(staging)


def check(data):
    """Validate a SWIFT ZIP completely without storing anything. -> (manifest, {path: bytes} for the geometry files)
    Raises ValueError with the reason."""
    if len(data) > MAX_ZIP:
        raise ValueError("That package is larger than the studio reads.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise ValueError("That is not a ZIP file, or it is damaged.")
    if len(infos) > MAX_ENTRIES:
        raise ValueError("That package has too many files in it.")
    seen, total = set(), 0
    for i in infos:
        name = i.filename
        parts = name.replace("\\", "/").split("/")
        if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or ".." in parts or "\x00" in name or any(p.strip() != p for p in parts if p):
            raise ValueError("The package has a file path that points outside the package. It was not opened.")
        key = name.lower().rstrip("/")
        if key in seen:
            raise ValueError("The package has two files with the same name. It was not opened.")
        seen.add(key)
        total += i.file_size
        if total > MAX_UNPACKED:
            raise ValueError("The package unpacks to more than the studio reads.")
    if "AssetManifest.json" not in z.namelist():
        raise ValueError("The package has no AssetManifest.json, so it is not a SWIFT asset package.")
    try:
        manifest = json.loads(z.read("AssetManifest.json").decode("utf-8"))
    except (ValueError, zipfile.BadZipFile, zlib_error()) as e:
        raise ValueError("The package's manifest could not be read.") from e
    if not isinstance(manifest, dict) or str(manifest.get("schemaVersion", "")).split(".")[0] != SCHEMA_MAJOR:
        raise ValueError(f"The package was made with a manifest version this studio does not read ({str(manifest.get('schemaVersion'))[:20] if isinstance(manifest, dict) else 'unknown'}). Nothing was imported.")
    files = {}
    listed = {f.get("path"): f for f in (manifest.get("package") or {}).get("files", []) if isinstance(f, dict)}
    arts = [a for a in manifest.get("artifacts", []) if isinstance(a, dict) and a.get("category") == "geometry"]
    if not arts:
        raise ValueError("The package's manifest lists no geometry.")
    for a in arts:
        path = a.get("path")
        if not isinstance(path, str) or path not in z.namelist():
            raise ValueError(f"The manifest names a file that is not in the package: {str(path)[:80]}.")
        try:
            raw = z.read(path)
        except (zipfile.BadZipFile, zlib_error(), OSError, RuntimeError) as e:
            raise ValueError(f"A file in the package is damaged: {path[:80]}.") from e
        want = (listed.get(path) or {}).get("sha256") or a.get("sha256")
        if hashlib.sha256(raw).hexdigest() != want:
            raise ValueError(f"A file in the package does not match its checksum and may have been changed: {path[:80]}. Nothing was imported.")
        try:
            fbx.analyse(raw)
        except fbx.FBXError as e:
            raise ValueError(f"A geometry file in the package cannot be read: {e}") from e
        files[path] = raw
    return manifest, files


def zlib_error():
    import zlib
    return zlib.error


def reimport(studio, project, data, approve=False):
    """Bring a SWIFT ZIP back as an editable asset. Everything is validated first; then the asset is stored in one step.
    -> (asset record, notes for the person)"""
    manifest, files = check(data)
    store, notes = studio.store, []
    cls = manifest.get("classification") or {}
    kind = cls.get("typeKey") if cls.get("typeKey") in __import__("reference").TYPES else "scene_prop"
    fields = {"name": manifest.get("name"), "description": manifest.get("description"), "type": kind, "subtype": cls.get("subtype"), "structural_profile": cls.get("structuralProfile"),
              "generation_mode": manifest.get("generationMode"), "quality": (manifest.get("geometry") or {}).get("qualityProfile"), "dimensions": manifest.get("dimensions"),
              "origin": manifest.get("origin"), "tags": (manifest.get("metadata") or {}).get("tags")}
    with store.lock:
        asset = None
        selected = (manifest.get("geometry") or {}).get("selectedArtifactId")
        for a in [a for a in manifest["artifacts"] if a.get("category") == "geometry"]:
            raw = files[a["path"]]
            asset, art = studio.import_geometry(project, asset["id"] if asset else None, raw, a.get("name") or os.path.basename(a["path"]), approve=approve, fields=fields, origin="reimported")
            asset = store.load(asset["id"])
            art = next(x for x in asset["artifacts"] if x["id"] == art["id"])
            by_model = {c.get("source_model"): c for c in a.get("components", []) if isinstance(c, dict)}
            for c in art["components"]:                    # names, roles, sides and locks the package recorded
                old = by_model.get(c["source_model"])
                if old:
                    c.update(name=str(old.get("name") or c["name"])[:80], role=str(old.get("role") or "")[:40], side=old.get("side") if old.get("side") in ("", "left", "right", "center") else "",
                             visible=bool(old.get("visible", True)), locked=bool(old.get("locked", False)))
            if a.get("artifactId") == selected:
                asset["selected"]["geometry"] = art["id"]
            store.save(asset)
        tv = (manifest.get("geometry") or {}).get("targetVertices")
        if tv:
            asset = studio.update(asset["id"], {"target_vertices": tv})
        refs = [{"artifact": x.get("artifactId"), "role": (x.get("roles") or [""])[0], "direction": x.get("direction"), "component": x.get("component")} for x in manifest.get("references", []) if isinstance(x, dict)]
        if refs:
            asset = studio.assign_references(asset["id"], refs)
            notes.append("Reference pictures are linked by id. Any that are not in this project show as unavailable; none were recreated.")
        if manifest.get("assetId") and any(r["id"] == manifest["assetId"] for r in store.records()):
            notes.append("An asset with the package's identity is already here, so this came in as a separate asset. The existing one was not changed.")
        notes.append("Imported as a candidate to review. " + ("It was approved on import." if approve else "It is pending and is deleted in 10 days unless approved."))
        omitted = (manifest.get("package") or {}).get("omitted") or []
        if omitted:
            notes.append("The package did not contain: " + ", ".join(str(o) for o in omitted[:8]) + ".")
        return store.load(asset["id"]), notes
