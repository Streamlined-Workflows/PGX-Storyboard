"""Identity Studio's API: everything under /api/identity/.

SWIFT Director's server hands these requests over with handle(); this module decides the rest.
It returns plain data and raises ValueError with a message a person can read.

    GET   /api/identity/info                  what the workspace offers (styles, layouts, platforms)
    GET   /api/identity/projects              list of identity projects
    GET   /api/identity/project?id=…          one project
    POST  /api/identity/projects              create        {name, description}
    PUT   /api/identity/project?id=…          save edits    {name?, description?, settings?}
    POST  /api/identity/projects/duplicate    {id}
    POST  /api/identity/projects/delete       {id}          moved to the trash folder; its jobs are cancelled
    GET   /api/identity/models                what Identity Studio runs that the storyboard does not, for System status
    GET   /api/identity/queue                 is the render queue free, and how many identity jobs are in play
    GET   /api/identity/jobs?project=…        identity jobs (all, or one project's)
    POST  /api/identity/jobs/cancel           {id}          stops that job only
    POST  /api/identity/jobs/retry            {id}

    POST  /api/identity/references?project=…&name=…   the image file itself as the request body
    GET   /api/identity/reference?project=…&id=…      the stored image (returns a File, not JSON)
    PUT   /api/identity/reference?project=…&id=…      {use?, note?, name?}
    POST  /api/identity/references/remove             {project, id}

There is deliberately no route that accepts a ComfyUI graph from the browser. Jobs are created by
module code (jobs().add), so the page can only ask for things the module knows how to build.
"""
import os

from . import references, schemas, tools
from .jobs import Jobs
from .storage import Store

PREFIX = "/api/identity/"
_store = None
_jobs = None


def store():
    """Created on first use, so tests and a future standalone app can choose the data folder."""
    global _store
    if _store is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _store = Store(os.environ.get("DATA_DIR", os.path.join(root, "data")))
    return _store


def use_store(custom, comfy=None):
    """Point the module at another data folder (and, for tests, another ComfyUI)."""
    global _store, _jobs
    _store = custom
    _jobs = Jobs(custom.root, comfy) if custom else None


def jobs():
    global _jobs
    if _jobs is None:
        _jobs = Jobs(store().root)
    return _jobs


def start():
    """Called once when the server starts, so jobs left waiting by a restart carry on."""
    jobs().start()


class File:
    """A stored file to send back as it is. The server adds headers that forbid scripts and outside resources."""

    def __init__(self, path, content_type):
        self.path, self.content_type = path, content_type


RAW_ROUTES = ("references",)        # POST routes whose body is a file, not JSON


def wants_raw(path):
    return path[len(PREFIX):] in RAW_ROUTES


def handles(path):
    return path.startswith(PREFIX)


def handle(method, path, query=None, payload=None, raw=None):
    """Answer one request. `query` and `payload` are plain dicts; `raw` is an uploaded file's bytes.
    Unknown routes raise LookupError."""
    query, payload = query or {}, payload if isinstance(payload, dict) else {}
    route = path[len(PREFIX):]
    s = store()
    if method == "GET":
        if route == "info":
            return {"module": "identity-studio", "schema": schemas.SCHEMA_VERSION, "phase": 1,
                    "styles": list(schemas.STYLES), "layouts": list(schemas.LAYOUTS),
                    "backgrounds": list(schemas.BACKGROUNDS), "platforms": list(schemas.PLATFORMS), "reference_uses": list(references.USES),
                    "ready": {"projects": True, "jobs": True, "generation": False, "references": True, "exports": False}}
        if route == "projects":
            return {"projects": s.list()}
        if route == "project":
            return s.load(query.get("id", ""))
        if route == "reference":
            return File(*s.reference_file(query.get("project", ""), query.get("id", "")))
        if route == "models":
            return tools.status()
        if route == "queue":
            return jobs().status()
        if route == "jobs":
            pid = query.get("project") or None
            if pid is not None and not schemas.valid_id(pid):
                raise ValueError("That is not a valid identity project id.")
            return {"jobs": jobs().list(pid)}
    elif method == "POST":
        if route == "projects":
            return s.create(payload.get("name", ""), payload.get("description", ""))
        if route == "references":
            return s.add_reference(query.get("project", ""), query.get("name", ""), raw or b"")
        if route == "references/remove":
            return s.remove_reference(payload.get("project", ""), payload.get("id", ""))
        if route == "projects/duplicate":
            return s.duplicate(payload.get("id", ""))
        if route == "projects/delete":
            done = s.delete(payload.get("id", ""))
            jobs().cancel_project(payload.get("id", ""))
            return done
        if route == "jobs/cancel":
            return jobs().cancel(payload.get("id", ""))
        if route == "jobs/retry":
            return jobs().retry(payload.get("id", ""))
    elif method == "PUT":
        if route == "project":
            return s.update(query.get("id", ""), payload)
        if route == "reference":
            return s.update_reference(query.get("project", ""), query.get("id", ""), payload)
    raise LookupError(path)
