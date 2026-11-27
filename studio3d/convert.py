"""Talking to the converter service (convert-service/): Blender, run without a window, that turns GLB into FBX.

The studio never runs Blender itself. If the service is not there, GLB import is simply unavailable and says why.
A converter is only trusted after it has passed a real test on this machine (decision Q19-04): `self_test` converts a
known one-metre cube and checks the result is the studio's conventions and the right size. The pass is remembered
for that exact Blender version, so an updated Blender has to pass again.
"""
import json
import os
import struct
import time
import urllib.error
import urllib.request

from . import fbx

URL = os.environ.get("CONVERT_URL", "http://127.0.0.1:8193")
PROVIDER = "blender.convert"
_seen = {"at": 0.0, "info": None}


def info(fresh=False):
    """-> {"ok", "blender", "reason"}; the answer is reused for 20 seconds."""
    if not fresh and time.time() - _seen["at"] < 20 and _seen["info"]:
        return _seen["info"]
    try:
        with urllib.request.urlopen(URL + "/info", timeout=5) as r:
            got = json.loads(r.read())
        out = {"ok": bool(got.get("ok")), "blender": str(got.get("blender") or "")[:40], "reason": str(got.get("reason") or "")[:200]}
    except (OSError, ValueError):
        out = {"ok": False, "blender": "", "reason": "The converter service is not running on this computer."}
    _seen.update(at=time.time(), info=out)
    return out


def glb_to_fbx(data, timeout=660):
    req = urllib.request.Request(URL + "/convert", data=data, headers={"Content-Type": "application/octet-stream"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        try:
            raise ValueError(json.loads(e.read()).get("error") or "The converter could not convert that file.")
        except (ValueError, AttributeError) as inner:
            if isinstance(inner, ValueError) and inner.args and not isinstance(inner, json.JSONDecodeError):
                raise
            raise ValueError("The converter could not convert that file.")
    except OSError:
        raise ValueError("The converter service did not answer. It may not be running.")


def test_cube():
    """A one-metre cube standing on the ground, 2 m forward and 3 m to +X, as a GLB. Off-centre so a flipped axis shows."""
    h = 0.5
    pts = [(x, y + h, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    tris = [0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3]
    vb, ib = b"".join(struct.pack("<3f", *p) for p in pts), struct.pack("<36H", *tris)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "TestCube", "translation": [3, 0, 2]}],
           "meshes": [{"name": "TestCube", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}], "buffers": [{"byteLength": len(vb) + len(ib)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vb), "target": 34962}, {"buffer": 0, "byteOffset": len(vb), "byteLength": len(ib), "target": 34963}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-h, 0, -h], "max": [h, 1, h]}, {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = vb + ib
    return b"glTF" + struct.pack("<II", 2, 28 + len(js) + len(body)) + struct.pack("<I", len(js)) + b"JSON" + js + struct.pack("<I", len(body)) + b"BIN\x00" + body


def check(report):
    """Is a converted test cube what it should be? -> the list of things wrong (empty when it passes)."""
    wrong = []
    c, t = report["conventions"], report["totals"]
    if not c["canonical"]:
        wrong.append("the axes or units are not the studio's: " + " ".join(c["notes"]))
    if t["vertices"] != 8:
        wrong.append(f"it has {t['vertices']} control points instead of 8")
    if not t["bounds"]:
        return wrong + ["it has no measurable size"]
    (x0, y0, z0), (x1, y1, z1) = t["bounds"]
    near = lambda a, b: abs(a - b) <= 0.5
    if not all(near(a, b) for a, b in ((x1 - x0, 100), (y1 - y0, 100), (z1 - z0, 100))):
        wrong.append(f"a one-metre cube came out {x1 - x0:.1f} × {y1 - y0:.1f} × {z1 - z0:.1f} cm")
    if not (near(y0, 0) and near((x0 + x1) / 2, 300) and near((z0 + z1) / 2, 200)):
        wrong.append("it was moved or turned: it should stand on the ground 3 m along +X and 2 m along +Z")
    if any(d["severity"] in ("technical failure", "significant defect") for d in report["defects"]):
        wrong.append("the converted mesh has faults")
    return wrong


def self_test(run=glb_to_fbx):
    """Convert the test cube and judge it. -> {"passed", "problems", "blender"}"""
    version = info(fresh=True)
    if not version["ok"]:
        return {"passed": False, "problems": [version["reason"]], "blender": ""}
    try:
        problems = check(fbx.analyse(run(test_cube())))
    except (ValueError, fbx.FBXError) as e:
        problems = [str(e)]
    return {"passed": not problems, "problems": problems, "blender": version["blender"]}
