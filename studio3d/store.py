"""Where the 3D studio keeps its files and records (3d_Generation_Plan Phases 4 and 22).

Two kinds of thing are stored under one folder:

  blobs/     file contents, each stored once under the SHA-256 of its bytes. Identical files share one copy however
             many records point at them. A blob has no approval state of its own.
  assets/    one JSON record per asset. A record names the blobs it uses. Approval, expiry and every other fact
             about an artifact live in the record, never in the blob.

Writing is done so that a crash leaves either the old state or the new one, never half of each: a file is written
beside its place under a temporary name and then renamed onto it. A record is the commit: a blob with no record
pointing at it is an orphan, and `sweep()` removes orphans. So an interrupted import leaves at worst an orphan that
the next sweep clears, and an interrupted deletion leaves at worst a blob that the next sweep clears.

Nothing here knows what an asset means; assets.py does. This module only stores, counts and deletes.
"""
import hashlib
import json
import os
import shutil
import threading
import time
import uuid

FLOOR_DEFAULT = 2 * 1024 ** 3            # new work is refused when the disk would have less than this free
ORPHAN_AGE = 15 * 60                     # an unreferenced blob younger than this may belong to a write in progress


class Blocked(ValueError):
    """New work cannot start for a reason the person can act on (disk space, a lock). The message says which."""


class Store:
    def __init__(self, root, clock=time.time, disk=None):
        self.root, self.clock = root, clock
        self.disk = disk or (lambda: shutil.disk_usage(self.root).free)
        self.lock = threading.RLock()
        self.pins = {}                    # blob -> how many live jobs are reading it
        for d in ("blobs", "assets", "staging", "exports"):
            os.makedirs(os.path.join(root, d), exist_ok=True)
        self.settings_path = os.path.join(root, "settings.json")

    # ---- small helpers ----
    def new_id(self, lead):
        return f"{lead}_{uuid.uuid4().hex[:16]}"

    def _write(self, path, data):
        tmp = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def settings(self):
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            s = {}
        passed = s.get("qualified") if isinstance(s.get("qualified"), dict) else {}
        return {"floor_bytes": max(256 * 1024 ** 2, int(s.get("floor_bytes", FLOOR_DEFAULT))), "budget_bytes": max(0, int(s.get("budget_bytes") or 0)),
                "qualified": {str(k)[:60]: str(v)[:60] for k, v in passed.items()}}      # provider id -> the version that passed a test on this machine

    def set_settings(self, **changes):
        s = dict(self.settings(), **{k: int(v or 0) for k, v in changes.items() if k in ("floor_bytes", "budget_bytes")})
        if isinstance(changes.get("qualified"), dict):
            s["qualified"] = changes["qualified"]
        s["floor_bytes"] = max(256 * 1024 ** 2, s["floor_bytes"])      # the floor cannot be set below a hard minimum
        self._write(self.settings_path, json.dumps(s).encode())
        return self.settings()

    # ---- blobs ----
    def blob_path(self, digest):
        if not (isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)):
            raise ValueError("Not a stored file.")
        return os.path.join(self.root, "blobs", digest[:2], digest)

    def put(self, data):
        """Store bytes; -> (digest, size). Storing the same bytes again stores nothing new."""
        digest = hashlib.sha256(data).hexdigest()
        path = self.blob_path(digest)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._write(path, data)
        return digest, len(data)

    def read(self, digest):
        with open(self.blob_path(digest), "rb") as f:
            data = f.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("A stored file no longer matches its record. It may have been damaged on disk.")
        return data

    def has(self, digest):
        try:
            return os.path.exists(self.blob_path(digest))
        except ValueError:
            return False

    def pin(self, digest):
        with self.lock:
            self.pins[digest] = self.pins.get(digest, 0) + 1

    def unpin(self, digest):
        with self.lock:
            if self.pins.get(digest, 0) <= 1:
                self.pins.pop(digest, None)
            else:
                self.pins[digest] -= 1

    # ---- records ----
    def _record_path(self, asset_id):
        if not (isinstance(asset_id, str) and asset_id.replace("_", "").isalnum() and len(asset_id) < 64):
            raise LookupError("No such asset.")
        return os.path.join(self.root, "assets", asset_id + ".json")

    def load(self, asset_id):
        try:
            with open(self._record_path(asset_id), encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            raise LookupError("That asset is no longer there.")

    def save(self, record):
        self._write(self._record_path(record["id"]), json.dumps(record, ensure_ascii=False).encode("utf-8"))
        return record

    def remove_record(self, asset_id):
        try:
            os.remove(self._record_path(asset_id))
        except OSError:
            pass

    def records(self):
        out = []
        for name in sorted(os.listdir(os.path.join(self.root, "assets"))):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(self.root, "assets", name), encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError):
                    continue
        return out

    # ---- counting and cleaning ----
    def referenced(self, records=None):
        """blob -> the states of the artifacts that use it, across every record."""
        used = {}
        for r in records if records is not None else self.records():
            for a in r.get("artifacts", []):
                if a.get("blob"):
                    used.setdefault(a["blob"], []).append(a.get("state", "approved"))
        return used

    def usage(self, records=None):
        """How much space is used. Shared files are counted once in the physical figures."""
        used, physical, by = self.referenced(records), 0, {"approved": 0, "pending": 0, "orphan": 0}
        logical = 0
        for r in records if records is not None else self.records():
            logical += sum(a.get("size", 0) for a in r.get("artifacts", []) if a.get("blob"))
        for sub in os.listdir(os.path.join(self.root, "blobs")):
            folder = os.path.join(self.root, "blobs", sub)
            for name in os.listdir(folder) if os.path.isdir(folder) else []:
                if name.endswith(".tmp"):
                    continue
                size = os.path.getsize(os.path.join(folder, name))
                physical += size
                states = used.get(name)
                by["orphan" if not states else "approved" if "approved" in states else "pending"] += size
        temp = sum(os.path.getsize(os.path.join(dp, f)) for d in ("staging", "exports") for dp, _, fs in os.walk(os.path.join(self.root, d)) for f in fs)
        s = self.settings()
        return {"physical": physical, "logical": logical, "approved": by["approved"], "pending": by["pending"], "orphan": by["orphan"], "temporary": temp,
                "free": self.disk(), "floor": s["floor_bytes"], "budget": s["budget_bytes"]}

    def admit(self, needed):
        """Refuse new work that would take the disk below its floor or the studio above its budget (Phase 22, AVP-013).
        Approved files are never removed to make room."""
        s, free = self.settings(), self.disk()
        if free - needed < s["floor_bytes"]:
            raise Blocked(f"There is not enough free disk space: this needs {_size(needed)} and would leave less than the {_size(s['floor_bytes'])} kept free. Free some space or lower the floor.")
        if s["budget_bytes"]:
            used = self.usage()
            if used["physical"] + used["temporary"] + needed > s["budget_bytes"]:
                raise Blocked(f"This would take the 3D studio over its storage budget of {_size(s['budget_bytes'])}. Approve less, clean up, or raise the budget.")

    def sweep(self, records=None, now=None):
        """Delete blobs no record points at and leftover temporary files. -> bytes reclaimed.
        A pinned blob, or a very new one that a write in progress may be about to record, is left for next time."""
        now = now or self.clock()
        used, freed = self.referenced(records), 0
        for sub in os.listdir(os.path.join(self.root, "blobs")):
            folder = os.path.join(self.root, "blobs", sub)
            for name in os.listdir(folder) if os.path.isdir(folder) else []:
                path = os.path.join(folder, name)
                try:
                    age = now - os.path.getmtime(path)
                    if name.endswith(".tmp"):
                        if age > ORPHAN_AGE:
                            freed += os.path.getsize(path)
                            os.remove(path)
                    elif name not in used and name not in self.pins and age > ORPHAN_AGE:
                        freed += os.path.getsize(path)
                        os.remove(path)
                except OSError:
                    continue
        for d in ("staging", "exports"):
            for dp, _, files in os.walk(os.path.join(self.root, d)):
                for f in files:
                    path = os.path.join(dp, f)
                    try:
                        if now - os.path.getmtime(path) > (ORPHAN_AGE if d == "staging" else 24 * 3600):
                            freed += os.path.getsize(path)
                            os.remove(path)
                    except OSError:
                        continue
        return freed

    def drop(self, digests, records=None):
        """Delete these blobs now if nothing uses them any more. -> bytes reclaimed."""
        used, freed = self.referenced(records), 0
        for d in set(digests):
            if d in used or d in self.pins or not self.has(d):
                continue
            try:
                freed += os.path.getsize(self.blob_path(d))
                os.remove(self.blob_path(d))
            except OSError:
                pass
        return freed


def _size(n):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
