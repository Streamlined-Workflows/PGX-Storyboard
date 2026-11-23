"""The shape of audio assets and timelines, and the checking of anything a browser sends.

Three rules run through everything here:

  1. Originals are never changed. A clip points at an asset and carries instructions (where to start,
     how long, gain, fades, effects). Rendering applies them; the asset's file stays as it arrived.
  2. Time is counted in whole samples at the timeline's sample rate, never in fractions of a second, so
     two clips that should meet exactly do, and an export is the same every time.
  3. Generated, approved and arranged are three different things. An asset has an approval state; the
     timeline is an arrangement and says nothing about approval.
"""
import re
import time
import uuid

SCHEMA = 1
SAMPLE_RATES = (44100, 48000, 96000)
DEFAULT_RATE = 48000
MAX_SECONDS = 6 * 3600                      # the longest timeline or asset this version will accept

ASSET_KINDS = ("music", "narration", "dialogue", "sfx", "ambience", "foley", "other")
ORIGINS = ("upload", "generated", "recorded", "derived", "extracted")     # extracted: the sound taken from a video file
APPROVAL = ("draft", "approved", "rejected")
TRACK_KINDS = ("music", "narration", "dialogue", "sfx", "ambience", "foley", "custom")
FORMATS = ("wav", "flac", "mp3", "ogg", "m4a", "aac", "opus")
EFFECTS = {                                  # effect type -> {parameter: (lowest, highest, default)}
    "eq": {"low_db": (-24, 24, 0), "mid_db": (-24, 24, 0), "high_db": (-24, 24, 0), "low_hz": (40, 500, 120), "mid_hz": (200, 8000, 1000), "high_hz": (2000, 16000, 8000)},
    "compressor": {"threshold_db": (-60, 0, -18), "ratio": (1, 20, 3), "attack_ms": (0.1, 200, 10), "release_ms": (10, 2000, 150), "makeup_db": (0, 24, 0)},
    "reverb": {"size": (0, 1, 0.3), "decay_s": (0.1, 10, 1.5), "mix": (0, 1, 0.2)},
}
_ID = re.compile(r"^[0-9a-f]{8,32}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def new_id():
    return uuid.uuid4().hex[:12]


def valid_id(value):
    return isinstance(value, str) and bool(_ID.match(value))


def _num(value, low, high, fallback):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and low <= value <= high
    return value if ok else fallback


def _int(value, low, high, fallback):
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high else fallback


def _text(value, limit, fallback=""):
    return value.strip()[:limit] if isinstance(value, str) else fallback


def seconds(samples, rate):
    return samples / float(rate)


def samples(secs, rate):
    return int(round(float(secs) * rate))


# ---------- assets ----------

def new_asset(name, kind="other", origin="upload"):
    now = time.time()
    return clean_asset({"id": new_id(), "name": name, "kind": kind, "origin": origin, "created": now, "updated": now})


def clean_asset(incoming, current=None):
    """A complete, valid asset record. Facts about the file (format, rate, length) are set by the server when it reads
    the file and cannot be changed from a browser: pass them in `current`."""
    cur = current if isinstance(current, dict) else {}
    src = incoming if isinstance(incoming, dict) else {}
    pick = lambda key, options, fallback: src.get(key) if src.get(key) in options else cur.get(key) if cur.get(key) in options else fallback
    file = cur.get("file") if isinstance(cur.get("file"), dict) else src.get("file") if current is None and isinstance(src.get("file"), dict) else {}
    gen = src.get("generation") if isinstance(src.get("generation"), dict) else cur.get("generation") if isinstance(cur.get("generation"), dict) else None
    rate = file.get("sample_rate") if isinstance(file.get("sample_rate"), int) and 8000 <= file.get("sample_rate") <= 192000 else None
    asset = {
        "schema": SCHEMA,
        "id": cur.get("id") if valid_id(cur.get("id")) else src.get("id") if valid_id(src.get("id")) else new_id(),
        "name": _text(src.get("name"), 120) or _text(cur.get("name"), 120) or "Untitled sound",
        "kind": pick("kind", ASSET_KINDS, "other"),
        "origin": cur.get("origin") if cur.get("origin") in ORIGINS else src.get("origin") if src.get("origin") in ORIGINS else "upload",   # where it came from never changes
        "approval": pick("approval", APPROVAL, "draft"),
        "file": {"name": _text(file.get("name"), 200), "format": file.get("format") if file.get("format") in FORMATS else None,
                 "sample_rate": rate, "channels": _int(file.get("channels"), 1, 8, None),
                 "length": _int(file.get("length"), 0, MAX_SECONDS * 192000, None),          # in samples at its own rate
                 "bytes": _int(file.get("bytes"), 0, 2**40, None), "sha256": _text(file.get("sha256"), 64)},
        "parent_id": cur.get("parent_id") if valid_id(cur.get("parent_id")) else src.get("parent_id") if valid_id(src.get("parent_id")) else None,
        "generation": None if gen is None else {"role": _text(gen.get("role"), 40), "model": _text(gen.get("model"), 200),
                                                 "settings": gen.get("settings") if isinstance(gen.get("settings"), dict) else {},
                                                 "source_text": _text(gen.get("source_text"), 20000), "seed": _int(gen.get("seed"), 0, 2**63, None)},
        "speaker": _text(src.get("speaker") if "speaker" in src else cur.get("speaker"), 80),
        "voice_profile_id": src.get("voice_profile_id") if valid_id(src.get("voice_profile_id")) else cur.get("voice_profile_id") if valid_id(cur.get("voice_profile_id")) else None,
        "category": _text(src.get("category") if "category" in src else cur.get("category"), 40),
        "tags": [t for t in (_text(x, 40) for x in (src.get("tags") if isinstance(src.get("tags"), list) else cur.get("tags") or [])) if t][:30],
        "projects": [p for p in (src.get("projects") if isinstance(src.get("projects"), list) else cur.get("projects") or []) if isinstance(p, str) and p][:500],
        "created": _num(cur.get("created", src.get("created")), 0, 1e11, time.time()),
        "updated": _num(src.get("updated"), 0, 1e11, time.time()),
    }
    return asset


def asset_seconds(asset):
    f = asset.get("file") or {}
    return seconds(f["length"], f["sample_rate"]) if f.get("length") is not None and f.get("sample_rate") else None


# ---------- timelines ----------

def clean_effects(chain):
    """A list of effects in the order they are applied. Unknown effects are dropped; out-of-range values take the default."""
    out = []
    for fx in chain if isinstance(chain, list) else []:
        if not isinstance(fx, dict) or fx.get("type") not in EFFECTS:
            continue
        spec = EFFECTS[fx["type"]]
        params = fx.get("params") if isinstance(fx.get("params"), dict) else {}
        out.append({"id": fx.get("id") if valid_id(fx.get("id")) else new_id(), "type": fx["type"], "on": fx.get("on") is not False,
                    "params": {k: _num(params.get(k), low, high, default) for k, (low, high, default) in spec.items()}})
    return out[:8]


def clean_clip(clip, rate):
    """One placed piece of an asset. start = where it sits on the timeline; offset = how far into the asset it begins;
    length = how much of the asset plays. All three are whole samples at the timeline's rate."""
    if not isinstance(clip, dict) or not valid_id(clip.get("asset_id")):
        return None
    limit = MAX_SECONDS * rate
    length = _int(clip.get("length"), 1, limit, None)
    if length is None:
        return None
    fade_in, fade_out = _int(clip.get("fade_in"), 0, length, 0), _int(clip.get("fade_out"), 0, length, 0)
    if fade_in + fade_out > length:                               # fades may meet in the middle but not cross
        fade_out = length - fade_in
    return {"id": clip.get("id") if valid_id(clip.get("id")) else new_id(), "asset_id": clip["asset_id"],
            "start": _int(clip.get("start"), 0, limit, 0), "offset": _int(clip.get("offset"), 0, limit, 0), "length": length,
            "gain_db": _num(clip.get("gain_db"), -60, 24, 0), "fade_in": fade_in, "fade_out": fade_out,
            "speed": _num(clip.get("speed"), 0.25, 4, 1), "pitch": _num(clip.get("pitch"), -24, 24, 0), "reverse": clip.get("reverse") is True,
            "muted": clip.get("muted") is True, "locked": clip.get("locked") is True, "label": _text(clip.get("label"), 120),
            "effects": clean_effects(clip.get("effects")),
            "link": clip.get("link") if isinstance(clip.get("link"), dict) and clip["link"].get("kind") in ("segment", "line", "section") and isinstance(clip["link"].get("id"), str)
                    else None}                                    # what it belongs to: a storyboard segment, a script line, a narration section


def clean_track(track, rate):
    if not isinstance(track, dict):
        return None
    clips = sorted(filter(None, (clean_clip(c, rate) for c in (track.get("clips") if isinstance(track.get("clips"), list) else []))), key=lambda c: (c["start"], c["id"]))
    return {"id": track.get("id") if valid_id(track.get("id")) else new_id(), "name": _text(track.get("name"), 60) or "Track",
            "kind": track.get("kind") if track.get("kind") in TRACK_KINDS else "custom",
            "color": track.get("color") if isinstance(track.get("color"), str) and _COLOR.match(track["color"]) else None,
            "volume_db": _num(track.get("volume_db"), -60, 12, 0), "pan": _num(track.get("pan"), -1, 1, 0),
            "mute": track.get("mute") is True, "solo": track.get("solo") is True, "locked": track.get("locked") is True,
            "output": "master", "effects": clean_effects(track.get("effects")), "clips": clips[:2000]}


def new_timeline(project_id, rate=DEFAULT_RATE):
    return clean_timeline({"project_id": project_id, "sample_rate": rate, "created": time.time()})


def clean_timeline(incoming, current=None):
    """A complete, valid timeline. The sample rate is fixed when the timeline is made: changing it would move every clip."""
    src = incoming if isinstance(incoming, dict) else {}
    cur = current if isinstance(current, dict) else {}
    rate = cur.get("sample_rate") if cur.get("sample_rate") in SAMPLE_RATES else src.get("sample_rate") if src.get("sample_rate") in SAMPLE_RATES else DEFAULT_RATE
    tracks = src.get("tracks") if isinstance(src.get("tracks"), list) else cur.get("tracks") or []
    master = src.get("master") if isinstance(src.get("master"), dict) else cur.get("master") or {}
    markers = src.get("markers") if isinstance(src.get("markers"), list) else cur.get("markers") or []
    tempo = src.get("tempo") if isinstance(src.get("tempo"), dict) else cur.get("tempo") or {}
    limit = MAX_SECONDS * rate
    return {
        "schema": SCHEMA,
        "project_id": cur.get("project_id") or (src.get("project_id") if isinstance(src.get("project_id"), str) else ""),
        "sample_rate": rate,
        "tracks": list(filter(None, (clean_track(t, rate) for t in tracks)))[:64],
        "master": {"volume_db": _num(master.get("volume_db"), -60, 12, 0), "effects": clean_effects(master.get("effects"))},
        "markers": sorted(({"id": m.get("id") if valid_id(m.get("id")) else new_id(), "at": _int(m.get("at"), 0, limit, 0), "name": _text(m.get("name"), 80),
                            "kind": m.get("kind") if m.get("kind") in ("marker", "chapter", "segment") else "marker"}
                           for m in markers if isinstance(m, dict)), key=lambda m: m["at"])[:1000],
        # For music projects: the tempo and first beat from song analysis, so the grid can snap to beats.
        "tempo": {"bpm": _num(tempo.get("bpm"), 20, 400, None), "first_beat": _int(tempo.get("first_beat"), 0, limit, 0), "beats_per_bar": _int(tempo.get("beats_per_bar"), 1, 16, 4)},
        "revision": _int(cur.get("revision"), 0, 2**53, 0) + (1 if current is not None else 0),   # goes up by one on every save
        "created": _num(cur.get("created", src.get("created")), 0, 1e11, time.time()),
        "updated": time.time(),
    }


def timeline_length(timeline):
    """Where the last clip ends, in samples."""
    return max((c["start"] + c["length"] for t in timeline["tracks"] for c in t["clips"]), default=0)


def assets_used(timeline):
    return sorted({c["asset_id"] for t in timeline["tracks"] for c in t["clips"]})


def audible_tracks(timeline):
    """Solo wins over mute: if any track is soloed only soloed tracks play; otherwise every track that is not muted."""
    solo = [t for t in timeline["tracks"] if t["solo"]]
    return solo if solo else [t for t in timeline["tracks"] if not t["mute"]]
