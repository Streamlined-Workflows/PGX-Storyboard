"""The FBX reader: counting, conventions and checks (3d_Phase_4 4.14, 3d_Phase_6 6.4 and 6.8)."""
import array
import unittest

from studio3d import fbx
from studio3d.fbx import Node
from studio3d.tests import fixtures


class Reading(unittest.TestCase):
    def test_a_cube_is_counted_as_stored(self):
        for version in (7400, 7500):                                  # the two layouts of the binary form
            r = fbx.analyse(fixtures.cube(version))
            t = r["totals"]
            self.assertEqual((r["version"], t["vertices"], t["faces"], t["triangles"], t["edges"], t["quads"], t["tris"], t["ngons"]), (version, 8, 6, 12, 12, 6, 0, 0))
            self.assertEqual((t["islands"], t["boundary_edges"], r["defects"]), (1, 0, []))
            self.assertEqual(t["size_cm"], [100.0, 100.0, 100.0])

    def test_triangulating_changes_faces_but_not_control_points(self):          # GMA-020
        tris = [[a, b, c] for f in fixtures.CUBE[1] for a, b, c in ((f[0], f[1], f[2]), (f[0], f[2], f[3]))]
        data = fixtures.scene([fixtures.mesh(100, "Tri", fixtures.CUBE[0], tris), fixtures.model(200, "Tri")], [(100, 200), (200, 0)])
        t = fbx.analyse(data)["totals"]
        self.assertEqual((t["vertices"], t["faces"], t["triangles"], t["edges"], t["tris"]), (8, 12, 12, 18, 12))

    def test_rendering_vertices_are_counted_apart_from_control_points(self):     # GMA-021
        plain, mapped = fbx.analyse(fixtures.cube())["totals"], fbx.analyse(fixtures.cube(uv=True))["totals"]
        self.assertEqual((plain["vertices"], plain["rendering_vertices"]), (8, 8))
        self.assertEqual((mapped["vertices"], mapped["rendering_vertices"]), (8, 24))   # every corner has its own UV here

    def test_conventions_are_reported_not_changed(self):
        ok = fbx.analyse(fixtures.cube())["conventions"]
        self.assertEqual((ok["up"], ok["front"], ok["unit_scale"], ok["canonical"], ok["notes"]), ("+Y", "+Z", 1.0, True, []))
        z_up = fbx.analyse(fixtures.cube(up=2, front=1, unit=100.0))
        self.assertFalse(z_up["conventions"]["canonical"]); self.assertEqual(len(z_up["conventions"]["notes"]), 2)
        self.assertEqual(z_up["totals"]["size_cm"], [10000.0, 10000.0, 10000.0])        # a unit of one metre

    def test_hierarchy_and_placement(self):
        r = fbx.analyse(fixtures.character())
        by = {m["name"]: m for m in r["models"]}
        self.assertEqual(sorted(by), ["Base_Body", "Captain", "Pirate_Coat", "Pirate_Hat"])
        self.assertEqual((by["Pirate_Hat"]["parent"], by["Captain"]["parent"], by["Captain"]["geometry"]), (by["Captain"]["id"], None, None))
        self.assertEqual(r["totals"]["size_cm"], [48.0, 182.0, 30.0])                    # the hat sits on the body: 170 + 12
        self.assertEqual((r["totals"]["vertices"], len(r["geometries"])), (24, 3))
        coat = next(g for g in r["geometries"] if g["name"] == "Coat")
        self.assertEqual((coat["boundary_edges"], coat["faces"]), (8, 4))                # open at top and bottom, which is not a fault
        body = next(g for g in r["geometries"] if g["name"] == "Body")
        self.assertEqual((body["material_slots"], body["uv_channels"][0]["name"]), (2, "UVMap"))
        self.assertEqual(r["defects"], [])

    def test_known_faults_are_found_and_located(self):                           # GMA-034
        r = fbx.analyse(fixtures.broken())
        found = {d["kind"]: d for d in r["defects"]}
        self.assertEqual(sorted(found), ["degenerate faces", "duplicate faces", "non-manifold edges", "unused control points"])
        self.assertEqual((found["degenerate faces"]["faces"], found["duplicate faces"]["faces"], found["unused control points"]["count"]), ([6], [7], 1))
        self.assertEqual(found["degenerate faces"]["severity"], "significant defect")

    def test_rigging_is_noticed(self):
        extra = [fixtures.model(300, "Hips", "LimbNode"), Node("Deformer", [fbx.Long(400), "Skin\x00\x01Deformer", "Skin"]), Node("AnimationStack", [fbx.Long(500), "Take\x00\x01AnimStack", ""])]
        data = fixtures.scene([fixtures.mesh(100, "Cube", *fixtures.CUBE), fixtures.model(200, "Cube")], [(100, 200), (200, 0), (300, 0)], extra=extra)
        self.assertEqual({k: fbx.analyse(data)["rigging"][k] for k in ("skeleton", "skin", "animation", "blend_shapes")}, {"skeleton": 1, "skin": 1, "animation": 1, "blend_shapes": 0})


class Refusing(unittest.TestCase):
    def test_other_files_are_refused_with_a_reason(self):
        for data, word in ((b"not a model", "not an FBX"), (b"; FBX 7.4.0 project file\nFBXHeaderExtension:  {", "text-form"), (fixtures.cube()[:300], "outside the file")):
            with self.assertRaises(fbx.FBXError) as e:
                fbx.analyse(data)
            self.assertIn(word, str(e.exception))

    def test_a_file_that_lies_about_its_arrays_is_refused(self):
        bomb = bytearray(fixtures.cube())
        at = bomb.index(b"Vertices") + len(b"Vertices") + 1
        bomb[at:at + 4] = (10 ** 9).to_bytes(4, "little")                            # claims a billion numbers
        with self.assertRaises(fbx.FBXError):
            fbx.analyse(bytes(bomb))

    def test_faces_pointing_nowhere_are_a_technical_failure(self):
        data = fixtures.scene([fixtures.mesh(100, "Bad", fixtures.CUBE[0], [[0, 1, 99]]), fixtures.model(200, "Bad")], [(100, 200), (200, 0)])
        d = fbx.analyse(data)["defects"][0]
        self.assertEqual((d["kind"], d["severity"], d["faces"]), ("invalid indices", "technical failure", [0]))


class Profiles(unittest.TestCase):
    def test_density_profiles_are_by_control_points(self):
        self.assertEqual([fbx.profile(n) for n in (8, 500, 10_000, 10_001, 30_000, 30_001, 500_000, 500_001)], ["below", "low", "low", "mid", "mid", "high", "high", "above"])


if __name__ == "__main__":
    unittest.main()
