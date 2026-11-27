"""The studio's routes end to end, without a browser (Gate B: import, review, reopen, pending export, reimport)."""
import io
import shutil
import tempfile
import unittest
import zipfile

from studio3d import api
from studio3d.store import Store
from studio3d.tests import fixtures


class Api(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [2_000_000.0]
        api.configure()
        api.use(Store(self.dir, clock=lambda: self.now[0], disk=lambda: 100 * 1024 ** 3))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def get(self, route, **q):
        return api.handle("GET", api.PREFIX + route, q)

    def post(self, route, body=None, raw=None, **q):
        return api.handle("POST", api.PREFIX + route, q, body, raw=raw)

    def bring(self, data=None, name="Captain.fbx", **q):
        return self.post("import", raw=fixtures.character() if data is None else data, project="p1", name=name, **q)

    def test_the_gate_b_path(self):
        out = self.bring()
        a = out["asset"]
        art = a["artifacts"][0]
        self.assertEqual((a["name"], art["state"], art["days_left"], len(art["components"]), a["budget"]["measured"] > 0), ("Captain", "pending", 10, 4, True))
        self.assertEqual(self.get("assets", project="p1")["assets"][0]["pending"], 1)
        with open(self.get("file", asset=a["id"], artifact=art["id"]).path, "rb") as f:
            self.assertEqual(f.read(), fixtures.character())
        api.use(Store(self.dir, clock=lambda: self.now[0], disk=lambda: 100 * 1024 ** 3))            # the application restarts
        again = self.get("asset", id=a["id"])
        self.assertEqual((again["artifacts"][0]["id"], again["selected"]["geometry"]), (art["id"], art["id"]))
        first = self.post("export", {"asset": a["id"]})
        self.assertTrue(first["needs_confirmation"]); self.assertEqual(first["plan"]["pending"][0]["id"], art["id"])
        self.assertEqual(self.get("jobs", project="p1")["jobs"], [j for j in self.get("jobs", project="p1")["jobs"] if j["operation"] != "package.export"])
        done = self.post("export", {"asset": a["id"], "confirmed": True})
        self.assertEqual((done["name"], done["pending"]), ("Captain.zip", 1))
        with open(self.get("export/file", id=done["id"]).path, "rb") as f:
            data = f.read()
        self.assertIn("Geometry/Captain.fbx", zipfile.ZipFile(io.BytesIO(data)).namelist())
        self.assertEqual(self.get("asset", id=a["id"])["artifacts"][0]["state"], "pending")           # exporting approved nothing
        back = self.bring(data, "Captain.zip")
        self.assertNotEqual(back["asset"]["id"], a["id"]); self.assertEqual(back["asset"]["artifacts"][0]["origin"], "reimported")
        self.assertEqual(len(self.get("assets", project="p1")["assets"]), 2)

    def test_approve_deny_and_cleanup(self):
        a = self.bring(fixtures.cube(), "Crate.fbx")["asset"]
        art = a["artifacts"][0]["id"]
        self.assertEqual(self.post("approve", {"asset": a["id"], "ids": [art]})["approved"], [art])
        b = self.bring(fixtures.character(), "Other.fbx", asset=a["id"])["asset"]
        other = next(x["id"] for x in b["artifacts"] if x["id"] != art)
        self.assertEqual(len(self.post("deny", {"asset": a["id"], "ids": [other]})["artifacts"]), 1)
        c = self.bring(fixtures.cube(), "Temp.fbx")["asset"]
        self.now[0] += 11 * 86400
        out = self.post("cleanup")
        self.assertEqual(out["expired"], 1)
        with self.assertRaises(LookupError):
            self.get("asset", id=c["id"])["artifacts"][0]
        self.assertEqual(self.get("asset", id=a["id"])["artifacts"][0]["state"], "approved")

    def test_what_is_refused(self):
        for data, word in ((b"; FBX 7.4.0 project file\nFBXHeaderExtension:  {\n}\n", "ASCII"), (b"hello", "FBX"), (b"", "No file")):
            with self.assertRaises(ValueError) as e:
                self.bring(data, "x.fbx")
            self.assertIn(word, str(e.exception))
        with self.assertRaises(ValueError) as e:
            self.bring(b"PK\x03\x04junk", "x.zip")
        self.assertIn("ZIP", str(e.exception))
        self.assertEqual((self.get("assets", project="p1")["assets"], __import__("os").listdir(self.dir + "/staging")), ([], []))
        with self.assertRaises(LookupError):
            self.get("asset", id="../../etc/passwd")
        with self.assertRaises(LookupError):
            self.get("export/file", id="req_nope")

    def test_faulty_faces_come_back_as_shapes(self):
        a = self.bring(fixtures.broken(), "Broken.fbx")["asset"]
        art = a["artifacts"][0]
        out = self.get("defects", asset=a["id"], artifact=art["id"])["defects"]
        self.assertTrue(out and all(d["model"] and d["polygons"] and all(len(p) % 3 == 0 and len(p) >= 9 for p in d["polygons"]) for d in out))
        self.assertEqual({d["kind"] for d in out}, {d["kind"] for d in art["report"]["defects"] if d["faces"]})

    def test_info_says_what_is_not_available(self):
        info = self.get("info")
        caps = {c["capability"]: c for c in info["capabilities"]}
        self.assertTrue(caps["geometry.import"]["available"]); self.assertFalse(caps["geometry.generate"]["available"])
        self.assertIn("No provider", caps["texture.generate"]["reason"])
        self.assertEqual((info["retention_days"], info["quality"]["mid"]["preset"]), (10, 20000))

    def test_character_and_components_through_the_routes(self):
        a = self.bring()["asset"]
        api.handle("PUT", api.PREFIX + "asset", {"id": a["id"]}, {"fields": {"type": "humanoid"}})
        art = a["artifacts"][0]
        body = next(c for c in art["components"] if c["name"] == "Base_Body")
        v = self.post("component", {"asset": a["id"], "artifact": art["id"], "component": body["id"], "fields": {"role": "Base anatomy"}})
        self.assertTrue(v["character"]["applies"]); self.assertEqual({c["id"]: c["status"] for c in v["character"]["checks"]}["base"], "pass")
        v = self.post("character", {"asset": a["id"], "artifact": art["id"], "fields": {"pose": "a-pose", "confirmed": ["hidden", "facing"]}})
        self.assertTrue(v["character"]["eligible"])                                                    # two meshes still have no role: a warning, not a block
        self.assertEqual(self.post("character/handoff", {"asset": a["id"]})["character"]["handoff"]["base_name"], "Base_Body")
        self.assertEqual([c["status"] for c in v["character"]["checks"] if c["status"] in ("fail", "manual")], [])


if __name__ == "__main__":
    unittest.main()
