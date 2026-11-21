#!/usr/bin/env python3
"""Storyboard server for the PGX. Standard library only.

Serves the browser page, keeps the project in data/project.json, forwards uploads and
media to ComfyUI, and turns segments into ComfyUI jobs.

  COMFY_URL  ComfyUI address (default http://127.0.0.1:8188)
  PORT       port to listen on (default 8190)
"""
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import workflows

ROOT = os.path.dirname(os.path.abspath(__file__))
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
PORT = int(os.environ.get("PORT", "8190"))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
PROJECT_FILE = os.path.join(DATA_DIR, "project.json")
LOCK = threading.RLock()

EDITABLE = ("name", "start", "end", "type", "begin_image", "end_image", "prompt", "runs", "chosen")
PENDING = ("queued", "running")
COMFY_PORT = urllib.parse.urlsplit(COMFY).port or 8188


def empty_project():
    return {"song": None, "settings": {"width": 832, "height": 480}, "actors": [], "segments": []}


def load_project():
    with LOCK:
        try:
            with open(PROJECT_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return empty_project()


def save_project(project):
    with LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PROJECT_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(project, f, indent=1)
        os.replace(tmp, PROJECT_FILE)


def comfy_json(path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(COMFY + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return {"_http_error": e.code, **json.loads(body)}
        except ValueError:
            return {"_http_error": e.code, "error": body[:500]}


def merge_project(incoming):
    """Apply the browser's edits. Render results stay owned by the server."""
    with LOCK:
        current = load_project()
        old = {s["id"]: s for s in current.get("segments", [])}
        segments = []
        for seg in incoming.get("segments", []):
            sid = seg.get("id") or uuid.uuid4().hex[:8]
            kept = old.get(sid, {})
            out = {"id": sid, "results": kept.get("results", [])}
            for key in EDITABLE:
                out[key] = seg.get(key, kept.get(key))
            out["runs"] = max(1, min(8, int(out.get("runs") or 1)))
            out["type"] = "singing" if out.get("type") == "singing" else "story"
            segments.append(out)
        current["segments"] = segments
        current["song"] = incoming.get("song", current.get("song"))
        current["actors"] = incoming.get("actors", current.get("actors", []))
        current["settings"] = {**current.get("settings", {}), **incoming.get("settings", {})}
        save_project(current)
        return current


def describe_error(entry):
    for kind, info in (entry.get("status", {}).get("messages") or []):
        if kind == "execution_error":
            return f'{info.get("node_type", "node")}: {info.get("exception_message", "failed")}'.strip()[:400]
    return "ComfyUI reported an error."


def collect_files(entry):
    files = []
    for node_out in (entry.get("outputs") or {}).values():
        for value in node_out.values():
            if isinstance(value, list):
                files += [v for v in value if isinstance(v, dict) and v.get("filename")]
    return [{"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")}
            for f in files]


def refresh_statuses():
    """Ask ComfyUI about every unfinished run and record what it says."""
    with LOCK:
        project = load_project()
        pending = [r for s in project["segments"] for r in s.get("results", []) if r.get("status") in PENDING]
        if not pending:
            return project
        try:
            queue = comfy_json("/queue", timeout=10)
        except OSError:
            return project
        running = {item[1] for item in queue.get("queue_running", [])}
        waiting = {item[1] for item in queue.get("queue_pending", [])}
        for res in pending:
            pid = res["prompt_id"]
            if pid in running:
                res["status"] = "running"
                continue
            if pid in waiting:
                res["status"] = "queued"
                continue
            try:
                entry = comfy_json("/history/" + pid, timeout=10).get(pid)
            except OSError:
                continue
            if not entry:
                if time.time() - res.get("created", 0) > 60:
                    res.update(status="error", error="ComfyUI no longer knows this job (it may have restarted).")
                continue
            if entry.get("status", {}).get("status_str") == "error":
                res.update(status="error", error=describe_error(entry))
            else:
                res.update(status="done", files=collect_files(entry), finished=time.time())
        save_project(project)
        return project


def effective_begin(project, seg):
    """A segment with no begin shot starts from the end shot of the segment before it."""
    if seg.get("begin_image"):
        return seg["begin_image"]
    index = project["segments"].index(seg)
    return project["segments"][index - 1].get("end_image") if index > 0 else None


def render_all():
    """Queue every segment's listed runs. Segments that cannot render are reported, not fatal."""
    queued, skipped = 0, []
    for seg in load_project()["segments"]:
        try:
            queued += len(render_segment(seg["id"]))
        except ValueError as e:
            skipped.append({"name": seg.get("name") or "Unnamed segment", "reason": str(e)})
    return {"queued": queued, "skipped": skipped}


def render_segment(segment_id, runs=None):
    with LOCK:
        project = load_project()
        seg = next((s for s in project["segments"] if s["id"] == segment_id), None)
        if seg is None:
            raise ValueError("Segment not found. Save the storyboard and try again.")
        source = dict(seg, begin_image=effective_begin(project, seg))
        song = (project.get("song") or {}).get("filename")
        settings = project.get("settings", {})
        count = max(1, min(8, int(runs or seg.get("runs") or 1)))
        made = []
        for _ in range(count):
            rid = uuid.uuid4().hex[:8]
            seed = random.randint(1, 2**31 - 1)
            prefix = f"storyboard/{workflows.safe_name(seg.get('name'))}_{rid}"
            graph = workflows.build(source, song, seed, width=int(settings.get("width", 832)),
                                    height=int(settings.get("height", 480)), prefix=prefix)
            reply = comfy_json("/prompt", {"prompt": graph, "client_id": "storyboard"})
            if reply.get("_http_error") or reply.get("node_errors") or not reply.get("prompt_id"):
                detail = json.dumps(reply.get("node_errors") or reply.get("error") or reply)
                if "not in" in detail and ".safetensors" in detail:
                    raise ValueError("A model file this shot needs is not on the PGX yet. " + detail[:400])
                raise ValueError("ComfyUI rejected the job: " + detail[:600])
            result = {"id": rid, "prompt_id": reply["prompt_id"], "seed": seed, "status": "queued",
                      "files": [], "created": time.time(), "engine": workflows.engine(seg),
                      "prompt": seg.get("prompt", ""), **workflows.plan(seg)}
            seg.setdefault("results", []).append(result)
            made.append(result)
            save_project(project)
        return made


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def proxy(self, method, path, body=None):
        """Pass a request through to ComfyUI, including Range so media can seek."""
        headers = {k: self.headers[k] for k in ("Content-Type", "Range") if self.headers.get(k)}
        req = urllib.request.Request(COMFY + path, data=body, headers=headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            resp = e
        except OSError as e:
            return self.send_json({"error": f"Cannot reach ComfyUI at {COMFY}: {e}"}, 502)
        data = resp.read()
        self.send_response(resp.status if hasattr(resp, "status") else resp.code)
        for key in ("Content-Type", "Content-Range", "Accept-Ranges", "Content-Disposition"):
            if resp.headers.get(key):
                self.send_header(key, resp.headers[key])
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "static", "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        if url.path == "/api/project":
            return self.send_json(refresh_statuses())
        if url.path == "/api/health":
            try:
                queue = comfy_json("/queue", timeout=5)
                return self.send_json({"comfy": True, "comfy_port": COMFY_PORT, "running": len(queue.get("queue_running", [])),
                                       "waiting": len(queue.get("queue_pending", []))})
            except OSError as e:
                return self.send_json({"comfy": False, "error": str(e)})
        if url.path == "/comfy/view":
            return self.proxy("GET", "/view?" + url.query)
        self.send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        if urllib.parse.urlsplit(self.path).path == "/api/project":
            try:
                return self.send_json(merge_project(json.loads(self.read_body() or b"{}")))
            except (ValueError, TypeError) as e:
                return self.send_json({"error": str(e)}, 400)
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        body = self.read_body()
        if path == "/api/upload":
            return self.proxy("POST", "/upload/image", body)
        try:
            payload = json.loads(body or b"{}")
            if path == "/api/render":
                return self.send_json({"results": render_segment(payload.get("segment_id"), payload.get("runs"))})
            if path == "/api/render_all":
                return self.send_json(render_all())
            if path == "/api/result/delete":
                with LOCK:
                    project = load_project()
                    for seg in project["segments"]:
                        if seg["id"] == payload.get("segment_id"):
                            seg["results"] = [r for r in seg.get("results", []) if r["id"] != payload.get("result_id")]
                            if seg.get("chosen") == payload.get("result_id"):
                                seg["chosen"] = None
                    save_project(project)
                return self.send_json(project)
            if path == "/api/cancel":
                comfy_json("/interrupt", {})
                comfy_json("/queue", {"clear": True})
                return self.send_json({"ok": True})
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        except OSError as e:
            return self.send_json({"error": f"Cannot reach ComfyUI at {COMFY}: {e}"}, 502)
        self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Storyboard on http://0.0.0.0:{PORT}  ->  ComfyUI at {COMFY}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
