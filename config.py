"""Project configuration: the settings behind the Project Configuration Center.

Every storyboard carries a `config` block (project schema 2). This file owns its shape: the
choices each field offers, the defaults, and the cleaning of anything a browser sends. A project
from before schema 2 gets the defaults in memory when it is opened, so it behaves exactly as it
did; its file is rewritten only when it is next saved.

What is stored and what is used are different things. USED lists the settings that change what
the application does today. Everything else is kept for the milestone that will act on it, and
the interface says so beside each one.
"""
import copy
import json
import os

SCHEMA = 2
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

# (key, label) pairs, in the order shown. Keys are stored; labels are what a person reads.
RATINGS = [("E", "E: Everyone"), ("PG-13", "PG-13"), ("R", "R"), ("M", "M"), ("X", "X")]
VIDEO_TYPES = [("story", "Story"), ("music_video", "Music Video"), ("commercial", "Commercial")]
STORY_TYPES = [("short_story", "Short Story"), ("series", "Series"), ("story_scene", "Story Scene")]
STORY_SUBTYPES = [("narrative", "Narrative"), ("musical", "Musical"), ("in_between", "In-between"), ("cinematic", "Cinematic")]
IN_BETWEEN = [("set_up_event", "Set Up Event"), ("foreshadowing", "Foreshadowing"), ("time_lapse", "Time Lapse")]
MUSIC_TYPES = [("single", "Single"), ("album_song", "Album Song")]
MUSIC_SUBTYPES = [("live_performance", "Live Performance"), ("reenactment", "Re-enactment of Events"), ("abstract", "Abstract Videos"),
                  ("lyric", "Lyric Videos"), ("bpm", "BPM Videos"), ("dance", "Dance Videos"), ("montage", "Montage Videos")]
COMMERCIAL_TYPES = [("product_ad", "Product Advertisement"), ("brand_story", "Brand Story"), ("trailer", "Promotional Trailer"),
                    ("explainer", "Explainer"), ("social_ad", "Social Advertisement"), ("psa", "Public Service Announcement")]
ASPECTS = [("16:9", "16:9"), ("9:16", "9:16"), ("1:1", "1:1"), ("21:9", "21:9"), ("custom", "Custom")]
RESOLUTIONS = [("720p", "720p"), ("1080p", "1080p"), ("1440p", "1440p"), ("4k", "4K")]
FPS = [(24, "24"), (30, "30"), (60, "60")]
PLATFORMS = [("general", "General"), ("youtube", "YouTube"), ("social", "Social Media"), ("custom", "Custom")]
DIRECTIONS = [("realistic", "Realistic"), ("stylized", "Stylized"), ("animated", "Animated"), ("cinematic", "Cinematic"), ("custom_reference", "Custom Reference")]
DETAILS = [("basic", "Basic"), ("standard", "Standard"), ("cinematic", "Cinematic")]
ENVIRONMENTS = [("local", "Local"), ("remote", "Remote"), ("hybrid", "Hybrid")]
CONTINUITY = [("character", "Character continuity"), ("environment", "Environment continuity"), ("costume", "Costume continuity"),
              ("style", "Visual-style continuity"), ("narrative", "Narrative continuity")]
WORKFLOW = [("approve_each_scene", "Require approval for each scene"), ("approve_each_shot", "Require approval for each shot"),
            ("approve_before_assets", "Require approval before generating assets"), ("approve_before_render", "Require approval before rendering video"),
            ("auto_progress", "Allow automatic progression through approved stages"), ("keep_alternatives", "Preserve generated alternatives"),
            ("keep_history", "Preserve production history"), ("auto_model_recommendations", "Allow automatic model recommendations")]
ROLES = [("analysis", "Analysis Model"), ("prompting", "Prompting Model"), ("image", "Image Model"), ("image_lora", "Image Model LoRA"),
         ("singing_video", "Singing Video Model"), ("story_video", "Story Video Model"), ("begin_end_video", "Begin/End Video Model"),
         ("stt", "STT Model"), ("tts", "TTS Model")]

# The settings that change behaviour today. Anything not here is stored and labelled "not used yet".
USED = ("identity.music.subtype", "production.storyboard_detail")

DEFAULTS = {
    "identity": {
        "rating": "PG-13",
        "video_type": "music_video",
        "story": {"type": "short_story", "subtype": "narrative", "in_between_purpose": "set_up_event"},
        "music": {"type": "single", "subtype": "reenactment"},
        "commercial": {"type": "product_ad", "audience": "", "message": "", "call_to_action": "", "runtime": None},
    },
    "models": {key: "auto" for key, _ in ROLES},
    "production": {
        "aspect": "16:9", "custom_aspect": "", "export_resolution": "1080p", "target_fps": 24, "platform": "general",
        "visual_direction": "cinematic", "visual_notes": "", "visual_references": [],
        "storyboard_detail": "standard",
        "continuity": {key: True for key, _ in CONTINUITY},
        "environment": "local",
    },
    "workflow": {"approve_each_scene": False, "approve_each_shot": False, "approve_before_assets": False, "approve_before_render": True,
                 "auto_progress": False, "keep_alternatives": True, "keep_history": True, "auto_model_recommendations": True},
}


def _pick(value, options, fallback):
    return value if value in [k for k, _ in options] else fallback


def _text(value, limit, fallback=""):
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else fallback


def _get(source, *path):
    for key in path:
        source = source.get(key) if isinstance(source, dict) else None
    return source


def clean(incoming, current=None):
    """A complete, valid config. Starts from `current` (or the defaults), takes each valid value from `incoming`,
    and keeps the current value wherever `incoming` is missing or wrong. Nothing is ever deleted: the settings
    for the video types that are not selected stay as they were."""
    base = copy.deepcopy(DEFAULTS)
    for source in (current, incoming):                       # layering: defaults, then what was stored, then the edit
        if not isinstance(source, dict):
            continue
        g = lambda *path: _get(source, *path)
        i = base["identity"]
        i["rating"] = _pick(g("identity", "rating"), RATINGS, i["rating"])
        i["video_type"] = _pick(g("identity", "video_type"), VIDEO_TYPES, i["video_type"])
        i["story"]["type"] = _pick(g("identity", "story", "type"), STORY_TYPES, i["story"]["type"])
        i["story"]["subtype"] = _pick(g("identity", "story", "subtype"), STORY_SUBTYPES, i["story"]["subtype"])
        i["story"]["in_between_purpose"] = _pick(g("identity", "story", "in_between_purpose"), IN_BETWEEN, i["story"]["in_between_purpose"])
        i["music"]["type"] = _pick(g("identity", "music", "type"), MUSIC_TYPES, i["music"]["type"])
        i["music"]["subtype"] = _pick(g("identity", "music", "subtype"), MUSIC_SUBTYPES, i["music"]["subtype"])
        c = i["commercial"]
        c["type"] = _pick(g("identity", "commercial", "type"), COMMERCIAL_TYPES, c["type"])
        for key, limit in (("audience", 300), ("message", 600), ("call_to_action", 200)):
            if g("identity", "commercial", key) is not None:
                c[key] = _text(g("identity", "commercial", key), limit, c[key])
        given = g("identity", "commercial")
        if isinstance(given, dict) and "runtime" in given:   # seconds, or empty for "not decided"
            runtime = given["runtime"]
            ok = isinstance(runtime, (int, float)) and not isinstance(runtime, bool) and 1 <= runtime <= 3600
            c["runtime"] = round(float(runtime), 1) if ok else None
        for key, _ in ROLES:                                 # "auto" or "<provider>:<identifier>"; Milestone 2 checks the identifier
            value = g("models", key)
            if value == "auto" or (isinstance(value, str) and ":" in value and len(value) <= 200):
                base["models"][key] = value
        p = base["production"]
        p["aspect"] = _pick(g("production", "aspect"), ASPECTS, p["aspect"])
        if g("production", "custom_aspect") is not None:
            p["custom_aspect"] = _text(g("production", "custom_aspect"), 20, p["custom_aspect"])
        p["export_resolution"] = _pick(g("production", "export_resolution"), RESOLUTIONS, p["export_resolution"])
        p["target_fps"] = _pick(g("production", "target_fps"), FPS, p["target_fps"])
        p["platform"] = _pick(g("production", "platform"), PLATFORMS, p["platform"])
        p["visual_direction"] = _pick(g("production", "visual_direction"), DIRECTIONS, p["visual_direction"])
        if g("production", "visual_notes") is not None:
            p["visual_notes"] = _text(g("production", "visual_notes"), 1200, p["visual_notes"])
        refs = g("production", "visual_references")
        if isinstance(refs, list):
            p["visual_references"] = [r for r in refs if isinstance(r, str) and r][:12]
        p["storyboard_detail"] = _pick(g("production", "storyboard_detail"), DETAILS, p["storyboard_detail"])
        p["environment"] = _pick(g("production", "environment"), ENVIRONMENTS, p["environment"])
        for key, _ in CONTINUITY:
            if isinstance(g("production", "continuity", key), bool):
                p["continuity"][key] = g("production", "continuity", key)
        for key, _ in WORKFLOW:
            if isinstance(g("workflow", key), bool):
                base["workflow"][key] = g("workflow", key)
    return base


# ---------- defaults for new projects ----------

def _defaults_path():
    return os.path.join(DATA_DIR, "defaults.json")


def new_project_config():
    """What a newly created project starts with: the person's saved defaults, or the built-in ones."""
    try:
        with open(_defaults_path()) as f:
            return clean(json.load(f))
    except (OSError, ValueError):
        return clean(None)


def save_defaults(config):
    value = clean(config)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_defaults_path() + ".tmp", "w") as f:
        json.dump(value, f, indent=1)
    os.replace(_defaults_path() + ".tmp", _defaults_path())
    return value


def has_saved_defaults():
    return os.path.isfile(_defaults_path())


# ---------- the two settings that take effect in Milestone 1 ----------

# Added to the story request for a music video. The default (re-enactment) adds nothing, so existing
# projects get exactly the story they got before.
MUSIC_GUIDANCE = {
    "live_performance": "This is a live performance video. Stay with the performers, their instruments and the stage: each segment is a moment of the performance, and the story is how the performance builds. Do not cut away to a separate plot.",
    "reenactment": "",
    "abstract": "This is an abstract video. Do not tell a literal plot: describe images, shapes, colour, motion and texture that carry the feeling of each segment.",
    "lyric": "This is a lyric video. Each segment is a visual background for the words on screen: one clear, uncluttered image or slow motion per segment that suits its lyric, with room left for typography.",
    "bpm": "This is a BPM video. Drive every segment from the rhythm: describe motion, pulses and transitions that land on the beat, with intensity following the energy of the music.",
    "dance": "This is a dance video. Keep the dancers and their movement at the centre: each segment is a phrase of choreography, with continuity of place and costume unless the music changes section.",
    "montage": "This is a montage video. Each segment is its own short scene; vary the places and moments, and link them by theme and by the order of the song, not by one continuous plot.",
}
# Added to the shot-planning request. "standard" adds nothing.
DETAIL_GUIDANCE = {
    "basic": "Keep every description short: one or two plain sentences saying who or what is in frame and where.",
    "standard": "",
    "cinematic": "Write every description as three or four sentences and be specific about the framing and lens feel, the direction, quality and colour of the light, depth and what is in the foreground and background, and the composition of the frame.",
}


def story_guidance(config):
    c = clean(config)
    return MUSIC_GUIDANCE[c["identity"]["music"]["subtype"]] if c["identity"]["video_type"] == "music_video" else ""


def shot_guidance(config):
    return DETAIL_GUIDANCE[clean(config)["production"]["storyboard_detail"]]


def options():
    """Everything the interface needs to draw the Configuration Center."""
    pairs = lambda items: [{"key": k, "label": l} for k, l in items]
    return {"schema": SCHEMA, "used": list(USED), "defaults": new_project_config(), "saved_defaults": has_saved_defaults(),
            "ratings": pairs(RATINGS), "video_types": pairs(VIDEO_TYPES), "story_types": pairs(STORY_TYPES), "story_subtypes": pairs(STORY_SUBTYPES),
            "in_between": pairs(IN_BETWEEN), "music_types": pairs(MUSIC_TYPES), "music_subtypes": pairs(MUSIC_SUBTYPES),
            "commercial_types": pairs(COMMERCIAL_TYPES), "aspects": pairs(ASPECTS), "resolutions": pairs(RESOLUTIONS), "fps": pairs(FPS),
            "platforms": pairs(PLATFORMS), "directions": pairs(DIRECTIONS), "details": pairs(DETAILS), "environments": pairs(ENVIRONMENTS),
            "continuity": pairs(CONTINUITY), "workflow": pairs(WORKFLOW), "roles": pairs(ROLES)}
