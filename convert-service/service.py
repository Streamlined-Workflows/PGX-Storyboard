"""SWIFT Director's converter: a small local service that turns a GLB file into the studio's FBX using Blender.

    GET  /info      {"ok": true, "blender": "4.0.2"}  (or ok false with the reason)
    POST /convert   body: the GLB file  ->  the FBX file, or JSON {"error": "..."} with a 4xx/5xx status

It listens on this computer only (127.0.0.1) and has no login, like the other services. Each file is converted in
its own temporary folder, which is deleted afterwards, by a separate Blender process with a time limit. Blender
makes no network requests here. Nothing is kept and nothing about a file is logged.
"""
import json
import os
import shlex
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CONVERT_PORT", "8193"))
HOST = os.environ.get("CONVERT_HOST", "127.0.0.1")
HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = shlex.split(os.environ.get("BLENDER_CMD", "blender --background --factory-startup --python-exit-code 1 --python"))
VERSION = shlex.split(os.environ.get("BLENDER_VERSION_CMD", "blender --version"))
MAX_BYTES = 512 * 1024 * 1024
TIME_LIMIT = int(os.environ.get("CONVERT_TIMEOUT", "600"))


def blender_version():
    try:
        out = subprocess.run(VERSION, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        words = line.split()
        if words and words[0] == "Blender" and len(words) > 1:
            return words[1]
    return out.strip().splitlines()[-1][:40] if out.strip() else None


def convert(data):
    """-> the FBX bytes. Raises ValueError with a reason a person can read."""
    if data[:4] != b"glTF":
        raise ValueError("That is not a GLB file.")
    with tempfile.TemporaryDirectory(prefix="swift-convert-") as folder:
        src, dst = os.path.join(folder, "in.glb"), os.path.join(folder, "out.fbx")
        with open(src, "wb") as f:
            f.write(data)
        try:
            done = subprocess.run(BLENDER + [os.path.join(HERE, "glb_to_fbx.py"), "--", src, dst], capture_output=True, text=True, timeout=TIME_LIMIT, cwd=folder)
        except subprocess.TimeoutExpired:
            raise ValueError(f"Blender did not finish within {TIME_LIMIT // 60} minutes, so the conversion was stopped.")
        except OSError:
            raise ValueError("Blender could not be started.")
        if done.returncode != 0 or not os.path.isfile(dst):
            said = [line for line in (done.stderr + "\n" + done.stdout).splitlines() if "no mesh" in line or "Error" in line]
            raise ValueError("The GLB file has no mesh in it." if any("no mesh" in s for s in said) else "Blender could not read or convert that file.")
        with open(dst, "rb") as f:
            return f.read()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, kind="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/info":
            v = blender_version()
            return self.reply(200, json.dumps({"ok": bool(v), "blender": v, "reason": "" if v else "Blender is not installed in the converter."}).encode())
        self.reply(404, b'{"error": "Not found"}')

    def do_POST(self):
        if self.path != "/convert":
            return self.reply(404, b'{"error": "Not found"}')
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 < size <= MAX_BYTES:
            return self.reply(413, b'{"error": "That file is larger than the converter reads."}')
        try:
            self.reply(200, convert(self.rfile.read(size)), "application/octet-stream")
        except ValueError as e:
            self.reply(422, json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    print(f"SWIFT Director converter on http://{HOST}:{PORT}  Blender {blender_version() or 'NOT FOUND'}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
