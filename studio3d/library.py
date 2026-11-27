"""The asset library: approved 3D assets kept for reuse in any project (3d_Generation_Plan Phase 17, whole assets only).

A library item is its own record with its own identity, holding a snapshot of one approved geometry file. It points
at the same stored bytes as the asset it came from, so nothing is duplicated on disk, and it keeps those bytes alive
on its own: deleting the source asset later does not empty the library item.

    add       only an approved file can be added, and adding is a separate, deliberate step (approving does not enrol)
    use       makes a new, independent asset in a project, pinned to the exact file the item holds; changing that
              asset never changes the item or any other project's copy
    archive   hides an item from the usual list and keeps everything
    remove    takes the item out of the catalogue; its bytes go only if nothing else still uses them
    collections   flat, named groups of items; deleting a group or taking an item out of one deletes nothing else

Materials, texture sets and shared (update-everywhere) assignments are not here yet: there is nothing that makes them.
"""
import json
import os

from . import assets

LIBRARY = "@library"                        # the "project" library records live under; no real project has this id


def _meta(store):
    try:
        with open(os.path.join(store.root, "library.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data.get("collections"), list) else {"collections": []}
    except (OSError, ValueError, AttributeError):
        return {"collections": []}


def _save_meta(store, meta):
    store._write(os.path.join(store.root, "library.json"), json.dumps(meta, indent=1).encode("utf-8"))


def _item(store, item_id):
    r = store.load(item_id)
    if r.get("project") != LIBRARY:
        raise LookupError("That is not in the library.")
    return r


def is_item(record):
    return record.get("project") == LIBRARY


def add(studio, asset_id):
    """Enrol an asset's selected file. Refused unless that file is approved. Adding the same file twice returns the
    item already there. -> the library record"""
    store = studio.store
    with store.lock:
        r = store.load(asset_id)
        if is_item(r):
            raise ValueError("That is already a library item.")
        art = next((a for a in r["artifacts"] if a["id"] == r["selected"].get("geometry")), None)
        if not art:
            raise ValueError("There is no file to add. Import geometry first.")
        if art["state"] != "approved":
            raise ValueError("Only approved files can go in the library. Approve the selected file first.")
        if not store.has(art["blob"]):
            raise ValueError("The file is missing from storage, so it cannot be added.")
        for other in store.records():
            if is_item(other) and other["library"]["source_artifact"] == art["id"]:
                return other
        now = store.clock()
        new_art = dict(art, id=store.new_id("art"), state="approved", requires=[], components=[dict(c) for c in art["components"]])
        item = dict(r, id=store.new_id("asset"), project=LIBRARY, created=now, modified=now, artifacts=[new_art], selected={"geometry": new_art["id"]}, references=[], character=None,
                    library={"source_asset": r["id"], "source_artifact": art["id"], "source_project": r["project"], "favorite": False, "archived": False, "added": now})
        item.pop("from_library", None)
        return store.save(item)


def summary(store, r, records, meta):
    art = r["artifacts"][0] if r["artifacts"] else None
    t = assets.registry.TYPES[r["type"]]
    used = [x for x in records if (x.get("from_library") or {}).get("item") == r["id"]]
    return {"id": r["id"], "name": r["name"], "description": r["description"], "type": r["type"], "type_label": t["label"], "parent_label": t["parent_label"], "subtype": r["subtype"],
            "tags": r["tags"], "favorite": r["library"]["favorite"], "archived": r["library"]["archived"], "added": r["library"]["added"], "artifact": art["id"] if art else None,
            "file": art["name"] if art else "", "size": art["size"] if art else 0, "vertices": art["report"]["totals"]["vertices"] if art else None,
            "size_cm": art["report"]["totals"]["size_cm"] if art else None, "canonical": art["report"]["conventions"]["canonical"] if art else None,
            "complete": bool(art and store.has(art["blob"])), "uses": len(used), "collections": [c["id"] for c in meta["collections"] if r["id"] in c["items"]]}


def items(studio, query="", kind="", favorite=False, archived=False, collection=""):
    """The catalogue, newest first. Archived items show only when asked for. Search looks in names, tags, type and
    subtype. Built from the records as they are now, so nothing deleted can reappear."""
    store = studio.store
    with store.lock:
        records, meta = store.records(), _meta(store)
    words = [w for w in str(query or "").lower().split() if w][:8]
    members = next((set(c["items"]) for c in meta["collections"] if c["id"] == collection), None) if collection else None
    out = []
    for r in records:
        if not is_item(r) or bool(r["library"]["archived"]) != bool(archived) or (favorite and not r["library"]["favorite"]) or (kind and r["type"] != kind):
            continue
        if members is not None and r["id"] not in members:
            continue
        s = summary(store, r, records, meta)
        text = " ".join([s["name"], s["type_label"], s["parent_label"], s["subtype"], s["description"]] + s["tags"]).lower()
        if all(w in text for w in words):
            out.append(s)
    out.sort(key=lambda s: -s["added"])
    live = {r["id"] for r in records if is_item(r)}
    return {"items": out, "collections": [{"id": c["id"], "name": c["name"], "count": len([i for i in c["items"] if i in live])} for c in meta["collections"]],
            "total": len(live)}


def update(studio, item_id, fields):
    store = studio.store
    g = fields if isinstance(fields, dict) else {}
    with store.lock:
        r = _item(store, item_id)
        studio._fields(r, {k: g[k] for k in ("name", "description", "tags") if k in g})
        for key in ("favorite", "archived"):
            if key in g:
                r["library"][key] = bool(g[key])
        r["modified"] = store.clock()
        return store.save(r)


def usage(studio, item_id, project_name=None):
    """Where an item is in use: the assets made from it, and the asset it came from if that is still there."""
    store = studio.store
    name = project_name or (lambda pid: pid)
    with store.lock:
        r = _item(store, item_id)
        records = store.records()
    out = [{"project": x["project"], "project_name": name(x["project"]), "asset": x["id"], "name": x["name"], "relation": "made from this item"}
           for x in records if (x.get("from_library") or {}).get("item") == item_id]
    src = next((x for x in records if x["id"] == r["library"]["source_asset"]), None)
    if src:
        out.append({"project": src["project"], "project_name": name(src["project"]), "asset": src["id"], "name": src["name"], "relation": "the asset this came from"})
    return out


def use(studio, item_id, project):
    """Make a new asset in a project from a library item. It is independent: its own identity, pinned to the item's
    exact file, already approved because the item is. No bytes are copied. -> the new asset record"""
    store = studio.store
    with store.lock:
        r = _item(store, item_id)
        art = r["artifacts"][0] if r["artifacts"] else None
        if not art or not store.has(art["blob"]):
            raise ValueError("This library item's file is missing, so it cannot be used until it is added again.")
        if r["library"]["archived"]:
            raise ValueError("This item is archived. Restore it to use it.")
        now = store.clock()
        new_art = dict(art, id=store.new_id("art"), state="approved", origin="library", components=[dict(c, id=store.new_id("cmp")) for c in art["components"]])
        ids = {c["id"]: n["id"] for c, n in zip(art["components"], new_art["components"])}
        for c in new_art["components"]:
            c["parent"] = ids.get(c["parent"])
        new = dict(r, id=store.new_id("asset"), project=project, created=now, modified=now, artifacts=[new_art], selected={"geometry": new_art["id"]},
                   references=[], character=None, from_library={"item": r["id"], "artifact": art["id"], "sha256": art["blob"], "used": now})
        new.pop("library", None)
        return store.save(new)


def remove(studio, item_id):
    """Take an item out of the catalogue. Assets made from it are untouched and keep their files. -> bytes reclaimed"""
    store = studio.store
    with store.lock:
        r = _item(store, item_id)
        meta = _meta(store)
        for c in meta["collections"]:
            c["items"] = [i for i in c["items"] if i != item_id]
        _save_meta(store, meta)
        store.remove_record(item_id)
        return store.drop([a["blob"] for a in r["artifacts"] if a.get("blob")])


def collection(studio, fields):
    """Make, rename or delete a collection, or put an item in or take it out.
    {name} | {id, name} | {id, delete: true} | {id, item, on: bool}"""
    store = studio.store
    g = fields if isinstance(fields, dict) else {}
    with store.lock:
        meta = _meta(store)
        c = next((c for c in meta["collections"] if c["id"] == g.get("id")), None)
        if g.get("id") and not c:
            raise LookupError("That collection is no longer there.")
        name = assets._text(g.get("name"), 60)
        if not c:
            if not name:
                raise ValueError("Give the collection a name.")
            if len(meta["collections"]) >= 200:
                raise ValueError("There are too many collections.")
            meta["collections"].append({"id": store.new_id("col"), "name": name, "items": []})
        elif g.get("delete") is True:
            meta["collections"].remove(c)
        elif isinstance(g.get("item"), str):
            _item(store, g["item"])
            c["items"] = [i for i in c["items"] if i != g["item"]] + ([g["item"]] if g.get("on") else [])
        elif name:
            c["name"] = name
        _save_meta(store, meta)
        return meta["collections"]
