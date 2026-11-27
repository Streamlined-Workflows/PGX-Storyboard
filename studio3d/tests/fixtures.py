"""Small FBX files made in memory for the tests and the browser checks. Not shipped as assets."""
import array

from studio3d.fbx import Long, Node, write

CUBE = ([-50, 0, -50, 50, 0, -50, 50, 100, -50, -50, 100, -50, -50, 0, 50, 50, 0, 50, 50, 100, 50, -50, 100, 50],
        [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5]])


def poly_index(faces):
    out = []
    for f in faces:
        out += list(f[:-1]) + [-f[-1] - 1]
    return array.array("i", out)


def p70(**props):
    kids = []
    for name, value in props.items():
        name = name.replace("_", " ")
        if isinstance(value, (list, tuple)):
            kids.append(Node("P", [name, name, "", "A"] + [float(v) for v in value]))
        elif isinstance(value, float):
            kids.append(Node("P", [name, "double", "Number", "", value]))
        else:
            kids.append(Node("P", [name, "int", "Integer", "", int(value)]))
    return Node("Properties70", [], kids)


def mesh(gid, name, verts, faces, uv=False, material_slots=0):
    kids = [Node("Vertices", [array.array("d", [float(v) for v in verts])]), Node("PolygonVertexIndex", [poly_index(faces)])]
    if uv:
        corners = sum(len(f) for f in faces)
        kids.append(Node("LayerElementUV", [0], [Node("Name", ["UVMap"]), Node("MappingInformationType", ["ByPolygonVertex"]), Node("ReferenceInformationType", ["IndexToDirect"]),
                                                 Node("UV", [array.array("d", [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0] * corners)[:corners * 2]]), Node("UVIndex", [array.array("i", range(corners))])]))
    if material_slots:
        kids.append(Node("LayerElementMaterial", [0], [Node("MappingInformationType", ["ByPolygon"]), Node("Materials", [array.array("i", [k % material_slots for k in range(len(faces))])])]))
    return Node("Geometry", [Long(gid), name + "\x00\x01Geometry", "Mesh"], kids)


def model(mid, name, kind="Mesh", translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    return Node("Model", [Long(mid), name + "\x00\x01Model", kind], [Node("Version", [232]), p70(Lcl_Translation=translation, Lcl_Rotation=rotation, Lcl_Scaling=scale)])


def scene(objects, links, version=7400, up=1, front=2, unit=1.0, extra=()):
    settings = Node("GlobalSettings", [], [Node("Version", [1000]), p70(UpAxis=up, UpAxisSign=1, FrontAxis=front, FrontAxisSign=1, CoordAxis=0, CoordAxisSign=1, UnitScaleFactor=float(unit))])
    return write([Node("FBXHeaderExtension", [], [Node("FBXVersion", [version])]), settings, Node("Objects", [], list(objects) + list(extra)),
                  Node("Connections", [], [Node("C", ["OO", Long(a), Long(b)]) for a, b in links])], version)


def cube(version=7400, **kw):
    """One cube, a metre on each side, standing on the ground: 8 control points, 6 quads."""
    return scene([mesh(100, "Cube", *CUBE, uv=kw.pop("uv", False)), model(200, "Cube")], [(100, 200), (200, 0)], version, **kw)


def character():
    """A stand-in modular character: a body, a hat above it, and a coat around it, under one root. Not a real figure."""
    body = ([-20, 0, -10, 20, 0, -10, 20, 170, -10, -20, 170, -10, -20, 0, 10, 20, 0, 10, 20, 170, 10, -20, 170, 10], CUBE[1])
    hat = ([-15, 0, -15, 15, 0, -15, 15, 12, -15, -15, 12, -15, -15, 0, 15, 15, 0, 15, 15, 12, 15, -15, 12, 15], CUBE[1])
    coat = ([-24, 0, -13, 24, 0, -13, 24, 70, -13, -24, 70, -13, -24, 0, 13, 24, 0, 13, 24, 70, 13, -24, 70, 13], CUBE[1][:4])     # open top and bottom
    objs = [model(1, "Captain", "Null"), mesh(10, "Body", *body, uv=True, material_slots=2), model(11, "Base_Body"),
            mesh(20, "Hat", *hat), model(21, "Pirate_Hat", translation=(0, 170, 0)), mesh(30, "Coat", *coat), model(31, "Pirate_Coat", translation=(0, 80, 0))]
    return scene(objs, [(1, 0), (11, 1), (10, 11), (21, 1), (20, 21), (31, 1), (30, 31)])


def broken():
    """A cube with known faults: a face with a repeated corner, a duplicated face, and a point nothing uses."""
    verts = CUBE[0] + [999, 999, 999]
    faces = CUBE[1] + [[0, 1, 1, 2], [0, 3, 2, 1]]
    return scene([mesh(100, "Broken", verts, faces), model(200, "Broken")], [(100, 200), (200, 0)])


def glb_cube(size=1.0, lift=0.5, name="Crate", at=(0, 0, 0)):
    """A cube as a binary glTF file (GLB), in metres as GLB is, standing on the ground. 8 points, 12 triangles."""
    import json
    import struct
    h = size / 2
    pts = [(x, y + lift, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    tris = [0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3]
    vb, ib = b"".join(struct.pack("<3f", *p) for p in pts), struct.pack("<36H", *tris)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name, "translation": list(at)}],
           "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "buffers": [{"byteLength": len(vb) + len(ib)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vb), "target": 34962}, {"buffer": 0, "byteOffset": len(vb), "byteLength": len(ib), "target": 34963}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [min(p[i] for p in pts) for i in range(3)], "max": [max(p[i] for p in pts) for i in range(3)]},
                         {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = vb + ib
    body += b"\x00" * (-len(body) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body)) + struct.pack("<I", len(js)) + b"JSON" + js + struct.pack("<I", len(body)) + b"BIN\x00" + body
