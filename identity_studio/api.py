"""Identity Studio's API: everything under /api/identity/.

SWIFT Director's server hands these requests over with handle(); this module decides the rest.
It returns plain data and raises ValueError with a message a person can read.

    GET   /api/identity/info                  what the workspace offers (styles, layouts, platforms)
    GET   /api/identity/projects              list of identity projects
    GET   /api/identity/project?id=…          one project
    POST  /api/identity/projects              create        {name, description}
    PUT   /api/identity/project?id=…          save edits    {name?, description?, settings?}
    POST  /api/identity/projects/duplicate    {id}
    POST  /api/identity/projects/delete       {id}          moved to the trash folder
"""
import os

from . import schemas
from .storage import Store

PREFIX = "/api/identity/"
_store = None


def store():
    """Created on first use, so tests and a future standalone app can choose the data folder."""
    global _store
    if _store is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _store = Store(os.environ.get("DATA_DIR", os.path.join(root, "data")))
    return _store


def use_store(custom):
    global _store
    _store = custom


def handles(path):
    return path.startswith(PREFIX)


def handle(method, path, query=None, payload=None):
    """Answer one request. `query` and `payload` are plain dicts. Unknown routes raise LookupError."""
    query, payload = query or {}, payload if isinstance(payload, dict) else {}
    route = path[len(PREFIX):]
    s = store()
    if method == "GET":
        if route == "info":
            return {"module": "identity-studio", "schema": schemas.SCHEMA_VERSION, "phase": 1,
                    "styles": list(schemas.STYLES), "layouts": list(schemas.LAYOUTS),
                    "backgrounds": list(schemas.BACKGROUNDS), "platforms": list(schemas.PLATFORMS),
                    "ready": {"projects": True, "generation": False, "references": False, "exports": False}}
        if route == "projects":
            return {"projects": s.list()}
        if route == "project":
            return s.load(query.get("id", ""))
    elif method == "POST":
        if route == "projects":
            return s.create(payload.get("name", ""), payload.get("description", ""))
        if route == "projects/duplicate":
            return s.duplicate(payload.get("id", ""))
        if route == "projects/delete":
            return s.delete(payload.get("id", ""))
    elif method == "PUT":
        if route == "project":
            return s.update(query.get("id", ""), payload)
    raise LookupError(path)
