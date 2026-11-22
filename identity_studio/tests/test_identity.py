"""Run from the repository root:  python -m unittest discover -s identity_studio/tests -t ."""
import json
import os
import tempfile
import unittest

from identity_studio import api, schemas
from identity_studio.storage import Store


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        api.use_store(self.store)

    def tearDown(self):
        api.use_store(None)
        self.tmp.cleanup()


class SchemaTests(Base):
    def test_ids_are_only_short_hex(self):
        self.assertTrue(schemas.valid_id(schemas.new_id()))
        for bad in ("", "../etc/passwd", "abc", "ABCDEF123456", "a" * 40, "12345678.json", None, 12345678, "1234 5678"):
            self.assertFalse(schemas.valid_id(bad), bad)

    def test_settings_fall_back_instead_of_storing_bad_values(self):
        s = schemas.clean_settings({"style": "<script>", "layout": "sideways", "background": 7, "concept_count": 99,
                                    "palette": ["#22C55E", "red", "#12345", 5, "#000000"], "platforms": ["teams", "toaster"],
                                    "app_name": "  SWIFT Director  ", "surprise": "dropped"})
        self.assertEqual(s["style"], schemas.STYLES[0])
        self.assertEqual(s["layout"], schemas.LAYOUTS[0])
        self.assertEqual(s["background"], schemas.BACKGROUNDS[0])
        self.assertEqual(s["concept_count"], 8)
        self.assertEqual(s["palette"], ["#22c55e", "#000000"])
        self.assertEqual(s["platforms"], ["teams"])
        self.assertEqual(s["app_name"], "SWIFT Director")
        self.assertNotIn("surprise", s)
        self.assertEqual(set(s), set(schemas.default_settings()))

    def test_partial_settings_keep_the_rest(self):
        current = schemas.clean_settings({"app_name": "Folio", "tagline": "Cards", "concept_count": 6})
        s = schemas.clean_settings({"tagline": "New"}, current)
        self.assertEqual((s["app_name"], s["tagline"], s["concept_count"]), ("Folio", "New", 6))


class StorageTests(Base):
    def test_create_load_and_survive_a_restart(self):
        p = self.store.create("Director icon", "The app icon")
        again = Store(self.tmp.name).load(p["id"])            # a fresh Store is what a restart looks like
        self.assertEqual((again["name"], again["description"]), ("Director icon", "The app icon"))
        self.assertEqual(again["schema"], schemas.SCHEMA_VERSION)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, "identity", "projects", p["id"] + ".json")))

    def test_update_only_takes_editable_fields(self):
        p = self.store.create("One")
        out = self.store.update(p["id"], {"name": "Two", "settings": {"app_name": "Folio"}, "id": "deadbeef0000",
                                          "concepts": [{"image": "x.png"}], "approved_concept_id": "zzz", "created": 1})
        self.assertEqual((out["id"], out["name"], out["settings"]["app_name"]), (p["id"], "Two", "Folio"))
        self.assertEqual((out["concepts"], out["approved_concept_id"], out["created"]), ([], None, p["created"]))
        self.assertGreaterEqual(out["updated"], p["updated"])

    def test_a_name_is_required(self):
        p = self.store.create("One")
        with self.assertRaises(ValueError):
            self.store.update(p["id"], {"name": "   "})

    def test_duplicate_is_independent_and_copies_files(self):
        p = self.store.create("Original")
        os.makedirs(self.store.asset_dir(p["id"]))
        with open(os.path.join(self.store.asset_dir(p["id"]), "mark.svg"), "w") as f:
            f.write("<svg/>")
        copy = self.store.duplicate(p["id"])
        self.assertNotEqual(copy["id"], p["id"])
        self.assertEqual(copy["name"], "Original (copy)")
        self.assertTrue(os.path.isfile(os.path.join(self.store.asset_dir(copy["id"]), "mark.svg")))
        self.store.update(copy["id"], {"name": "Changed"})
        self.assertEqual(self.store.load(p["id"])["name"], "Original")

    def test_delete_moves_to_trash_and_erases_nothing(self):
        p = self.store.create("Gone")
        os.makedirs(self.store.asset_dir(p["id"]))
        self.store.delete(p["id"])
        self.assertEqual(self.store.list(), [])
        with self.assertRaises(ValueError):
            self.store.load(p["id"])
        trash = os.listdir(self.store.trash)
        self.assertEqual(len(trash), 2)
        self.assertTrue(all(name.startswith(p["id"]) for name in trash))

    def test_bad_ids_never_reach_the_disk(self):
        outside = os.path.join(self.tmp.name, "secret.json")
        with open(outside, "w") as f:
            json.dump({"id": "x"}, f)
        for bad in ("../secret", "..%2Fsecret", "/etc/passwd", "", "secret", "a/b"):
            for action in (self.store.load, self.store.delete, self.store.duplicate):
                with self.assertRaises(ValueError):
                    action(bad)
        self.assertTrue(os.path.isfile(outside))

    def test_list_is_newest_first_and_skips_damaged_files(self):
        a = self.store.create("A")
        b = self.store.create("B")
        self.store.update(a["id"], {"description": "touched"})
        with open(os.path.join(self.store.projects, "0123456789ab.json"), "w") as f:
            f.write("{ not json")
        with open(os.path.join(self.store.projects, "notes.txt"), "w") as f:
            f.write("ignore me")
        self.assertEqual([p["id"] for p in self.store.list()], [a["id"], b["id"]])

    def test_storyboard_files_are_never_touched(self):
        board = os.path.join(self.tmp.name, "projects")
        os.makedirs(board)
        with open(os.path.join(board, "abc123abc123.json"), "w") as f:
            f.write('{"name": "storyboard project"}')
        p = self.store.create("Identity")
        self.store.duplicate(p["id"])
        self.store.delete(p["id"])
        self.assertEqual(os.listdir(board), ["abc123abc123.json"])
        with open(os.path.join(board, "abc123abc123.json")) as f:
            self.assertEqual(f.read(), '{"name": "storyboard project"}')


class ApiTests(Base):
    def test_full_round_trip(self):
        made = api.handle("POST", "/api/identity/projects", payload={"name": "Teams Tickets", "description": "App icon"})
        pid = made["id"]
        self.assertEqual(api.handle("GET", "/api/identity/projects")["projects"][0]["name"], "Teams Tickets")
        api.handle("PUT", "/api/identity/project", {"id": pid}, {"name": "Tickets", "settings": {"style": "futuristic"}})
        got = api.handle("GET", "/api/identity/project", {"id": pid})
        self.assertEqual((got["name"], got["settings"]["style"]), ("Tickets", "futuristic"))
        copy = api.handle("POST", "/api/identity/projects/duplicate", payload={"id": pid})
        self.assertEqual(len(api.handle("GET", "/api/identity/projects")["projects"]), 2)
        api.handle("POST", "/api/identity/projects/delete", payload={"id": copy["id"]})
        self.assertEqual([p["id"] for p in api.handle("GET", "/api/identity/projects")["projects"]], [pid])

    def test_info_says_what_is_not_built_yet(self):
        info = api.handle("GET", "/api/identity/info")
        self.assertEqual(info["ready"], {"projects": True, "jobs": True, "generation": False, "references": False, "exports": False})
        self.assertIn("custom", info["styles"])

    def test_unknown_routes_and_missing_projects(self):
        with self.assertRaises(LookupError):
            api.handle("GET", "/api/identity/nope")
        with self.assertRaises(LookupError):
            api.handle("DELETE", "/api/identity/projects")
        with self.assertRaises(ValueError):
            api.handle("GET", "/api/identity/project", {"id": "0123456789ab"})
        self.assertTrue(api.handles("/api/identity/projects"))
        self.assertFalse(api.handles("/api/projects"))


if __name__ == "__main__":
    unittest.main()
