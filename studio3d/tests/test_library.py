"""The asset library (3d_Phase_17, whole assets)."""
import os
import shutil
import tempfile
import unittest

from studio3d import assets, library
from studio3d.store import Store
from studio3d.tests import fixtures


class Library(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [3_000_000.0]
        self.store = Store(self.dir, clock=lambda: self.now[0], disk=lambda: 100 * 1024 ** 3)
        self.studio = assets.Studio(self.store)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def approved(self, name="Crate.fbx", data=None, **fields):
        return self.studio.import_geometry("p1", None, data or fixtures.cube(), name, approve=True, fields=fields or None)

    def test_only_approved_files_are_enrolled_and_only_once(self):                    # LIB-001, LIB-002
        r, art = self.studio.import_geometry("p1", None, fixtures.cube(), "Crate.fbx")
        with self.assertRaises(ValueError) as e:
            library.add(self.studio, r["id"])
        self.assertIn("Only approved", str(e.exception)); self.assertEqual(library.items(self.studio)["total"], 0)
        self.studio.approve(r["id"], [art["id"]])
        item = library.add(self.studio, r["id"])
        self.assertEqual(library.add(self.studio, r["id"])["id"], item["id"])
        self.assertEqual((library.items(self.studio)["total"], [a["name"] for a in self.studio.list("p1")]), (1, ["Crate"]))    # not shown as a project asset
        self.assertEqual(self.store.usage()["physical"], art["size"])                 # the same bytes, stored once

    def test_use_makes_an_independent_pinned_asset_in_another_project(self):          # LIB-A01, LIB-005, LIB-006
        r, art = self.approved("Captain.fbx", fixtures.character(), type="humanoid", tags=["pirate"])
        item = library.add(self.studio, r["id"])
        a = library.use(self.studio, item["id"], "p2")
        b = library.use(self.studio, item["id"], "p3")
        self.assertEqual((a["project"], a["artifacts"][0]["state"], a["artifacts"][0]["blob"], a["from_library"]["sha256"], a["type"]), ("p2", "approved", art["blob"], art["blob"], "humanoid"))
        self.assertEqual(len({a["id"], b["id"], r["id"], item["id"]}), 4)
        hat = next(c for c in a["artifacts"][0]["components"] if c["name"] == "Pirate_Hat")
        self.assertEqual(next(c for c in a["artifacts"][0]["components"] if c["id"] == hat["parent"])["name"], "Captain")
        self.studio.component(a["id"], a["artifacts"][0]["id"], hat["id"], {"name": "Tricorn"})
        names = lambda rec: sorted(c["name"] for c in self.store.load(rec["id"])["artifacts"][0]["components"])
        self.assertIn("Tricorn", names(a)); self.assertNotIn("Tricorn", names(b)); self.assertNotIn("Tricorn", names(item))
        got = library.usage(self.studio, item["id"], lambda p: p.upper())
        self.assertEqual(sorted((u["project_name"], u["relation"]) for u in got), [("P1", "the asset this came from"), ("P2", "made from this item"), ("P3", "made from this item")])
        self.assertEqual((library.items(self.studio)["items"][0]["uses"], self.store.usage()["physical"]), (2, art["size"]))

    def test_the_item_outlives_its_source_and_removal_frees_bytes_only_when_unused(self):   # LIB-008, LIB-009
        r, art = self.approved()
        item = library.add(self.studio, r["id"])
        self.studio.delete(r["id"])
        self.assertTrue(self.store.has(art["blob"])); self.assertTrue(library.items(self.studio)["items"][0]["complete"])
        used = library.use(self.studio, item["id"], "p2")
        self.assertEqual(library.remove(self.studio, item["id"]), 0)                  # still in use by p2's asset
        self.assertEqual((library.items(self.studio)["total"], self.store.load(used["id"])["artifacts"][0]["blob"]), (0, art["blob"]))
        self.assertEqual(self.studio.delete(used["id"]), art["size"]); self.assertFalse(self.store.has(art["blob"]))

    def test_search_favourites_archive_and_collections(self):                         # LIB-003, LIB-008, LIB-013
        a = library.add(self.studio, self.approved("Crate.fbx", type="scene_prop", tags=["wood", "dock"])[0]["id"])
        self.now[0] += 5
        b = library.add(self.studio, self.approved("Captain.fbx", fixtures.character(), type="humanoid", tags=["pirate"])[0]["id"])
        find = lambda **kw: [i["name"] for i in library.items(self.studio, **kw)["items"]]
        self.assertEqual((find(), find(query="dock"), find(query="PIRATE humanoid"), find(kind="scene_prop"), find(query="spaceship")), (["Captain", "Crate"], ["Crate"], ["Captain"], ["Crate"], []))
        library.update(self.studio, a["id"], {"favorite": True, "name": "Old crate", "tags": ["barrel"]})
        self.assertEqual((find(favorite=True), find(query="barrel")), (["Old crate"], ["Old crate"]))
        library.update(self.studio, b["id"], {"archived": True})
        self.assertEqual((find(), find(archived=True)), (["Old crate"], ["Captain"]))
        with self.assertRaises(ValueError):
            library.use(self.studio, b["id"], "p2")
        col = library.collection(self.studio, {"name": "Harbour set"})[0]
        library.collection(self.studio, {"id": col["id"], "item": a["id"], "on": True})
        self.assertEqual((find(collection=col["id"]), library.items(self.studio)["collections"][0]["count"]), (["Old crate"], 1))
        library.collection(self.studio, {"id": col["id"], "item": a["id"], "on": False})
        self.assertEqual(find(collection=col["id"]), [])
        library.collection(self.studio, {"id": col["id"], "delete": True})
        self.assertEqual((library.items(self.studio)["collections"], find()), ([], ["Old crate"]))               # deleting a group deletes no item

    def test_a_missing_file_marks_the_item_incomplete_and_blocks_use(self):           # LIB-010
        r, art = self.approved()
        item = library.add(self.studio, r["id"])
        os.remove(self.store.blob_path(art["blob"]))
        self.assertFalse(library.items(self.studio)["items"][0]["complete"])
        with self.assertRaises(ValueError):
            library.use(self.studio, item["id"], "p2")
        with self.assertRaises(LookupError):
            library.update(self.studio, r["id"], {"favorite": True})                  # a project asset is not a library item


if __name__ == "__main__":
    unittest.main()
