"""Every /api/studio3d/ route. The server hands requests here and sends back whatever this returns.

    GET   /api/studio3d/info                         what the studio can and cannot do, its limits, storage in use
    GET   /api/studio3d/assets?project=…             this project's 3D assets and the hand-overs from Reference Generation
    POST  /api/studio3d/assets          {project, fields}
    GET   /api/studio3d/asset?id=…                   one asset: files, components, budget, references, character checks
    PUT   /api/studio3d/asset?id=…      {fields}
    POST  /api/studio3d/asset/copy      {id}         /asset/delete {id}
    POST  /api/studio3d/import?project=…&asset=…&name=…&approve=1     the FBX or SWIFT ZIP itself as the request body
    GET   /api/studio3d/file?asset=…&artifact=…      a stored FBX, exactly as stored
    GET   /api/studio3d/defects?asset=…&artifact=…   the faulty faces as shapes, for the 3D view to mark
    POST  /api/studio3d/select          {asset, artifact}
    POST  /api/studio3d/component       {asset, artifact, component, fields}
    POST  /api/studio3d/approve         {asset, ids, confirmed}       /deny {asset, ids}
    POST  /api/studio3d/references      {asset, items}                /reference {asset, ref, fields | remove}
    POST  /api/studio3d/character       {asset, artifact, fields}     /character/handoff {asset}
    GET   /api/studio3d/export/plan?asset=…&profile=…&references=1
    POST  /api/studio3d/export          {asset, profile, references, confirmed}
    GET   /api/studio3d/export/file?id=…             the finished package
    GET   /api/studio3d/jobs?project=…
    POST  /api/studio3d/jobs/cancel     {id}         /jobs/retry {id}     /jobs/force {id, confirmed}
    POST  /api/studio3d/cleanup                      delete what has expired, now
    PUT   /api/studio3d/settings        {floor_gb?, budget_gb?}

Imports and exports go through the queue so that nothing heavy overlaps; they are quick, so the request waits for
its turn and its result. Nothing here reaches outside this computer.
"""
import os
import threading
import time

from . import assets, character, fbx, jobs, package
from .store import Blocked, Store

PREFIX = "/api/studio3d/"
RAW_ROUTES = ("import",)
WAIT = 300                                  # seconds an import or export waits for its turn before reporting back
_state = {"studio": None, "ledger": None, "worker": False}
_hooks = {"resolve_reference": None, "read_reference": None, "handovers": None}


class File:
    def __init__(self, path, content_type):
        self.path, self.content_type = path, content_type


class Refusal(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def configure(resolve_reference=None, read_reference=None, handovers=None):
    """resolve_reference(project, artifact_id) -> {image, state, expires, what} or None; read_reference(project, image)
    -> bytes or None; handovers(project) -> the Reference Generation hand-overs. Without them references show as
    unavailable and nothing else changes."""
    _hooks.update(resolve_reference=resolve_reference, read_reference=read_reference, handovers=handovers)
    if _state["studio"]:
        _state["studio"].resolve_reference = resolve_reference or (lambda project, artifact: None)


def root():
    base = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    return os.path.join(base, "studio3d")


def use(store):
    """Point the module at a given store (tests)."""
    _state.update(studio=assets.Studio(store, _hooks["resolve_reference"]), ledger=None, worker=False)


def studio():
    if _state["studio"] is None:
        use(Store(root()))
    return _state["studio"]


def ledger():
    if _state["ledger"] is None:
        st = studio()
        reg = jobs.Registry()
        reg.register(jobs.Provider("director.fbx", "Director FBX reader", fbx.__dict__.get("VERSION", "1.0"), ("geometry.import", "character.inspect"), _run_import,
                                   limits="Reads binary FBX and measures it. It does not convert, repair or rewrite files."))
        reg.register(jobs.Provider("director.package", "Director packager", "1.0", ("package.export", "package.import"), _run_package,
                                   limits="Writes and reads SWIFT ZIP packages. Tested only against this application."))
        _state["ledger"] = jobs.Ledger(st.store.root, reg, clock=st.store.clock)
    return _state["ledger"]


def start():
    """Begin the queue's worker and the hourly cleanup. Called once when the server starts."""
    ledger().start()
    _state["worker"] = True

    def sweep():
        while True:
            try:
                clean()
            except Exception:
                pass
            time.sleep(3600)
    threading.Thread(target=sweep, daemon=True, name="studio3d-cleanup").start()


def clean():
    st = studio()
    out = st.cleanup()
    st.store.sweep()
    return out


# ---------- the work the queue runs ----------
def _staged(payload):
    with open(payload["staged"], "rb") as f:
        return f.read()


def _run_import(request, ctx):
    p, st = request["payload"], studio()
    try:
        r, art = st.import_geometry(p["project"], p.get("asset"), _staged(p), p["name"], approve=p.get("approve", False), fields=p.get("fields"))
    finally:
        _drop(p["staged"])
    return {"asset": r["id"], "artifacts": [art["id"]], "notes": []}


def _run_package(request, ctx):
    p, st = request["payload"], studio()
    if request["operation"] == "package.import":
        try:
            r, notes = package.reimport(st, p["project"], _staged(p), approve=p.get("approve", False))
        finally:
            _drop(p["staged"])
        return {"asset": r["id"], "artifacts": [a["id"] for a in r["artifacts"]], "notes": notes}
    path, name, plan = package.build(st, p["asset"], p.get("profile", "standard"), references=p.get("references", False), read_reference=_hooks["read_reference"])
    return {"asset": p["asset"], "file": os.path.basename(path), "name": name, "size": os.path.getsize(path), "pending": len(plan["pending"]), "warnings": plan["warnings"]}


def _drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _do(operation, payload, **kw):
    """Send a request through the queue and wait for it. -> the finished request. Raises with its reason."""
    led = ledger()
    try:
        r = led.submit(operation, payload, **kw)
    except jobs.Refused as e:
        raise Refusal(str(e), 409)
    if not _state["worker"]:
        led.run_pending()
    end = time.time() + WAIT
    while time.time() < end:
        r = led.get(r["id"])
        if r["state"] in jobs.TERMINAL:
            break
        time.sleep(0.05)
    if r["state"] == "succeeded":
        return r
    if r["state"] in jobs.TERMINAL:
        raise Refusal((r["error"] or {}).get("message") or "It failed.")
    raise Refusal("It is still waiting for its turn. It shows under Jobs and will finish there.", 202)


# ---------- views ----------
def info():
    st, led = studio(), ledger()
    return {"capabilities": led.registry.table(), "providers": [p.describe() for p in led.registry.providers.values()],
            "storage": dict(st.store.usage(), **st.store.settings()), "retention_days": assets.RETENTION // 86400,
            "quality": {k: {"low": v[0], "high": v[1], "preset": v[2]} for k, v in assets.QUALITY.items()},
            "modes": assets.MODES, "production": assets.PRODUCTION, "structural": assets.STRUCTURAL, "origins": assets.ORIGINS, "sides": assets.SIDES,
            "reference_roles": assets.REFERENCE_ROLES, "directions": assets.DIRECTIONS, "types": _types(),
            "character": {"profiles": character.PROFILES, "poses": character.POSES, "unavailable": [{"capability": c, "label": l} for c, l in character.UNAVAILABLE]},
            "export_profiles": package.PROFILES, "max_import": assets.MAX_IMPORT,
            "conventions": "+Y up, +Z forward, centimetres, right-handed", "access": "This computer and the computers linked to it through Tailscale. Nothing is sent anywhere else."}


def _types():
    reg = assets.registry
    return [{"key": k, "label": t["label"], "parent": t["parent"], "parent_label": t["parent_label"], "subtypes": list(t.get("subtypes", [])), "roles": character.roles(k)} for k, t in reg.TYPES.items()]


def asset_view(asset_id):
    st = studio()
    v = st.view(asset_id)
    c = character.state(v)
    art = next((a for a in v["artifacts"] if a["id"] == (c["artifact"] or v["selected"].get("geometry"))), None)
    found, eligible = character.checks(v, art) if art and v["type"] in ("humanoid", "creature") else ([], False)
    v["character"] = dict(c, artifact=art["id"] if art else None, checks=found, eligible=eligible, applies=v["type"] in ("humanoid", "creature"), roles=character.roles(v["type"]))
    v["busy"] = [j for j in ledger().listing(v["project"]) if j["asset"] == asset_id and j["state"] in jobs.ACTIVE]
    return v


def listing(project):
    return {"assets": studio().list(project), "handovers": (_hooks["handovers"](project) if _hooks["handovers"] else []), "storage": dict(studio().store.usage(), **studio().store.settings())}


def _gb(value, least):
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise Refusal("Give the size as a number of gigabytes.")
    if not least <= n <= 100000:
        raise Refusal(f"That must be at least {least:g} GB.")
    return int(n * 1024 ** 3)


# ---------- routes ----------
def handles(path):
    return path.startswith(PREFIX)


def wants_raw(path):
    return path[len(PREFIX):] in RAW_ROUTES


def _need(d, *keys):
    out = []
    for k in keys:
        v = (d or {}).get(k)
        if not isinstance(v, str) or not v or len(v) > 200:
            raise Refusal(f"The request is missing “{k}”.")
        out.append(v)
    return out[0] if len(out) == 1 else out


def handle(method, path, query, body=None, raw=None):
    route, st = path[len(PREFIX):], studio()
    try:
        return _handle(method, route, query, body, raw, st)
    except Blocked as e:
        raise Refusal(str(e), 507)
    except jobs.Refused as e:
        raise Refusal(str(e), 409)
    except fbx.FBXError as e:
        raise Refusal(str(e))


def _handle(method, route, query, body, raw, st):
    b = body if isinstance(body, dict) else {}
    if method == "GET":
        if route == "info":
            return info()
        if route == "assets":
            return listing(_need(query, "project"))
        if route == "asset":
            return asset_view(_need(query, "id"))
        if route == "file":
            r = st.store.load(_need(query, "asset"))
            art = st._find(r, _need(query, "artifact"))
            if not st.store.has(art["blob"]):
                raise LookupError("That file is missing from storage.")
            return File(st.store.blob_path(art["blob"]), "application/octet-stream")
        if route == "defects":                              # the faulty faces as shapes the 3D view can draw in red
            r = st.store.load(_need(query, "asset"))
            art = st._find(r, _need(query, "artifact"))
            listed = [d for d in art["report"]["defects"] if d["faces"]]
            wanted = {}
            for d in listed:
                wanted.setdefault(d["geometry"], set()).update(d["faces"][:500])
            shapes = fbx.faces(st.store.read(art["blob"]), wanted) if wanted else {}
            owner = {m["geometry"]: m["id"] for m in art["report"]["models"] if m["geometry"]}
            return {"defects": [{"kind": d["kind"], "severity": d["severity"], "model": owner.get(d["geometry"]), "count": d["count"],
                                 "polygons": [shapes.get(d["geometry"], {}).get(f) for f in d["faces"][:500] if shapes.get(d["geometry"], {}).get(f)]} for d in listed]}
        if route == "export/plan":
            return package.plan(st, _need(query, "asset"), query.get("profile", "standard"), references=query.get("references") == "1")
        if route == "export/file":
            r = ledger().get(_need(query, "id"))
            name = (r.get("result") or {}).get("file") if r["operation"] == "package.export" else None
            path = os.path.join(st.store.root, "exports", os.path.basename(name or "-"))
            if not name or not os.path.isfile(path):
                raise LookupError("That export is no longer here. Export it again.")
            return File(path, "application/zip" if path.endswith(".zip") else "application/octet-stream")
        if route == "jobs":
            ledger().check_stops()
            return {"jobs": ledger().listing(query.get("project"))}
    if method == "PUT":
        if route == "asset":
            st.update(_need(query, "id"), b.get("fields"))
            return asset_view(query["id"])
        if route == "settings":
            changes = {}
            if "floor_gb" in b:
                changes["floor_bytes"] = _gb(b["floor_gb"], 0.25)
            if "budget_gb" in b:
                changes["budget_bytes"] = _gb(b["budget_gb"], 1) if b["budget_gb"] else None
            st.store.set_settings(**changes)
            return dict(st.store.usage(), **st.store.settings())
    if method == "POST":
        if route == "import":
            return _import(query, raw or b"", st)
        if route == "assets":
            return asset_view(st.create(_need(b, "project"), b.get("fields"))["id"])
        if route == "asset/copy":
            return asset_view(st.copy(_need(b, "id"))["id"])
        if route == "asset/delete":
            aid = _need(b, "id")
            if any(j["asset"] == aid and j["state"] in jobs.ACTIVE for j in ledger().listing()):
                raise Refusal("Something is still running for this asset. Cancel it or wait, then delete.", 409)
            st.delete(aid)
            ledger().forget(asset=aid)
            return {"deleted": aid}
        if route == "select":
            st.select(*_need(b, "asset", "artifact"))
            return asset_view(b["asset"])
        if route == "component":
            st.component(*_need(b, "asset", "artifact", "component"), b.get("fields"))
            return asset_view(b["asset"])
        if route == "approve":
            out = st.approve(_need(b, "asset"), b.get("ids") if isinstance(b.get("ids"), list) else [], confirmed=b.get("confirmed") is True)
            return dict(out, asset=asset_view(b["asset"]))
        if route == "deny":
            aid, ids = _need(b, "asset"), b.get("ids") if isinstance(b.get("ids"), list) else []
            st.deny(aid, ids)
            ledger().forget(artifacts=ids)
            return asset_view(aid)
        if route == "references":
            st.assign_references(_need(b, "asset"), b.get("items"))
            return asset_view(b["asset"])
        if route == "reference":
            st.reference(*_need(b, "asset", "ref"), fields=b.get("fields"), remove=b.get("remove") is True)
            return asset_view(b["asset"])
        if route == "character":
            character.update(st, *_need(b, "asset", "artifact"), b.get("fields"))
            return asset_view(b["asset"])
        if route == "character/handoff":
            character.hand_off(st, _need(b, "asset"))
            return asset_view(b["asset"])
        if route == "export":
            aid = _need(b, "asset")
            profile, refs = b.get("profile") if b.get("profile") in package.PROFILES else "standard", b.get("references") is True
            plan = package.plan(st, aid, profile, references=refs)
            if plan["blocked"]:
                raise Refusal(plan["blocked"])
            if plan["pending"] and b.get("confirmed") is not True:            # the page asks first; nothing is written
                return {"needs_confirmation": True, "plan": plan}
            r = st.store.load(aid)
            job = _do("package.export", {"asset": aid, "profile": profile, "references": refs}, asset=aid, project=r["project"], label=f"Export {r['name']}")
            return dict(job["result"], id=job["id"])
        if route == "jobs/cancel":
            return {"job": _public(ledger().cancel(_need(b, "id")))}
        if route == "jobs/retry":
            r = ledger().retry(_need(b, "id"))
            if not _state["worker"]:
                ledger().run_pending()
            return {"job": _public(ledger().get(r["id"]))}
        if route == "jobs/force":
            return {"job": _public(ledger().force(_need(b, "id"), b.get("confirmed") is True))}
        if route == "cleanup":
            out = clean()
            return dict(out, storage=dict(st.store.usage(), **st.store.settings()))
    raise LookupError(route)


def _public(r):
    return {k: r.get(k) for k in ("id", "operation", "label", "asset", "state", "stage", "error", "result")}


def _import(query, data, st):
    project = _need(query, "project")
    name = os.path.basename(str(query.get("name") or "Imported.fbx").replace("\\", "/"))[:120] or "Imported.fbx"
    if not data:
        raise Refusal("No file arrived.")
    if len(data) > assets.MAX_IMPORT:
        raise Refusal("That file is larger than the studio reads.")
    is_zip = data[:4] == b"PK\x03\x04"
    if not is_zip and not data.startswith(b"Kaydara FBX Binary"):
        fbx.analyse(data)                               # raises with the reason: ASCII FBX, or not FBX at all
    st.store.admit(len(data) * 2)
    asset = query.get("asset") or None
    if asset and not is_zip:
        st.store.load(asset)
    staged = os.path.join(st.store.root, "staging", st.store.new_id("upload"))
    with open(staged, "wb") as f:
        f.write(data)
    payload = {"project": project, "staged": staged, "name": name, "approve": query.get("approve") == "1"}
    if is_zip:
        result = _do("package.import", payload, project=project, label=f"Reimport {name}")["result"]
    else:
        result = _do("geometry.import", dict(payload, asset=asset), asset=asset, project=project, label=f"Import {name}")["result"]
    return {"asset": asset_view(result["asset"]), "artifacts": result["artifacts"], "notes": result.get("notes", [])}
