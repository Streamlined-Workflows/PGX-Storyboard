#!/usr/bin/env python3
"""Storyboard server for the PGX. Standard library only.

Serves the browser page, keeps each project in data/projects/<id>.json, forwards uploads and
media to ComfyUI, turns segments into ComfyUI jobs, and reports system load.

  COMFY_URL  ComfyUI address (default http://127.0.0.1:8188)
  PORT       port to listen on (default 8190)
"""
import base64
import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import assist
import models
import workflows

ROOT = os.path.dirname(os.path.abspath(__file__))
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
PORT = int(os.environ.get("PORT", "8190"))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
TRASH_DIR = os.path.join(DATA_DIR, "trash")
LEGACY_FILE = os.path.join(DATA_DIR, "project.json")
LOCK = threading.RLock()

EDITABLE = ("name", "start", "end", "type", "begin_image", "end_image", "prompt", "runs", "chosen")
PENDING = ("queued", "running")
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
COMFY_PORT = urllib.parse.urlsplit(COMFY).port or 8188
ASSIST = os.environ.get("ASSIST_URL", "http://127.0.0.1:8191").rstrip("/")


# ---------- projects on disk ----------

def new_id():
    return uuid.uuid4().hex[:8]


def empty_project(name="Untitled project"):
    now = time.time()
    return {"id": new_id(), "name": name, "created": now, "updated": now, "song": None,
            "settings": {"width": 832, "height": 480}, "audio": [], "actors": [], "photos": [], "segments": []}


def project_path(pid):
    if not pid or not all(c.isalnum() for c in pid):
        raise ValueError("Unknown project.")
    return os.path.join(PROJECTS_DIR, pid + ".json")


def normalize(project):
    """Fill in fields that older project files do not have."""
    project.setdefault("name", "Untitled project")
    project.setdefault("created", time.time())
    project.setdefault("updated", project["created"])
    project.setdefault("settings", {"width": 832, "height": 480})
    project.setdefault("segments", [])
    project.setdefault("actors", [])
    project.setdefault("audio", [])
    project.setdefault("photos", [])
    project.setdefault("image_jobs", [])
    if "generated" not in project:          # the Library's record of every picture made here; older projects are rebuilt from what survives
        made = re.compile(r"_[0-9a-f]{8}\.png$")
        found = [{"image": v["image"], "label": f"{a.get('name') or 'Actor'} · {v.get('label') or 'view'}", "kind": "actor_view", "actor_id": a.get("id")}
                 for a in project.get("actors", []) for v in a.get("views", []) if made.search(v.get("image") or "")]
        found += [{"image": ph["image"], "label": ph.get("name") or "Shot", "kind": "shot"}
                  for ph in project.get("photos", []) if made.search(ph.get("image") or "")]
        project["generated"] = [dict(g, id=new_id(), created=None) for g in found]
    if any("views" not in a for a in project["actors"]):
        migrate_actors(project)
    song = project.get("song")
    if song and song.get("filename") and not any(a.get("filename") == song["filename"] for a in project["audio"]):
        project["audio"].append({"id": new_id(), "name": song["filename"], "filename": song["filename"],
                                 "duration": song.get("duration", 0)})
    return project


def migrate_actors(project):
    """Older projects stored one entry per still. An actor is now one character with several views.

    Stills whose names share a first word (pilot_medium, pilot_fullbody) become views of one actor.
    """
    kept, groups = [], {}
    for entry in project["actors"]:
        if "views" in entry:
            kept.append(entry)
        elif entry.get("kind") == "photo":
            project["photos"].append({"id": entry.get("id") or new_id(), "name": entry.get("name", ""), "image": entry["image"]})
        else:
            words = re.split(r"[_\-\s]+", (entry.get("name") or "").strip(), maxsplit=1)
            groups.setdefault(words[0].lower(), []).append((entry, words))
    for items in groups.values():
        shared = len(items) > 1
        first_entry, first_words = items[0]
        actor = {"id": new_id(), "description": "", "views": [],
                 "name": first_words[0].capitalize() if shared and first_words[0] else (first_entry.get("name") or "Actor")}
        for entry, words in items:
            label = re.sub(r"[_\-]+", " ", words[1]).strip() if shared and len(words) > 1 else ""
            actor["views"].append({"id": entry.get("id") or new_id(), "image": entry["image"], "label": label})
        kept.append(actor)
    project["actors"] = kept


def load_project(pid):
    with LOCK:
        try:
            with open(project_path(pid)) as f:
                return normalize(json.load(f))
        except OSError:
            raise ValueError("That project no longer exists.")


def save_project(project, touch=True):
    with LOCK:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        if touch:
            project["updated"] = time.time()
        path = project_path(project["id"])
        with open(path + ".tmp", "w") as f:
            json.dump(project, f, indent=1)
        os.replace(path + ".tmp", path)
        return project


def migrate_legacy():
    """Move the single-project file from version 1 into the projects folder."""
    with LOCK:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        if os.path.exists(LEGACY_FILE) and not os.listdir(PROJECTS_DIR):
            try:
                with open(LEGACY_FILE) as f:
                    old = json.load(f)
                project = {**empty_project("My first project"), **old}
                save_project(normalize(project))
                os.replace(LEGACY_FILE, LEGACY_FILE + ".migrated")
            except (OSError, ValueError):
                pass


def list_projects():
    with LOCK:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        out = []
        for name in os.listdir(PROJECTS_DIR):
            if not name.endswith(".json"):
                continue
            try:
                p = load_project(name[:-5])
            except ValueError:
                continue
            clips = [r for s in p["segments"] for r in s.get("results", []) if r.get("status") == "done"]
            thumb = next((s.get("begin_image") for s in p["segments"] if s.get("begin_image")), None)
            out.append({"id": p["id"], "name": p["name"], "created": p["created"], "updated": p["updated"],
                        "segments": len(p["segments"]), "clips": len(clips), "assets": sum(len(a.get("views", [])) for a in p["actors"]) + len(p["photos"]) + len(p["audio"]),
                        "song": (p.get("song") or {}).get("filename"), "thumb": thumb or next((v["image"] for a in p["actors"] for v in a.get("views", [])), None)})
        return sorted(out, key=lambda p: -p["updated"])


def everything():
    """Assets and finished clips of every project, for the All view in Assets and Library."""
    out = []
    for info in list_projects():
        try:
            p = load_project(info["id"])
        except ValueError:
            continue
        clips = [{"segment": s.get("name") or "Segment", "segment_id": s["id"], "chosen": s.get("chosen") == r["id"],
                  "id": r["id"], "files": r.get("files", []), "engine": r.get("engine", ""),
                  "finished": r.get("finished") or r.get("created")}
                 for s in p["segments"] for r in s.get("results", []) if r.get("status") == "done" and r.get("files")]
        out.append({"id": p["id"], "name": p["name"], "actors": p["actors"], "photos": p["photos"], "audio": p["audio"], "clips": clips,
                    "images": p.get("generated", [])})
    return out


def merge_project(pid, incoming):
    """Apply the browser's edits. Render results stay owned by the server."""
    with LOCK:
        current = load_project(pid)
        old = {s["id"]: s for s in current.get("segments", [])}
        segments = []
        for seg in incoming.get("segments", []):
            sid = seg.get("id") or new_id()
            kept = old.get(sid, {})
            out = {"id": sid, "results": kept.get("results", [])}
            for key in EDITABLE:
                out[key] = seg.get(key, kept.get(key))
            out["runs"] = max(1, min(8, int(out.get("runs") or 1)))
            out["type"] = "singing" if out.get("type") == "singing" else "story"
            if out["type"] == "singing":
                out["end_image"] = None                 # the lip sync engine only takes a start image
            segments.append(out)
        current["segments"] = segments
        for key in ("song", "actors", "audio", "photos"):
            if key in incoming:
                current[key] = incoming[key]
        if incoming.get("name"):
            current["name"] = str(incoming["name"])[:80]
        current["settings"] = {**current.get("settings", {}), **incoming.get("settings", {})}
        return save_project(normalize(current))


# ---------- ComfyUI ----------

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


def comfy_bytes(path, timeout=60):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as r:
        return r.read()


def import_output(file, name):
    """Copy a generated image from ComfyUI's output folder into its input folder so shots can use it."""
    data = comfy_bytes("/view?" + urllib.parse.urlencode({"filename": file["filename"], "subfolder": file.get("subfolder", ""),
                                                         "type": file.get("type", "output")}))
    boundary = "----storyboard" + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f'Content-Type: image/png\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(COMFY + "/upload/image", data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def refresh_statuses(pid):
    """Ask ComfyUI about every unfinished clip and still in a project and record what it says."""
    with LOCK:
        project = load_project(pid)
        released = release_waiting(project)
        clips = [r for s in project["segments"] for r in s.get("results", []) if r.get("status") in PENDING]
        stills = [j for j in project["image_jobs"] if j.get("status") in PENDING]
        if not clips and not stills:
            return save_project(project, touch=False) if released else project
        try:
            queue = comfy_json("/queue", timeout=10)
        except OSError:
            return project
        running = {item[1] for item in queue.get("queue_running", [])}
        waiting = {item[1] for item in queue.get("queue_pending", [])}
        for res in clips + stills:
            pid_ = res["prompt_id"]
            if pid_ in running:
                res["status"] = "running"
                continue
            if pid_ in waiting:
                res["status"] = "queued"
                continue
            try:
                entry = comfy_json("/history/" + pid_, timeout=10).get(pid_)
            except OSError:
                continue
            if not entry:
                if time.time() - res.get("created", 0) > 60:
                    res.update(status="error", error="ComfyUI no longer knows this job (it may have restarted).")
                continue
            if entry.get("status", {}).get("status_str") == "error":
                res.update(status="error", error=describe_error(entry))
                continue
            files = collect_files(entry)
            if res in stills:
                picture = next((f for f in files if f["filename"].lower().endswith((".png", ".jpg", ".jpeg", ".webp"))), None)
                if not picture:
                    res.update(status="error", error="ComfyUI finished but returned no image.")
                    continue
                try:
                    res.update(status="done", image=import_output(picture, res.get("save_as") or picture["filename"]),
                               finished=time.time())
                    actor = next((a for a in project.get("actors", []) if a.get("id") == res.get("actor_id")), None)
                    project["generated"].append({
                        "id": res["id"], "image": res["image"], "kind": res.get("kind"), "created": res["finished"], "seed": res.get("seed"),
                        "actor_id": res.get("actor_id"), "segment_id": res.get("segment_id"), "source": res.get("source"), "fix": res.get("fix"),
                        "label": f"{actor.get('name') or 'Actor'} · {res.get('label')}" if actor else res.get("label") or "Picture"})
                except (OSError, ValueError, KeyError) as e:
                    res.update(status="error", error=f"Could not save the generated image: {e}")
            else:
                pictures = [f for f in files if f["filename"].lower().endswith(IMAGE_TYPES)]
                res.update(status="done", files=[f for f in files if f not in pictures] or files, finished=time.time())
                if pictures:                # the clip's final frame, kept so the next segment can continue from it
                    try:
                        res["last_image"] = import_output(pictures[0], pictures[0]["filename"])
                    except (OSError, ValueError, KeyError):
                        res["last_frame"] = pictures[0]
        return save_project(project, touch=False)


# ---------- actors: describe from images, generate views ----------

def find_actor(project, actor_id):
    actor = next((a for a in project["actors"] if a.get("id") == actor_id), None)
    if actor is None:
        raise ValueError("That actor was not found. Save and try again.")
    return actor


def actor_describe(pid, actor_id):
    actor = find_actor(load_project(pid), actor_id)
    views = [v["image"] for v in actor.get("views", [])][:4]
    if not views:
        raise ValueError("Add at least one view of this actor first.")
    images = []
    for image in views:
        try:
            images.append(base64.b64encode(comfy_bytes("/view?" + urllib.parse.urlencode({"filename": image, "type": "input"}))).decode())
        except OSError as e:
            raise ValueError(f"Could not read the view {image} from the PGX: {e}")
    return {"description": assist.describe_actor(actor.get("name", ""), images)}


def actor_generate(pid, actor_id, refs=None, views=None, extra=""):
    """Queue stills of an actor. `views` names the framings (default: the three standard ones). `refs` names which of
    the actor's pictures to use as references (default: the first three); an empty list means description only. `extra` is a one-off addition to the description."""
    with LOCK:
        project = load_project(pid)
        actor = find_actor(project, actor_id)
        description = (actor.get("description") or "").strip()
        own = [v["image"] for v in actor.get("views", [])]
        refs = own[:3] if refs is None else [r for r in refs if r in own][:4]
        wanted = [v for v in (views or assist.STANDARD_VIEWS) if v in dict(assist.VIEW_FRAMINGS)]
        if not wanted:
            raise ValueError("Choose which view to generate.")
        extra = str(extra or "").strip()[:600]
        if not description and not refs and not extra:
            raise ValueError("Write a description for this actor first, or add a view of them.")
        threading.Thread(target=assist.unload, daemon=True).start()
        made = []
        for label, framing in assist.VIEW_FRAMINGS:
            if label not in wanted:
                continue
            stem = f"{workflows.safe_name(actor.get('name') or 'actor')}_{workflows.safe_name(label)}"
            made.append(queue_still(project, assist.view_prompt(description, framing, bool(refs), extra), refs, stem,
                                    kind="actor_view", actor_id=actor_id, label=label))
        return {"jobs": made}


def image_fix(pid, image, mask, text, width, height, label):
    """Queue an inpaint: repaint the masked area of `image` as `text` describes. The original is kept."""
    text = str(text or "").strip()[:800]
    if not image or not mask:
        raise ValueError("Paint over the area to fix first.")
    if not text:
        raise ValueError("Describe what the painted area should look like.")
    with LOCK:
        project = load_project(pid)
        actor = next((a for a in project.get("actors", []) if any(v.get("image") == image for v in a.get("views", []))), None)
        view = next((v for v in actor["views"] if v.get("image") == image), {}) if actor else {}
        label = (view.get("label") or str(label or "Picture"))[:60].replace(" (fixed)", "") + " (fixed)"
        prompt = (f"{text.rstrip('.')}. Only this part of the picture changes. It blends seamlessly with the rest of the image: "
                  "the same character, art style, lighting and colours as the reference image, no visible seam, no text.")
        threading.Thread(target=assist.unload, daemon=True).start()
        graph = lambda seed, prefix: workflows.build_fix(image, mask, prompt, seed, int(width or 1248), int(height or 720), prefix)
        stem = f"{workflows.safe_name((actor or {}).get('name') or 'picture')}_{workflows.safe_name(label)}"
        return {"job": queue_still(project, prompt, [], stem, graph=graph, kind="fix", source=image, label=label,
                                   actor_id=actor["id"] if actor else None, fix=text)}


def queue_still(project, prompt, refs, stem, graph=None, **fields):
    """Queue one FLUX.2 image and record it on the project. Call with LOCK held. `graph(seed, prefix)` overrides the standard graph."""
    rid = new_id()
    seed = random.randint(1, 2**31 - 1)
    stem = f"{stem}_{rid}"
    prefix = f"storyboard/{project['id']}/stills/{stem}"
    graph = graph(seed, prefix) if graph else workflows.build_image(prompt, refs, seed, prefix=prefix)
    reply = comfy_json("/prompt", {"prompt": graph, "client_id": "storyboard"})
    if reply.get("_http_error") or reply.get("node_errors") or not reply.get("prompt_id"):
        detail = json.dumps(reply.get("node_errors") or reply.get("error") or reply)
        if "not in" in detail and ".safetensors" in detail:
            raise ValueError("The FLUX.2 image model files are not on the PGX yet. " + detail[:300])
        raise ValueError("ComfyUI rejected the image job: " + detail[:500])
    job = {"id": rid, "prompt_id": reply["prompt_id"], "status": "queued", "seed": seed, "created": time.time(),
           "save_as": stem + ".png", "steps": workflows.IMAGE_STEPS, "passes": 1, **fields}
    project["image_jobs"].append(job)
    save_project(project, touch=False)
    return job


def generated_remove(pid, gid):
    """Take a picture out of the Library list. The file itself, and any actor or shot using it, are left alone."""
    with LOCK:
        project = load_project(pid)
        project["generated"] = [g for g in project.get("generated", []) if g.get("id") != gid]
        save_project(project, touch=False)
        return {"generated": project["generated"]}


def image_jobs_clear(pid, ids):
    with LOCK:
        project = load_project(pid)
        project["image_jobs"] = [j for j in project["image_jobs"] if j["id"] not in set(ids or [])]
        return save_project(project, touch=False)


def resolve_begin(project, seg):
    """Where a segment starts: (image, None), or (None, why it has to wait).

    A segment with its own begin shot is a new angle and uses that picture. A segment without one continues from the
    segment before it: from that segment's end shot if it has one, otherwise from the last frame of the clip you
    picked there. Until a clip is picked, the segment waits.
    """
    if seg.get("begin_image"):
        return seg["begin_image"], None
    index = project["segments"].index(seg)
    if index == 0:
        return None, None
    prev = project["segments"][index - 1]
    name = prev.get("name") or f"segment {index}"
    if prev.get("type") != "singing" and prev.get("end_image"):
        return prev["end_image"], None
    picked = next((r for r in prev.get("results", []) if r.get("id") == prev.get("chosen") and r.get("status") == "done"), None)
    if not picked:
        return None, f'Waiting for you to pick a clip on "{name}". This segment continues from its last frame.'
    if not picked.get("last_image") and picked.get("last_frame"):
        picked["last_image"] = import_output(picked["last_frame"], picked["last_frame"]["filename"])
    if not picked.get("last_image"):
        raise ValueError(f'The clip picked on "{name}" was made before the storyboard kept last frames. Render "{name}" again '
                         "and pick a new clip, or give this segment its own begin shot.")
    return picked["last_image"], None


def queue_clip(project, seg, begin, rid):
    """Send one render of a segment to ComfyUI and return the fields that describe the queued job."""
    seed = random.randint(1, 2**31 - 1)
    settings = project.get("settings", {})
    prefix = f"storyboard/{project['id']}/{workflows.safe_name(seg.get('name'))}_{rid}"
    graph = workflows.build(dict(seg, begin_image=begin), (project.get("song") or {}).get("filename"), seed,
                            width=int(settings.get("width", 832)), height=int(settings.get("height", 480)), prefix=prefix)
    reply = comfy_json("/prompt", {"prompt": graph, "client_id": "storyboard"})
    if reply.get("_http_error") or reply.get("node_errors") or not reply.get("prompt_id"):
        detail = json.dumps(reply.get("node_errors") or reply.get("error") or reply)
        if "not in" in detail and ".safetensors" in detail:
            raise ValueError("A model file this shot needs is not on the PGX yet. " + detail[:400])
        raise ValueError("ComfyUI rejected the job: " + detail[:600])
    return {"prompt_id": reply["prompt_id"], "seed": seed, "status": "queued", "created": time.time(),
            "engine": workflows.engine(seg), "prompt": seg.get("prompt", ""), "begin": begin, **workflows.plan(seg)}


def release_waiting(project):
    """Start any held renders whose starting picture is now known. Returns True if anything changed. Call with LOCK held."""
    changed = False
    for seg in project["segments"]:
        held = [r for r in seg.get("results", []) if r.get("status") == "waiting"]
        if not held:
            continue
        try:
            begin, wait = resolve_begin(project, seg)
            if wait:
                if any(r.get("wait") != wait for r in held):
                    for r in held:
                        r["wait"] = wait
                    changed = True
                continue
            for r in held:
                r.update(queue_clip(project, seg, begin, r["id"]))
                r.pop("wait", None)
        except (ValueError, OSError) as e:
            for r in held:
                if r.get("status") == "waiting":
                    r.update(status="error", error=str(e))
        changed = True
    return changed


def render_all(pid):
    """Queue every segment's listed runs. Segments that cannot render are reported, not fatal."""
    queued, skipped = 0, []
    for seg in load_project(pid)["segments"]:
        try:
            queued += len(render_segment(pid, seg["id"], hold=False))
        except ValueError as e:
            skipped.append({"name": seg.get("name") or "Unnamed segment", "reason": str(e)})
    return {"queued": queued, "skipped": skipped}


def render_segment(pid, segment_id, runs=None, hold=True):
    """Queue a segment's runs. With hold=False (overnight batches) a segment that would have to wait is skipped instead."""
    with LOCK:
        project = load_project(pid)
        seg = next((s for s in project["segments"] if s["id"] == segment_id), None)
        if seg is None:
            raise ValueError("Segment not found. Save the storyboard and try again.")
        begin, wait = resolve_begin(project, seg)
        if not begin and not wait:
            raise ValueError("This segment has no begin shot yet.")
        if wait and not hold:
            index = project["segments"].index(seg)
            raise ValueError(f'continues from "{project["segments"][index - 1].get("name") or "the segment before it"}", which has no picked clip yet')
        threading.Thread(target=assist.unload, daemon=True).start()      # give the language model's memory back
        count = max(1, min(8, int(runs or seg.get("runs") or 1)))
        made = []
        for _ in range(count):
            rid = new_id()
            if wait:
                result = {"id": rid, "status": "waiting", "wait": wait, "files": [], "created": time.time(),
                          "engine": workflows.engine(seg), "prompt": seg.get("prompt", ""), **workflows.plan(seg)}
            else:
                result = {"id": rid, "files": [], **queue_clip(project, seg, begin, rid)}
            seg.setdefault("results", []).append(result)
            made.append(result)
            save_project(project)
        return made


def cancel_waiting(pid):
    with LOCK:
        project = load_project(pid)
        for seg in project["segments"]:
            seg["results"] = [r for r in seg.get("results", []) if r.get("status") != "waiting"]
        save_project(project, touch=False)


# ---------- Full Assist ----------

def assist_service(path, payload=None, timeout=15):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(ASSIST + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except OSError as e:
        raise ValueError(f"The song analysis service is not running on the PGX ({e}). Run ~/PGX-Storyboard/run.sh to start it.")


def song_key(project):
    song = (project.get("song") or {}).get("filename")
    if not song:
        raise ValueError("Choose a song for this project first.")
    return f"{project['id']}:{song}", song


def assist_analyze(pid):
    with LOCK:
        project = load_project(pid)
        key, song = song_key(project)
        if project.get("assist"):
            project["assist"]["analysis_key"] = None          # a fresh run replaces the stored result
            save_project(project, touch=False)
    url = COMFY + "/view?" + urllib.parse.urlencode({"filename": song, "type": "input"})
    return assist_service("/analyze", {"key": key, "url": url})


def assist_status(pid):
    """Poll the analysis job; when it finishes, store its result in the project."""
    project = load_project(pid)
    key, _ = song_key(project)
    stored = (project.get("assist") or {}).get("analysis_key") == key
    job = assist_service("/status?" + urllib.parse.urlencode({"key": key}))
    state = job.get("state", "none")
    if state == "done" and not stored:
        with LOCK:
            project = load_project(pid)
            result = dict(job["result"])
            lines = result.pop("lines", [])
            project["assist"] = {"analysis": result, "analysis_key": key, "lines": lines}
            save_project(project, touch=False)
    elif state == "none" and stored:
        state = "done"
    return {"state": state, "progress": job.get("progress", ""), "error": job.get("error")}


def assist_data(project, need_lines=False):
    data = project.get("assist") or {}
    if not data.get("analysis"):
        raise ValueError("Analyze the song first.")
    return data


def update_assist(pid, **changes):
    with LOCK:
        project = load_project(pid)
        project.setdefault("assist", {}).update(changes)
        return save_project(project, touch=False)


def assist_split(pid):
    data = assist_data(load_project(pid))
    cuts = assist.propose_cuts(data["analysis"], data.get("lines", []))
    return update_assist(pid, split=assist.name_and_merge(data["analysis"], data.get("lines", []), cuts))


def assist_apply_split(pid):
    with LOCK:
        project = load_project(pid)
        split = (project.get("assist") or {}).get("split")
        if not split:
            raise ValueError("Propose segments first.")
        project["segments"] = [{"id": new_id(), "name": s.get("name") or f"Segment {i + 1}", "start": s["start"], "end": s["end"],
                                "type": s.get("type", "story"), "begin_image": None, "end_image": None, "prompt": "",
                                "runs": 2, "chosen": None, "results": []} for i, s in enumerate(split)]
        project["assist"].pop("story_draft", None)
        project["assist"].pop("story", None)
        project["assist"].pop("shots", None)
        return save_project(project)


def assist_story(pid, direction, style, another):
    project = load_project(pid)
    data = assist_data(project)
    if not project["segments"]:
        raise ValueError("Put segments on the storyboard first (step 2).")
    previous = (data.get("story_draft") or {}).get("logline") if another else None
    draft = assist.write_story(data["analysis"], data.get("lines", []), project["segments"], direction or "", style or "", previous)
    draft["segment_ids"] = [s["id"] for s in project["segments"]]
    return update_assist(pid, story_draft=draft)


def assist_approve_story(pid, fill_prompts):
    with LOCK:
        project = load_project(pid)
        draft = (project.get("assist") or {}).get("story_draft")
        if not draft:
            raise ValueError("Write a story concept first.")
        project["assist"]["story"] = draft
        if fill_prompts:
            beats = dict(zip(draft.get("segment_ids", []), draft.get("beats", [])))
            for seg in project["segments"]:
                if not (seg.get("prompt") or "").strip() and beats.get(seg["id"]):
                    seg["prompt"] = beats[seg["id"]]
        return save_project(project)


def approved_story(project):
    story = (project.get("assist") or {}).get("story")
    if not story:
        raise ValueError("Approve a story concept first (step 3).")
    return story


def cast_members(project):
    """The chosen actors, with the role each plays: [{"name", "role", "description", "views"}]."""
    actors = {a["id"]: a for a in project.get("actors", [])}
    out = []
    for entry in (project.get("assist") or {}).get("cast", []):
        actor = actors.get(entry.get("actor_id"))
        if actor:
            out.append({"name": actor.get("name") or "Actor", "role": entry.get("role") or "",
                        "description": actor.get("description") or "", "views": actor.get("views", [])})
    return out


def assist_cast_save(pid, cast):
    with LOCK:
        project = load_project(pid)
        known = {a["id"] for a in project.get("actors", [])}
        clean = [{"actor_id": c["actor_id"], "role": str(c.get("role") or "")[:300]} for c in cast or []
                 if isinstance(c, dict) and c.get("actor_id") in known]
        return update_assist(pid, cast=clean)


def assist_recommend_cast(pid):
    project = load_project(pid)
    data = assist_data(project)
    ideas = assist.recommend_cast(approved_story(project), data["analysis"], data.get("lines", []), project["segments"],
                                  [a.get("name") for a in project.get("actors", []) if a.get("name")])
    if not ideas:
        raise ValueError("The language model did not suggest anyone. Try again.")
    return update_assist(pid, cast_ideas=ideas)


def assist_shots(pid):
    project = load_project(pid)
    data = assist_data(project)
    if not project["segments"]:
        raise ValueError("Put segments on the storyboard first (step 2).")
    story = approved_story(project)
    shots = assist.write_shots(story, data["analysis"], data.get("lines", []), project["segments"], cast_members(project))
    for seg, end in zip(project["segments"], shots["ends"]):
        end["segment_id"] = seg["id"]
    old = (load_project(pid).get("assist") or {}).get("shots") or {}       # locked frames survive a rewrite, words and all
    if (old.get("first") or {}).get("locked"):
        shots["first"] = old["first"]
        if shots["ends"]:
            shots["ends"][0]["begin"] = old["first"]
    kept = {e.get("segment_id"): e for e in old.get("ends", [])}
    for end in shots["ends"]:
        was = kept.get(end["segment_id"]) or {}
        if was.get("locked"):
            end.update(text=was.get("text", ""), who=was.get("who", []), locked=True)
        if (was.get("begin") or {}).get("locked") and end is not shots["ends"][0]:
            end.update(start="new", begin=was["begin"])
    return update_assist(pid, shots=shots)


def assist_shots_save(pid, shots):
    with LOCK:
        project = load_project(pid)
        current = (project.get("assist") or {}).get("shots")
        if not current or not isinstance(shots, dict):
            raise ValueError("Write the shots first.")
        current["first"]["text"] = str((shots.get("first") or {}).get("text", current["first"]["text"]))[:1500]
        current["first"]["locked"] = bool((shots.get("first") or {}).get("locked", current["first"].get("locked")))
        edits = {e.get("segment_id"): e for e in shots.get("ends", []) if isinstance(e, dict)}
        for end in current["ends"]:
            edit = edits.get(end.get("segment_id"))
            if edit:
                end["text"] = str(edit.get("text", end["text"]))[:1500]
                if edit.get("start") in ("new", "continue"):
                    end["start"] = edit["start"]
                end.setdefault("begin", {"text": "", "who": []})
                end["begin"]["text"] = str((edit.get("begin") or {}).get("text", end["begin"].get("text", "")))[:1500]
                end["locked"] = bool(edit.get("locked", end.get("locked")))
                end["begin"]["locked"] = bool((edit.get("begin") or {}).get("locked", end["begin"].get("locked")))
        return update_assist(pid, shots=current)


def assist_shot_images(pid, targets):
    """Queue key frame images. `targets` lists "first", "begin:<segment id>" and segment ids (end frames); None means every frame."""
    with LOCK:
        project = load_project(pid)
        story = approved_story(project)
        shots = (project.get("assist") or {}).get("shots")
        if not shots:
            raise ValueError("Write the shots first.")
        cast = {c["name"]: c for c in cast_members(project)}
        segments = {s["id"]: s for s in project["segments"]}
        if not project["segments"]:
            raise ValueError("There are no segments on the storyboard.")
        plan = [("first", project["segments"][0], "begin_image", shots["first"], "Opening frame")]
        for i, e in enumerate(shots["ends"]):
            seg = segments.get(e.get("segment_id"))
            if seg and seg is not project["segments"][0] and e.get("start") == "new":      # a new scene opens on its own picture
                plan.append(("begin:" + seg["id"], seg, "begin_image", e.get("begin") or {}, f"{seg.get('name') or 'Segment'} begin"))
            plan.append((e.get("segment_id"), seg, "end_image", e, None))
        busy = {(j.get("segment_id"), j.get("slot")) for j in project["image_jobs"] if j.get("kind") == "shot" and j.get("status") in PENDING}
        threading.Thread(target=assist.unload, daemon=True).start()
        made = []
        for key, seg, slot, shot, label in plan:
            if seg and slot == "end_image" and seg.get("type") == "singing":
                continue                    # singing clips have no end shot
            if targets is None and shot.get("locked"):
                continue                    # locked pictures are kept when everything else is regenerated
            if not seg or not (shot.get("text") or "").strip() or (targets is not None and key not in targets) or (seg["id"], slot) in busy:
                continue
            people = [cast[n] for n in shot.get("who", []) if n in cast and cast[n]["views"]][:4]
            refs = [next((v for v in c["views"] if "waist" in (v.get("label") or "").lower()), c["views"][0])["image"] for c in people]
            label = label or f"{seg.get('name') or 'Segment'} end"
            project["image_jobs"] = [j for j in project["image_jobs"] if not (j.get("kind") == "shot" and j.get("status") == "error"
                                                                           and j.get("segment_id") == seg["id"] and j.get("slot") == slot)]
            made.append(queue_still(project, assist.shot_prompt(shot["text"], story.get("style", ""), people), refs,
                                    workflows.safe_name(label), kind="shot", segment_id=seg["id"], slot=slot, label=label))
        if not made:
            raise ValueError("Nothing to generate: those frames are already being made, or have no description.")
        return {"jobs": made}


# ---------- system status ----------

def cpu_percent(interval=0.25):
    def snap():
        with open("/proc/stat") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return idle, sum(parts)
    try:
        idle1, total1 = snap()
        time.sleep(interval)
        idle2, total2 = snap()
        span = total2 - total1
        return round(100.0 * (1 - (idle2 - idle1) / span), 1) if span else 0.0
    except (OSError, ValueError, IndexError):
        return None


def memory_info():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0]) * 1024
        total, free = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
        return {"total": total, "used": total - free, "percent": round(100.0 * (total - free) / total, 1)}
    except (OSError, ValueError, KeyError, IndexError):
        return None


def gpu_info():
    """GPU load from nvidia-smi. Returns None when the tool is not available in this container."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,power.draw",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        name, util, temp, power = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")][:4]

        def num(value):
            try:
                return float(value)
            except ValueError:
                return None
        return {"name": name, "percent": num(util), "temperature": num(temp), "power": num(power)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def system_status():
    started = time.time()
    try:
        queue = comfy_json("/queue", timeout=5)
        comfy = {"ok": True, "ms": round((time.time() - started) * 1000),
                 "running": len(queue.get("queue_running", [])), "waiting": len(queue.get("queue_pending", []))}
    except OSError as e:
        comfy = {"ok": False, "error": str(e)}
    try:
        disk = shutil.disk_usage(ROOT)
        disk = {"total": disk.total, "used": disk.used, "percent": round(100.0 * disk.used / disk.total, 1)}
    except OSError:
        disk = None
    try:
        with open("/proc/loadavg") as f:
            load = float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        load = None
    return {"comfy": comfy, "cpu": {"percent": cpu_percent(), "cores": os.cpu_count(), "load": load},
            "memory": memory_info(), "gpu": gpu_info(), "disk": disk, "time": time.time()}


# ---------- HTTP ----------

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
        query = urllib.parse.parse_qs(url.query)
        try:
            if url.path.startswith("/static/"):            # the SWIFT tokens, logo and fonts
                kinds = {".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2"}
                base = os.path.join(ROOT, "static")
                path = os.path.realpath(os.path.join(base, urllib.parse.unquote(url.path[len("/static/"):])))
                kind = kinds.get(os.path.splitext(path)[1].lower())
                if not kind or not path.startswith(base + os.sep) or not os.path.isfile(path):
                    return self.send_error(404)
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=3600")
                self.end_headers()
                return self.wfile.write(body)
            if url.path in ("/", "/index.html"):
                with open(os.path.join(ROOT, "static", "index.html"), "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return self.wfile.write(body)
            if url.path == "/api/projects":
                return self.send_json({"projects": list_projects()})
            if url.path == "/api/all":
                return self.send_json({"projects": everything()})
            if url.path == "/api/project":
                return self.send_json(refresh_statuses(query.get("id", [""])[0]))
            if url.path == "/api/ping":
                return self.send_json({"ok": True, "time": time.time()})
            if url.path == "/api/system":
                return self.send_json(system_status())
            if url.path == "/api/models":
                return self.send_json(models.listing())
            if url.path == "/api/assist/status":
                return self.send_json(assist_status(query.get("project", [""])[0]))
            if url.path == "/api/assist/health":
                try:
                    service = assist_service("/health", timeout=4)
                except ValueError as e:
                    service = {"ok": False, "error": str(e)}
                return self.send_json({"llm": assist.status(), "service": service})
            if url.path == "/api/health":
                try:
                    queue = comfy_json("/queue", timeout=5)
                    return self.send_json({"comfy": True, "comfy_port": COMFY_PORT,
                                           "running": len(queue.get("queue_running", [])),
                                           "waiting": len(queue.get("queue_pending", []))})
                except OSError as e:
                    return self.send_json({"comfy": False, "comfy_port": COMFY_PORT, "error": str(e)})
            if url.path == "/comfy/view":
                return self.proxy("GET", "/view?" + url.query)
        except ValueError as e:
            return self.send_json({"error": str(e)}, 404)
        self.send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/api/project":
            try:
                pid = urllib.parse.parse_qs(url.query).get("id", [""])[0]
                return self.send_json(merge_project(pid, json.loads(self.read_body() or b"{}")))
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
            pid = payload.get("project")
            if path == "/api/models/check":
                return self.send_json(models.start_check())
            if path == "/api/models/token":
                return self.send_json(models.set_token(payload.get("token")))
            if path == "/api/models/forget_token":
                return self.send_json(models.forget_token())
            if path == "/api/models/update":
                return self.send_json(models.start_update(payload.get("id")))
            if path == "/api/projects":
                return self.send_json(save_project(empty_project(str(payload.get("name") or "Untitled project")[:80])))
            if path == "/api/projects/duplicate":
                with LOCK:
                    copy = load_project(payload.get("id"))
                    copy.update(id=new_id(), name=(copy["name"] + " copy")[:80], created=time.time())
                    for seg in copy["segments"]:          # the copy keeps finished clips, drops unfinished jobs
                        seg["results"] = [r for r in seg.get("results", []) if r.get("status") == "done"]
                    return self.send_json(save_project(copy))
            if path == "/api/projects/delete":
                with LOCK:
                    os.makedirs(TRASH_DIR, exist_ok=True)
                    src = project_path(payload.get("id"))
                    if not os.path.exists(src):
                        raise ValueError("That project no longer exists.")
                    os.replace(src, os.path.join(TRASH_DIR, f"{payload['id']}-{int(time.time())}.json"))
                return self.send_json({"ok": True})
            if path == "/api/actor/describe":
                return self.send_json(actor_describe(pid, payload.get("actor_id")))
            if path == "/api/actor/generate":
                return self.send_json(actor_generate(pid, payload.get("actor_id"), payload.get("refs"), payload.get("views"), payload.get("extra")))
            if path == "/api/image/fix":
                return self.send_json(image_fix(pid, payload.get("image"), payload.get("mask"), payload.get("prompt"),
                                                payload.get("width"), payload.get("height"), payload.get("label")))
            if path == "/api/generated/remove":
                return self.send_json(generated_remove(pid, payload.get("id")))
            if path == "/api/image_jobs/clear":
                return self.send_json(image_jobs_clear(pid, payload.get("ids")))
            if path == "/api/assist/analyze":
                return self.send_json(assist_analyze(pid))
            if path == "/api/assist/lyrics":
                lines = [{"start": float(l["start"]), "end": float(l["end"]), "text": str(l["text"])[:300]}
                         for l in payload.get("lines", []) if str(l.get("text", "")).strip()]
                return self.send_json(update_assist(pid, lines=lines))
            if path == "/api/assist/align":
                data = assist_data(load_project(pid))
                if not data.get("lines"):
                    raise ValueError("There is no transcription to match the lyrics against.")
                return self.send_json(update_assist(pid, lines=assist.align_lyrics(data["lines"], str(payload.get("text", "")))))
            if path == "/api/assist/split":
                return self.send_json(assist_split(pid))
            if path == "/api/assist/apply_split":
                return self.send_json(assist_apply_split(pid))
            if path == "/api/assist/story":
                return self.send_json(assist_story(pid, payload.get("direction"), payload.get("style"), bool(payload.get("another"))))
            if path == "/api/assist/approve_story":
                return self.send_json(assist_approve_story(pid, bool(payload.get("fill_prompts", True))))
            if path == "/api/assist/cast":
                return self.send_json(assist_cast_save(pid, payload.get("cast")))
            if path == "/api/assist/recommend_cast":
                return self.send_json(assist_recommend_cast(pid))
            if path == "/api/assist/shots":
                return self.send_json(assist_shots(pid))
            if path == "/api/assist/shots_save":
                return self.send_json(assist_shots_save(pid, payload.get("shots")))
            if path == "/api/assist/shot_images":
                return self.send_json(assist_shot_images(pid, payload.get("targets")))
            if path == "/api/render":
                return self.send_json({"results": render_segment(pid, payload.get("segment_id"), payload.get("runs"))})
            if path == "/api/render_all":
                return self.send_json(render_all(pid))
            if path == "/api/result/delete":
                with LOCK:
                    project = load_project(pid)
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
                if pid:
                    cancel_waiting(pid)
                return self.send_json({"ok": True})
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        except OSError as e:
            return self.send_json({"error": f"Cannot reach ComfyUI at {COMFY}: {e}"}, 502)
        self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    migrate_legacy()
    print(f"Storyboard on http://0.0.0.0:{PORT}  ->  ComfyUI at {COMFY}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
