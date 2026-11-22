"""Checking uploaded reference images before they are stored.

A reference is something the person already has: a mark that must be kept exactly (an icon, a
letterform), or a picture that shows the style they want. Uploads are untrusted, so:

  * The kind of file is decided from its first bytes, never from its name.
  * PNG, JPEG and WebP are stored as they are.
  * SVG is rebuilt from an allow-list. Scripts, event handlers, embedded pages, images, links to
    anything outside the file, and risky styles are removed. What is stored is the rebuilt file.
  * The page shows references only inside <img>, where a browser runs no script, and the server
    sends them with a policy that forbids scripts and outside resources.
"""
import re
import xml.etree.ElementTree as ET

MAX_BYTES = 20 * 1024 * 1024          # per raster file
MAX_SVG_BYTES = 2 * 1024 * 1024
MAX_PER_PROJECT = 24
# "insert" keeps the reference's own pixels and has the rest of the picture drawn around it.
# The other three hand the reference to the image model as guidance, and the model redraws it.
USES = ("insert", "keep exactly", "style guide", "inspiration")
TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ALLOWED_TAGS = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "defs",
                "linearGradient", "radialGradient", "stop", "clipPath", "mask", "use", "symbol",
                "title", "desc", "text", "tspan", "style"}
BAD_TEXT = re.compile(r"javascript:|expression\s*\(|@import|url\s*\(\s*(?!['\"]?#)|\\|<", re.I)


def sniff(data):
    """-> 'png' | 'jpg' | 'webp' | 'svg' | None, from the file's own bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:65536].lower()) or head.startswith(b"<!--") and b"<svg" in data[:65536].lower():
        return "svg"
    return None


def has_transparency(data):
    """True for a PNG saved with an alpha channel: a cut-out mark rather than a photograph."""
    return data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR" and len(data) > 25 and data[25] in (4, 6)


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def clean_svg(data):
    """-> (safe SVG bytes, number of parts removed). Raises ValueError if it cannot be made safe."""
    if len(data) > MAX_SVG_BYTES:
        raise ValueError("That SVG is larger than 2 MB. Simplify it or export it as a PNG.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("That SVG is not plain UTF-8 text, so it cannot be checked.")
    text = re.sub(r"<!DOCTYPE[^>\[]*>", "", text, flags=re.I)             # a plain doctype line is harmless; drop it
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        raise ValueError("That SVG defines its own entities, which is not allowed. Re-export it as a plain SVG.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"That SVG could not be read: {e}")
    if root.tag != f"{{{SVG_NS}}}svg":
        raise ValueError("That file is not an SVG image.")
    removed = 0

    def scrub(node):
        nonlocal removed
        for name in list(node.attrib):
            local, value = _local(name).lower(), node.attrib[name]
            bad = (local.startswith("on")                                  # onclick, onload, …
                   or (local == "href" and not value.strip().startswith("#"))   # only links inside the file
                   or BAD_TEXT.search(value))
            if bad:
                del node.attrib[name]; removed += 1
        for child in list(node):
            ok = (isinstance(child.tag, str) and child.tag.startswith(f"{{{SVG_NS}}}")
                  and _local(child.tag) in ALLOWED_TAGS)
            if ok and _local(child.tag) == "style" and BAD_TEXT.search("".join(child.itertext())):
                ok = False
            if not ok:
                tail = child.tail
                node.remove(child); removed += 1
                if tail and tail.strip():
                    node.text = (node.text or "") + tail
            else:
                scrub(child)

    scrub(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), removed


def check(data):
    """-> (kind, bytes to store, parts removed). Raises ValueError with a message for a person."""
    if not data:
        raise ValueError("That file is empty.")
    kind = sniff(data)
    if kind is None:
        raise ValueError("Only PNG, JPEG, WebP and SVG images can be used as references.")
    if kind == "svg":
        safe, removed = clean_svg(data)
        return kind, safe, removed
    if len(data) > MAX_BYTES:
        raise ValueError("That image is larger than 20 MB.")
    return kind, data, 0


def display_name(name):
    """A file name safe to show and store: no folders, no control characters."""
    name = re.sub(r"[\x00-\x1f\x7f]", "", str(name or "")).replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:120] or "reference"
