"""Reference Generation: the rules in reference.py (docs/Reference_Generation_Design.md)."""
import unittest

import reference

DAY = 86400


def project(**ref):
    return {"id": "p1", "generated": [], "image_jobs": [], "reference": reference.clean({"projects": [dict({"id": "rpaaaaaa01", "name": "Misty"}, **ref)]})}


def finish(p, gid, created, rid="rpaaaaaa01", **job):
    """What app.py leaves behind when a sheet finishes: a done job and a generated picture."""
    p["image_jobs"].append(dict({"id": gid, "kind": "ref", "slot": rid, "status": "done", "ref_prompt": "a sheet", "ref_sources": [], "width": 1024, "height": 576}, **job))
    p["generated"].append({"id": gid, "image": gid + ".png", "kind": "ref", "slot": rid, "created": created, "seed": 7})


class Registry(unittest.TestCase):
    def test_four_parents_and_eight_types_each_with_a_custom_subtype(self):
        v = reference.view(project())
        self.assertEqual([g["label"] for g in v["registry"]], ["Actors", "Scene Assets", "Props", "World Assets"])
        types = [t for g in v["registry"] for t in g["types"]]
        self.assertEqual(len(types), 8)
        self.assertTrue(all(t["subtypes"][-1] == "Custom" for t in types))
        self.assertEqual(set(reference.TEMPLATES), {t["key"] for t in types})          # every type has a recommended sheet

    def test_classification_is_kept_consistent(self):
        s = reference.clean({"projects": [{"id": "rpaaaaaa01", "type": "vehicle", "parent": "actors", "subtype": "Quadruped"}]})
        p = s["projects"][0]
        self.assertEqual((p["parent"], p["type"], p["subtype"]), ("scene_assets", "vehicle", ""))     # the parent follows the type; a subtype of another type is dropped
        p = reference.clean({"projects": [{"id": "rpaaaaaa01", "type": "vehicle", "subtype": "Custom", "custom_subtype": "Hover barge"}]})["projects"][0]
        self.assertEqual((p["subtype"], p["custom_subtype"]), ("Custom", "Hover barge"))
        self.assertIn("hover barge vehicle", p["prompt"])


class Prompt(unittest.TestCase):
    def test_the_prompt_follows_the_classification_until_the_person_writes_their_own(self):
        s = reference.clean({"projects": [{"id": "rpaaaaaa01", "name": "Misty", "type": "humanoid"}]})
        self.assertIn("A-pose", s["projects"][0]["prompt"]); self.assertIn("Misty", s["projects"][0]["prompt"])
        self.assertIn("No text", s["projects"][0]["prompt"])                                # lettering is the application's job, not the image model's
        s = reference.clean({"projects": [dict(s["projects"][0], type="vehicle")]}, s)
        self.assertIn("exterior of the complete vehicle", s["projects"][0]["prompt"])
        s = reference.clean({"projects": [dict(s["projects"][0], prompt="my own words", prompt_edited=True)]}, s)
        s = reference.clean({"projects": [dict(s["projects"][0], type="creature")]}, s)
        self.assertEqual(s["projects"][0]["prompt"], "my own words")

    def test_limits(self):
        p = reference.clean({"projects": [{"id": "rpaaaaaa01", "sources": ["a", "b", "b", "c", "d", "e"], "count": 99, "profile": 7, "aspect": "5:1"}]})["projects"][0]
        self.assertEqual((p["sources"], p["count"], p["profile"], p["aspect"]), (["a", "b", "c", "d"], 10, 1024, "16:9"))


class Sizes(unittest.TestCase):
    def test_sizes_keep_the_long_side_and_are_multiples_of_16(self):
        self.assertEqual(reference.size(1024, "16:9"), (1024, 576))
        self.assertEqual(reference.size(1024, "9:16"), (576, 1024))
        self.assertEqual(reference.size(2048, "1:1"), (2048, 2048))
        for pr in reference.PROFILES:
            for a, _, _ in reference.ASPECTS:
                self.assertTrue(all(v % 16 == 0 for v in reference.size(pr, a)))

    def test_a_size_the_provider_cannot_make_is_refused_before_anything_is_queued(self):
        self.assertEqual(reference.supported(2048, "16:9"), "")
        self.assertIn("upscale model", reference.supported(4096, "16:9"))
        p = project(profile=4096)
        with self.assertRaises(ValueError) as e:
            reference.plan(p, "rpaaaaaa01")
        self.assertIn("4096", str(e.exception))

    def test_plan(self):
        p = project(sources=["front.png", "side.png"], count=3, aspect="3:2")
        todo = reference.plan(p, "rpaaaaaa01")
        self.assertEqual((todo["count"], todo["width"], todo["height"], todo["sources"], todo["unused"]), (3, 1024, 688, ["front.png", "side.png"], []))
        self.assertIn("reference images", todo["prompt"])


class Retention(unittest.TestCase):
    def test_a_finished_sheet_is_pending_with_ten_days(self):
        p = project(); finish(p, "g1", 1000.0, ref_sources=["front.png"])
        state, gone = reference.sync(p, now=2000.0)
        a = state["artifacts"][0]
        self.assertEqual((a["state"], a["expires"], a["role"], a["prompt"], a["sources"], a["width"], gone), ("pending", 1000.0 + 10 * DAY, "sheet", "a sheet", ["front.png"], 1024, []))
        self.assertEqual(reference.view(p, now=1000.0 + DAY + 5)["artifacts"][0]["days_left"], 9)
        self.assertEqual(reference.view(p, now=1000.5)["artifacts"][0]["days_left"], 10)
        reference.sync(p, now=3000.0)                                      # looking again neither adds it twice nor moves its expiry
        self.assertEqual([(a["id"], a["expires"]) for a in p["reference"]["artifacts"]], [("g1", 1000.0 + 10 * DAY)])

    def test_an_unapproved_sheet_is_deleted_after_ten_days_with_its_prompt_and_library_entry(self):
        p = project(at="g1", selected="g1"); finish(p, "g1", 1000.0); finish(p, "g2", 1000.0 + 5 * DAY)
        reference.sync(p, now=1000.0 + 5 * DAY)
        _, gone = reference.sync(p, now=1000.0 + 10 * DAY + 1)
        self.assertEqual(gone, ["g1.png"])
        self.assertEqual([a["id"] for a in p["reference"]["artifacts"]], ["g2"])
        self.assertEqual([g["id"] for g in p["generated"]], ["g2"]); self.assertEqual([j["id"] for j in p["image_jobs"]], ["g2"])
        self.assertEqual((p["reference"]["projects"][0]["at"], p["reference"]["projects"][0]["selected"]), (None, None))

    def test_an_approved_sheet_does_not_expire(self):
        p = project(); finish(p, "g1", 1000.0); reference.sync(p, now=1001.0)
        self.assertEqual(reference.approve(p, ["g1"]), {"approved": ["g1"]})
        _, gone = reference.sync(p, now=1000.0 + 400 * DAY)
        self.assertEqual((gone, p["reference"]["artifacts"][0]["state"]), ([], "approved"))

    def test_a_picture_a_running_job_is_reading_is_not_cleaned_up_until_it_ends(self):
        p = project(); finish(p, "g1", 1000.0); reference.sync(p, now=1001.0)
        p["image_jobs"].append({"id": "j9", "kind": "ref", "slot": "rpaaaaaa01", "status": "running", "ref_sources": ["g1.png"]})
        self.assertEqual(reference.sync(p, now=1000.0 + 11 * DAY)[1], [])
        p["image_jobs"][-1]["status"] = "error"
        self.assertEqual(reference.sync(p, now=1000.0 + 11 * DAY)[1], ["g1.png"])               # no extra time was given: it goes as soon as it is safe

    def test_deny_deletes_now(self):
        p = project(); finish(p, "g1", 1000.0); reference.sync(p, now=1001.0)
        self.assertEqual(reference.delete(p, ["g1"]), ["g1.png"])
        self.assertEqual((p["reference"]["artifacts"], p["generated"], p["image_jobs"]), ([], [], []))

    def test_removing_a_reference_project_drops_its_artifacts_from_the_list(self):
        p = project(); finish(p, "g1", 1000.0); reference.sync(p, now=1001.0)
        self.assertEqual(reference.clean({"projects": []}, p["reference"])["artifacts"], [])


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.p = project()
        for g in ("sheet", "row", "view"):
            finish(self.p, g, 1000.0)
        reference.sync(self.p, now=1001.0)
        by = {a["id"]: a for a in self.p["reference"]["artifacts"]}
        by["sheet"]["requires"] = [{"id": "row", "reason": "The row this sheet was assembled from."}]
        by["row"]["requires"] = [{"id": "view", "reason": "The front view in that row."}]
        self.by = by

    def test_pending_dependencies_are_listed_with_reasons_and_nothing_changes_until_confirmed(self):
        out = reference.approve(self.p, ["sheet"])
        self.assertEqual([(n["id"], n["reason"]) for n in out["needs"]], [("row", "The row this sheet was assembled from."), ("view", "The front view in that row.")])   # nested ones too
        self.assertEqual({a["state"] for a in self.by.values()}, {"pending"})
        self.assertEqual(reference.approve(self.p, ["sheet"], confirmed=True), {"approved": ["row", "sheet", "view"]})
        self.assertEqual({a["state"] for a in self.by.values()}, {"approved"})

    def test_an_already_approved_dependency_is_not_asked_about_again(self):
        reference.approve(self.p, ["view"])
        self.assertEqual([n["id"] for n in reference.approve(self.p, ["sheet"])["needs"]], ["row"])

    def test_a_missing_dependency_blocks_approval(self):
        self.p["reference"]["artifacts"] = [a for a in self.p["reference"]["artifacts"] if a["id"] != "view"]
        with self.assertRaises(ValueError):
            reference.approve(self.p, ["sheet"], confirmed=True)
        self.assertEqual(self.by["sheet"]["state"], "pending")

    def test_what_an_approved_picture_needs_cannot_be_deleted_or_expire(self):
        reference.approve(self.p, ["sheet"], confirmed=True)
        self.assertEqual(reference.protected(self.p["reference"], ["row", "view"]), ["row", "view"])
        self.assertEqual(reference.delete(self.p, ["row"]), [])
        self.assertEqual(len(self.p["reference"]["artifacts"]), 3)


class Regions(unittest.TestCase):
    def test_regions_are_stored_in_whole_pixels_with_known_labels(self):
        ex = {"source": "sheet.png", "regions": [{"x": 10.4, "y": 5, "w": 200, "h": 300.6, "direction": "front", "section": "base", "component": "body"},
                                                  {"x": 0, "y": 0, "w": 3, "h": 3}, {"x": 1, "y": 1, "w": 50, "h": 50, "direction": "sideways", "section": "nowhere"}]}
        r = reference.clean({"projects": [{"id": "rpaaaaaa01", "extraction": ex}]})["projects"][0]["extraction"]["regions"]
        self.assertEqual([(x["x"], x["w"], x["h"], x["direction"], x["section"]) for x in r], [(10, 200, 301, "front", "base"), (1, 50, 50, "", "base")])


class Files(unittest.TestCase):
    def test_a_deleted_pictures_file_is_removed_only_when_the_folder_is_known_and_nothing_else_uses_it(self):
        import os, tempfile
        from tests import test_core            # sets DATA_DIR before the app is imported
        import app
        with tempfile.TemporaryDirectory() as folder:
            for name in ("gone.png", "shared.png"):
                open(os.path.join(folder, name), "wb").close()
            p = {"actors": [{"views": [{"image": "shared.png"}]}]}
            was, app.COMFY_INPUT_DIR = app.COMFY_INPUT_DIR, ""
            try:
                self.assertEqual(app.reference_forget(p, ["gone.png"]), 0)                    # folder not configured: files are left alone
                app.COMFY_INPUT_DIR = folder
                self.assertEqual(app.reference_forget(p, ["gone.png", "shared.png", "../outside.png", "missing.png"]), 1)
                self.assertEqual(sorted(os.listdir(folder)), ["shared.png"])                 # an actor still uses that one
            finally:
                app.COMFY_INPUT_DIR = was


if __name__ == "__main__":
    unittest.main()
