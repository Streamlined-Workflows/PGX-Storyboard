"""Every /api/audio/ route. The server hands requests here and sends back whatever this returns.

    GET   /api/audio/info                              limits, kinds, whether the audio tools are present
    GET   /api/audio/assets?project=…                  the sounds this project uses
    POST  /api/audio/assets?project=…&name=…&kind=…    the file itself as the request body
    POST  /api/audio/assets/adopt       {project}      brings the project's earlier audio uploads into the library
    GET   /api/audio/asset/file?id=…                   the original file
    GET   /api/audio/asset/peaks?id=…                  cached waveform data
    PUT   /api/audio/asset?id=…         {name?, kind?, approval?, tags?, category?}
    POST  /api/audio/assets/remove      {project, id}
    GET   /api/audio/timeline?project=…
    PUT   /api/audio/timeline?project=… {timeline, based_on}
"""
import os

from . import media, schemas
from .storage import Conflict, Library

PREFIX = "/api/audio/"
RAW_ROUTES = ("assets",)
_library = None
_hooks = {"project_audio": None}


class File:
    def __init__(self, path, content_type):
        self.path, self.content_type = path, content_type


def library():
    global _library
    if _library is None:
        _library = Library(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")))
    return _library


def use_library(custom):
    global _library
    _library = custom


def configure(project_audio=None):
    """project_audio(project_id) -> [(name, bytes)]: the host's way of handing over audio a project uploaded before
    the library existed. Without it, adopt simply finds nothing."""
    _hooks["project_audio"] = project_audio


def handles(path):
    return path.startswith(PREFIX)


def wants_raw(path):
    return path[len(PREFIX):] in RAW_ROUTES


def handle(method, path, query=None, payload=None, raw=None):
    route, query, payload, lib = path[len(PREFIX):], query or {}, payload if isinstance(payload, dict) else {}, library()
    if method == "GET":
        if route == "info":
            return {"schema": schemas.SCHEMA, "tools": media.has_ffmpeg(), "sample_rate": schemas.DEFAULT_RATE, "asset_kinds": list(schemas.ASSET_KINDS),
                    "track_kinds": list(schemas.TRACK_KINDS), "peak_rate": media.PEAK_RATE, "max_tracks": 64}
        if route == "assets":
            return {"assets": lib.for_project(_project(query))}
        if route == "asset/file":
            return File(*lib.file(query.get("id", "")))
        if route == "asset/peaks":
            return File(*lib.peaks_file(query.get("id", "")))
        if route == "timeline":
            return lib.timeline(_project(query))
    if method == "POST":
        if route == "assets":
            kind = query.get("kind") if query.get("kind") in schemas.ASSET_KINDS else "other"
            asset, existed = lib.add(query.get("name", ""), raw or b"", _project(query), kind)
            return dict(asset, already_there=existed)
        if route == "assets/adopt":
            project = _project(payload)
            found = _hooks["project_audio"](project) if _hooks["project_audio"] else []
            brought, problems = [], []
            for name, data in found:
                try:
                    brought.append(lib.add(name, data, project, "music")[0]["id"])
                except ValueError as e:
                    problems.append(f"{name}: {e}")
            return {"brought": brought, "problems": problems}
        if route == "assets/remove":
            return lib.remove_from(payload.get("id", ""), _project(payload))
    if method == "PUT":
        if route == "asset":
            return lib.update(query.get("id", ""), payload)
        if route == "timeline":
            based = payload.get("based_on")
            return lib.save_timeline(_project(query), payload.get("timeline"), based if isinstance(based, int) and not isinstance(based, bool) else None)
    raise LookupError(route)


def _project(source):
    pid = source.get("project", "")
    if not isinstance(pid, str) or not pid:
        raise ValueError("Open a project first.")
    return pid
