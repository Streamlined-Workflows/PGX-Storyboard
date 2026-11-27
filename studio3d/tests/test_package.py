"""Export, reimport and character preparation (3d_Phase_14, 3d_Phase_18, 3d_Phase_22)."""
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile

from studio3d import assets, character, package
from studio3d.store import Store
from studio3d.tests import fixtures

DAY = 86400


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [1_000_000.0]
        self.store = Store(self.dir, clock=lambda: self.now[0], disk=lambda: 100 * 1024 ** 3)
        self.studio = assets.Studio(self.store)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def zipped(self, asset_id, **kw):
        path, name, plan = package.build(self.studio, asset_id, **kw)
        with open(path, "rb") as f:
            return f.read(), name, plan

    def rezip(self, data, change):
        src, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for name in src.namelist():
                new = change(name, src.read(name))
                if new is not None:
                    z.writestr(*new)
        return out.getvalue()


class Export(Base):
    def test_a_geometry_only_prop(self):                                              # EX-A01
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx", approve=True, fields={"type": "scene_prop", "subtype": "Container"})
        data, name, plan = self.zipped(r["id"])
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual((name, sorted(z.namelist()), plan["pending"]), ("Crate.zip", ["AssetManifest.json", "Documentation/Compatibility_Report.md", "Geometry/Crate.fbx"], []))
        self.assertEqual(z.read("Geometry/Crate.fbx"), fixtures.cube())                           # byte for byte
        m = json.loads(z.read("AssetManifest.json"))
        self.assertEqual((m["classification"]["type"], m["classification"]["subtype"], m["artifacts"][0]["path"], m["package"]["files"][0]["sha256"]), ("Scene Prop", "Container", "Geometry/Crate.fbx", art["blob"]))
        self.assertNotIn(self.dir, z.read("AssetManifest.json").decode()); self.assertIn("not tested", z.read("Documentation/Compatibility_Report.md").decode())
        self.assertEqual(os.listdir(os.path.join(self.dir, "staging")), [])                       # nothing half-written is left

    def test_exporting_something_pending_changes_nothing_about_it(self):              # EX-A06, AEA-008, AVP-011
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.now[0] += DAY
        plan = package.plan(self.studio, r["id"])
        self.assertEqual([(p["id"], p["hours_left"]) for p in plan["pending"]], [(art["id"], 9 * 24)])
        self.zipped(r["id"])
        kept = self.store.load(r["id"])["artifacts"][0]
        self.assertEqual((kept["state"], kept["expires"]), ("pending", art["expires"]))
        self.now[0] += 10 * DAY
        self.assertEqual(self.studio.cleanup()["expired"], 1)                                     # the export did not keep it alive

    def test_only_the_selected_candidate_goes_unless_others_are_named(self):          # AEA-006
        r, a = self.studio.import_geometry("p1", None, fixtures.cube(), "One.fbx")
        _, b = self.studio.import_geometry("p1", r["id"], fixtures.character(), "Two.fbx")
        self.assertEqual([f["path"] for f in package.plan(self.studio, r["id"])["files"]], ["Geometry/One.fbx"])
        self.assertEqual(len(package.plan(self.studio, r["id"], artifacts=[a["id"], b["id"]])["files"]), 2)
        path, name, _ = package.build(self.studio, r["id"], profile="geometry")
        with open(path, "rb") as f:
            self.assertEqual((name, f.read()), ("One.fbx", fixtures.cube()))

    def test_nothing_to_export_and_a_missing_file_are_blocked(self):                  # EX-A12
        empty = self.studio.create("p1", {"name": "Empty"})
        self.assertIn("no geometry", package.plan(self.studio, empty["id"])["blocked"])
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        os.remove(self.store.blob_path(art["blob"]))
        with self.assertRaises(ValueError) as e:
            package.build(self.studio, r["id"])
        self.assertIn("missing from storage", str(e.exception)); self.assertEqual(os.listdir(os.path.join(self.dir, "exports")), [])

    def test_a_file_in_other_conventions_is_exported_as_is_with_a_warning(self):
        r, _ = self.studio.import_geometry("p1", None, fixtures.cube(up=2, front=1, unit=100.0), "Zup.fbx")
        self.assertIn("does not convert", package.plan(self.studio, r["id"])["warnings"][0])


class Reimport(Base):
    def test_a_modular_asset_round_trips_as_an_editable_asset(self):                  # EX-A11, AVV-011, REL-002
        r, art = self.studio.import_geometry("p1", None, fixtures.character(), "Captain.fbx", fields={"type": "humanoid", "subtype": "Organic", "quality": "low", "target_vertices": 7000, "tags": ["pirate"]})
        hat = next(c for c in art["components"] if c["name"] == "Pirate_Hat")
        self.studio.component(r["id"], art["id"], hat["id"], {"name": "Tricorn", "role": "Headwear", "side": "center", "locked": True})
        data, _, _ = self.zipped(r["id"])
        clean = assets.Studio(Store(tempfile.mkdtemp(dir=self.dir), clock=lambda: self.now[0], disk=lambda: 100 * 1024 ** 3))
        back, notes = package.reimport(clean, "p2", data)
        self.assertEqual((back["name"], back["type"], back["subtype"], back["quality"], back["target_vertices"], back["tags"], back["project"]), ("Captain", "humanoid", "Organic", "low", 7000, ["pirate"], "p2"))
        got = back["artifacts"][0]
        self.assertEqual((got["blob"], got["state"], got["origin"], back["selected"]["geometry"]), (art["blob"], "pending", "reimported", got["id"]))
        by = {c["name"]: c for c in got["components"]}
        self.assertEqual((by["Tricorn"]["role"], by["Tricorn"]["side"], by["Tricorn"]["locked"], by["Tricorn"]["parent"], by["Base_Body"]["transform"]), ("Headwear", "center", True, by["Captain"]["id"], next(c for c in art["components"] if c["name"] == "Base_Body")["transform"]))
        self.assertTrue(any("pending" in n for n in notes))
        self.assertEqual(clean.component(back["id"], got["id"], by["Tricorn"]["id"], {"locked": False, "role": "Hat"})["role"], "Hat")      # still editable

    def test_reimporting_where_the_asset_already_exists_does_not_overwrite_it(self):  # EX-008
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx", approve=True)
        data, _, _ = self.zipped(r["id"])
        back, notes = package.reimport(self.studio, "p1", data)
        self.assertNotEqual(back["id"], r["id"]); self.assertTrue(any("separate asset" in n for n in notes))
        self.assertEqual((self.store.load(r["id"])["artifacts"][0]["state"], len(self.studio.list("p1"))), ("approved", 2))

    def test_changed_unsafe_or_unknown_packages_are_refused_and_store_nothing(self):  # EX-A05, SEC-A03
        r, _ = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx", approve=True)
        data, _, _ = self.zipped(r["id"])
        before = len(self.studio.list("p1"))
        flip = lambda n, b: (n, b[:300] + bytes([b[300] ^ 1]) + b[301:]) if n.endswith(".fbx") else (n, b)
        escape = lambda n, b: ("../outside.fbx", b) if n.endswith(".fbx") else (n, b)
        newer = lambda n, b: (n, json.dumps(dict(json.loads(b), schemaVersion="2.0")).encode()) if n == "AssetManifest.json" else (n, b)
        gone = lambda n, b: None if n.endswith(".fbx") else (n, b)
        for change, word in ((flip, "checksum"), (escape, "outside the package"), (newer, "manifest version"), (gone, "not in the package")):
            with self.assertRaises(ValueError) as e:
                package.reimport(self.studio, "p1", self.rezip(data, change))
            self.assertIn(word, str(e.exception))
        for junk, word in ((b"not a zip", "not a ZIP"), (self.rezip(data, lambda n, b: None if n == "AssetManifest.json" else (n, b)), "no AssetManifest")):
            with self.assertRaises(ValueError) as e:
                package.reimport(self.studio, "p1", junk)
            self.assertIn(word, str(e.exception))
        self.assertEqual(len(self.studio.list("p1")), before)


class Character(Base):
    def prepared(self):
        r, art = self.studio.import_geometry("p1", None, fixtures.character(), "Captain.fbx", fields={"type": "humanoid"})
        by = {c["name"]: c for c in art["components"]}
        for name, role in (("Base_Body", "Base anatomy"), ("Pirate_Hat", "Accessory"), ("Pirate_Coat", "Clothing")):
            self.studio.component(r["id"], art["id"], by[name]["id"], {"role": role})
        return r, art

    def found(self, r, art):
        rec = self.store.load(r["id"])
        got, ok = character.checks(rec, next(a for a in rec["artifacts"] if a["id"] == art["id"]))
        return {c["id"]: c for c in got}, ok

    def test_a_base_is_required_and_roles_are_checked(self):                          # CPA-004, CPA-010
        r, art = self.studio.import_geometry("p1", None, fixtures.character(), "Captain.fbx", fields={"type": "humanoid"})
        got, ok = self.found(r, art)
        self.assertEqual((got["base"]["status"], got["roles"]["status"], ok), ("fail", "warn", False))
        by = {c["name"]: c for c in art["components"]}
        for name in ("Base_Body", "Pirate_Coat"):
            self.studio.component(r["id"], art["id"], by[name]["id"], {"role": "Base anatomy"})
        self.assertIn("exactly one", self.found(r, art)[0]["base"]["detail"])

    def test_measurements_and_the_things_only_a_person_can_judge(self):               # CPA-002, CPA-007
        r, art = self.prepared()
        character.update(self.studio, r["id"], art["id"], {"stature_cm": 180})
        got, ok = self.found(r, art)
        self.assertEqual((got["base"]["status"], got["conventions"]["status"], got["ground"]["status"], got["centre"]["status"], got["faults"]["status"], got["uvs"]["status"]), ("pass",) * 6)
        self.assertIn("Measured 182.0 cm", got["stature"]["detail"]); self.assertEqual(got["stature"]["status"], "pass")
        self.assertEqual((got["pose"]["status"], got["hidden"]["status"], got["facing"]["status"], ok), ("fail", "manual", "manual", False))
        with self.assertRaises(ValueError) as e:
            character.hand_off(self.studio, r["id"])
        self.assertIn("Neutral pose", str(e.exception))
        character.update(self.studio, r["id"], art["id"], {"pose": "a-pose", "confirmed": ["hidden", "facing"]})
        self.assertTrue(self.found(r, art)[1])
        before = self.store.read(art["blob"])
        h = character.hand_off(self.studio, r["id"])["handoff"]
        self.assertEqual((h["artifact"], h["sha256"], h["base_name"], h["pose"], h["height_cm"], h["pending"]), (art["id"], art["blob"], "Base_Body", "a-pose", 182.0, True))
        self.assertEqual((self.store.read(art["blob"]), self.store.load(r["id"])["artifacts"][0]["state"], len(self.store.load(r["id"])["artifacts"])), (before, "pending", 1))   # nothing changed, approved or generated

    def test_changing_the_pose_or_the_body_withdraws_the_hand_off(self):              # CHP-006
        r, art = self.prepared()
        character.update(self.studio, r["id"], art["id"], {"pose": "t-pose", "confirmed": ["hidden", "facing"]})
        character.hand_off(self.studio, r["id"])
        self.assertIsNone(character.update(self.studio, r["id"], art["id"], {"pose": "a-pose"})["handoff"])
        _, other = self.studio.import_geometry("p1", r["id"], fixtures.cube(), "Other.fbx")
        c = character.update(self.studio, r["id"], other["id"], {})
        self.assertEqual((c["artifact"], c["confirmed"], c["handoff"]), (other["id"], [], None))

    def test_the_anatomy_profile_other_conventions_and_creatures(self):               # CPA-010
        r, art = self.prepared()
        character.update(self.studio, r["id"], art["id"], {"profile": "anatomy"})
        got, _ = self.found(r, art)
        self.assertEqual((got["eyes"]["status"], got["teeth"]["status"], got["tongue"]["status"]), ("fail", "fail", "fail"))
        z, zart = self.studio.import_geometry("p1", None, fixtures.cube(up=2, front=1), "Zup.fbx", fields={"type": "humanoid"})
        self.assertEqual(self.found(z, zart)[0]["conventions"]["status"], "fail")
        self.studio.update(r["id"], {"type": "creature"})
        got, ok = self.found(r, art)
        self.assertEqual((got["scope"]["status"], ok), ("info", False)); self.assertIn("Wings", character.roles("creature"))


if __name__ == "__main__":
    unittest.main()
