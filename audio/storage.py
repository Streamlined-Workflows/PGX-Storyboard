"""Where audio lives on disk.

    <data>/audio/assets/<id>/asset.json      what the sound is and where it came from
                             original.<ext>  the file as it arrived; never changed
                             peaks.bin       cached waveform data, made once
    <data>/audio/timelines/<project id>.json        the arrangement
    <data>/audio/timelines/<project id>.history/    the last 20 saved versions, for recovery
    <data>/audio/trash/                             anything removed

Every write goes to a temporary name and is then swapped in, so a crash or a full disk leaves the
previous file intact, never half of a new one.
"""
import hashlib
import json
import os
import re
import shutil
import threading
import time

from . import media, schemas

LOCK = threading.RLock()
MAX_UPLOAD = 2 * 1024**3        # the largest single audio file accepted
HISTORY = 20
_PROJECT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Conflict(ValueError):
    """The timeline was saved from somewhere else since this copy was loaded."""
    status = 409


def _write(path, data, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, mode) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Library:
    def __init__(self, data_dir):
        self.root = os.path.join(data_dir, "audio")
        self.assets_dir = os.path.join(self.root, "assets")
        self.timelines_dir = os.path.join(self.root, "timelines")
        self.trash = os.path.join(self.root, "trash")

    # ---- assets ----
    def _dir(self, aid):
        if not schemas.valid_id(aid):
            raise ValueError("That is not a valid sound.")
        return os.path.join(self.assets_dir, aid)

    def load(self, aid):
        try:
            with open(os.path.join(self._dir(aid), "asset.json")) as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            if isinstance(e, ValueError) and "valid sound" in str(e):
                raise
            raise ValueError("That sound is no longer in the library.")

    def _save(self, asset):
        _write(os.path.join(self._dir(asset["id"]), "asset.json"), json.dumps(asset, indent=1))
        return asset

    def all(self):
        out = []
        if os.path.isdir(self.assets_dir):
            for name in os.listdir(self.assets_dir):
                if schemas.valid_id(name):
                    try:
                        out.append(self.load(name))
                    except ValueError:
                        continue
        return sorted(out, key=lambda a: a.get("created", 0))

    def for_project(self, project_id):
        return [a for a in self.all() if project_id in a.get("projects", [])]

    def find_by_hash(self, digest):
        return next((a for a in self.all() if a["file"].get("sha256") == digest), None)

    def add(self, name, data, project_id=None, kind="other", origin="upload", **more):
        """Take a file into the library. The same file added twice is stored once: the existing sound is
        returned, now also listed under this project. -> (asset, True if it was already there)."""
        if not data:
            raise ValueError("That file is empty.")
        if len(data) > MAX_UPLOAD:
            raise ValueError("That file is larger than 2 GB.")
        digest = hashlib.sha256(data).hexdigest()
        with LOCK:
            existing = self.find_by_hash(digest)
            if existing:
                return (self.use_in(existing["id"], project_id) if project_id else existing), True
            asset = schemas.new_asset(os.path.splitext(os.path.basename(str(name or "")))[0] or "Untitled sound", kind, origin)
            folder = self._dir(asset["id"])
            os.makedirs(folder, exist_ok=True)
            staging = os.path.join(folder, "incoming")
            try:
                with open(staging, "wb") as f:
                    f.write(data)
                facts = media.probe(staging)                                 # refuses anything that is not sound
                ext = media.extension(name, facts["format"])
                if not ext:
                    raise ValueError("That kind of audio file is not supported. Use WAV, FLAC, MP3, OGG, M4A or the sound from an MP4.")
                final = os.path.join(folder, "original." + ext)
                os.replace(staging, final)
                _write(os.path.join(folder, "peaks.bin"), media.peaks(final), "wb")
            except Exception:
                shutil.rmtree(folder, ignore_errors=True)                    # nothing half-added is left behind
                raise
            asset["file"] = {"name": "original." + ext, "format": ext, "sample_rate": facts["sample_rate"], "channels": facts["channels"],
                             "length": facts["length"], "bytes": len(data), "sha256": digest}
            asset.update({k: v for k, v in more.items() if k in ("generation", "speaker", "category", "tags", "parent_id")})
            asset["projects"] = [project_id] if project_id else []
            asset = schemas.clean_asset(asset, asset)
            return self._save(asset), False

    def use_in(self, aid, project_id):
        with LOCK:
            asset = self.load(aid)
            if project_id and project_id not in asset["projects"]:
                asset["projects"].append(project_id)
                self._save(asset)
            return asset

    def update(self, aid, changes):
        with LOCK:
            return self._save(schemas.clean_asset(changes, self.load(aid)))

    def file(self, aid):
        asset = self.load(aid)
        path = os.path.join(self._dir(aid), asset["file"]["name"] or "")
        if not asset["file"]["name"] or os.path.dirname(asset["file"]["name"]) or not os.path.isfile(path):
            raise ValueError("That sound's file is missing.")
        return path, {"wav": "audio/wav", "flac": "audio/flac", "mp3": "audio/mpeg", "ogg": "audio/ogg", "opus": "audio/ogg",
                      "aac": "audio/aac", "m4a": "audio/mp4"}.get(asset["file"]["format"], "application/octet-stream")

    def peaks_file(self, aid):
        path = os.path.join(self._dir(aid), "peaks.bin")
        if not os.path.isfile(path):                                         # made once; made again only if the cache was lost
            with LOCK:
                _write(path, media.peaks(self.file(aid)[0]), "wb")
        return path, "application/octet-stream"

    def remove_from(self, aid, project_id):
        """Take a sound out of a project. When no project uses it any more it moves to the trash folder."""
        with LOCK:
            asset = self.load(aid)
            asset["projects"] = [p for p in asset["projects"] if p != project_id]
            if asset["projects"]:
                self._save(asset)
                return {"removed": aid, "kept_for": len(asset["projects"])}
            os.makedirs(self.trash, exist_ok=True)
            os.replace(self._dir(aid), os.path.join(self.trash, f"{aid}-{time.strftime('%Y%m%d-%H%M%S')}"))
            return {"removed": aid, "kept_for": 0}

    # ---- timelines ----
    def _timeline_path(self, project_id):
        if not isinstance(project_id, str) or not _PROJECT.match(project_id):
            raise ValueError("That is not a valid project.")
        return os.path.join(self.timelines_dir, project_id + ".json")

    def timeline(self, project_id):
        """The project's timeline, or a new empty one. Nothing is written until it is first saved."""
        path = self._timeline_path(project_id)
        try:
            with open(path) as f:
                return json.load(f)
        except OSError:
            return schemas.new_timeline(project_id)
        except ValueError:
            raise ValueError("This project's audio timeline file is damaged. Its earlier versions are in the history folder beside it.")

    def save_timeline(self, project_id, incoming, based_on=None):
        """Save an arrangement. `based_on` is the revision the browser loaded; if the stored one has moved on, the save
        is refused so that one browser tab cannot silently undo another's work."""
        path = self._timeline_path(project_id)
        with LOCK:
            current = self.timeline(project_id)
            exists = os.path.isfile(path)
            if exists and based_on is not None and based_on != current["revision"]:
                raise Conflict("This timeline was changed in another window. Reload to see the latest version.")
            known = {a["id"] for a in self.all()}
            cleaned = schemas.clean_timeline(incoming, current)                # the revision goes up by one: an unsaved timeline is 0, its first save is 1
            for track in cleaned["tracks"]:                                   # a clip must point at a sound that exists
                track["clips"] = [c for c in track["clips"] if c["asset_id"] in known]
            cleaned["project_id"] = project_id
            if exists:
                history = path[:-5] + ".history"
                os.makedirs(history, exist_ok=True)
                shutil.copyfile(path, os.path.join(history, f"{current['revision']:08d}.json"))
                for old in sorted(os.listdir(history))[:-HISTORY]:
                    os.remove(os.path.join(history, old))
            _write(path, json.dumps(cleaned))
            for aid in schemas.assets_used(cleaned):
                self.use_in(aid, project_id)
            return cleaned
