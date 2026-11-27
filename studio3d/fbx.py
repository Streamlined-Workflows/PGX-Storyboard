"""Reading FBX files: what is in them, how big they are, and whether they are sound.

FBX is the one geometry format the 3D studio keeps (3d_Generation_Plan/3d_Phase_4.md, 4.14). This module reads the
binary form of it with nothing but the standard library, so the application can measure and check a file itself and
never has to take a tool's word for it (Phase 6, GPB-003). It only reads: a file is never changed here.

    analyse(data) -> report      everything below, as plain data that can be stored as JSON
    parse(data)   -> Node        the raw tree, for anything else
    write(nodes, version) -> bytes   a minimal writer, used to make test files

The report:
    version, conventions {up, front, coord, unit_scale, canonical, notes}
    models      [{id, name, kind, parent, translation, rotation, scale, geometry}]   the hierarchy
    geometries  [{id, name, model, vertices, faces, triangles, edges, quads, tris, ngons, rendering_vertices,
                  uv_channels, materials, bounds, islands, boundary_edges, defects}]
    totals      the same counts summed, and overall bounds and size in centimetres
    rigging     {skeleton, skin, blend_shapes, animation}     what else the file carries
    defects     [{kind, severity, geometry, count, faces, description}]   faces are polygon numbers, capped
    limits      which checks were skipped because the file is large

Counting follows Phase 6, 6.4.1: geometric vertices are the control points as stored (coincident ones are not merged),
faces are the stored polygons, triangles are what a fan triangulation would give, edges are unique pairs of control
points joined by a face, and rendering vertices are the distinct position / UV / normal combinations at polygon
corners. Text-form (ASCII) FBX is recognised and refused with a clear message.
"""
import array
import math
import struct
import zlib

MAGIC = b"Kaydara FBX Binary  \x00"
MAX_BYTES = 1024 * 1024 * 1024          # the largest file read
MAX_ARRAY = 60_000_000                  # the most numbers in one array
MAX_NODES = 2_000_000
MAX_DEPTH = 64
MAX_LISTED = 2000                       # the most faces named for one kind of defect
DEEP_CHECK_FACES = 1_500_000            # beyond this the slower checks are skipped and the report says so
AXES = ("X", "Y", "Z")


class FBXError(ValueError):
    """The file is not an FBX this reader can use. The message is for the person."""


class Node:
    __slots__ = ("name", "props", "children")

    def __init__(self, name, props=None, children=None):
        self.name, self.props, self.children = name, props or [], children or []

    def find(self, name):
        return next((c for c in self.children if c.name == name), None)

    def all(self, name):
        return [c for c in self.children if c.name == name]

    def value(self, name, default=None):
        c = self.find(name)
        return c.props[0] if c and c.props else default


_ARRAYS = {"f": ("f", 4), "d": ("d", 8), "l": ("q", 8), "i": ("i", 4), "b": ("b", 1)}
_SCALARS = {"Y": ("<h", 2), "C": ("<?", 1), "I": ("<i", 4), "F": ("<f", 4), "D": ("<d", 8), "L": ("<q", 8)}


def _prop(data, at):
    kind = chr(data[at])
    at += 1
    if kind in _SCALARS:
        fmt, size = _SCALARS[kind]
        return struct.unpack_from(fmt, data, at)[0], at + size
    if kind in _ARRAYS:
        code, size = _ARRAYS[kind]
        count, encoding, length = struct.unpack_from("<III", data, at)
        at += 12
        if count > MAX_ARRAY or at + length > len(data):
            raise FBXError("The FBX file has an array that is too large or runs past the end of the file.")
        raw = data[at:at + length]
        if encoding == 1:
            unpacker = zlib.decompressobj()
            raw = unpacker.decompress(bytes(raw), count * size + 1)      # never inflate past what was declared
            if len(raw) != count * size:
                raise FBXError("An array in the FBX file does not unpack to the size it declares.")
        elif encoding != 0 or length != count * size:
            raise FBXError("An array in the FBX file is stored in a way this reader does not know.")
        values = array.array(code)
        values.frombytes(bytes(raw))
        return values, at + length
    if kind in ("S", "R"):
        length = struct.unpack_from("<I", data, at)[0]
        at += 4
        if at + length > len(data):
            raise FBXError("A text value in the FBX file runs past the end of the file.")
        raw = bytes(data[at:at + length])
        return (raw.decode("utf-8", "replace") if kind == "S" else raw), at + length
    raise FBXError("The FBX file contains a value of an unknown kind.")


def parse(data):
    """-> the root Node, whose children are the file's top-level records."""
    if len(data) > MAX_BYTES:
        raise FBXError("The FBX file is larger than this application reads.")
    if bytes(data[:21]) != MAGIC:
        if b"FBXHeaderExtension" in bytes(data[:4096]):
            raise FBXError("This is a text-form (ASCII) FBX file. Save it as binary FBX, which every common tool can do, and import that.")
        raise FBXError("This is not an FBX file.")
    data = memoryview(data)
    version = struct.unpack_from("<I", data, 23)[0]
    wide = version >= 7500
    head, size, null = ("<QQQB", 25, 25) if wide else ("<IIIB", 13, 13)
    count = [0]

    def node(at, depth):
        if depth > MAX_DEPTH:
            raise FBXError("The FBX file is nested too deeply.")
        if at + size > len(data):
            raise FBXError("The FBX file ends in the middle of a record.")
        end, nprops, plen, nlen = struct.unpack_from(head, data, at)
        if end == 0:
            return None, at + null
        if end > len(data) or end < at:
            raise FBXError("A record in the FBX file points outside the file.")
        count[0] += 1
        if count[0] > MAX_NODES:
            raise FBXError("The FBX file has more records than this application reads.")
        at += size
        name = bytes(data[at:at + nlen]).decode("ascii", "replace")
        at += nlen
        props, stop = [], at + plen
        for _ in range(nprops):
            value, at = _prop(data, at)
            props.append(value)
        at = stop
        children = []
        while at < end:
            child, at = node(at, depth + 1)
            if child is None:
                break
            children.append(child)
        return Node(name, props, children), end

    root, at = Node("", [version]), 27
    while at + size <= len(data):
        child, at = node(at, 0)
        if child is None:
            break
        root.children.append(child)
    return root


def _write_prop(value):
    if isinstance(value, bool):
        return b"C" + struct.pack("<?", value)
    if isinstance(value, int):
        return (b"I" + struct.pack("<i", value)) if -2 ** 31 <= value < 2 ** 31 else (b"L" + struct.pack("<q", value))
    if isinstance(value, float):
        return b"D" + struct.pack("<d", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return b"S" + struct.pack("<I", len(raw)) + raw
    if isinstance(value, bytes):
        return b"R" + struct.pack("<I", len(value)) + value
    if isinstance(value, array.array):
        code = {"d": b"d", "f": b"f", "i": b"i", "q": b"l", "b": b"b"}[value.typecode]
        raw = value.tobytes()
        return code + struct.pack("<III", len(value), 0, len(raw)) + raw
    if isinstance(value, Long):
        return b"L" + struct.pack("<q", value.value)
    raise TypeError(type(value))


class Long:
    """A whole number that must be written as 64-bit (object ids are)."""
    def __init__(self, value):
        self.value = value


def write(nodes, version=7400):
    """A minimal binary FBX from Nodes. Enough for three.js and this reader; used for test files."""
    wide = version >= 7500
    head, null = ("<QQQB", b"\0" * 25) if wide else ("<IIIB", b"\0" * 13)
    size = struct.calcsize(head)

    def node(n, at):
        props = b"".join(_write_prop(p) for p in n.props)
        name = n.name.encode("ascii")
        body, here = b"", at + size + len(name) + len(props)
        for c in n.children:
            raw = node(c, here)
            body += raw
            here += len(raw)
        if n.children or not n.props:
            body += null
            here += len(null)
        return struct.pack(head, here, len(n.props), len(props), len(name)) + name + props + body

    out = MAGIC + b"\x1a\x00" + struct.pack("<I", version)
    for n in nodes:
        out += node(n, len(out))
    out += null
    out += b"\xfa\xbc\xab\x09\xd0\xc8\xd4\x66\xb1\x76\xfb\x83\x1c\xf7\x26\x7e" + b"\0" * 4
    out += b"\0" * (16 - len(out) % 16)
    out += struct.pack("<I", version) + b"\0" * 120 + b"\xf8\x5a\x8c\x6a\xde\xf5\xd9\x7e\xec\xe9\x0c\xe3\x75\x8f\x29\x0b"
    return out


def _props70(node):
    """Properties70 as {name: values after the four describing strings}."""
    out = {}
    p70 = node.find("Properties70") if node else None
    for p in p70.all("P") if p70 else []:
        if p.props and isinstance(p.props[0], str):
            out[p.props[0]] = p.props[4:]
    return out


def _name(prop):
    return str(prop).split("\x00")[0] if isinstance(prop, str) else ""


def _matrix(t, r, s):
    """A 3x4 transform from translation, Euler rotation in degrees (applied X then Y then Z) and scale."""
    rx, ry, rz = (math.radians(v) for v in r)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    m = [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
         [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
         [-sy, cy * sx, cy * cx]]
    return [[m[i][j] * s[j] for j in range(3)] + [t[i]] for i in range(3)]


def _combine(a, b):
    """a then b: the transform that applies b first, then a."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) + (a[i][3] if j == 3 else 0) for j in range(4)] for i in range(3)]


def _apply(m, p):
    return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3)]


def _geometry(node, deep):
    """Counts and checks for one mesh. -> (statistics, defects)"""
    verts = node.value("Vertices")
    index = node.value("PolygonVertexIndex")
    if not isinstance(verts, array.array) or not isinstance(index, array.array):
        return None, [{"kind": "missing data", "severity": "technical failure", "count": 1, "faces": [],
                       "description": "The mesh has no control points or no faces."}]
    n = len(verts) // 3
    defects, found = [], {}

    def note(kind, severity, description, face=None, count=1):
        d = found.get(kind)
        if not d:
            d = found[kind] = {"kind": kind, "severity": severity, "count": 0, "faces": [], "description": description}
            defects.append(d)
        d["count"] += count
        if face is not None and len(d["faces"]) < MAX_LISTED:
            d["faces"].append(face)

    bad = sum(1 for v in verts if v != v or v in (math.inf, -math.inf))
    if bad:
        note("invalid coordinates", "technical failure", "Some control points are not real numbers.", count=bad)
    faces = triangles = tris = quads = ngons = 0
    edges, face_keys, used = {}, {}, bytearray(n)
    parent = list(range(n)) if deep else None

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    corners = []
    for raw in index:
        last = raw < 0
        v = -raw - 1 if last else raw
        corners.append(v)
        if not last:
            continue
        k = len(corners)
        if any(c >= n or c < 0 for c in corners):
            note("invalid indices", "technical failure", "Some faces point at control points that do not exist.", faces)
        elif k < 3 or len(set(corners)) < k:
            note("degenerate faces", "significant defect", "Faces with fewer than three distinct corners.", faces)
        else:
            if deep:
                key = tuple(sorted(corners))
                if key in face_keys:
                    note("duplicate faces", "warning", "Faces that use exactly the same control points as another face.", faces)
                face_keys[key] = faces
                a = corners[-1]
                r0 = root(corners[0])
                for b in corners:
                    e = (a, b) if a < b else (b, a)
                    edges[e] = edges.get(e, 0) + 1
                    rb = root(b)
                    if rb != r0:
                        parent[rb] = r0
                    used[b] = 1
                    a = b
                p0 = verts[corners[0] * 3:corners[0] * 3 + 3]
                area = 0.0
                for j in range(1, k - 1):
                    p1, p2 = verts[corners[j] * 3:corners[j] * 3 + 3], verts[corners[j + 1] * 3:corners[j + 1] * 3 + 3]
                    ux, uy, uz, vx, vy, vz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2], p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
                    area += math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)
                if area == 0:
                    note("zero-area faces", "warning", "Faces whose corners lie on one line, so they cover no surface.", faces)
        faces += 1
        triangles += max(0, k - 2)
        tris, quads, ngons = tris + (k == 3), quads + (k == 4), ngons + (k > 4)
        corners = []
    if corners:
        note("invalid indices", "technical failure", "The last face is not closed.", faces)
    stats = {"vertices": n, "faces": faces, "triangles": triangles, "tris": tris, "quads": quads, "ngons": ngons,
             "edges": None, "boundary_edges": None, "islands": None, "rendering_vertices": None}
    if deep:
        stats["edges"] = len(edges)
        stats["boundary_edges"] = sum(1 for c in edges.values() if c == 1)
        many = sum(1 for c in edges.values() if c > 2)
        if many:
            note("non-manifold edges", "significant defect", "Edges shared by more than two faces.", count=many)
        stats["islands"] = len({root(i) for i in range(n) if used[i]})
        loose = n - sum(used)
        if loose:
            note("unused control points", "informational", "Control points that no face uses.", count=loose)
    if n and not bad:
        xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
        stats["bounds"] = [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]]
    else:
        stats["bounds"] = None
    uvs = node.all("LayerElementUV")
    stats["uv_channels"] = [{"index": int(u.props[0]) if u.props else k, "name": u.value("Name", "") or f"UV {k}"} for k, u in enumerate(uvs)]
    mat = node.find("LayerElementMaterial")
    slots = mat.value("Materials") if mat else None
    stats["material_slots"] = (max(slots) + 1) if isinstance(slots, array.array) and len(slots) else (1 if mat else 0)
    # Rendering vertices: distinct position / UV / normal combinations at polygon corners.
    if deep and not found.get("invalid indices"):
        uv_index = uvs[0].value("UVIndex") if uvs and uvs[0].value("MappingInformationType") == "ByPolygonVertex" else None
        normal = node.find("LayerElementNormal")
        normals = normal.value("Normals") if normal and normal.value("MappingInformationType") == "ByPolygonVertex" and normal.value("ReferenceInformationType") == "Direct" else None
        if (uvs and uv_index is None) or (normal and normals is None):
            stats["rendering_note"] = "Not measured: the file stores UVs or normals in a layout this reader does not count."
        else:
            seen = set()
            for k, raw in enumerate(index):
                v = -raw - 1 if raw < 0 else raw
                seen.add((v, uv_index[k] if uv_index is not None and k < len(uv_index) else -1,
                          (round(normals[k * 3], 4), round(normals[k * 3 + 1], 4), round(normals[k * 3 + 2], 4)) if normals is not None and k * 3 + 2 < len(normals) else None))
            stats["rendering_vertices"] = len(seen)
            stats["rendering_note"] = "Distinct position, UV and normal combinations at polygon corners" + ("" if uvs or normal else " (the file has no UVs or normals, so this equals the control points in use)") + "."
    return stats, defects


def analyse(data):
    """Read an FBX file and report what it holds. Raises FBXError if it cannot be read."""
    try:
        root = parse(data)
    except (struct.error, zlib.error, IndexError, MemoryError) as e:
        raise FBXError("The FBX file is damaged and could not be read.") from e
    version = root.props[0]
    objects, settings = root.find("Objects"), _props70(root.find("GlobalSettings"))
    if not objects:
        raise FBXError("The FBX file has no objects in it.")
    num = lambda key, default: (settings.get(key) or [default])[0]
    up, front, coord, unit = int(num("UpAxis", 1)), int(num("FrontAxis", 2)), int(num("CoordAxis", 0)), float(num("UnitScaleFactor", 1.0))
    signs = [int(num(k, 1)) for k in ("UpAxisSign", "FrontAxisSign", "CoordAxisSign")]
    canonical = (up, front, coord) == (1, 2, 0) and signs == [1, 1, 1] and abs(unit - 1.0) < 1e-9
    notes = []
    if (up, front, coord) != (1, 2, 0) or signs != [1, 1, 1]:
        notes.append(f"The file's axes are {'+' if signs[0] > 0 else '-'}{AXES[up % 3]} up and {'+' if signs[1] > 0 else '-'}{AXES[front % 3]} front; the studio's are +Y up and +Z forward.")
    if abs(unit - 1.0) >= 1e-9:
        notes.append(f"One unit in the file is {unit:g} cm; the studio works in centimetres.")
    conventions = {"up": ("+" if signs[0] > 0 else "-") + AXES[up % 3], "front": ("+" if signs[1] > 0 else "-") + AXES[front % 3],
                   "coord": ("+" if signs[2] > 0 else "-") + AXES[coord % 3], "unit_scale": unit, "canonical": canonical, "notes": notes}

    links = {}                                                     # child id -> [parent ids]
    for c in (root.find("Connections").all("C") if root.find("Connections") else []):
        if len(c.props) >= 3 and c.props[0] in ("OO", "OP"):
            links.setdefault(c.props[1], []).append(c.props[2])
    models, geoms, kinds = {}, {}, {}
    for o in objects.children:
        if not o.props:
            continue
        oid = o.props[0]
        kinds[oid] = (o.name, o.props[2] if len(o.props) > 2 else "")
        if o.name == "Model":
            p = _props70(o)
            vec = lambda key, d: [float(v) for v in (p.get(key) or d)[:3]]
            models[oid] = {"id": str(oid), "name": _name(o.props[1]) or "Model", "kind": o.props[2] if len(o.props) > 2 else "",
                           "translation": vec("Lcl Translation", [0, 0, 0]), "rotation": vec("Lcl Rotation", [0, 0, 0]), "scale": vec("Lcl Scaling", [1, 1, 1]),
                           "parent": None, "geometry": None, "approximate": any(k in p for k in ("PreRotation", "RotationPivot", "ScalingPivot", "GeometricTranslation"))}
        elif o.name == "Geometry" and (len(o.props) < 3 or o.props[2] == "Mesh"):
            geoms[oid] = o
    for mid, m in models.items():
        m["parent"] = next((str(p) for p in links.get(mid, []) if p in models), None)
    total_faces = sum(len(g.value("PolygonVertexIndex") or ()) for g in geoms.values())
    deep = total_faces <= DEEP_CHECK_FACES * 4
    geometries, defects = [], []
    for gid, g in geoms.items():
        stats, found = _geometry(g, deep)
        owner = next((p for p in links.get(gid, []) if p in models), None)
        if owner is not None:
            models[owner]["geometry"] = str(gid)
        for d in found:
            defects.append(dict(d, geometry=str(gid)))
        if stats:
            geometries.append(dict(stats, id=str(gid), name=_name(g.props[1]) if len(g.props) > 1 else "", model=str(owner) if owner is not None else None))

    def world(mid, seen=()):
        m = models[mid]
        local = _matrix(m["translation"], m["rotation"], m["scale"])
        parent = next((p for p in links.get(mid, []) if p in models and p not in seen), None)
        return _combine(world(parent, seen + (mid,)), local) if parent is not None else local

    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for g in geometries:
        if not g["bounds"]:
            continue
        m = world(int(g["model"])) if g["model"] else _matrix([0, 0, 0], [0, 0, 0], [1, 1, 1])
        (x0, y0, z0), (x1, y1, z1) = g["bounds"]
        pts = [_apply(m, (x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        g["world_bounds"] = [[min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]]
        lo = [min(lo[i], g["world_bounds"][0][i]) for i in range(3)]
        hi = [max(hi[i], g["world_bounds"][1][i]) for i in range(3)]
    add = lambda key: (sum(g[key] for g in geometries) if all(g[key] is not None for g in geometries) else None) if geometries else 0
    totals = {k: add(k) for k in ("vertices", "faces", "triangles", "tris", "quads", "ngons", "edges", "rendering_vertices", "boundary_edges", "islands")}
    totals["bounds"] = [lo, hi] if geometries and lo[0] != math.inf else None
    totals["size_cm"] = [round((hi[i] - lo[i]) * unit, 3) for i in range(3)] if totals["bounds"] else None
    totals["approximate_bounds"] = any(m["approximate"] for m in models.values())
    count = lambda name, sub=None: sum(1 for n, s in kinds.values() if n == name and (sub is None or s == sub))
    rigging = {"skeleton": sum(1 for m in models.values() if m["kind"] in ("LimbNode", "Root", "Limb")), "skin": count("Deformer", "Skin"),
               "clusters": count("Deformer", "Cluster"), "blend_shapes": count("Deformer", "BlendShape"), "animation": count("AnimationStack"),
               "materials": count("Material"), "textures": count("Texture")}
    limits = [] if deep else ["The file is very large, so edges, islands, duplicate and zero-area faces and rendering vertices were not measured."]
    return {"version": version, "conventions": conventions, "models": list(models.values()), "geometries": geometries, "totals": totals,
            "rigging": rigging, "defects": defects, "limits": limits}


def faces(data, wanted):
    """The corner positions of chosen faces, in each mesh's own coordinates, so a page can draw over them.
    wanted: {geometry id (str): face numbers} -> {geometry id: {face number: [x, y, z, x, y, z, …]}}"""
    objects = parse(data).find("Objects")
    out = {}
    for o in objects.children if objects else []:
        gid = str(o.props[0]) if o.props else ""
        if o.name != "Geometry" or gid not in wanted:
            continue
        verts, index = o.value("Vertices"), o.value("PolygonVertexIndex")
        if not isinstance(verts, array.array) or not isinstance(index, array.array):
            continue
        want, got, face, corners, n = set(wanted[gid]), {}, 0, [], len(verts) // 3
        for v in index:
            i = v if v >= 0 else -v - 1
            corners.append(i)
            if v < 0:
                if face in want and all(0 <= c < n for c in corners):
                    got[face] = [round(float(verts[c * 3 + k]), 6) for c in corners for k in range(3)]
                face, corners = face + 1, []
        out[gid] = got
    return out


def profile(vertices):
    """The density profile a control-point count falls in (Phase 6, 6.4). -> "low" | "mid" | "high" | "below" | "above" """
    return "below" if vertices < 500 else "low" if vertices <= 10_000 else "mid" if vertices <= 30_000 else "high" if vertices <= 500_000 else "above"
