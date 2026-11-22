"""Identity Studio's own files. Nothing here reads or writes a storyboard project.

    <data>/identity/projects/<id>.json    one file per identity project
    <data>/identity/trash/                deleted projects, moved here rather than erased
    <data>/identity/assets/<id>/          a project's files; references/ holds uploaded reference images

<data> is SWIFT Director's data folder, which lives outside the container image, so everything here
survives a restart and a container rebuild.
"""
import json
import os
import shutil
import threading
import time

from . import references, schemas

LOCK = threading.RLock()


class Store:
    """All identity project storage under one root folder. Tests point it at a temporary folder."""

    def __init__(self, data_dir):
        self.root = os.path.join(os.path.abspath(data_dir), "identity")
        self.projects = os.path.join(self.root, "projects")
        self.trash = os.path.join(self.root, "trash")
        self.assets = os.path.join(self.root, "assets")

    # ---- paths ----
    def _path(self, pid):
        if not schemas.valid_id(pid):
            raise ValueError("That is not a valid identity project id.")
        path = os.path.realpath(os.path.join(self.projects, pid + ".json"))
        if os.path.dirname(path) != os.path.realpath(self.projects):       # belt and braces against path tricks
            raise ValueError("That is not a valid identity project id.")
        return path

    def asset_dir(self, pid):
        self._path(pid)
        return os.path.join(self.assets, pid)

    # ---- reading ----
    def load(self, pid):
        path = self._path(pid)
        with LOCK:
            try:
                with open(path) as f:
                    return schemas.normalize(json.load(f))
            except FileNotFoundError:
                raise ValueError("That identity project no longer exists.")
            except (OSError, ValueError) as e:
                raise ValueError(f"Could not read that identity project: {e}")

    def list(self):
        """Every project's summary, most recently changed first. A damaged file is skipped, not fatal."""
        out = []
        with LOCK:
            if not os.path.isdir(self.projects):
                return out
            for name in os.listdir(self.projects):
                if not name.endswith(".json") or not schemas.valid_id(name[:-5]):
                    continue
                try:
                    out.append(schemas.summary(self.load(name[:-5])))
                except ValueError:
                    continue
        return sorted(out, key=lambda p: p["updated"], reverse=True)

    # ---- writing ----
    def save(self, project, touch=True):
        path = self._path(project.get("id"))
        with LOCK:
            schemas.normalize(project)
            if touch:
                project["updated"] = time.time()
            os.makedirs(self.projects, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(project, f, indent=1)
            os.replace(tmp, path)                  # never leaves a half-written project behind
        return project

    def create(self, name="", description=""):
        return self.save(schemas.new_project(name or "Untitled identity", description), touch=False)

    def update(self, pid, changes):
        """Apply the fields a person edits. Concepts, exports and ids are never taken from the browser."""
        with LOCK:
            project = self.load(pid)
            if not isinstance(changes, dict):
                raise ValueError("Nothing to save.")
            if "name" in changes:
                name = str(changes["name"]).strip()[:schemas.NAME_MAX]
                if not name:
                    raise ValueError("An identity project needs a name.")
                project["name"] = name
            if "description" in changes:
                project["description"] = str(changes["description"]).strip()[:schemas.TEXT_MAX]
            if "settings" in changes:
                project["settings"] = schemas.clean_settings(changes["settings"], project["settings"])
            return self.save(project)

    # ---- reference images ----
    def reference_dir(self, pid):
        return os.path.join(self.asset_dir(pid), "references")

    def add_reference(self, pid, filename, data):
        """Check an uploaded image and keep it with the project. -> the reference's record."""
        with LOCK:
            project = self.load(pid)
            if len(project["references"]) >= references.MAX_PER_PROJECT:
                raise ValueError(f"A project can hold {references.MAX_PER_PROJECT} references. Remove one first.")
            kind, safe, removed = references.check(data)
            ref = {"id": schemas.new_id(), "name": references.display_name(filename), "kind": kind,
                   "bytes": len(safe), "use": references.USES[0] if kind == "svg" else references.USES[1],
                   "note": "", "cleaned": removed, "added": time.time()}
            os.makedirs(self.reference_dir(pid), exist_ok=True)
            path = os.path.join(self.reference_dir(pid), f"{ref['id']}.{kind}")     # the name on disk is ours, never the upload's
            with open(path + ".tmp", "wb") as f:
                f.write(safe)
            os.replace(path + ".tmp", path)
            project["references"].append(ref)
            self.save(project)
            return ref

    def _reference(self, project, rid):
        for ref in project["references"]:
            if isinstance(ref, dict) and ref.get("id") == rid and ref.get("kind") in references.TYPES:
                return ref
        raise ValueError("That reference no longer exists.")

    def reference_file(self, pid, rid):
        """-> (path on disk, content type) for one stored reference."""
        ref = self._reference(self.load(pid), rid)
        path = os.path.join(self.reference_dir(pid), f"{ref['id']}.{ref['kind']}")
        if not schemas.valid_id(ref["id"]) or not os.path.isfile(path):
            raise ValueError("That reference's file is missing.")
        return path, references.TYPES[ref["kind"]]

    def update_reference(self, pid, rid, changes):
        with LOCK:
            project = self.load(pid)
            ref = self._reference(project, rid)
            if not isinstance(changes, dict):
                raise ValueError("Nothing to save.")
            if changes.get("use") in references.USES:
                ref["use"] = changes["use"]
            if "note" in changes:
                ref["note"] = str(changes["note"]).strip()[:500]
            if "name" in changes:
                ref["name"] = references.display_name(changes["name"])
            self.save(project)
            return ref

    def remove_reference(self, pid, rid):
        """Take a reference off the project. Its file goes to the trash folder, not the bin."""
        with LOCK:
            project = self.load(pid)
            ref = self._reference(project, rid)
            project["references"].remove(ref)
            path = os.path.join(self.reference_dir(pid), f"{ref['id']}.{ref['kind']}")
            if schemas.valid_id(ref["id"]) and os.path.isfile(path):
                os.makedirs(self.trash, exist_ok=True)
                os.replace(path, os.path.join(self.trash, f"{pid}-ref-{ref['id']}.{ref['kind']}"))
            self.save(project)
            return {"removed": rid}

    def duplicate(self, pid):
        with LOCK:
            source = self.load(pid)
            copy = json.loads(json.dumps(source))
            copy["id"] = schemas.new_id()
            copy["name"] = (source["name"] + " (copy)")[:schemas.NAME_MAX]
            copy["created"] = copy["updated"] = time.time()
            copy["exports"] = []                   # a copy has not been exported or approved
            copy["approved_concept_id"] = None
            if os.path.isdir(self.asset_dir(pid)):
                shutil.copytree(self.asset_dir(pid), self.asset_dir(copy["id"]))
            return self.save(copy, touch=False)

    def delete(self, pid):
        """Move a project and its files to the trash folder. Nothing is erased."""
        path = self._path(pid)
        with LOCK:
            if not os.path.isfile(path):
                raise ValueError("That identity project no longer exists.")
            stamp = time.strftime("%Y%m%d-%H%M%S")
            os.makedirs(self.trash, exist_ok=True)
            os.replace(path, os.path.join(self.trash, f"{pid}-{stamp}.json"))
            if os.path.isdir(self.asset_dir(pid)):
                os.replace(self.asset_dir(pid), os.path.join(self.trash, f"{pid}-{stamp}-assets"))
        return {"deleted": pid}
