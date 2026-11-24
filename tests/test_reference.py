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


def advanced(**row):
    r = dict({"id": "rowaaaa001", "label": "Complete character", "role": "Complete asset"}, **row)
    p = project(mode="advanced", rows=[r, {"id": "rowaaaa002", "section": "detail", "label": "Pirate hat", "role": "Headwear"}])
    return p, p["reference"]["projects"][0]


def view(p, gid, direction, created, row="rowaaaa001"):
    finish(p, gid, created, row=row, direction=direction, component="Complete asset", type="humanoid")


class Rows(unittest.TestCase):
    def test_a_row_starts_with_four_views_and_a_prompt_that_fits_what_it_is(self):
        p, ref = advanced()
        whole, hat = ref["rows"]
        self.assertEqual([d for d in reference.DIRECTIONS if whole["slots"][d]["enabled"]], ["front", "left", "right", "rear"])
        self.assertIn("neutral A-pose", whole["prompt"]); self.assertIn("Misty", whole["prompt"])
        self.assertIn("Pirate hat of Misty, shown on its own", hat["prompt"]); self.assertNotIn("A-pose", hat["prompt"])
        self.assertEqual((whole["aspect"], hat["section"], hat["type"]), ("2:3", "detail", ""))            # a row inherits the project's classification

    def test_a_row_can_have_its_own_classification(self):
        p, ref = advanced(type="creature", subtype="Quadruped", label="Rue", role="Complete asset")
        self.assertEqual((ref["rows"][0]["type"], ref["rows"][0]["subtype"], ref["rows"][0]["aspect"]), ("creature", "Quadruped", "3:2"))
        view(p, "g1", "front", 1000.0); p["image_jobs"][-1].update(type="creature", subtype="Quadruped"); reference.sync(p, now=1001.0)
        a = p["reference"]["artifacts"][0]
        self.assertEqual((a["role"], a["row"], a["direction"], a["type"], a["subtype"], a["component"]), ("view", "rowaaaa001", "front", "creature", "Quadruped", "Complete asset"))

    def test_generate_row_targets_enabled_unlocked_views_only(self):
        p, ref = advanced(count=2)
        row = ref["rows"][0]
        view(p, "g1", "front", 1000.0); view(p, "g2", "left", 1000.0); reference.sync(p, now=1001.0)
        ref = p["reference"]["projects"][0]; row = ref["rows"][0]
        row["slots"]["front"]["locked"] = True
        t = reference.targets(p["reference"], row, "row")
        self.assertEqual(t, {"make": ["left", "right", "rear"], "locked": ["front"], "disabled": ["top", "bottom"]})
        self.assertEqual(reference.targets(p["reference"], row, "missing")["make"], ["right", "rear"])     # populated views are left alone
        self.assertEqual(reference.targets(p["reference"], row, "front")["make"], [])
        todo = reference.plan_views(p, "rpaaaaaa01", "rowaaaa001", "missing")
        self.assertEqual([(v["direction"], v["count"], v["width"], v["height"]) for v in todo], [("right", 2, 688, 1024), ("rear", 2, 688, 1024)])
        self.assertIn("Right side view", todo[0]["prompt"])
        self.assertEqual(todo[0]["sources"], ["g1.png"])                                                   # the locked view only: an unlocked view may be the one being replaced
        row["locked"] = True
        with self.assertRaises(ValueError):
            reference.plan_views(p, "rpaaaaaa01", "rowaaaa001", "row")

    def test_new_candidates_do_not_replace_the_chosen_picture(self):
        p, ref = advanced()
        view(p, "g1", "front", 1000.0); reference.sync(p, now=1001.0)
        row = p["reference"]["projects"][0]["rows"][0]
        self.assertEqual(reference.chosen(p["reference"], row, "front")["id"], "g1")
        view(p, "g2", "front", 2000.0); reference.sync(p, now=2001.0)
        row = p["reference"]["projects"][0]["rows"][0]
        self.assertEqual(reference.chosen(p["reference"], row, "front")["id"], "g1")
        row["slots"]["front"]["selected"] = "g2"
        self.assertEqual(reference.chosen(p["reference"], row, "front")["id"], "g2")
        self.assertIsNone(reference.chosen(p["reference"], row, "rear"))

    def test_only_as_many_pictures_as_the_model_takes_are_sent_and_the_rest_are_named(self):
        p, ref = advanced(sources=[{"image": f"s{n}.png"} for n in range(1, 7)])
        self.assertEqual(len(ref["rows"][0]["sources"]), 6)
        c = reference.conditioning(p["reference"], ref, ref["rows"][0], "front")
        self.assertEqual([x["image"] for x in c["used"]], ["s1.png", "s2.png", "s3.png", "s4.png"])
        self.assertEqual([x["what"] for x in c["unused"]], ["source 5", "source 6"])

    def test_a_row_can_use_another_rows_chosen_view_without_copying_it(self):
        p, ref = advanced()
        view(p, "g1", "front", 1000.0); reference.sync(p, now=1001.0)
        state = reference.clean({"projects": [dict(p["reference"]["projects"][0], rows=[p["reference"]["projects"][0]["rows"][0],
                                 dict(p["reference"]["projects"][0]["rows"][1], sources=[{"row": "rowaaaa001", "direction": "front"}, {"row": "rowaaaa001", "direction": "rear"}, {"row": "nowhere", "direction": "front"}])])]}, p["reference"])
        p["reference"] = state; ref = state["projects"][0]; hat = ref["rows"][1]
        self.assertEqual(hat["sources"], [{"row": "rowaaaa001", "direction": "front"}, {"row": "rowaaaa001", "direction": "rear"}])
        c = reference.conditioning(state, ref, hat, "front")
        self.assertEqual([x["image"] for x in c["used"]], ["g1.png"])                                      # looked up, not stored
        self.assertEqual(len(c["unavailable"]), 1); self.assertIn("rear view of Complete character", c["unavailable"][0])
        self.assertEqual(len([a for a in state["artifacts"]]), 1)

    def test_rows_cannot_inherit_from_each_other_in_a_circle(self):
        p, ref = advanced()
        rows = [dict(ref["rows"][0], sources=[{"row": "rowaaaa002", "direction": "front"}]), dict(ref["rows"][1], sources=[{"row": "rowaaaa001", "direction": "front"}])]
        out = reference.clean({"projects": [dict(ref, rows=rows)]}, p["reference"])["projects"][0]["rows"]
        self.assertEqual(sum(len(r["sources"]) for r in out), 1)

    def test_an_uploaded_view_fills_the_slot_and_a_locked_one_refuses(self):
        p, ref = advanced()
        ids = iter(["u1", "u2", "u3"])
        a = reference.place(p, "rpaaaaaa01", "rowaaaa001", "rear", "mine.png", lambda: next(ids), now=500.0)
        row = p["reference"]["projects"][0]["rows"][0]
        self.assertEqual((a["role"], a["state"], a["origin"], row["slots"]["rear"]["selected"]), ("view", "approved", "uploaded", "u1"))
        row["slots"]["rear"]["locked"] = True
        with self.assertRaises(ValueError):
            reference.place(p, "rpaaaaaa01", "rowaaaa001", "rear", "other.png", lambda: next(ids))
        whole = reference.place(p, "rpaaaaaa01", "rowaaaa001", None, "strip.png", lambda: next(ids), now=600.0)
        self.assertEqual((whole["role"], row["selected"], len(reference.candidates(p["reference"], "rowaaaa001", "rear"))), ("row", "u2", 1))   # a complete row is kept whole, not split

    def test_placing_a_pending_picture_keeps_it_pending_and_shares_the_file(self):
        p, ref = advanced()
        view(p, "g1", "front", 1000.0); reference.sync(p, now=1001.0)
        a = reference.place(p, "rpaaaaaa01", "rowaaaa002", "front", "g1.png", lambda: "u1", now=5000.0)
        self.assertEqual((a["state"], a["expires"]), ("pending", 1000.0 + 10 * DAY))                       # no approval, no extra time
        self.assertEqual(reference.delete(p, ["g1"]), [])                                                  # the other record still needs the file
        self.assertEqual(reference.delete(p, ["u1"]), ["g1.png"])

    def test_a_locked_views_picture_cannot_be_denied_until_it_is_unlocked(self):
        from tests import test_core
        import app
        p, ref = advanced()
        import time
        t = time.time()                                                                                    # real time: the server's own clock decides expiry here
        view(p, "g1", "front", t - 3); view(p, "g2", "front", t - 2); view(p, "g3", "left", t - 1); reference.sync(p)
        row = p["reference"]["projects"][0]["rows"][0]; row["slots"]["front"]["locked"] = True
        self.assertEqual(reference.locked_pictures(p["reference"]), {"g1"})                                # the one in use, not the slot's other candidate
        p.update(app.empty_project("Locks"), generated=p["generated"], image_jobs=p["image_jobs"], reference=p["reference"]); pid = app.save_project(p)["id"]
        with self.assertRaises(ValueError) as e:
            app.reference_decide(pid, ["g1"], "deny")
        self.assertIn("locked view", str(e.exception))
        self.assertEqual(app.reference_decide(pid, ["g2", "g3"], "deny")["denied"], 2)                     # other candidates and unlocked views can go
        self.assertEqual(app.reference_decide(pid, ["g1"], "deny", force=True)["denied"], 1)              # removing the whole row says so itself

    def test_a_locked_view_that_loses_its_only_picture_to_expiry_is_unlocked(self):
        p, ref = advanced()
        view(p, "g1", "front", 1000.0); reference.sync(p, now=1001.0)
        row = p["reference"]["projects"][0]["rows"][0]; row["slots"]["front"].update(locked=True, selected="g1")
        reference.delete(p, ["g1"])
        self.assertEqual((row["slots"]["front"]["locked"], row["slots"]["front"]["selected"]), (False, None))


class PanelsAndAssembly(unittest.TestCase):
    def test_panels_start_with_label_and_sub_label_and_keep_their_text_when_switched_off(self):
        p, ref = advanced()
        self.assertEqual((ref["panel"]["label"], ref["panel"]["sub_label"], ref["panel"]["include"]), ("", "", False))       # empty: drawn as the name and type
        hat = ref["rows"][1]["panel"]
        self.assertEqual((hat["label"], hat["sub_label"], [f["name"] for f in hat["fields"]]), ("", "", ["Build", "Materials", "Colours", "Style", "Notes"]))
        hat = dict(hat, include=True, label="Pirate Hat", dims={"height": 25.4, "width": "x", "depth": -3}, fields=[{"name": "Material", "value": "Felt"}, {"name": "Notes", "value": ""}])
        s = reference.clean({"projects": [dict(ref, rows=[ref["rows"][0], dict(ref["rows"][1], panel=hat)])]}, p["reference"])
        kept = s["projects"][0]["rows"][1]["panel"]
        self.assertEqual((kept["dims"], kept["fields"][0]), ({"height": 25.4, "width": None, "depth": None}, {"name": "Material", "value": "Felt"}))
        off = reference.clean({"projects": [dict(s["projects"][0], rows=[s["projects"][0]["rows"][0], dict(s["projects"][0]["rows"][1], panel=dict(kept, include=False))])]}, s)["projects"][0]["rows"][1]["panel"]
        self.assertEqual((off["include"], off["label"], off["fields"][0]["value"], off["dims"]["height"]), (False, "Pirate Hat", "Felt", 25.4))

    def test_layout_settings_are_limited_to_what_exists(self):
        p, ref = advanced()
        self.assertEqual(ref["layout"], reference.LAYOUT_DEFAULT)
        lay = reference.clean({"projects": [dict(ref, layout={"orientation": "diagonal", "resolution": 999, "colour": "red", "spacing": 9999, "background": "transparent", "units": "imperial", "labels": False})]}, p["reference"])["projects"][0]["layout"]
        self.assertEqual((lay["orientation"], lay["resolution"], lay["colour"], lay["spacing"], lay["background"], lay["units"], lay["labels"]), ("landscape", 2048, "#e6e6e6", 200, "transparent", "imperial", False))
        row = reference.clean({"projects": [dict(ref, rows=[dict(ref["rows"][0], width="half", width_pct=5, assemble="whole")])]}, p["reference"])["projects"][0]["rows"][0]
        self.assertEqual((row["width"], row["width_pct"], row["assemble"]), ("half", 20, "whole"))

    def test_an_assembled_sheet_is_pending_and_needs_the_pictures_on_it(self):
        p, ref = advanced()
        view(p, "g1", "front", 1000.0); view(p, "g2", "left", 1000.0); reference.sync(p, now=1001.0)
        with self.assertRaises(ValueError):
            reference.assembled(p, "rpaaaaaa01", "sheet.png", 2048, 900, ["nothing"], lambda: "s1")
        a = reference.assembled(p, "rpaaaaaa01", "sheet.png", 2048, 900, ["g1", "g2", "g1"], lambda: "s1", now=2000.0)
        self.assertEqual((a["role"], a["origin"], a["state"], a["expires"], [r["id"] for r in a["requires"]]), ("sheet", "assembled", "pending", 2000.0 + 10 * DAY, ["g1", "g2"]))
        self.assertEqual(a["requires"][0]["reason"], "The front view of the row \u201cComplete character\u201d, shown on this sheet.")
        self.assertEqual([n["id"] for n in reference.approve(p, ["s1"])["needs"]], ["g1", "g2"])          # the dependency question now has something to ask
        self.assertEqual(reference.approve(p, ["s1"], confirmed=True), {"approved": ["g1", "g2", "s1"]})
        self.assertEqual(reference.delete(p, ["g1"]), [])                                                  # a view an approved sheet shows is kept
        self.assertEqual(len([x for x in p["reference"]["artifacts"] if x["role"] == "view"]), 2)         # assembling changed no view


class ChecksExportAndHandOver(unittest.TestCase):
    def setUp(self):
        self.p, _ = advanced()
        view(self.p, "g1", "front", 1000.0); view(self.p, "g2", "left", 1000.0); view(self.p, "g3", "front", 1000.0, row="rowaaaa002")
        finish(self.p, "s1", 1000.0)
        reference.sync(self.p, now=1001.0)
        self.ref = self.p["reference"]["projects"][0]

    def test_plain_notes_about_a_row_never_block_anything(self):
        by = {a["id"]: a for a in self.p["reference"]["artifacts"]}
        by["g2"].update(width=1024, height=1024)
        got = reference.notes(self.p["reference"], self.ref, self.ref["rows"][0])
        self.assertEqual([n["aspect"] for n in got], ["completeness", "projection"])
        self.assertIn("right, rear", got[0]["description"])
        self.assertEqual(reference.view(self.p, now=1002.0)["state"]["projects"][0]["rows"][0]["notes"], got)
        self.assertNotIn("notes", self.p["reference"]["projects"][0]["rows"][0])                           # for the page only, not stored
        self.assertEqual(len(reference.plan_views(self.p, "rpaaaaaa01", "rowaaaa001", "missing")), 2)      # generation goes ahead regardless

    def test_a_check_needs_two_views_and_its_findings_are_stored_as_advice(self):
        with self.assertRaises(ValueError):
            reference.to_check(self.p, "rpaaaaaa01", "rowaaaa002")
        _, _, views = reference.to_check(self.p, "rpaaaaaa01", "rowaaaa001")
        self.assertEqual([d for d, _ in views], ["front", "left"])
        v = reference.checked(self.p, "rpaaaaaa01", "rowaaaa001", [{"views": ["front", "left", "sideways"], "aspect": "components", "description": "The left view has no sword.", "certain": True},
                                                                    {"views": ["left"], "aspect": "nonsense", "description": "  ", "certain": True}, "junk"], "qwen", now=5.0)
        self.assertEqual(v["findings"], [{"views": ["front", "left"], "aspect": "components", "description": "The left view has no sword.", "certain": True}])
        self.assertEqual(v["pictures"], {"front": "g1", "left": "g2"})
        shown = reference.view(self.p, now=1002.0)["state"]["projects"][0]["rows"][0]["validation"]
        self.assertFalse(shown["stale"])
        view(self.p, "g9", "left", 2000.0); reference.sync(self.p, now=2001.0)
        self.p["reference"]["projects"][0]["rows"][0]["slots"]["left"]["selected"] = "g9"
        self.assertTrue(reference.view(self.p, now=2002.0)["state"]["projects"][0]["rows"][0]["validation"]["stale"])   # it was about other pictures
        kept = reference.clean({"projects": [dict(self.p["reference"]["projects"][0], rows=[dict(r, validation={"findings": ["forged"]}) for r in self.p["reference"]["projects"][0]["rows"]])]}, self.p["reference"])
        self.assertEqual(kept["projects"][0]["rows"][0]["validation"]["findings"][0]["description"], "The left view has no sword.")   # the page cannot write findings

    def test_sheet_only_needs_a_selected_sheet(self):
        with self.assertRaises(ValueError):
            reference.export_plan(self.p, "rpaaaaaa01", "sheet")
        self.ref["selected"] = "s1"
        out = reference.export_plan(self.p, "rpaaaaaa01", "sheet", now=1000.0 + DAY)
        self.assertEqual((out["zip"], out["name"], [f["image"] for f in out["files"]], out["pending"][0]["hours_left"]), (False, "Misty_Reference_Sheet.png", ["s1.png"], 9 * 24))

    def test_individual_views_are_only_ones_that_exist_and_exporting_changes_nothing(self):
        before = repr(self.p["reference"])
        out = reference.export_plan(self.p, "rpaaaaaa01", "views", now=2000.0)
        self.assertEqual([f["path"] for f in out["files"]], ["Views/Complete_character/Front.png", "Views/Complete_character/Left.png", "Views/Pirate_hat/Front.png"])
        self.assertEqual(len(out["pending"]), 3); self.assertEqual(repr(self.p["reference"]), before)
        entry = out["manifest"]["files"][2]
        self.assertEqual((entry["direction"], entry["component"], entry["approval"], entry["classification"]["type"]), ("front", "Headwear", "pending", "humanoid"))
        empty, _ = advanced(); finish(empty, "s1", 1000.0); reference.sync(empty, now=1001.0)
        with self.assertRaises(ValueError) as e:                                                         # a sheet alone is not split into views
            reference.export_plan(empty, "rpaaaaaa01", "views")
        self.assertIn("not split automatically", str(e.exception))

    def test_the_complete_package_has_the_sheet_the_views_and_a_manifest(self):
        self.ref["selected"] = "s1"; reference.approve(self.p, ["g1"])
        out = reference.export_plan(self.p, "rpaaaaaa01", "package", now=2000.0)
        self.assertEqual(len(out["files"]), 4); self.assertEqual(out["name"], "Misty_Complete_Reference_Package.zip")
        m = out["manifest"]
        self.assertEqual((m["reference"]["type"], m["profile"], len(m["rows"]), m["rows"][1]["component_role"], m["rows"][1]["classification"]["inherited"]), ("humanoid", "Complete Reference Package", 2, "Headwear", True))
        self.assertEqual(sorted(x["id"] for x in out["pending"]), ["g2", "g3", "s1"])                      # the approved view is not in the warning
        self.assertEqual(m["files"][1]["expires"], None)

    def test_component_sheets_are_one_per_row_and_carry_the_panel_setting(self):
        self.ref["rows"][1]["panel"]["include"] = True
        out = reference.export_plan(self.p, "rpaaaaaa01", "components", now=2000.0)
        self.assertEqual([(c["path"], c["pictures"]) for c in out["components"]], [("Complete_asset/Complete_character_Reference.png", ["g1", "g2"]), ("Headwear/Pirate_hat_Reference.png", ["g3"])])
        self.assertEqual([f["panel_included"] for f in out["manifest"]["files"]], [False, True]); self.assertEqual(out["files"], [])

    def test_sending_to_3d_records_ids_only_and_follows_the_pictures(self):
        self.ref["selected"] = "s1"
        h = reference.send_to_3d(self.p, "rpaaaaaa01", lambda: "h1", now=3000.0)
        self.assertEqual([(i["artifact"], i["role"], i["component"]) for i in h["items"]], [("s1", "sheet", ""), ("g1", "front", "Complete asset"), ("g2", "left", "Complete asset"), ("g3", "front", "Headwear")])
        self.assertEqual({a["state"] for a in self.p["reference"]["artifacts"]}, {"pending"})             # nothing was approved
        self.assertEqual([a["expires"] for a in self.p["reference"]["artifacts"]][0], 1000.0 + 10 * DAY)   # or given more time
        reference.send_to_3d(self.p, "rpaaaaaa01", lambda: "h2", now=4000.0)
        self.assertEqual(len(self.p["reference"]["handover"]), 1)                                          # sending again updates the same one
        reference.delete(self.p, ["g2"])
        shown = reference.handed_over(self.p["reference"])[0]
        self.assertEqual([(i["state"], i["image"]) for i in shown["items"]][2], ("gone", None))
        self.assertEqual((shown["type_label"], shown["parent_label"], shown["name"]), ("Humanoid", "Actors", "Misty"))
        kept = reference.clean({"projects": self.p["reference"]["projects"]}, self.p["reference"])
        self.assertEqual(len(kept["handover"]), 1)
        self.assertEqual(reference.clean({"projects": []}, self.p["reference"])["handover"], [])


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
