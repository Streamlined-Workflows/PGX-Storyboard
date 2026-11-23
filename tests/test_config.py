"""Project schema 2: the configuration block. Old projects must behave as before; nothing a person set is ever lost."""
import json
import os
import unittest

from tests import test_core            # sets DATA_DIR to the shared temporary folder before the app is imported
import app
import assist
import config


class ConfigTests(unittest.TestCase):
    def test_defaults_reproduce_the_old_behaviour(self):
        c = config.clean(None)
        self.assertEqual(c["identity"]["video_type"], "music_video")
        self.assertEqual(config.story_guidance(c), "")                      # nothing added to the story request
        self.assertEqual(config.shot_guidance(c), "")                       # nothing added to the shot request
        self.assertEqual(set(c["models"].values()), {"auto"})
        self.assertEqual(json.loads(json.dumps(c)), c)                      # plain data, safe to store

    def test_bad_values_keep_what_was_stored(self):
        stored = config.clean({"identity": {"rating": "R", "music": {"subtype": "dance"}}, "production": {"target_fps": 30}})
        after = config.clean({"identity": {"rating": "ZZ", "video_type": 7, "music": {"subtype": "<script>"}},
                              "production": {"target_fps": 61, "aspect": None, "continuity": {"costume": "yes"}},
                              "workflow": "nonsense", "models": {"image": "no-provider"}, "extra": 1}, stored)
        self.assertEqual((after["identity"]["rating"], after["identity"]["music"]["subtype"], after["production"]["target_fps"]), ("R", "dance", 30))
        self.assertEqual(after["models"]["image"], "auto")
        self.assertNotIn("extra", after)
        self.assertTrue(after["production"]["continuity"]["costume"])

    def test_changing_video_type_keeps_the_other_types_settings(self):
        c = config.clean({"identity": {"video_type": "music_video", "music": {"subtype": "lyric"}, "story": {"subtype": "in_between", "in_between_purpose": "time_lapse"},
                                       "commercial": {"type": "psa", "audience": "pilots", "runtime": 30}}})
        c = config.clean({"identity": {"video_type": "story"}}, c)
        c = config.clean({"identity": {"video_type": "commercial"}}, c)
        i = c["identity"]
        self.assertEqual((i["music"]["subtype"], i["story"]["in_between_purpose"], i["commercial"]["audience"], i["commercial"]["runtime"]),
                         ("lyric", "time_lapse", "pilots", 30.0))
        self.assertIsNone(config.clean({"identity": {"commercial": {"runtime": ""}}}, c)["identity"]["commercial"]["runtime"])

    def test_every_choice_in_the_task_is_offered(self):
        o = config.options()
        count = lambda key: len(o[key])
        self.assertEqual([count(k) for k in ("ratings", "video_types", "story_types", "story_subtypes", "in_between", "music_types", "music_subtypes",
                                             "commercial_types", "aspects", "resolutions", "fps", "platforms", "directions", "details", "environments",
                                             "continuity", "workflow", "roles")], [5, 3, 3, 4, 3, 2, 7, 6, 5, 4, 3, 4, 5, 3, 3, 5, 8, 9])
        for key in ("music_subtypes", "details"):                           # every choice that is used has its guidance written
            table = config.MUSIC_GUIDANCE if key == "music_subtypes" else config.DETAIL_GUIDANCE
            self.assertEqual({x["key"] for x in o[key]}, set(table))

    def test_guidance_only_applies_where_it_should(self):
        dance = config.clean({"identity": {"music": {"subtype": "dance"}}, "production": {"storyboard_detail": "cinematic"}})
        self.assertIn("dance video", config.story_guidance(dance))
        self.assertIn("three or four sentences", config.shot_guidance(dance))
        self.assertEqual(config.story_guidance(config.clean({"identity": {"video_type": "story"}}, dance)), "")   # a music setting does not leak into a story project

    def test_guidance_reaches_the_language_model(self):
        seen, real = {}, assist.chat
        assist.chat = lambda system, user, schema, **kw: seen.update(user=user) or {"title": "T", "logline": "L", "style": "S", "beats": ["a"], "first_frame": {}, "segments": []}
        try:
            segs = [dict(test_core.SEG)]
            assist.write_story({"tempo": 120, "duration": 6}, [], segs, guidance="This is a dance video.")
            self.assertIn("Kind of video: This is a dance video.", seen["user"])
            assist.write_shots({"title": "t"}, {"tempo": 120}, [], segs, [], guidance="Keep every description short.")
            self.assertIn("Level of detail wanted: Keep every description short.", seen["user"])
            assist.write_story({"tempo": 120, "duration": 6}, [], segs)
            self.assertNotIn("Kind of video", seen["user"])
        finally:
            assist.chat = real


class SchemaTests(unittest.TestCase):
    def write(self, project):
        os.makedirs(app.PROJECTS_DIR, exist_ok=True)
        with open(app.project_path(project["id"]), "w") as f:
            json.dump(project, f)
        return project["id"]

    def test_a_version_1_project_opens_as_version_2_without_being_rewritten(self):
        pid = self.write({"id": app.new_id(), "name": "Before config", "segments": [dict(test_core.SEG)], "settings": {"width": 832, "height": 480}})
        before = os.path.getmtime(app.project_path(pid))
        p = app.load_project(pid)
        self.assertEqual((p["schema"], p["config"]["identity"]["video_type"], p["settings"]), (2, "music_video", {"width": 832, "height": 480}))
        self.assertEqual((p["intake"]["kind"], p["collection_id"]), ("song", None))
        self.assertEqual(os.path.getmtime(app.project_path(pid)), before)                    # opening alone changes nothing on disk
        with open(app.project_path(pid)) as f:
            self.assertNotIn("config", json.load(f))

    def test_a_project_from_a_newer_version_keeps_its_number_and_unknown_fields(self):
        pid = self.write({"id": app.new_id(), "name": "From later", "schema": 5, "segments": [], "scenes": [{"id": "x"}],
                          "config": {"identity": {"rating": "R"}, "future_block": {"a": 1}}})
        app.save_project(app.load_project(pid))
        p = app.load_project(pid)
        self.assertEqual((p["schema"], p["scenes"], p["config"]["identity"]["rating"]), (5, [{"id": "x"}], "R"))

    def test_the_browser_saves_config_and_only_valid_choices_land(self):
        p = app.save_project(app.normalize(app.empty_project("Cfg")))
        app.merge_project(p["id"], {"segments": [], "config": {"identity": {"rating": "E", "video_type": "story", "story": {"subtype": "in_between"}},
                                                                "workflow": {"auto_progress": True}, "production": {"export_resolution": "8k"}}})
        c = app.load_project(p["id"])["config"]
        self.assertEqual((c["identity"]["rating"], c["identity"]["video_type"], c["identity"]["story"]["subtype"], c["workflow"]["auto_progress"], c["production"]["export_resolution"]),
                         ("E", "story", "in_between", True, "1080p"))
        app.merge_project(p["id"], {"segments": []})                                         # a save without config leaves it alone
        self.assertEqual(app.load_project(p["id"])["config"], c)

    def test_new_projects_start_from_saved_defaults_and_existing_ones_do_not_change(self):
        old = app.save_project(app.normalize(app.empty_project("Existing")))
        try:
            config.save_defaults({"identity": {"rating": "E"}, "production": {"target_fps": 30, "storyboard_detail": "cinematic"}})
            new = app.empty_project("New")
            self.assertEqual((new["config"]["identity"]["rating"], new["config"]["production"]["target_fps"]), ("E", 30))
            self.assertEqual(app.load_project(old["id"])["config"]["identity"]["rating"], "PG-13")
            self.assertTrue(config.options()["saved_defaults"])
        finally:
            os.remove(os.path.join(test_core._TMP.name, "defaults.json"))

    def test_models_in_use_names_every_role_and_admits_what_is_missing(self):
        using = app.models_in_use()
        self.assertEqual(set(using), {k for k, _ in config.ROLES})
        self.assertFalse(using["tts"]["ready"])
        self.assertFalse(using["begin_end_video"]["ready"])
        self.assertTrue(using["image"]["ready"])


if __name__ == "__main__":
    unittest.main()
