"""Exports: finished files made from a timeline, and the record of each one.

    <data>/audio/exports/<project id>/<export id>.json     what was asked for and how it went
                                      <export id>.<ext>     the file (a .zip for stems)
    <data>/audio/rooms/                                     reverb impulse files, made once per setting

One export runs at a time, in the background; the browser asks how it is going. Exports use the
processor, not the graphics card, so they do not wait for or disturb video renders.
"""
import json
import os
import queue
import re
import shutil
import threading
import time
import zipfile

from . import render, schemas
from .storage import LOCK, _write

KEEP = 30                       # exports kept per project; the oldest are removed beyond this
_SAFE = re.compile(r"[^A-Za-z0-9 _.-]+")


class Exporter:
    def __init__(self, library):
        self.lib = library
        self.root = os.path.join(library.root, "exports")
        self.rooms = os.path.join(library.root, "rooms")
        self.queue, self.running, self.thread = queue.Queue(), {}, None
        self.swept = False

    # ---- records ----
    def _folder(self, project_id):
        self.lib._timeline_path(project_id)                     # refuses anything that is not a project id
        return os.path.join(self.root, project_id)

    def _path(self, project_id, eid):
        if not schemas.valid_id(eid):
            raise ValueError("That is not a valid export.")
        return os.path.join(self._folder(project_id), eid + ".json")

    def _save(self, record):
        _write(self._path(record["project_id"], record["id"]), json.dumps(record, indent=1))
        return record

    def load(self, project_id, eid):
        try:
            with open(self._path(project_id, eid)) as f:
                return json.load(f)
        except OSError:
            raise ValueError("That export is no longer there.")

    def list(self, project_id):
        folder, out = self._folder(project_id), []
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.endswith(".json") and schemas.valid_id(name[:-5]):
                    try:
                        out.append(self.load(project_id, name[:-5]))
                    except ValueError:
                        continue
        for r in out:                                           # left over from before a restart: nothing is working on it now
            if r["state"] in ("waiting", "running") and r["id"] not in self.running:
                r.update(state="stopped", note="The server restarted before this finished.")
                self._save(r)
        return sorted(out, key=lambda r: -r["created"])

    def room(self, size, decay_s, rate=schemas.DEFAULT_RATE):
        with LOCK:
            return render.impulse(self.rooms, size, decay_s, rate)

    # ---- asking for one ----
    def start(self, project_id, options):
        """Queue an export of the project's saved timeline. -> its record."""
        options = options if isinstance(options, dict) else {}
        timeline = self.lib.timeline(project_id)
        fmt = options.get("format") if options.get("format") in render.OUT_FORMATS else "wav"
        if fmt == "mp3" and not render.features()["mp3"]:
            raise ValueError("This server cannot write MP3 files. Choose WAV or FLAC.")
        what = options.get("what") if options.get("what") in ("mix", "stems", "range") else "mix"
        rate = timeline["sample_rate"]
        span = None
        if what == "range":
            first, last = options.get("start"), options.get("end")
            if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (first, last)) or last <= first:
                raise ValueError("Set where the range starts and ends. The end must be after the start.")
            if last - first > schemas.MAX_SECONDS * rate:
                raise ValueError("That range is too long.")
            span = [first, last]
        audible = [t for t in schemas.audible_tracks(timeline) if any(not c["muted"] for c in t["clips"])]
        if not audible and what != "range":
            raise ValueError("There is nothing audible on the timeline to export. Check for muted tracks.")
        name = _SAFE.sub("", str(options.get("name") or "")).strip(" .")[:80] or "mix"
        record = {"id": schemas.new_id(), "project_id": project_id, "name": name, "what": what, "format": fmt,
                  "bits": options.get("bits") if options.get("bits") in render.OUT_FORMATS[fmt][1] else (16 if render.OUT_FORMATS[fmt][1] else None),
                  "kbps": (options.get("kbps") if options.get("kbps") in render.MP3_RATES else 320) if fmt == "mp3" else None,
                  "sample_rate": options.get("sample_rate") if options.get("sample_rate") in render.OUT_RATES else (rate if rate in render.OUT_RATES else 48000),
                  "span": span, "timeline_revision": timeline["revision"], "timeline_rate": rate,
                  "tracks": [{"id": t["id"], "name": t["name"]} for t in audible],
                  "state": "waiting", "progress": 0.0, "note": "", "file": None, "bytes": None, "seconds": None, "peak_db": None,
                  "created": time.time(), "finished": None}
        with LOCK:
            self.running[record["id"]] = {"timeline": timeline}
            self._save(record)
            self.queue.put((project_id, record["id"]))
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._work, daemon=True, name="audio-export")
                self.thread.start()
        return record

    def stop(self, project_id, eid):
        record = self.load(project_id, eid)
        holder = self.running.get(eid)
        if holder is not None and record["state"] in ("waiting", "running"):
            holder["stopped"] = True
            if holder.get("process"):
                holder["process"].terminate()
        return self.load(project_id, eid)

    def remove(self, project_id, eid):
        record = self.load(project_id, eid)
        if record["state"] in ("waiting", "running") and eid in self.running:
            raise ValueError("Stop the export before removing it.")
        self._forget(record)
        return {"removed": eid}

    def _forget(self, record):
        folder = self._folder(record["project_id"])
        for name in (record["id"] + ".json", record.get("file") or ""):
            path = os.path.join(folder, name)
            if name and not os.path.dirname(name) and os.path.isfile(path):
                os.remove(path)
        shutil.rmtree(os.path.join(folder, record["id"] + ".parts"), ignore_errors=True)

    def file(self, project_id, eid):
        record = self.load(project_id, eid)
        name = record.get("file") or ""
        path = os.path.join(self._folder(project_id), name)
        if record["state"] != "done" or not name or os.path.dirname(name) or not os.path.isfile(path):
            raise ValueError("That export has no file.")
        kind = "application/zip" if name.endswith(".zip") else render.OUT_FORMATS[record["format"]][0]
        return path, kind

    # ---- doing the work ----
    def _work(self):
        while True:
            try:
                project_id, eid = self.queue.get(timeout=5)
            except queue.Empty:
                with LOCK:
                    if self.queue.empty():
                        self.thread = None
                        return
                continue
            holder = self.running.get(eid, {})
            try:
                record = self.load(project_id, eid)
                if holder.get("stopped"):
                    raise InterruptedError
                self._make(record, holder)
                record.update(state="done", progress=1.0, finished=time.time())
            except InterruptedError:
                record.update(state="stopped", note="Stopped before it finished.", finished=time.time())
            except (ValueError, OSError) as e:
                record.update(state="failed", note=str(e)[:400], finished=time.time())
            except Exception as e:                                # never leave an export stuck as "running"
                record.update(state="failed", note=f"Something unexpected went wrong: {e}"[:400], finished=time.time())
            if record["state"] != "done":
                folder = self._folder(project_id)
                shutil.rmtree(os.path.join(folder, eid + ".parts"), ignore_errors=True)
                for name in os.listdir(folder) if os.path.isdir(folder) else []:
                    if name.startswith(eid + ".") and not name.endswith(".json"):
                        os.remove(os.path.join(folder, name))
                record["file"] = None
            with LOCK:
                self.running.pop(eid, None)
                self._save(record)
                for old in self.list(project_id)[KEEP:]:
                    self._forget(old)

    def _make(self, record, holder):
        timeline, folder = holder["timeline"], self._folder(record["project_id"])
        rate = timeline["sample_rate"]
        files = {}
        for aid in schemas.assets_used(timeline):
            try:
                facts = self.lib.load(aid)["file"]
                files[aid] = (self.lib.file(aid)[0], facts["format"], facts["channels"] or 2)
            except ValueError:
                raise ValueError("A sound used on the timeline is missing from the library. Remove its clips or add the sound again.")
        room = lambda size, decay: self.room(size, decay, rate)
        ext = record["format"]
        stems = record["tracks"] if record["what"] == "stems" else [None]
        peaks, made = [], []
        parts = os.path.join(folder, record["id"] + ".parts")
        os.makedirs(parts if record["what"] == "stems" else folder, exist_ok=True)

        def report(index):
            last = [0.0]
            def tell(fraction):
                now = (index + fraction) / len(stems)
                if now - last[0] >= 0.02:                        # a save every couple of percent is plenty
                    last[0] = now
                    record.update(state="running", progress=round(now, 3))
                    self._save(record)
            return tell

        record.update(state="running")
        self._save(record)
        for i, track in enumerate(stems):
            if holder.get("stopped"):
                raise InterruptedError
            job = render.build(timeline, files, room, only=track and track["id"], span=record["span"], out_rate=record["sample_rate"])
            if track:
                label = _SAFE.sub("", track["name"]).strip(" .")[:60] or "Track"
                target = os.path.join(parts, f"{i + 1:02d} {label}.{ext}")
            else:
                target = os.path.join(folder, f"{record['id']}.{ext}")
            result = render.run(job, target, ext, record["bits"] or 16, record["kbps"] or 320, report(i), holder)
            peaks.append(result["peak_db"])
            made.append(target)
            record["seconds"] = round(job["samples"] / rate, 6)
        if record["what"] == "stems":
            target = os.path.join(folder, record["id"] + ".zip")
            with zipfile.ZipFile(target + ".tmp", "w", zipfile.ZIP_STORED) as z:      # audio does not shrink; storing is quicker
                for path in made:
                    z.write(path, os.path.basename(path))
            os.replace(target + ".tmp", target)
            shutil.rmtree(parts, ignore_errors=True)
            for track, peak in zip(record["tracks"], peaks):
                track["peak_db"] = peak
        else:
            target = made[0]
        known = [p for p in peaks if p is not None]
        record.update(file=os.path.basename(target), bytes=os.path.getsize(target), peak_db=max(known) if known else None)
        if record["peak_db"] is not None and record["peak_db"] > 0 and record["what"] != "stems":
            record["note"] = f"The mix goes {record['peak_db']:.1f} dB over full level and is clipped there. Lower the master volume by at least that much and export again."
        elif record["what"] == "stems" and known and max(known) > 0:
            record["note"] = "At least one track goes over full level and is clipped there. Lower that track's volume and export again."
