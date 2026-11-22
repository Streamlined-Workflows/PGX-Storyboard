"""Uploaded reference images: what is accepted, what is stripped from an SVG, and where files go."""
import os
import tempfile
import unittest

from identity_studio import api, references as R
from identity_studio.storage import Store

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20
GOOD_SVG = b'''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
  <defs><linearGradient id="g"><stop offset="0" stop-color="#22c55e"/></linearGradient>
  <style>.a{fill:#22c55e}</style></defs>
  <path class="a" d="M0 0h10v10z" fill="url(#g)"/><use xlink:href="#g"/>
</svg>'''
NASTY_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" onload="alert(1)">
  <script>alert(1)</script>
  <foreignObject><body xmlns="http://www.w3.org/1999/xhtml"><iframe src="https://evil.example"/></body></foreignObject>
  <image href="https://evil.example/track.png"/>
  <a xlink:href="javascript:alert(1)"><circle r="1"/></a>
  <style>@import url(https://evil.example/x.css);</style>
  <rect width="5" height="5" style="fill:url(https://evil.example/f.svg#x)" onclick="alert(2)"/>
  <use xlink:href="https://evil.example/s.svg#a"/>
  <circle r="2" fill="#000"/>
</svg>'''


class CheckTests(unittest.TestCase):
    def test_kind_comes_from_the_bytes_not_the_name(self):
        self.assertEqual([R.sniff(d) for d in (PNG, JPG, WEBP, GOOD_SVG)], ["png", "jpg", "webp", "svg"])
        for bad in (b"", b"GIF89a....", b"<html><script>1</script></html>", b"MZ\x90\x00", b"%PDF-1.7"):
            with self.assertRaises(ValueError):
                R.check(bad)

    def test_a_clean_svg_keeps_its_drawing(self):
        kind, safe, removed = R.check(GOOD_SVG)
        self.assertEqual((kind, removed), ("svg", 0))
        for part in (b"<path", b"linearGradient", b"url(#g)", b".a{fill:#22c55e}", b'href="#g"'):
            self.assertIn(part, safe)

    def test_everything_dangerous_is_removed_from_an_svg(self):
        _, safe, removed = R.check(NASTY_SVG)
        low = safe.lower()
        for gone in (b"script", b"onload", b"onclick", b"foreignobject", b"iframe", b"evil.example", b"javascript", b"@import", b"<image", b"<a "):
            self.assertNotIn(gone, low, gone)
        self.assertIn(b'r="2"', safe)                       # the harmless shape survives
        self.assertGreaterEqual(removed, 7)

    def test_entities_and_non_svg_xml_are_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><svg xmlns="http://www.w3.org/2000/svg">&b;</svg>'
        external = b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>'
        for bad in (bomb, external, b"<svg><broken", b'<svg xmlns="http://example.com/not-svg"/>'):
            with self.assertRaises(ValueError):
                R.check(bad)
        plain = b'<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
        self.assertEqual(R.check(plain)[0], "svg")          # an ordinary Illustrator-style doctype is fine
        self.assertNotIn(b"DOCTYPE", R.check(plain)[1])

    def test_size_limits(self):
        with self.assertRaises(ValueError):
            R.check(PNG + b"\x00" * R.MAX_BYTES)
        with self.assertRaises(ValueError):
            R.check(b'<svg xmlns="http://www.w3.org/2000/svg">' + b" " * R.MAX_SVG_BYTES + b"</svg>")

    def test_names_cannot_carry_a_path(self):
        self.assertEqual(R.display_name("../../etc/passwd"), "passwd")
        self.assertEqual(R.display_name("C:\\Users\\me\\i icon.svg"), "i icon.svg")
        self.assertEqual(R.display_name(""), "reference")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        api.use_store(self.store)
        self.pid = api.handle("POST", "/api/identity/projects", payload={"name": "Icon"})["id"]
        self.q = {"project": self.pid}

    def tearDown(self):
        api.use_store(None); self.tmp.cleanup()

    def up(self, name, data):
        return api.handle("POST", "/api/identity/references", dict(self.q, name=name), raw=data)

    def test_upload_read_back_edit_and_remove(self):
        ref = self.up("../../i-icon.svg", NASTY_SVG)
        self.assertEqual((ref["name"], ref["kind"], ref["use"]), ("i-icon.svg", "svg", "keep exactly"))
        self.assertGreater(ref["cleaned"], 0)
        f = api.handle("GET", "/api/identity/reference", dict(self.q, id=ref["id"]))
        self.assertEqual(f.content_type, "image/svg+xml")
        self.assertEqual(os.path.dirname(f.path), self.store.reference_dir(self.pid))
        self.assertEqual(os.path.basename(f.path), ref["id"] + ".svg")           # our name on disk, not the upload's
        with open(f.path, "rb") as fh:
            self.assertNotIn(b"script", fh.read())                 # what is stored is the cleaned file
        png = self.up("style.png", PNG)
        self.assertEqual(png["use"], "style guide")
        edited = api.handle("PUT", "/api/identity/reference", dict(self.q, id=ref["id"]), {"use": "nonsense", "note": " the i "})
        self.assertEqual((edited["use"], edited["note"]), ("keep exactly", "the i"))
        self.assertEqual(len(api.handle("GET", "/api/identity/project", {"id": self.pid})["references"]), 2)
        api.handle("POST", "/api/identity/references/remove", payload={"project": self.pid, "id": ref["id"]})
        self.assertFalse(os.path.exists(f.path))
        self.assertTrue([n for n in os.listdir(self.store.trash) if ref["id"] in n])   # kept in the trash
        with self.assertRaises(ValueError):
            api.handle("GET", "/api/identity/reference", dict(self.q, id=ref["id"]))

    def test_bad_requests(self):
        for q, data in ((dict(self.q, name="a.exe"), b"MZ\x90"), ({"project": "../x", "name": "a.png"}, PNG), (dict(self.q, name="a.png"), b"")):
            with self.assertRaises(ValueError):
                api.handle("POST", "/api/identity/references", q, raw=data)
        for rid in ("", "../../x", "ffffffffffff"):
            with self.assertRaises(ValueError):
                api.handle("GET", "/api/identity/reference", dict(self.q, id=rid))

    def test_limit_duplicate_and_delete_carry_the_files(self):
        ref = self.up("a.png", PNG)
        copy = api.handle("POST", "/api/identity/projects/duplicate", payload={"id": self.pid})
        self.assertTrue(os.path.isfile(api.handle("GET", "/api/identity/reference", {"project": copy["id"], "id": ref["id"]}).path))
        for i in range(R.MAX_PER_PROJECT - 1):
            self.up(f"{i}.png", PNG)
        with self.assertRaises(ValueError):
            self.up("one-too-many.png", PNG)
        api.handle("POST", "/api/identity/projects/delete", payload={"id": self.pid})
        self.assertFalse(os.path.exists(self.store.reference_dir(self.pid)))
        self.assertTrue(any(n.endswith("-assets") for n in os.listdir(self.store.trash)))


if __name__ == "__main__":
    unittest.main()
