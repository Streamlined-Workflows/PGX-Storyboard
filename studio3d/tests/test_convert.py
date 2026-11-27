"""GLB import through the Blender converter (the user's decision of 27 Nov 2026: GLB becomes FBX with headless Blender).

The converter itself is stood in for here. The last test runs the real service code against a real Blender when
SWIFT_TEST_BLENDER_CMD names one (for example "/path/to/python" with the bpy module); otherwise it is skipped.
"""
import importlib.util
import os
import shutil
import tempfile
import unittest

from studio3d import api, convert, fbx
from studio3d.store import Store
from studio3d.tests import fixtures

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Convert(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        api.configure()
        api.use(Store(self.dir, disk=lambda: 100 * 1024 ** 3))
        self.seen = {"ok": True, "blender": "4.0.2", "reason": ""}
        self.calls = []
        api._state.update(convert_info=lambda fresh=False: self.seen, convert_run=lambda glb: (self.calls.append(len(glb)), fixtures.cube())[1],
                          convert_test=lambda: {"passed": True, "problems": [], "blender": self.seen["blender"]})

    def tearDown(self):
        for k in ("convert_info", "convert_run", "convert_test"):
            api._state.pop(k, None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def bring(self, data, name="Crate.glb"):
        return api.handle("POST", api.PREFIX + "import", {"project": "p1", "name": name}, raw=data)

    def test_glb_is_refused_until_the_converter_has_passed_its_test_here(self):       # Q19-04
        with self.assertRaises(ValueError) as e:
            self.bring(fixtures.glb_cube())
        self.assertIn("has not passed its test", str(e.exception)); self.assertEqual(self.calls, [])
        self.seen = {"ok": False, "blender": "", "reason": "The converter service is not running on this computer."}
        with self.assertRaises(ValueError) as e:
            self.bring(fixtures.glb_cube())
        self.assertIn("not running", str(e.exception))
        caps = {c["capability"]: c for c in api.handle("GET", api.PREFIX + "info", {})["capabilities"]}
        self.assertFalse(caps["geometry.convert"]["available"])

    def test_after_the_test_a_glb_becomes_a_pending_fbx_with_its_source_kept(self):
        out = api.handle("POST", api.PREFIX + "converter/test", {}, {})
        self.assertTrue(out["passed"] and out["converter"]["tested"])
        a = self.bring(fixtures.glb_cube())["asset"]
        made = next(x for x in a["artifacts"] if x["category"] == "geometry")
        src = next(x for x in a["artifacts"] if x["category"] == "source")
        self.assertEqual((a["name"], made["name"], made["origin"], made["state"], made["source"], src["format"], src["made"], src["state"], made["requires"]),
                         ("Crate", "Crate.fbx", "converted", "pending", src["id"], "glb", made["id"], "pending", []))
        self.assertEqual((self.calls, a["selected"]["geometry"], os.listdir(os.path.join(self.dir, "staging"))), ([len(fixtures.glb_cube())], made["id"], []))
        api.handle("POST", api.PREFIX + "deny", {}, {"asset": a["id"], "ids": [src["id"]]})                 # the source can go without taking the FBX
        self.assertEqual([x["category"] for x in api.handle("GET", api.PREFIX + "asset", {"id": a["id"]})["artifacts"]], ["geometry"])

    def test_a_changed_blender_has_to_pass_again_and_a_failed_test_withdraws_the_pass(self):   # Q19-03, Q19-04
        api.handle("POST", api.PREFIX + "converter/test", {}, {})
        self.seen = {"ok": True, "blender": "4.2.0", "reason": ""}
        with self.assertRaises(ValueError) as e:
            self.bring(fixtures.glb_cube())
        self.assertIn("Blender changed from 4.0.2 to 4.2.0", str(e.exception))
        api._state["convert_test"] = lambda: {"passed": False, "problems": ["a one-metre cube came out 1.0 × 1.0 × 1.0 cm"], "blender": "4.2.0"}
        out = api.handle("POST", api.PREFIX + "converter/test", {}, {})
        self.assertFalse(out["passed"] or out["converter"]["tested"]); self.assertIn("cube", out["problems"][0])

    def test_a_conversion_that_fails_stores_nothing(self):
        api.handle("POST", api.PREFIX + "converter/test", {}, {})
        def bad(glb):
            raise ValueError("Blender could not read or convert that file.")
        api._state["convert_run"] = bad
        with self.assertRaises(ValueError) as e:
            self.bring(fixtures.glb_cube())
        self.assertIn("could not read", str(e.exception))
        self.assertEqual((api.handle("GET", api.PREFIX + "assets", {"project": "p1"})["assets"], os.listdir(os.path.join(self.dir, "staging"))), ([], []))

    def test_the_check_catches_wrong_size_axes_and_position(self):
        good = fbx.analyse(fixtures.scene([fixtures.mesh(100, "TestCube", [c + (300 if i % 3 == 0 else 200 if i % 3 == 2 else 0) for i, c in enumerate(fixtures.CUBE[0])], fixtures.CUBE[1]), fixtures.model(200, "TestCube")], [(100, 200), (200, 0)]))
        self.assertEqual(convert.check(good), [])
        self.assertTrue(any("moved or turned" in p for p in convert.check(fbx.analyse(fixtures.cube()))))
        self.assertTrue(any("axes or units" in p for p in convert.check(fbx.analyse(fixtures.cube(up=2, front=1)))))
        self.assertEqual(convert.test_cube()[:4], b"glTF")

    @unittest.skipUnless(os.environ.get("SWIFT_TEST_BLENDER_CMD"), "no Blender to test against")
    def test_the_real_service_code_with_a_real_blender(self):
        os.environ["BLENDER_CMD"] = os.environ["SWIFT_TEST_BLENDER_CMD"]
        spec = importlib.util.spec_from_file_location("convert_service", os.path.join(HERE, "convert-service", "service.py"))
        service = importlib.util.module_from_spec(spec); spec.loader.exec_module(service)
        self.assertEqual(convert.check(fbx.analyse(service.convert(convert.test_cube()))), [])
        for junk, word in ((b"hello", "not a GLB"), (b"glTF" + b"\x00" * 40, "could not read")):
            with self.assertRaises(ValueError) as e:
                service.convert(junk)
            self.assertIn(word, str(e.exception))


if __name__ == "__main__":
    unittest.main()
