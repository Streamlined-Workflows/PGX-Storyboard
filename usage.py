"""What is using the server's memory and GPU, in terms a person can act on.

Two sources, each optional (a missing one is simply left out):
  * Ollama's own list of loaded language models and when each will be released.
  * The server's process list (memory per program), plus nvidia-smi's GPU memory per program.

The process list covers the whole server only when the container shares the host's process list
(run.sh starts it with --pid host). Otherwise it can see only itself, and says so.
"""
import json
import os
import subprocess
import time
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
MIN_BYTES = 150 * 1024 * 1024         # programs smaller than this are not worth a row

# (text to look for in the command line, the name shown). First match wins.
KNOWN = (("ollama", "Ollama (language model)"),
         ("comfyui", "ComfyUI (image and video models)"),
         ("service.py", "Song analysis (speech model)"),
         ("uvicorn", "Song analysis (speech model)"),
         ("app.py", "SWIFT Director"),
         ("dockerd", "Docker"), ("containerd", "Docker"),
         ("gnome-shell", "Desktop"), ("xorg", "Desktop"), ("chrome", "Web browser"), ("firefox", "Web browser"))


NOTES = {
    "ComfyUI (image and video models)": "The models from its last jobs, kept loaded so the next job starts quickly. It does not let go of them by itself while idle. Free memory releases them; the next job then takes longer to start while they load again.",
    "Ollama (language model)": "The language model used by Assisted Storyboard. Ollama releases it by itself after a few idle minutes.",
    "Song analysis (speech model)": "The speech model that listens to the song. Loaded while a song is analysed.",
}


# Which model servers each part of the application needs. Opening a part releases the ones it does not need.
# System status is deliberately absent: looking at memory must not change it.
NEEDS = {
    "storyboard": {"comfy"},             # renders
    "assist": {"comfy", "llm"},          # the language model writes; ComfyUI draws key frames
    "assets": {"comfy", "llm"},          # generating pictures, and describing an actor from them
    "identity": {"comfy"},               # concepts
    "projects": set(), "library": set(), "lore": set(),
    "audio": set(),                      # Audio Lab plays and edits in the browser; it needs no model
}


def _unload_llm():
    try:
        for m in _get(OLLAMA + "/api/ps").get("models") or []:
            req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps({"model": m.get("name"), "keep_alive": 0}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
            return True
    except (OSError, ValueError):
        pass
    return False


def _comfy_idle(comfy_json):
    queue = comfy_json("/queue", timeout=5)
    return len(queue.get("queue_running", [])) + len(queue.get("queue_pending", [])) == 0


def release(comfy_json, keep, llm_busy=False):
    """Unload every model server not named in `keep` ("comfy", "llm"). ComfyUI is only ever asked while its queue is
    empty, so a render or a waiting job is never disturbed. -> what was released, and what was left alone and why."""
    out = {"released": [], "left": []}
    if "comfy" not in keep:
        try:
            if _comfy_idle(comfy_json):
                comfy_json("/free", {"unload_models": True, "free_memory": True})
                out["released"].append("comfy")
            else:
                out["left"].append("ComfyUI is rendering or has jobs waiting")
        except OSError:
            out["left"].append("ComfyUI could not be reached")
    if "llm" not in keep:
        if llm_busy:
            out["left"].append("the language model is in the middle of writing")
        elif _unload_llm():
            out["released"].append("llm")
    return out


def release_for_view(comfy_json, view, llm_busy=False):
    """Called a moment after the person opens a part of the application."""
    if view not in NEEDS:
        return {"released": [], "left": []}
    return release(comfy_json, NEEDS[view], llm_busy)


def free(comfy_json):
    """The Free memory button: unload everything. Refuses while anything is rendering or waiting."""
    if not _comfy_idle(comfy_json):
        raise ValueError("A job is rendering or waiting. Memory can be freed when the queue is empty.")
    release(comfy_json, set())
    return {"ok": True}


def _get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def label(cmdline):
    low = cmdline.lower()
    for needle, name in KNOWN:
        if needle in low:
            return name
    first = cmdline.split()[0] if cmdline.split() else "?"
    return os.path.basename(first)[:40]


def sees_whole_server(proc="/proc"):
    """True when process 1 is the server's own (systemd or init), not this container's program."""
    try:
        with open(os.path.join(proc, "1", "comm")) as f:
            return f.read().strip() in ("systemd", "init")
    except OSError:
        return False


def processes(proc="/proc"):
    """-> {pid: (resident bytes, command line)} for every program this container can see."""
    out = {}
    try:
        names = os.listdir(proc)
    except OSError:
        return out
    for name in names:
        if not name.isdigit():
            continue
        try:
            rss = 0
            with open(os.path.join(proc, name, "status")) as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1]) * 1024
                        break
            if not rss:
                continue                                   # kernel threads have no memory of their own
            with open(os.path.join(proc, name, "cmdline"), "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            try:                                           # "python main.py" says little; the folder it runs in says which program it is
                cmd += " [in " + os.readlink(os.path.join(proc, name, "cwd")) + "]"
            except OSError:
                pass
            out[int(name)] = (rss, cmd)
        except (OSError, ValueError, IndexError):
            continue
    return out


def gpu_processes():
    """-> {pid: GPU memory bytes} from nvidia-smi, or {} when it cannot say."""
    try:
        text = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            out[int(parts[0])] = out.get(int(parts[0]), 0) + int(parts[1]) * 1024 * 1024
    return out


def programs(procs, gpu):
    """Group processes by what they are. -> rows sorted by the larger of memory and GPU memory."""
    groups = {}
    for pid, (rss, cmd) in procs.items():
        g = groups.setdefault(label(cmd), {"name": label(cmd), "memory": 0, "gpu": 0, "count": 0})
        g["memory"] += rss; g["count"] += 1; g["gpu"] += gpu.get(pid, 0)
    for pid, used in gpu.items():                          # on the GPU, but not in a process list we can see
        if pid not in procs:
            g = groups.setdefault("Another program (not visible from here)", {"name": "Another program (not visible from here)", "memory": 0, "gpu": 0, "count": 0})
            g["gpu"] += used; g["count"] += 1
    # On this machine GPU memory is counted apart from a program's ordinary memory, so its real footprint is the two added.
    for g in groups.values():
        g["total"] = g["memory"] + g["gpu"]
        g["note"] = NOTES.get(g["name"], "")
    rows = [g for g in groups.values() if g["total"] >= MIN_BYTES]
    return sorted(rows, key=lambda g: g["total"], reverse=True)[:8]


def loaded_models():
    """What the two model servers say they are holding right now."""
    rows = []
    try:
        for m in _get(OLLAMA + "/api/ps").get("models") or []:
            until = m.get("expires_at") or ""
            rows.append({"holder": "Ollama", "name": m.get("name", "language model"), "bytes": int(m.get("size") or 0),
                         "gpu_bytes": int(m.get("size_vram") or 0), "until": until,
                         "note": "The language model used by Assisted Storyboard. Ollama releases it by itself after a few idle minutes, and SWIFT Director asks it to before a render."})
    except (OSError, ValueError):
        pass
    # ComfyUI's own figure for what it holds reads as zero on this machine, so its row comes from the program list instead.
    return rows


def report():
    procs = processes()
    return {"models": loaded_models(), "programs": programs(procs, gpu_processes()),
            "whole_server": sees_whole_server(), "time": time.time()}
