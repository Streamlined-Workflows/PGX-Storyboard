"""The AI models SWIFT Director uses: what each one is for, whether it is current, and updating it.

Three kinds of model live on the PGX:
  file    - a weights file in ComfyUI's models folder, published on Hugging Face
  ollama  - the language model served by Ollama
  speech  - the speech-to-text model inside the song analysis service

"Up to date" for a file means its SHA-256 equals the one Hugging Face publishes for that file today.
Hashes of local files are cached (by size and modified time), so only the first check is slow.
"""
import fnmatch
import hashlib
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
MODELS_DIR = os.environ.get("MODELS_DIR", "/models")
HF = os.environ.get("HF_URL", "https://huggingface.co").rstrip("/")
HF_TOKEN_FILE = os.environ.get("HF_TOKEN_FILE", "/hf/token")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.6:35b")
OLLAMA_REGISTRY = os.environ.get("OLLAMA_REGISTRY", "https://registry.ollama.ai").rstrip("/")
ASSIST = os.environ.get("ASSIST_URL", "http://127.0.0.1:8191").rstrip("/")
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
HASH_CACHE = os.path.join(DATA_DIR, "model_hashes.json")
STATE_FILE = os.path.join(DATA_DIR, "model_status.json")
TOKEN_FILE = os.path.join(DATA_DIR, "hf_token")          # a key entered in the AI models panel; data/ is never committed
GATED = {"Lightricks/LTX-2.5"}                           # repos known to need a signed-in account that accepted the license
FINAL = ("current", "outdated", "missing", "error", "needs_key")
CHUNK = 8 * 1024 * 1024

WAN21 = "Comfy-Org/Wan_2.1_ComfyUI_repackaged"
WAN22 = "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
KJ = "Kijai/WanVideo_comfy"
FLUX2 = "Comfy-Org/flux2-dev"
LTX = "Lightricks/LTX-2.5"

GROUPS = [
    ("story", "Story clips", "Wan 2.1. Used whenever a segment is set to Story, and as the base of every Singing clip."),
    ("singing", "Singing clips", "InfiniteTalk on top of Wan 2.1. Used whenever a segment is set to Singing."),
    ("endshot", "Story clips that land on an end shot", "Wan 2.2. Only used when a Story segment has an end shot."),
    ("stills", "Stills", "FLUX.2 [dev]. Makes actor views and shots."),
    ("assist", "Assisted Storyboard", "The models that listen to the song and do the writing."),
    ("ltx", "LTX-2.5 (installed for testing)", "Not used by SWIFT Director yet. Listed so it stays current while we evaluate it as the next video engine."),
]

CATALOG = [
    # ---- Story (Wan 2.1) ----
    dict(id="wan21_i2v", group="story", name="Wan 2.1 image-to-video 14B (480p)", file="Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors",
         folder="diffusion_models", repos=["Kijai/WanVideo_comfy_fp8_scaled", KJ],
         use="The model that makes the picture move. It takes a segment's begin shot and your video prompt and produces the clip, "
             "5 seconds at a time, each pass picking up from the last frame of the one before. Singing clips are built on it too."),
    dict(id="wan21_fast", group="story", name="Lightx2v 4-step speed-up (LoRA)", file="lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
         folder="loras", repos=[KJ, "Kijai/WanVideo_comfy_fp8_scaled"],
         use="What makes drafts fast. It lets Wan 2.1 finish in 4 steps for Story and 6 for Singing, which is why a 5-second clip "
             "takes about two minutes instead of forty."),
    dict(id="umt5", group="story", name="UMT5-XXL text encoder", file="umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         folder="text_encoders", repos=[WAN21, WAN22],
         use="Reads the video prompt you type on a segment and turns it into what the video model understands. "
             "Shared by Story, Singing and end-shot clips."),
    dict(id="wan21_vae", group="story", name="Wan 2.1 VAE", file="Wan2_1_VAE_bf16.safetensors", folder="vae", repos=[KJ],
         use="Translates between pictures and the video model's working format: it reads the begin shot in, "
             "and turns the finished result back into the frames you watch. Used by Story and Singing clips."),
    dict(id="clip_vision", group="story", name="CLIP Vision H", file="clip_vision_h.safetensors", folder="clip_vision", repos=[WAN21],
         use="Looks at the begin shot so a Story clip holds on to your actor's face, outfit and art style instead of drifting."),
    # ---- Singing ----
    dict(id="infinitetalk", group="singing", name="InfiniteTalk (single singer)", file="wan2.1_infiniteTalk_single_fp16.safetensors",
         folder="model_patches", repos=[WAN21],
         use="The lip sync. It steers Wan 2.1 so the actor's mouth and head follow the vocals in that segment of the song. "
             "This is the one-character version, since each shot has one singer."),
    dict(id="wav2vec", group="singing", name="wav2vec2 audio encoder", file="wav2vec2-chinese-base_fp16.safetensors",
         folder="audio_encoders", repos=[WAN21],
         use="Listens to the segment's slice of the song and pulls out the mouth-sound timing that InfiniteTalk follows."),
    # ---- End shot (Wan 2.2) ----
    dict(id="wan22_high", group="endshot", name="Wan 2.2 image-to-video 14B, high noise", file="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
         folder="diffusion_models", repos=[WAN22], optional=True,
         use="First half of an end-shot render: lays out the motion that carries the begin shot toward the end shot."),
    dict(id="wan22_low", group="endshot", name="Wan 2.2 image-to-video 14B, low noise", file="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
         folder="diffusion_models", repos=[WAN22], optional=True,
         use="Second half of an end-shot render: fills in the detail so the last frame actually arrives at the end shot."),
    dict(id="wan22_fast_high", group="endshot", name="Lightx2v 4-step speed-up, high noise (LoRA)", file="wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
         folder="loras", repos=[WAN22], optional=True,
         use="Speed-up for the first half of an end-shot render, so it drafts in minutes like the other clips."),
    dict(id="wan22_fast_low", group="endshot", name="Lightx2v 4-step speed-up, low noise (LoRA)", file="wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
         folder="loras", repos=[WAN22], optional=True,
         use="Speed-up for the second half of an end-shot render."),
    dict(id="wan22_vae", group="endshot", name="Wan 2.1 VAE (ComfyUI build)", file="wan_2.1_vae.safetensors", folder="vae", repos=[WAN22, WAN21], optional=True,
         use="Reads the begin and end shots in and turns an end-shot render back into frames."),
    # ---- Stills (FLUX.2) ----
    dict(id="flux2", group="stills", name="FLUX.2 [dev]", file="flux2_dev_fp8mixed.safetensors", folder="diffusion_models", repos=[FLUX2],
         use="The image generator. It draws an actor's close-up, waist-up and full-body views from the description, "
             "using the actor's existing views as references so the character stays the same person."),
    dict(id="flux2_turbo", group="stills", name="FLUX.2 Turbo (LoRA)", file="Flux2TurboComfyv2.safetensors", folder="loras",
         repos=[FLUX2, "ByteZSzn/Flux.2-Turbo-ComfyUI"],
         use="Speed-up for stills. Lets FLUX.2 finish an image in 8 steps, so Generate views returns in a few minutes."),
    dict(id="flux2_text", group="stills", name="Mistral Small 3 text encoder", file="mistral_3_small_flux2_bf16.safetensors",
         folder="text_encoders", repos=[FLUX2],
         use="Reads the prompt for a still (the actor description plus the framing) for FLUX.2."),
    dict(id="flux2_vae", group="stills", name="FLUX.2 VAE", file="flux2-vae.safetensors", folder="vae", repos=[FLUX2],
         use="Reads an actor's reference views in for FLUX.2 and turns the result into the finished image."),
    # ---- Assisted Storyboard ----
    dict(id="llm", group="assist", kind="ollama", name=OLLAMA_MODEL,
         use="The writer. In Assisted Storyboard it names the segments, lines your pasted lyrics up with the song and writes the story concept. "
             "In Assets it looks at an actor's views to write the description, and writes the prompt for each new view."),
    dict(id="speech", group="assist", kind="speech", name="Whisper large-v3-turbo",
         use="Listens to the song and writes down the lyrics with the time of every word, "
             "which Assisted Storyboard uses to decide where the cuts go."),
    # ---- LTX-2.5 ----
    dict(id="ltx_model", group="ltx", name="LTX-2.5 22B distilled", file="ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
         folder="diffusion_models", repos=[LTX], optional=True,
         use="Candidate replacement for Wan: makes video and sound together and can aim for an end shot. Only used in your ComfyUI tests so far."),
    dict(id="ltx_video_vae", group="ltx", name="LTX-2.5 video VAE", file="ltx-2.5-video-vae*.safetensors", default_file="ltx-2.5-video-vae-conv-bf16.safetensors",
         folder="vae", repos=[LTX], optional=True,
         use="Turns LTX-2.5's result into video frames in the test workflow."),
    dict(id="ltx_audio_vae", group="ltx", name="LTX-2.5 audio VAE", file="ltx-2.5-audio-vae*.safetensors", default_file="ltx-2.5-audio-vae-bf16.safetensors",
         folder="vae", repos=[LTX], optional=True,
         use="Turns LTX-2.5's result into the clip's sound in the test workflow."),
    dict(id="ltx_text", group="ltx", name="Gemma 4 12B text encoder for LTX-2.5", file="gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
         folder="text_encoders", repos=[LTX], optional=True,
         use="Reads the video prompt for LTX-2.5 in the test workflow."),
    dict(id="ltx_enhance", group="ltx", name="Gemma 4 E2B prompt enhancer", file="gemma4_e2b_it_int8_convrot.safetensors",
         folder="text_encoders", repos=["Comfy-Org/gemma-4"], optional=True,
         use="The small model the LTX test workflow uses to expand a short prompt. A candidate for the Enhance prompt button."),
]
BY_ID = {m["id"]: m for m in CATALOG}

LOCK = threading.Lock()
STATUS = {}                 # id -> {"state", "detail", "progress", "checked"}
_check_running = False
_hash_lock = threading.Lock()


# ---------- small helpers ----------

def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f)
    os.replace(tmp, path)


def _set(mid, **fields):
    with LOCK:
        entry = STATUS.setdefault(mid, {"state": "unknown"})
        entry.update(fields)
        if fields.get("state") in FINAL:
            entry["checked"] = time.time()
            entry.pop("progress", None)
            _save(STATE_FILE, STATUS)


def _size(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def hf_token():
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        return token
    for path in (TOKEN_FILE, HF_TOKEN_FILE):
        try:
            with open(path) as f:
                token = f.read().strip()
            if token:
                return token
        except OSError:
            pass
    return ""


class NeedsKey(ValueError):
    """Hugging Face would not show this repo without a (working) key."""


def set_token(token):
    """Check a Hugging Face key with Hugging Face itself and keep it only if it works."""
    token = str(token or "").strip()
    if not token:
        raise ValueError("Paste your Hugging Face key first.")
    if not token.startswith("hf_") or len(token) < 20 or any(c.isspace() for c in token):
        raise ValueError("That does not look like a Hugging Face key. They start with hf_ and have no spaces.")
    req = urllib.request.Request(HF + "/api/whoami-v2", headers={"Authorization": "Bearer " + token, "User-Agent": "pgx-storyboard"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            who = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError("Hugging Face rejected that key. Check that you copied all of it and that it has not been revoked.")
        raise ValueError(f"Hugging Face answered with error {e.code} while checking the key. Try again.")
    except OSError as e:
        raise ValueError(f"Could not reach Hugging Face to check the key: {getattr(e, 'reason', e)}")
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    role = ((who.get("auth") or {}).get("accessToken") or {}).get("role") or ""
    return {"ok": True, "name": who.get("name") or "your account", "role": role}


def forget_token():
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass
    return listing()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(NoRedirect)


def hf_open(url, timeout=60):
    """Open a Hugging Face URL, following redirects by hand so the token is only ever sent to Hugging Face itself."""
    home = urllib.parse.urlsplit(HF).netloc
    for _ in range(8):
        headers = {"User-Agent": "pgx-storyboard"}
        if urllib.parse.urlsplit(url).netloc == home and hf_token():
            headers["Authorization"] = "Bearer " + hf_token()
        try:
            return _opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            if e.code in (401, 403):
                if hf_token():
                    raise ValueError("Hugging Face refused access with your key. Open this model's page on huggingface.co "
                                     "while signed in and accept its license, then check again.")
                raise NeedsKey("This model requires Hugging Face access to check. Press Check for updates and enter your key.")
            if e.code == 404:
                raise FileNotFoundError(url)
            raise ValueError(f"Hugging Face answered with error {e.code}.")
        except OSError as e:
            raise ValueError(f"Cannot reach Hugging Face: {getattr(e, 'reason', e)}")
    raise ValueError("Too many redirects from Hugging Face.")


def repo_files(repo, cache):
    """Every file in a Hugging Face repo: name -> {"path", "size", "sha256"}."""
    if repo in cache:
        return cache[repo]
    files, url = {}, f"{HF}/api/models/{repo}/tree/main?recursive=true"
    while url:
        with hf_open(url) as resp:
            for item in json.load(resp):
                if item.get("type") == "file":
                    lfs = item.get("lfs") or {}
                    files[os.path.basename(item["path"])] = {"path": item["path"], "size": lfs.get("size", item.get("size")),
                                                              "sha256": lfs.get("oid")}
            url = None
            for part in (resp.headers.get("Link") or "").split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<") + 1:part.find(">")]
    cache[repo] = files
    return files


def local_files():
    """name -> path for every weights file in ComfyUI's models folder."""
    found = {}
    for base, dirs, names in os.walk(MODELS_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in names:
            if not name.endswith(".part"):
                found.setdefault(name, os.path.join(base, name))
    return found


def file_hash(path, on_progress=None):
    stat = os.stat(path)
    key = f"{path}|{stat.st_size}|{stat.st_mtime_ns}"
    with _hash_lock:
        cache = _load(HASH_CACHE, {})
    if key in cache:
        return cache[key]
    digest, done = hashlib.sha256(), 0
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if on_progress:
                on_progress(done / max(1, stat.st_size))
    remember_hash(path, digest.hexdigest())
    return digest.hexdigest()


def remember_hash(path, value):
    stat = os.stat(path)
    with _hash_lock:
        cache = {k: v for k, v in _load(HASH_CACHE, {}).items() if not k.startswith(path + "|")}
        cache[f"{path}|{stat.st_size}|{stat.st_mtime_ns}"] = value
        _save(HASH_CACHE, cache)


# ---------- checking ----------

def _find_remote(model, name, repo_cache):
    """Where Hugging Face publishes this file: (repo, entry), or (None, None)."""
    problem = None
    for repo in model["repos"]:
        try:
            files = repo_files(repo, repo_cache)
        except FileNotFoundError:
            continue
        except NeedsKey:
            raise
        except ValueError as e:
            problem = problem or e
            continue
        if name in files:
            return repo, files[name]
    if problem:
        raise problem
    return None, None


def _local_name(model, local):
    if model["file"] in local:
        return model["file"]
    matches = sorted(n for n in local if fnmatch.fnmatch(n, model["file"]))
    return matches[0] if matches else None


def check_file(model, local, repo_cache):
    mid = model["id"]
    name = _local_name(model, local)
    if not name:
        return _set(mid, state="missing", file=model.get("default_file", model["file"]),
                    detail="Not on the PGX." + (" Only needed if you use this feature." if model.get("optional") else ""))
    path = local[name]
    _set(mid, file=name)
    if not hf_token() and any(r in GATED for r in model["repos"]):       # known to need a key: do not even ask
        raise NeedsKey("This model requires Hugging Face access to check. Press Check for updates and enter your key.")
    repo, remote = _find_remote(model, name, repo_cache)
    if not remote:
        return _set(mid, state="error", detail="Could not find this file on Hugging Face to compare against.")
    size = os.path.getsize(path)
    if remote.get("size") and size != remote["size"]:
        return _set(mid, state="outdated", detail=f"A different version is published ({_size(remote['size'])}, yours is {_size(size)}).")
    if not remote.get("sha256"):
        return _set(mid, state="current", detail=f"{_size(size)} · same size as the published file")
    _set(mid, state="checking", detail="Verifying the file…", progress=0)
    mine = file_hash(path, lambda p: _set(mid, progress=round(p, 3)))
    if mine == remote["sha256"]:
        return _set(mid, state="current", detail=f"{_size(size)} · matches {repo}")
    return _set(mid, state="outdated", detail=f"{repo} has published a newer version of this file.")


def _ollama_tags():
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=8) as r:
        return json.load(r).get("models", [])


def _ollama_local():
    wanted = OLLAMA_MODEL if ":" in OLLAMA_MODEL else OLLAMA_MODEL + ":latest"
    for m in _ollama_tags():
        if m.get("name") == wanted or m.get("model") == wanted:
            return m
    return None


def _ollama_remote_digest():
    name, _, tag = OLLAMA_MODEL.partition(":")
    if "/" not in name:
        name = "library/" + name
    req = urllib.request.Request(f"{OLLAMA_REGISTRY}/v2/{name}/manifests/{tag or 'latest'}",
                                 headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return hashlib.sha256(r.read()).hexdigest()


def check_ollama(model):
    mid = model["id"]
    try:
        mine = _ollama_local()
    except OSError as e:
        return _set(mid, state="error", detail=f"Ollama is not answering on the PGX: {getattr(e, 'reason', e)}")
    if not mine:
        return _set(mid, state="missing", detail="Not downloaded in Ollama yet.")
    try:
        published = _ollama_remote_digest()
    except OSError as e:
        return _set(mid, state="error", detail=f"Cannot reach the Ollama library to compare: {getattr(e, 'reason', e)}")
    size = _size(mine.get("size") or 0)
    # "pulled" covers an Ollama that reports its digest differently: a pull we ran against this same published build counts as current.
    if (mine.get("digest") or "").replace("sha256:", "") == published or STATUS.get(mid, {}).get("pulled") == published:
        return _set(mid, state="current", detail=f"{size} · matches the Ollama library")
    return _set(mid, state="outdated", detail="The Ollama library has a newer build of this model.")


def _assist(path, data=None, timeout=30):
    req = urllib.request.Request(ASSIST + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def check_speech(model):
    mid = model["id"]
    try:
        info = _assist("/model")
    except (OSError, ValueError) as e:
        return _set(mid, state="error", detail=f"The song analysis service is not answering: {getattr(e, 'reason', e)}")
    if info.get("error"):
        return _set(mid, state="error", detail=info["error"])
    if not info.get("local"):
        return _set(mid, state="missing", detail="Not downloaded yet. It downloads by itself the first time Assisted Storyboard analyzes a song.")
    if info["local"] == info.get("remote"):
        return _set(mid, state="current", detail=f"matches {info.get('repo')}")
    return _set(mid, state="outdated", detail=f"{info.get('repo')} has published a newer version.")


def _busy(mid):
    return STATUS.get(mid, {}).get("state") in ("updating", "checking")


def check_all():
    global _check_running
    with LOCK:
        if _check_running:
            return
        _check_running = True
    try:
        local, repo_cache = local_files(), {}
        for model in CATALOG:
            if STATUS.get(model["id"], {}).get("state") == "updating":
                continue
            _set(model["id"], state="checking", detail="Checking…", progress=None)
        for model in CATALOG:
            mid = model["id"]
            if STATUS.get(mid, {}).get("state") == "updating":
                continue
            try:
                kind = model.get("kind", "file")
                check_ollama(model) if kind == "ollama" else check_speech(model) if kind == "speech" else check_file(model, local, repo_cache)
            except NeedsKey as e:
                _set(mid, state="needs_key", detail=str(e))
            except Exception as e:                      # one model failing must not stop the rest
                _set(mid, state="error", detail=str(e)[:300])
    finally:
        _check_running = False


def start_check():
    if not _check_running:
        threading.Thread(target=check_all, daemon=True).start()
    return listing()


# ---------- updating ----------

def update_file(model):
    mid = model["id"]
    local = local_files()
    name = _local_name(model, local)
    repo, remote = _find_remote(model, name or model.get("default_file") or model["file"], {})
    if not remote:
        raise ValueError("Could not find this file on Hugging Face.")
    name = name or os.path.basename(remote["path"])
    folder = os.path.dirname(local[name]) if name in local else os.path.join(MODELS_DIR, model["folder"])
    os.makedirs(folder, exist_ok=True)
    dest, part = os.path.join(folder, name), os.path.join(folder, name + ".part")
    total = remote.get("size") or 0
    if total and shutil.disk_usage(folder).free < total + 2e9:
        raise ValueError(f"Not enough free disk space on the PGX for this download ({_size(total)}).")
    digest, done, started = hashlib.sha256(), 0, time.time()
    try:
        with hf_open(f"{HF}/{repo}/resolve/main/{urllib.parse.quote(remote['path'])}", timeout=120) as resp, open(part, "wb") as out:
            total = total or int(resp.headers.get("Content-Length") or 0)
            while True:
                block = resp.read(CHUNK)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                rate = done / max(0.5, time.time() - started)
                left = (total - done) / rate if total and rate else 0
                _set(mid, progress=round(done / total, 3) if total else None,
                     detail=f"Downloading {_size(done)} of {_size(total)}" + (f" · about {max(1, round(left / 60))} min left" if left > 45 else ""))
        if total and done != total:
            raise ValueError("The download stopped early. Press Update to try again.")
        if remote.get("sha256") and digest.hexdigest() != remote["sha256"]:
            raise ValueError("The downloaded file did not verify. Press Update to try again.")
        try:
            owner = os.stat(folder)
            os.chown(part, owner.st_uid, owner.st_gid)
        except OSError:
            pass
        os.replace(part, dest)
    finally:
        if os.path.exists(part):
            os.remove(part)
    remember_hash(dest, digest.hexdigest())
    try:      # make ComfyUI drop the old copy from memory so the next render loads the new file
        urllib.request.urlopen(urllib.request.Request(COMFY + "/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except OSError:
        pass
    _set(mid, state="current", file=name, detail=f"{_size(done)} · updated just now from {repo}")


def update_ollama(model):
    mid = model["id"]
    req = urllib.request.Request(OLLAMA + "/api/pull", data=json.dumps({"model": OLLAMA_MODEL, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        for line in resp:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("error"):
                raise ValueError(event["error"])
            total, done = event.get("total") or 0, event.get("completed") or 0
            _set(mid, progress=round(done / total, 3) if total else None,
                 detail=f"Downloading {_size(done)} of {_size(total)}" if total else str(event.get("status", "Working…")).capitalize())
    try:
        pulled = _ollama_remote_digest()
    except OSError:
        pulled = None
    _set(mid, state="current", pulled=pulled, detail="updated just now from the Ollama library")


def update_speech(model):
    mid = model["id"]
    _assist("/model/update", {})
    while True:
        time.sleep(2)
        info = _assist("/model")
        if info.get("update") == "error":
            raise ValueError(info.get("update_error") or "The download failed.")
        if info.get("update") != "running":
            break
        _set(mid, detail="Downloading…")
    _set(mid, state="current", detail=f"updated just now from {info.get('repo')}")


def _run_update(model):
    mid = model["id"]
    try:
        kind = model.get("kind", "file")
        update_ollama(model) if kind == "ollama" else update_speech(model) if kind == "speech" else update_file(model)
    except Exception as e:
        _set(mid, state="error", detail="Update failed: " + str(getattr(e, "reason", e))[:300])


def start_update(mid):
    model = BY_ID.get(mid)
    if not model:
        raise ValueError("Unknown model.")
    with LOCK:
        if _busy(mid):
            raise ValueError("That model is already being checked or updated.")
        STATUS.setdefault(mid, {}).update(state="updating", detail="Starting the download…", progress=0)
    threading.Thread(target=_run_update, args=(model,), daemon=True).start()
    return listing()


# ---------- what the page shows ----------

def listing():
    with LOCK:
        groups = []
        for gid, title, note in GROUPS:
            items = []
            for m in CATALOG:
                if m["group"] != gid:
                    continue
                s = STATUS.get(m["id"], {})
                items.append({"id": m["id"], "name": m["name"], "use": m["use"], "optional": bool(m.get("optional")),
                              "file": s.get("file") or m.get("default_file") or m.get("file") or "",
                              "state": s.get("state", "unknown"), "detail": s.get("detail", ""),
                              "progress": s.get("progress"), "checked": s.get("checked")})
            groups.append({"id": gid, "title": title, "note": note, "models": items})
        return {"groups": groups, "checking": _check_running, "signed_in": bool(hf_token()),
                "key_from_panel": os.path.exists(TOKEN_FILE) and not os.environ.get("HF_TOKEN", "").strip()}


for _mid, _entry in _load(STATE_FILE, {}).items():     # results of the last check survive a restart
    if _mid in BY_ID and _entry.get("state") in FINAL:
        STATUS[_mid] = _entry
