"""Identity Studio's own job tracking, and its manners on the shared ComfyUI queue.

SWIFT Director's video renders and Identity Studio share one ComfyUI. The rules here exist so an
identity job can never get in a render's way:

  1. An identity job is handed to ComfyUI only when ComfyUI has nothing running and nothing waiting.
  2. Only one identity job is in ComfyUI at a time; the rest wait here, in jobs.json.
  3. Cancelling an identity job removes or interrupts that job alone. It is interrupted only if it
     is the job ComfyUI is running at that moment; anything else running is left alone.
  4. If a job disappears from ComfyUI without finishing (the host's "Stop all renders" clears the
     whole queue), it is marked stopped and waits for a person to press Retry. It never restarts
     on its own.

Jobs are kept in <data>/identity/jobs.json so they survive a restart. Nothing here knows what a
job's graph draws; a later phase builds graphs and calls Jobs.add().
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from . import schemas

WAITING, SUBMITTED, RUNNING, DONE, FAILED, STOPPED, CANCELLED = (
    "waiting", "submitted", "running", "done", "failed", "stopped", "cancelled")
ACTIVE = (WAITING, SUBMITTED, RUNNING)
IN_COMFY = (SUBMITTED, RUNNING)
KEEP_FINISHED = 200            # finished jobs remembered before the oldest are dropped
CLIENT_ID = "identity-studio"  # not the storyboard's id, so its progress bars never show identity work


class ComfyDown(Exception):
    """ComfyUI could not be reached. Jobs simply keep waiting."""


class Comfy:
    """The few ComfyUI calls the tracker needs. Tests swap in a fake with the same methods."""

    def __init__(self, url=None):
        self.url = (url or os.environ.get("COMFY_URL", "http://127.0.0.1:8188")).rstrip("/")

    def _call(self, path, payload=None, timeout=10):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                return {"_http_error": e.code, **json.loads(body)}
            except ValueError:
                return {"_http_error": e.code, "error": body[:500]}
        except (OSError, ValueError) as e:
            raise ComfyDown(str(e))

    def queue(self):
        """-> (ids running, ids waiting), each a list of prompt ids."""
        q = self._call("/queue")
        pick = lambda rows: [row[1] for row in rows or [] if isinstance(row, list) and len(row) > 1]
        return pick(q.get("queue_running")), pick(q.get("queue_pending"))

    def submit(self, graph):
        reply = self._call("/prompt", {"prompt": graph, "client_id": CLIENT_ID}, timeout=30)
        if not reply.get("prompt_id"):
            err = reply.get("error")
            raise ValueError("ComfyUI refused the job: " + str((err.get("message") if isinstance(err, dict) else err) or reply)[:300])
        return reply["prompt_id"]

    def history(self, prompt_id):
        """-> the finished job's record, or None while it has not finished."""
        return self._call("/history/" + prompt_id).get(prompt_id)

    def remove(self, prompt_id):
        self._call("/queue", {"delete": [prompt_id]})

    def interrupt(self, prompt_id):
        self._call("/interrupt", {"prompt_id": prompt_id})


def _public(job):
    """A job as the browser sees it: everything except the graph."""
    return {k: v for k, v in job.items() if k != "graph"}


class Jobs:
    def __init__(self, root, comfy=None):
        self.path = os.path.join(root, "jobs.json")
        self.comfy = comfy or Comfy()
        self.lock = threading.RLock()
        self.note = ""                # why the next job is waiting, in words for a person
        self._thread = None
        self._jobs = self._read()

    # ---- the file ----
    def _read(self):
        try:
            with open(self.path) as f:
                rows = json.load(f)
            return [j for j in rows if isinstance(j, dict) and schemas.valid_id(j.get("id")) and j.get("state")]
        except (OSError, ValueError):
            return []

    def _write(self):
        finished = [j for j in self._jobs if j["state"] not in ACTIVE]
        for old in finished[:-KEEP_FINISHED] if len(finished) > KEEP_FINISHED else []:
            self._jobs.remove(old)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._jobs, f)
        os.replace(tmp, self.path)

    def _set(self, job, state, **more):
        job.update(state=state, updated=time.time(), **more)

    def _find(self, job_id):
        for j in self._jobs:
            if j["id"] == job_id:
                return j
        raise ValueError("That job no longer exists.")

    # ---- what callers use ----
    def add(self, project_id, kind, label, graph):
        """Queue a job. It goes to ComfyUI when ComfyUI is free. Called by module code, never by the browser."""
        if not schemas.valid_id(project_id):
            raise ValueError("That is not a valid identity project id.")
        if not isinstance(graph, dict) or not graph:
            raise ValueError("A job needs a ComfyUI graph.")
        now = time.time()
        job = {"id": schemas.new_id(), "project_id": project_id, "kind": str(kind)[:40], "label": str(label)[:200],
               "graph": graph, "state": WAITING, "prompt_id": None, "created": now, "updated": now,
               "outputs": [], "error": ""}
        with self.lock:
            self._jobs.append(job)
            self._write()
        self.start()
        return _public(job)

    def list(self, project_id=None):
        with self.lock:
            return [_public(j) for j in self._jobs if project_id is None or j["project_id"] == project_id]

    def active(self):
        with self.lock:
            return sum(1 for j in self._jobs if j["state"] in ACTIVE)

    def cancel(self, job_id):
        with self.lock:
            job = self._find(job_id)
            if job["state"] not in ACTIVE:
                return _public(job)
            if job["state"] in IN_COMFY and job["prompt_id"]:
                try:
                    self.comfy.remove(job["prompt_id"])                 # no effect if it has already started
                    running, _ = self.comfy.queue()
                    if job["prompt_id"] in running:                     # interrupt only our own job
                        self.comfy.interrupt(job["prompt_id"])
                except ComfyDown:
                    pass                                                # ComfyUI is down, so nothing is running there
            self._set(job, CANCELLED)
            self._write()
            return _public(job)

    def retry(self, job_id):
        with self.lock:
            job = self._find(job_id)
            if job["state"] not in (STOPPED, FAILED, CANCELLED):
                raise ValueError("Only a stopped, failed or cancelled job can be retried.")
            self._set(job, WAITING, prompt_id=None, error="", outputs=[])
            self._write()
        self.start()
        return _public(job)

    def cancel_project(self, project_id):
        """Used when an identity project is deleted."""
        for j in self.list(project_id):
            if j["state"] in ACTIVE:
                self.cancel(j["id"])

    # ---- the one step that moves jobs along ----
    def tick(self):
        """Check on the job that is in ComfyUI, then hand over the next one if ComfyUI is idle."""
        with self.lock:
            try:
                running, pending = self.comfy.queue()
            except ComfyDown:
                self.note = "ComfyUI cannot be reached. Identity jobs are waiting for it."
                return
            changed = False
            for job in [j for j in self._jobs if j["state"] in IN_COMFY]:
                pid = job["prompt_id"]
                if pid in running:
                    if job["state"] != RUNNING:
                        self._set(job, RUNNING); changed = True
                    continue
                if pid in pending:
                    continue
                try:
                    record = self.comfy.history(pid)
                except ComfyDown:
                    continue
                if record is None:
                    self._set(job, STOPPED, error="This job was cleared from the render queue before it finished. Press Retry to run it again.")
                elif (record.get("status") or {}).get("status_str") == "error":
                    self._set(job, FAILED, error=_error_text(record))
                else:
                    self._set(job, DONE, outputs=_outputs(record))
                changed = True
            if not any(j["state"] in IN_COMFY for j in self._jobs):
                nxt = next((j for j in self._jobs if j["state"] == WAITING), None)
                if nxt:
                    busy = len(running) + len(pending)
                    if busy:
                        self.note = f"Waiting behind {busy} job{'s' if busy != 1 else ''} already in the render queue."
                    else:
                        try:
                            self._set(nxt, SUBMITTED, prompt_id=self.comfy.submit(nxt["graph"]))
                            self.note = ""
                        except ComfyDown:
                            self.note = "ComfyUI cannot be reached. Identity jobs are waiting for it."
                        except ValueError as e:
                            self._set(nxt, FAILED, error=str(e))
                        changed = True
                else:
                    self.note = ""
            if changed:
                self._write()

    def status(self):
        """For the page: is ComfyUI reachable, how busy is it, and how many identity jobs are in play."""
        with self.lock:
            mine = {j["prompt_id"] for j in self._jobs if j["state"] in IN_COMFY}
            out = {"identity_active": self.active(), "note": self.note}
        try:
            running, pending = self.comfy.queue()
            out.update(comfy=True, other_jobs=len([p for p in running + pending if p not in mine]))
        except ComfyDown:
            out.update(comfy=False, other_jobs=0)
        return out

    # ---- the background checker: runs only while there is something to check ----
    def start(self):
        with self.lock:
            if self._thread and self._thread.is_alive():
                return
            if not self.active():
                return
            self._thread = threading.Thread(target=self._loop, name="identity-jobs", daemon=True)
            self._thread.start()

    def _loop(self):
        while True:
            try:
                self.tick()
            except Exception as e:                      # never let one bad reply end the checker
                self.note = "The job checker hit a problem: " + str(e)[:200]
            with self.lock:
                if not self.active():
                    self._thread = None
                    return
            time.sleep(2)


def _outputs(record):
    """The image files a finished job left in ComfyUI's output folder."""
    files = []
    for node in (record.get("outputs") or {}).values():
        for img in (node or {}).get("images") or []:
            if isinstance(img, dict) and img.get("filename"):
                files.append({"filename": str(img["filename"]), "subfolder": str(img.get("subfolder", "")),
                              "type": str(img.get("type", "output"))})
    return files


def _error_text(record):
    for kind, info in ((record.get("status") or {}).get("messages") or []):
        if kind == "execution_error" and isinstance(info, dict):
            return (str(info.get("node_type", "")) + ": " + str(info.get("exception_message", ""))).strip(": ")[:400]
    return "ComfyUI reported an error for this job."
