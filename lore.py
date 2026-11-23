"""Lore: long background text about a setting, written once and tagged to any number of storyboards.

Entries live in <data>/lore/<id>.json and belong to no single project. A storyboard lists the ids
it uses in its own "lore" field. When Assisted Storyboard writes a story, casts it or plans shots,
the tagged entries are given to the language model as background.
"""
import json
import os
import re
import threading
import time
import uuid

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
LOCK = threading.RLock()
BUDGET = 12000            # characters of lore given to the language model for one storyboard
TITLE_MAX, TEXT_MAX = 120, 200000
_ID = re.compile(r"^[0-9a-f]{8,32}$")


def _dir():
    return os.path.join(DATA_DIR, "lore")


def _path(lid):
    if not isinstance(lid, str) or not _ID.match(lid):
        raise ValueError("That is not a valid lore entry.")
    return os.path.join(_dir(), lid + ".json")


def load(lid):
    try:
        with open(_path(lid)) as f:
            entry = json.load(f)
    except (OSError, ValueError):
        raise ValueError("That lore entry no longer exists.")
    entry.setdefault("title", "Untitled lore"); entry.setdefault("text", "")
    return entry


def entries():
    """Every entry, most recently edited first."""
    out = []
    with LOCK:
        if os.path.isdir(_dir()):
            for name in os.listdir(_dir()):
                if name.endswith(".json") and _ID.match(name[:-5]):
                    try:
                        out.append(load(name[:-5]))
                    except ValueError:
                        continue
    return sorted(out, key=lambda e: e.get("updated", 0), reverse=True)


def save(lid, title, text):
    """Create (lid empty) or update an entry."""
    with LOCK:
        now = time.time()
        entry = load(lid) if lid else {"id": uuid.uuid4().hex[:12], "created": now}
        entry["title"] = str(title or "").strip()[:TITLE_MAX] or "Untitled lore"
        entry["text"] = str(text or "")[:TEXT_MAX]
        entry["updated"] = now
        os.makedirs(_dir(), exist_ok=True)
        path = _path(entry["id"])
        with open(path + ".tmp", "w") as f:
            json.dump(entry, f, indent=1)
        os.replace(path + ".tmp", path)
        return entry


def delete(lid):
    """Move an entry to the trash folder. Storyboards that tagged it simply stop finding it."""
    with LOCK:
        path = _path(lid)
        if not os.path.isfile(path):
            raise ValueError("That lore entry no longer exists.")
        trash = os.path.join(DATA_DIR, "trash")
        os.makedirs(trash, exist_ok=True)
        os.replace(path, os.path.join(trash, f"lore-{lid}-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    return {"deleted": lid}


def for_model(ids):
    """The tagged entries as one block of text for the language model, cut at BUDGET characters.
    -> (text, True if something had to be left out)."""
    parts, used, cut = [], 0, False
    for lid in ids or []:
        try:
            entry = load(lid)
        except ValueError:
            continue
        body = entry["text"].strip()
        if not body:
            continue
        room = BUDGET - used
        if room <= 200:
            cut = True
            break
        if len(body) > room:
            body, cut = body[:room].rsplit(" ", 1)[0] + " …", True
        parts.append(f"## {entry['title']}\n{body}")
        used += len(body)
    return "\n\n".join(parts), cut
