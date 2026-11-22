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

    PUT   …/reference also takes {enabled: true|false}: whether generation uses that reference
    POST  /api/identity/reference/flat?project=…&id=…  a flattened PNG of the reference, made by the page
    POST  /api/identity/concepts/generate              {project, direction?, insert?}   queues the brief's concepts
          insert = {reference, canvas, mask}: PNG data URLs the page makes when a reference is set to "insert"
    GET   /api/identity/concept?project=…&id=…         a finished concept's picture
    POST  /api/identity/concepts/fix?project=…&id=…&prompt=…   the painted mask (PNG) as the body
    POST  /api/identity/concepts/remove                {project, id}           refused while the concept is locked
    POST  /api/identity/concepts/lock                  {project, id, locked}
    POST  /api/identity/concepts/clean                 {project}   erases every concept that is not locked

There is deliberately no route that accepts a ComfyUI graph from the browser. Jobs are created by
module code (jobs().add), so the page can only ask for things the module knows how to build.
"""
import os

from . import generate, references, schemas, tools
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
    if _jobs:
        _jobs.on_change = lambda job: generate.on_job_change(custom, _jobs, job)


def jobs():
    global _jobs
    if _jobs is None:
        _jobs = Jobs(store().root)
    if _jobs.on_change is None:
        _jobs.on_change = lambda job: generate.on_job_change(store(), _jobs, job)
    return _jobs


def configure(**builders):
    """The host hands in its FLUX.2 graph builders here. See generate.configure."""
    generate.configure(**builders)


def start():
    """Called once when the server starts, so jobs left waiting by a restart carry on."""
    jobs().start()


class File:
    """A stored file to send back as it is. The server adds headers that forbid scripts and outside resources."""

    def __init__(self, path, content_type):
        self.path, self.content_type = path, content_type


RAW_ROUTES = ("references", "reference/flat", "concepts/fix")        # POST routes whose body is a file, not JSON


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
                    "backgrounds": list(schemas.BACKGROUNDS), "platforms": list(schemas.PLATFORMS), "reference_uses": list(references.USES), "max_references": generate.MAX_REFS,
                    "sizes": {k: list(v) for k, v in generate.SIZES.items()},
                    "ready": {"projects": True, "jobs": True, "generation": generate.ready(), "fix": generate.can_fix(), "references": True, "exports": False}}
        if route == "projects":
            return {"projects": s.list()}
        if route == "project":
            return s.load(query.get("id", ""))
        if route == "reference":
            return File(*s.reference_file(query.get("project", ""), query.get("id", "")))
        if route == "concept":
            return File(*s.concept_file(query.get("project", ""), query.get("id", "")))
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
        if route == "reference/flat":
            return s.save_reference_flat(query.get("project", ""), query.get("id", ""), raw or b"")
        if route == "concepts/generate":
            return generate.queue_concepts(s, jobs(), payload.get("project", ""), payload.get("direction", ""),
                                           payload.get("insert") if isinstance(payload.get("insert"), dict) else None)
        if route == "concepts/fix":
            return generate.queue_fix(s, jobs(), query.get("project", ""), query.get("id", ""), raw or b"", query.get("prompt", ""))
        if route == "concepts/remove":
            concept = s.remove_concept(payload.get("project", ""), payload.get("id", ""))
            if concept.get("job") and concept.get("state") in ("waiting", "running"):
                try:
                    jobs().cancel(concept["job"])
                except ValueError:
                    pass
            return {"removed": concept["id"]}
        if route == "concepts/lock":
            return s.lock_concept(payload.get("project", ""), payload.get("id", ""), payload.get("locked") is True)
        if route == "concepts/clean":
            return s.clean_concepts(payload.get("project", ""))
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
