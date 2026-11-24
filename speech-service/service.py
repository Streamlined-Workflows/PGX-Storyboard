#!/usr/bin/env python3
"""Speech generation service for SWIFT Director (port 8192, this machine only).

It holds the list of speech models, downloads one when asked to, loads one at a time onto the graphics
card, speaks text with it, and lets go of the memory when told to or after a few idle minutes.

    GET  /health            is the service up, can it see the graphics card, which engines were built
    GET  /models            every model: installed or not, download progress, loaded or not, memory measured
    POST /install {id}      download a model's files (nothing is ever downloaded without this call)
    POST /speak   {...}     -> a WAV file. See speak() for the fields
    POST /unload            stop the loaded model and give its memory back

Each model runs in its own process (worker.py) under the Python environment it needs. Unloading ends that
process, which is the only certain way to release graphics memory.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("SPEECH_PORT", "8192"))
HOST = os.environ.get("SPEECH_HOST", "127.0.0.1")
MODELS_DIR = os.environ.get("MODELS_DIR", "/models")
HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.environ.get("SPEECH_WORKER", os.path.join(HERE, "worker.py"))
PYTHON = {"qwen": os.environ.get("QWEN_PYTHON", "/opt/qwen/bin/python"), "ming": os.environ.get("MING_PYTHON", "/opt/ming/bin/python")}
MING_FAILED = os.environ.get("MING_FAILED_FILE", "/opt/ming.failed")
MING_LOG = os.environ.get("MING_BUILD_LOG", "/opt/ming-build.log")
IDLE_SECONDS = int(os.environ.get("SPEECH_IDLE_SECONDS", "300"))       # a model nobody has used for this long is unloaded
LOAD_TIMEOUT = int(os.environ.get("SPEECH_LOAD_TIMEOUT", "900"))
SPEAK_TIMEOUT = int(os.environ.get("SPEECH_SPEAK_TIMEOUT", "900"))
MAX_TEXT = 5000
MAX_REFERENCE = 20 * 1024 * 1024

# What each model can do: "clone" copies a voice from a recording, "design" makes one from a description,
# "preset" uses a speaker that comes with the model.
MODELS = {
    "qwen_clone": {"engine": "qwen", "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "modes": ["clone"]},
    "qwen_design": {"engine": "qwen", "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "modes": ["design"]},
    "qwen_preset": {"engine": "qwen", "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "modes": ["preset"]},
    "ming": {"engine": "ming", "repo": "inclusionAI/Ming-3.0-tts-0.5B", "modes": ["clone", "design", "preset"]},
}

LOCK = threading.RLock()           # guards the tables below
SPEAKING = threading.Lock()        # one piece of speech at a time
DOWNLOADS = {}                     # id -> {"state": running|error, "done", "total", "error"}
MEASURED = {}                      # id -> {"memory": bytes, "speakers": [...], "sample_rate": n}, learned when a model is loaded
loaded = None                      # {"id", "process", "used": time}
_gpu = None


def folder(mid):
    return os.path.join(MODELS_DIR, mid)


def marker(mid):
    return os.path.join(folder(mid), ".swift-installed.json")


def installed(mid):
    try:
        with open(marker(mid)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def folder_bytes(path):
    total = 0
    for base, _, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def token():
    for path in (os.environ.get("HF_TOKEN_FILE", "/hf/token"),):
        try:
            with open(path) as f:
                return f.read().strip() or None
        except OSError:
            pass
    return os.environ.get("HF_TOKEN") or None


# ---------- Hugging Face (replaced in tests) ----------

def published(repo):
    """-> {"revision": the commit published now, "bytes": total size of its files}"""
    from huggingface_hub import HfApi
    info = HfApi(token=token()).model_info(repo, files_metadata=True)
    return {"revision": info.sha, "bytes": sum((s.size or 0) for s in info.siblings)}


def fetch(repo, revision, target):
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo, revision=revision, local_dir=target, token=token())


# ---------- engines ----------

def gpu():
    """Whether the Qwen environment's PyTorch can use the graphics card. Asked once."""
    global _gpu
    if _gpu is None:
        try:
            out = subprocess.run([PYTHON["qwen"], "-c", "import torch; print(int(torch.cuda.is_available()), torch.__version__, torch.version.cuda or '')"],
                                 capture_output=True, text=True, timeout=180)
            parts = out.stdout.split()
            _gpu = {"ok": bool(parts) and parts[0] == "1", "detail": " ".join(parts[1:]) if parts else (out.stderr.strip().splitlines() or ["PyTorch did not start"])[-1][:300]}
        except (OSError, subprocess.SubprocessError) as e:
            _gpu = {"ok": False, "detail": str(e)[:300]}
    return _gpu


def engines():
    ming_ok = os.path.exists(PYTHON["ming"]) and not os.path.exists(MING_FAILED)
    problem = ""
    if not ming_ok:
        try:
            with open(MING_LOG, errors="replace") as f:
                lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            problem = next((l for l in reversed(lines) if "error" in l.lower()), lines[-1] if lines else "")[:400]
        except OSError:
            pass
        problem = "Ming-3.0-tts could not be installed on this machine when the service was built." + (" Last message: " + problem if problem else "")
    return {"qwen": {"ready": os.path.exists(PYTHON["qwen"]), "problem": ""}, "ming": {"ready": ming_ok, "problem": problem}}


# ---------- installing ----------

def install(mid):
    if mid not in MODELS:
        raise ValueError("Unknown speech model.")
    with LOCK:
        if DOWNLOADS.get(mid, {}).get("state") == "running":
            return
        DOWNLOADS[mid] = {"state": "running", "done": 0, "total": 0, "error": ""}
    threading.Thread(target=_install, args=(mid,), daemon=True).start()


def _install(mid):
    repo, target = MODELS[mid]["repo"], folder(mid)
    try:
        now = published(repo)
        DOWNLOADS[mid]["total"] = now["bytes"]
        os.makedirs(target, exist_ok=True)
        if now["bytes"] and shutil.disk_usage(target).free < now["bytes"] - folder_bytes(target) + 2e9:
            raise ValueError(f"Not enough free disk space for this download ({now['bytes'] / 1e9:.1f} GB).")
        if os.path.exists(marker(mid)):
            os.remove(marker(mid))                       # not "installed" again until the new files are all here
        stop = threading.Event()

        def watch():
            while not stop.wait(1.0):
                DOWNLOADS[mid]["done"] = folder_bytes(target)
        threading.Thread(target=watch, daemon=True).start()
        try:
            fetch(repo, now["revision"], target)
        finally:
            stop.set()
        with open(marker(mid) + ".tmp", "w") as f:
            json.dump({"repo": repo, "revision": now["revision"], "bytes": folder_bytes(target), "installed": time.time()}, f)
        os.replace(marker(mid) + ".tmp", marker(mid))
        with LOCK:
            DOWNLOADS.pop(mid, None)
            if loaded and loaded["id"] == mid:
                unload()                                 # the next use loads the new files
    except Exception as e:
        DOWNLOADS[mid] = {"state": "error", "done": 0, "total": 0, "error": str(getattr(e, "reason", e))[:400] or type(e).__name__}


def listing(check=False):
    """Every model as the application shows it. check=True also asks Hugging Face what is published now."""
    out, built = [], engines()
    for mid, m in MODELS.items():
        have, down, engine = installed(mid), DOWNLOADS.get(mid, {}), built[m["engine"]]
        entry = {"id": mid, "repo": m["repo"], "engine": m["engine"], "modes": m["modes"], "installed": bool(have),
                 "bytes": (have or {}).get("bytes"), "revision": (have or {}).get("revision"),
                 "downloading": down.get("state") == "running", "done": down.get("done", 0), "total": down.get("total", 0),
                 "error": down.get("error", "") if down.get("state") == "error" else "",
                 "engine_ready": engine["ready"], "engine_problem": engine["problem"],
                 "loaded": bool(loaded and loaded["id"] == mid), **MEASURED.get(mid, {})}
        if check:
            try:
                now = published(m["repo"])
                entry.update(published_revision=now["revision"], published_bytes=now["bytes"])
            except Exception as e:
                entry["check_error"] = str(getattr(e, "reason", e))[:300] or type(e).__name__
        out.append(entry)
    return {"models": out, "gpu": gpu(), "loaded": loaded["id"] if loaded else None}


# ---------- loading and speaking ----------

def _read(process, timeout):
    """One JSON line from a worker, or an error if it takes too long or ends."""
    box = {}

    def get():
        box["line"] = process.answers.readline()
    t = threading.Thread(target=get, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("The speech model did not answer in time.")
    if not box.get("line"):
        raise ValueError("The speech model stopped unexpectedly. " + _last_words(process))
    return json.loads(box["line"])


def _last_words(process):
    try:
        process.log.flush()
        with open(process.log.name, errors="replace") as f:
            lines = [l.strip() for l in f.read()[-4000:].splitlines() if l.strip()]
        return ("Last message: " + lines[-1][:300]) if lines else ""
    except OSError:
        return ""


def unload():
    global loaded
    with LOCK:
        was, loaded = loaded, None
    if not was:
        return False
    p = was["process"]
    try:
        p.stdin.close()
        p.terminate()
        p.wait(timeout=15)
    except (OSError, subprocess.SubprocessError):
        p.kill()
    for stream in (p.answers, p.log):
        try:
            stream.close()
        except OSError:
            pass
    try:
        os.remove(p.log.name)
    except OSError:
        pass
    return True


def load(mid):
    """Make `mid` the loaded model, unloading any other first. -> the loaded record."""
    global loaded
    if loaded and loaded["id"] == mid and loaded["process"].poll() is None:
        return loaded
    unload()
    m = MODELS[mid]
    engine = engines()[m["engine"]]
    if not engine["ready"]:
        raise ValueError(engine["problem"] or "This model's engine is not installed in the speech service.")
    if not installed(mid):
        raise ValueError("This model has not been downloaded yet. Install it under System status first.")
    if not gpu()["ok"]:
        raise ValueError("The speech service cannot use the graphics card: " + gpu()["detail"])
    log = tempfile.NamedTemporaryFile("w", prefix=f"speech-{mid}-", suffix=".log", delete=False)
    process = subprocess.Popen([PYTHON[m["engine"]], WORKER, m["engine"], folder(mid)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    process.answers, process.log = process.stdout, log
    loaded = {"id": mid, "process": process, "used": time.time()}
    try:
        hello = _read(process, LOAD_TIMEOUT)
        if not hello.get("ready"):
            raise ValueError("The model could not be loaded: " + (hello.get("error") or "no reason given"))
    except Exception:
        unload()
        raise
    MEASURED[mid] = {"memory": hello.get("memory") or None, "speakers": hello.get("speakers") or []}
    return loaded


def speak(r):
    """r: {id, text, mode, language?, instruct?, speaker?, ref_audio? (base64 of a sound file), ref_text?}
    -> (WAV bytes, facts about it)"""
    mid, text, mode = r.get("id"), str(r.get("text") or "").strip(), r.get("mode")
    if mid not in MODELS:
        raise ValueError("Unknown speech model.")
    if mode not in MODELS[mid]["modes"]:
        raise ValueError("This model cannot do that. It offers: " + ", ".join(MODELS[mid]["modes"]) + ".")
    if not text:
        raise ValueError("There is no text to speak.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"That is too much text for one piece of speech (the limit is {MAX_TEXT} characters). Split it up.")
    if mode == "design" and not str(r.get("instruct") or "").strip():
        raise ValueError("Describe the voice to make.")
    work = tempfile.mkdtemp(prefix="speech-")
    try:
        ask = {"op": "speak", "out": os.path.join(work, "out.wav"), "text": text, "mode": mode, "language": str(r.get("language") or "English")[:40],
               "instruct": str(r.get("instruct") or "")[:1000], "speaker": str(r.get("speaker") or "")[:80], "ref_text": str(r.get("ref_text") or "")[:2000]}
        if mode == "clone":
            try:
                raw = base64.b64decode(r.get("ref_audio") or "", validate=True)
            except ValueError:
                raw = b""
            if not raw:
                raise ValueError("A recording of the voice to copy is needed.")
            if len(raw) > MAX_REFERENCE:
                raise ValueError("That recording is too large. A clip of 5 to 15 seconds is enough.")
            src = os.path.join(work, "reference")
            with open(src, "wb") as f:
                f.write(raw)
            # Whatever was sent becomes a plain one-channel WAV, capped at 30 seconds: the models need no more.
            done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "24000", "-t", "30", os.path.join(work, "reference.wav")],
                                  capture_output=True, text=True, timeout=120)
            if done.returncode != 0:
                raise ValueError("That recording could not be read as sound.")
            ask["ref_audio"] = os.path.join(work, "reference.wav")
        with SPEAKING:
            with LOCK:
                record = load(mid)
            process = record["process"]
            process.stdin.write(json.dumps(ask) + "\n")
            process.stdin.flush()
            try:
                answer = _read(process, SPEAK_TIMEOUT)
            except Exception:
                unload()                                 # a model that stopped answering is not left holding memory
                raise
            record["used"] = time.time()
        if not answer.get("ok"):
            raise ValueError("The model could not speak this: " + (answer.get("error") or "no reason given"))
        if answer.get("memory"):
            MEASURED.setdefault(mid, {})["memory"] = answer["memory"]
        MEASURED.setdefault(mid, {})["sample_rate"] = answer.get("sample_rate")
        with open(ask["out"], "rb") as f:
            return f.read(), {"seconds": answer.get("seconds"), "took": answer.get("took"), "sample_rate": answer.get("sample_rate")}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def idle_watch():
    while True:
        time.sleep(20)
        with LOCK:
            stale = loaded and time.time() - loaded["used"] > IDLE_SECONDS and not SPEAKING.locked()
        if stale:
            unload()


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, kind="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/health":
            return self.send(200, {"ok": True, "gpu": gpu(), "engines": engines(), "loaded": loaded["id"] if loaded else None})
        if path == "/models":
            return self.send(200, listing(check="check=1" in query))
        self.send(404, {"error": "Not found."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 40 * 1024 * 1024:
                return self.send(413, {"error": "That request is too large."})
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Send a JSON object.")
            if self.path == "/install":
                install(payload.get("id"))
                return self.send(200, listing())
            if self.path == "/unload":
                return self.send(200, {"unloaded": unload()})
            if self.path == "/speak":
                wav, facts = speak(payload)
                return self.send(200, wav, "audio/wav", {"X-Speech-Seconds": facts["seconds"], "X-Speech-Took": facts["took"], "X-Speech-Rate": facts["sample_rate"]})
            self.send(404, {"error": "Not found."})
        except (ValueError, TimeoutError) as e:
            self.send(400, {"error": str(e)})
        except Exception as e:
            self.send(500, {"error": f"The speech service ran into a problem: {e}"[:400]})


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    threading.Thread(target=idle_watch, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
