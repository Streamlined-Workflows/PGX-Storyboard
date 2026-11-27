"""Asset records, storage and lifecycle (3d_Phase_2, 3d_Phase_4, 3d_Phase_22)."""
import os
import shutil
import tempfile
import unittest

from studio3d import assets, fbx
from studio3d.store import Blocked, Store
from studio3d.tests import fixtures

DAY = 86400
GB = 1024 ** 3


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [1_000_000.0]
        self.free = [100 * GB]
        self.store = Store(self.dir, clock=lambda: self.now[0], disk=lambda: self.free[0])
        self.studio = assets.Studio(self.store)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def blobs(self):
        return sorted(f for _, _, fs in os.walk(os.path.join(self.dir, "blobs")) for f in fs)

    def age_files(self):                       # make every stored file look old enough to be swept
        for dp, _, fs in os.walk(self.dir):
            for f in fs:
                os.utime(os.path.join(dp, f), (0, 0))


class Identity(Base):
    def test_renaming_and_reclassifying_keep_the_identity_and_the_files(self):       # ADMA-019
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.assertEqual((r["name"], r["type"], r["origin"], r["production"]), ("Crate", "scene_prop", "ground center", "in progress"))
        again = self.studio.update(r["id"], {"name": "Cargo crate", "type": "held_prop", "subtype": "Container", "quality": "low"})
        self.assertEqual((again["id"], again["parent"], again["subtype"], again["origin"], again["target_vertices"]), (r["id"], "props", "Container", "bounding center", 5000))
        self.assertEqual((again["artifacts"][0]["id"], again["artifacts"][0]["blob"]), (art["id"], art["blob"]))
        self.assertEqual(self.studio.update(r["id"], {"type": "vehicle"})["structural_profile"], "exterior")
        self.assertEqual(self.studio.update(r["id"], {"type": "scenery", "structural_profile": "interior"})["structural_profile"], "interior")

    def test_a_copy_is_a_new_asset_that_shares_the_files(self):                       # ADS-008, ADMA-018
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx", approve=True)
        c = self.studio.copy(r["id"])
        self.assertNotEqual(c["id"], r["id"]); self.assertNotEqual(c["artifacts"][0]["id"], art["id"])
        self.assertEqual((c["artifacts"][0]["blob"], len(self.blobs()), c["selected"]["geometry"]), (art["blob"], 1, c["artifacts"][0]["id"]))
        u = self.store.usage()
        self.assertEqual((u["physical"], u["logical"]), (art["size"], art["size"] * 2))           # one file on disk, two records

    def test_components_come_from_the_files_hierarchy(self):
        r, art = self.studio.import_geometry("p1", None, fixtures.character(), "Captain.fbx", fields={"type": "humanoid"})
        by = {c["name"]: c for c in art["components"]}
        self.assertEqual((by["Captain"]["node"], by["Base_Body"]["node"], by["Pirate_Hat"]["parent"], by["Base_Body"]["vertices"]), ("group", "mesh", by["Captain"]["id"], 8))
        c = self.studio.component(r["id"], art["id"], by["Pirate_Hat"]["id"], {"role": "Headwear", "locked": True})
        self.assertEqual((c["role"], c["locked"]), ("Headwear", True))
        with self.assertRaises(Blocked):
            self.studio.component(r["id"], art["id"], by["Pirate_Hat"]["id"], {"name": "Tricorn"})
        self.assertEqual(self.studio.component(r["id"], art["id"], by["Pirate_Hat"]["id"], {"locked": False, "name": "Tricorn"})["name"], "Tricorn")

    def test_requested_and_measured_control_points_are_shown_not_enforced(self):      # GMA-022
        r, _ = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx", fields={"quality": "low", "target_vertices": 600})
        b = self.studio.view(r["id"])["budget"]
        self.assertEqual((b["target"], b["measured"], b["difference"], b["within_profile"], b["measured_profile"]), (600, 8, -592, False, "below"))


class Lifecycle(Base):
    def test_an_import_is_a_pending_candidate_with_ten_days(self):                    # ARA-001
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.assertEqual((art["state"], art["expires"], art["origin"]), ("pending", self.now[0] + 10 * DAY, "imported"))
        self.now[0] += DAY + 5
        self.assertEqual(self.studio.view(r["id"])["artifacts"][0]["days_left"], 9)
        self.studio.select(r["id"], art["id"])
        self.assertEqual(self.store.load(r["id"])["artifacts"][0]["expires"], art["expires"])     # selecting moves nothing

    def test_a_file_that_cannot_be_read_stores_nothing(self):
        with self.assertRaises(fbx.FBXError):
            self.studio.import_geometry("p1", None, b"junk", "bad.fbx")
        self.assertEqual((self.blobs(), self.store.records()), ([], []))

    def test_an_unapproved_candidate_expires_and_its_file_goes(self):                 # ARA-004, DEA-002
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.now[0] += 10 * DAY + 1
        out = self.studio.cleanup()
        self.assertEqual((out["expired"], out["freed"], self.blobs()), (1, art["size"], []))
        self.assertEqual((self.store.load(r["id"])["artifacts"], self.store.load(r["id"])["selected"]["geometry"]), ([], None))
        self.assertEqual(sorted(out), ["expired", "freed"])                                       # totals only, no names

    def test_an_approved_candidate_does_not_expire(self):                             # ARA-005
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.assertEqual(self.studio.approve(r["id"], [art["id"]]), {"approved": [art["id"]]})
        self.now[0] += 400 * DAY
        self.assertEqual((self.studio.cleanup()["expired"], len(self.blobs())), (0, 1))

    def test_deny_deletes_now_but_not_bytes_another_record_uses(self):                # DEA-001, DEA-004, AVV-001
        a, art_a = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx", approve=True)
        b, art_b = self.studio.import_geometry("p1", None, fixtures.cube(), "B.fbx")
        self.assertEqual(len(self.blobs()), 1)
        out = self.studio.deny(b["id"], [art_b["id"]])
        self.assertEqual((out["denied"], out["freed"], len(self.blobs())), (1, 0, 1))             # the approved asset still needs the bytes
        self.assertEqual(self.store.read(art_a["blob"]), fixtures.cube())
        self.assertEqual(self.studio.deny(a["id"], [art_a["id"]])["freed"], art_a["size"]); self.assertEqual(self.blobs(), [])   # last reference gone: the file goes (DEA-005)

    def test_a_file_a_job_is_reading_outlives_its_expiry_without_coming_back(self):   # AVV-002
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        self.store.pin(art["blob"]); self.now[0] += 11 * DAY
        self.assertEqual((self.studio.cleanup()["expired"], len(self.blobs())), (0, 1))
        self.store.unpin(art["blob"])
        self.assertEqual((self.studio.cleanup()["expired"], self.blobs()), (1, []))

    def test_dependencies_are_approved_together_or_not_at_all(self):                  # ADA-001..005, AVV-003
        r, base = self.studio.import_geometry("p1", None, fixtures.cube(), "Base.fbx")
        _, mid = self.studio.import_geometry("p1", r["id"], fixtures.character(), "Mid.fbx")
        _, top = self.studio.import_geometry("p1", r["id"], fixtures.broken(), "Top.fbx")
        rec = self.store.load(r["id"]); by = {a["id"]: a for a in rec["artifacts"]}
        by[top["id"]]["requires"] = [{"id": mid["id"], "reason": "The mesh this was fitted to."}]
        by[mid["id"]]["requires"] = [{"id": base["id"], "reason": "The body it stands on."}]
        self.store.save(rec)
        out = self.studio.approve(r["id"], [top["id"]])
        self.assertEqual([(n["id"], n["reason"]) for n in out["needs"]], [(mid["id"], "The mesh this was fitted to."), (base["id"], "The body it stands on.")])
        self.assertEqual(out["bytes"], mid["size"] + base["size"])
        self.assertEqual({a["state"] for a in self.store.load(r["id"])["artifacts"]}, {"pending"})                    # cancelling changes nothing
        self.assertEqual(len(self.studio.approve(r["id"], [top["id"]], confirmed=True)["approved"]), 3)
        self.assertEqual(self.studio.deny(r["id"], [base["id"]])["held"], [base["id"]])                                # needed by an approved one

    def test_a_missing_dependency_blocks_approval(self):                              # ADA-008
        r, a = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx")
        rec = self.store.load(r["id"]); rec["artifacts"][0]["requires"] = [{"id": "art_gone", "reason": "The source mesh."}]; self.store.save(rec)
        with self.assertRaises(ValueError):
            self.studio.approve(r["id"], [a["id"]], confirmed=True)
        self.assertEqual(self.store.load(r["id"])["artifacts"][0]["state"], "pending")

    def test_deleting_an_asset_removes_its_record_and_files(self):
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx", approve=True)
        self.assertEqual(self.studio.delete(r["id"]), art["size"])
        self.assertEqual((self.blobs(), self.studio.list("p1")), ([], []))


class Storage(Base):
    def test_work_is_refused_below_the_disk_floor_and_above_the_budget(self):         # AVV-009
        self.free[0] = 1 * GB
        with self.assertRaises(Blocked) as e:
            self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx")
        self.assertIn("free disk space", str(e.exception)); self.assertEqual(self.blobs(), [])
        self.free[0] = 100 * GB
        r, _ = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx", approve=True)
        self.store.set_settings(budget_bytes=1000)
        with self.assertRaises(Blocked) as e:
            self.studio.import_geometry("p1", None, fixtures.character(), "B.fbx")
        self.assertIn("budget", str(e.exception))
        self.assertEqual(len(self.store.load(r["id"])["artifacts"]), 1)                           # nothing approved was removed to make room
        self.assertEqual(self.store.set_settings(floor_bytes=1)["floor_bytes"], 256 * 1024 ** 2)  # the floor has a hard minimum

    def test_leftovers_from_an_interrupted_write_are_swept(self):                     # AVV-004
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx", approve=True)
        orphan, _ = self.store.put(b"written but never recorded")
        with open(os.path.join(self.dir, "staging", "half.zip"), "wb") as f:
            f.write(b"x" * 10)
        self.assertEqual(self.studio.cleanup()["freed"], 0)                                       # too new: a write may be about to record it
        self.age_files()
        self.assertEqual(self.studio.cleanup()["freed"], len(b"written but never recorded") + 10)
        self.assertEqual(self.blobs(), [art["blob"]])

    def test_a_damaged_file_is_noticed(self):
        _, art = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx")
        with open(self.store.blob_path(art["blob"]), "r+b") as f:
            f.seek(40); f.write(b"\xff")
        with self.assertRaises(ValueError):
            self.store.read(art["blob"])

    def test_state_survives_a_restart(self):                                          # ARA-006, ADMA-009
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "A.fbx")
        again = assets.Studio(Store(self.dir, clock=lambda: self.now[0], disk=lambda: self.free[0]))
        kept = again.view(r["id"])["artifacts"][0]
        self.assertEqual((kept["state"], kept["expires"], kept["report"]["totals"]["vertices"]), ("pending", art["expires"], 8))


class References(Base):
    def test_pictures_are_attached_by_id_and_looked_up_live(self):                    # RMA-003, RMA-021, RMA-022
        live = {"g1": {"image": "front.png", "state": "pending", "what": "Front view"}}
        self.studio.resolve_reference = lambda project, artifact: live.get(artifact)
        r = self.studio.create("p1", {"name": "Skald", "type": "humanoid"})
        r = self.studio.assign_references(r["id"], [{"artifact": "g1", "direction": "front", "component": "Complete asset"}, {"artifact": "g2", "role": "component", "component": "Headwear"}, {"artifact": "g1"}])
        self.assertEqual([(x["artifact"], x["roles"], x["direction"]) for x in r["references"]], [("g1", ["directional"], "front"), ("g2", ["component"], "")])
        shown = self.studio.view(r["id"])["references"]
        self.assertEqual([(x["state"], x["image"]) for x in shown], [("pending", "front.png"), ("unavailable", None)])
        r = self.studio.reference(r["id"], r["references"][1]["id"], {"roles": ["primary", "component"], "included": False})
        r = self.studio.reference(r["id"], r["references"][0]["id"], {"roles": ["primary", "directional"]})
        self.assertEqual([x["roles"] for x in r["references"]], [["primary", "directional"], ["component"]])           # one primary; the other keeps its other role
        self.assertEqual(len(self.studio.reference(r["id"], r["references"][0]["id"], remove=True)["references"]), 1)


class Manifest(Base):
    def test_the_manifest_is_portable(self):                                          # MAN-001..008
        r, art = self.studio.import_geometry("p1", None, fixtures.character(), "Captain.fbx", fields={"type": "humanoid", "subtype": "Organic", "tags": ["pirate"]})
        m = self.studio.manifest(self.store.load(r["id"]), paths={art["id"]: "Geometry/Captain.fbx"})
        self.assertEqual((m["schemaVersion"], m["assetId"], m["classification"]["type"], m["classification"]["parent"], m["coordinates"]["unit"]), ("1.0", r["id"], "Humanoid", "Actors", "cm"))
        self.assertEqual((m["artifacts"][0]["path"], m["artifacts"][0]["sha256"], len(m["artifacts"][0]["components"]), m["geometry"]["measured"]["vertices"]), ("Geometry/Captain.fbx", art["blob"], 4, 24))
        import json
        self.assertNotIn(self.dir, json.dumps(m))                                                 # no storage paths


if __name__ == "__main__":
    unittest.main()
