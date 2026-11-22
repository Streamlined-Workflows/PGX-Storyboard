"""What an identity project looks like, and the checks that keep stored data well-formed.

No imports from the rest of SWIFT Director: this file must work on its own.
"""
import re
import time
import uuid

SCHEMA_VERSION = 1

# The starting styles offered in the workspace. Each is an editable prompt preset, not a limit.
STYLES = ("minimal geometric", "modern flat", "professional corporate", "technology-focused", "futuristic",
          "elegant", "monochromatic", "abstract", "illustrated", "custom")
LAYOUTS = ("icon only", "icon and text")
BACKGROUNDS = ("transparent", "light", "dark", "any")
PLATFORMS = ("general", "windows", "macos", "web", "teams")

NAME_MAX, TEXT_MAX = 120, 2000
_ID = re.compile(r"^[0-9a-f]{8,32}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def new_id():
    return uuid.uuid4().hex[:12]


def valid_id(value):
    """Ids become file names, so only short lowercase hex is ever accepted."""
    return isinstance(value, str) and bool(_ID.match(value))


def _text(value, limit, default=""):
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) else default


def _choice(value, allowed, default):
    return value if value in allowed else default


def default_settings():
    return {
        "app_name": "",            # the application or company the logo is for
        "tagline": "",
        "purpose": "",             # industry, or what the application does
        "description": "",         # what the logo should show
        "style": STYLES[0],
        "style_notes": "",         # the editable text of the chosen style preset
        "palette": [],             # "#rrggbb" strings, up to 8
        "background": BACKGROUNDS[0],
        "layout": LAYOUTS[0],
        "platforms": ["general"],
        "concept_count": 4,
    }


def clean_settings(incoming, current=None):
    """Return settings with every field present and valid. Unknown keys are dropped; bad values fall back."""
    base = dict(default_settings(), **(current or {}))
    src = incoming if isinstance(incoming, dict) else {}
    out = {
        "app_name": _text(src.get("app_name", base["app_name"]), NAME_MAX),
        "tagline": _text(src.get("tagline", base["tagline"]), 200),
        "purpose": _text(src.get("purpose", base["purpose"]), 300),
        "description": _text(src.get("description", base["description"]), TEXT_MAX),
        "style": _choice(src.get("style", base["style"]), STYLES, STYLES[0]),
        "style_notes": _text(src.get("style_notes", base["style_notes"]), TEXT_MAX),
        "background": _choice(src.get("background", base["background"]), BACKGROUNDS, BACKGROUNDS[0]),
        "layout": _choice(src.get("layout", base["layout"]), LAYOUTS, LAYOUTS[0]),
    }
    palette = src.get("palette", base["palette"])
    out["palette"] = [c.lower() for c in palette if isinstance(c, str) and _HEX.match(c)][:8] if isinstance(palette, list) else []
    platforms = src.get("platforms", base["platforms"])
    out["platforms"] = [p for p in PLATFORMS if isinstance(platforms, list) and p in platforms] or ["general"]
    try:
        out["concept_count"] = max(1, min(8, int(src.get("concept_count", base["concept_count"]))))
    except (TypeError, ValueError):
        out["concept_count"] = 4
    return out


def new_project(name="Untitled identity", description=""):
    now = time.time()
    return {
        "schema": SCHEMA_VERSION,
        "id": new_id(),
        "name": _text(name, NAME_MAX) or "Untitled identity",
        "description": _text(description, TEXT_MAX),
        "created": now,
        "updated": now,
        "brand_profile_id": None,      # a reusable brand profile (Phase 3)
        "settings": default_settings(),
        "references": [],              # uploaded vector assets and how each is used (Phase 3)
        "concepts": [],                # generated logos with their prompts and settings (Phase 2)
        "approved_concept_id": None,   # the chosen final identity (Phase 2)
        "exports": [],                 # packages produced from an approved identity (Phase 5)
    }


def normalize(project):
    """Bring a stored project up to the current shape without losing anything in it."""
    if not isinstance(project, dict) or not valid_id(project.get("id")):
        raise ValueError("This identity project file is damaged.")
    fresh = new_project()
    for key, value in fresh.items():
        project.setdefault(key, value)
    project["schema"] = SCHEMA_VERSION
    project["name"] = _text(project.get("name"), NAME_MAX) or "Untitled identity"
    project["description"] = _text(project.get("description"), TEXT_MAX)
    project["settings"] = clean_settings(project.get("settings"))
    for key in ("references", "concepts", "exports"):
        if not isinstance(project.get(key), list):
            project[key] = []
    return project


def summary(project):
    """The short form used in the project list."""
    return {"id": project["id"], "name": project["name"], "description": project["description"],
            "created": project["created"], "updated": project["updated"],
            "app_name": project["settings"]["app_name"], "concepts": len(project["concepts"]),
            "references": len(project["references"]), "approved": bool(project["approved_concept_id"])}
