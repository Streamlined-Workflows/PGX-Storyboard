"""Asset Generator: what is stored, what each box sends to the image model, and the depth workflow's rules."""
import unittest

from tests import test_core            # sets DATA_DIR before the app is imported
import app
import generator


class GeneratorTests(test_core.Base if hasattr(test_core, "Base") else unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.sent, self.graphs, self.real = [], [], app.queue_still

        def fake(project, prompt, refs, stem, graph=None, **f):
            job = {"id": f"j{len(self.sent)}", "prompt_id": "p", "status": "queued", "created": 0, **f}
            project["image_jobs"].append(job); self.sent.append((f.get("slot"), prompt, list(refs)))
            self.graphs.append(graph(7, "pre") if graph else None)
            return job
        app.queue_still = fake
        self.pid = app.save_project(app.empty_project("Gen"))["id"]

    def tearDown(self):
        app.queue_still = self.real
        super().tearDown()

    def finish(self, slot, *images):
        """Stand in for ComfyUI finishing pictures for a box."""
        with app.LOCK:
            p = app.load_project(self.pid)
            p["image_jobs"] = [j for j in p["image_jobs"] if j.get("slot") != slot]
            for n, image in enumerate(images):
                p["generated"].append({"id": image, "image": image, "kind": "gen", "slot": slot, "created": 100 + len(p["generated"]) + n})
            app.save_project(p, touch=False)

    def test_a_new_project_starts_empty_with_the_composed_prompt_ready(self):
        v = app.generator_view(self.pid)
        self.assertEqual(sorted(v["boxes"]), ["background", "composed", "foreground", "image", "middle"])
        self.assertEqual(v["state"]["image"], {"prompt": "", "refs": [], "at": None, "marks": [], "count": 1})
        self.assertEqual(v["state"]["approved"], [])
        self.assertEqual(v["prompt_limit"], {"model": "FLUX.2 [dev]", "tokens": 512, "characters": 2000})      # what the count beside each prompt is measured against
        self.assertEqual(v["state"]["composed"]["prompt"], generator.COMPOSE_PROMPT)
        self.assertIn("image 1 as the background", v["state"]["composed"]["prompt"])
        self.assertEqual(v["state"]["composed"]["applied"], {"background": None, "middle": None, "foreground": None})

    def test_image_generation_sends_the_prompt_as_typed_with_up_to_four_references_once_per_generation(self):
        state = {"image": {"prompt": "  A ship in a debris field.  ", "count": 3}}
        v = app.generator_run(self.pid, "image", state)
        self.assertEqual(self.sent, [("image", "A ship in a debris field.", [])] * 3)          # no references: nothing is added to the prompt
        self.sent.clear()
        app.generator_run(self.pid, "image", {"image": {"refs": ["a.png", "b.png", "c.png", "d.png", "e.png"], "count": 1}})
        self.assertEqual(self.sent[0][2], ["a.png", "b.png", "c.png", "d.png"])
        self.assertEqual([j["status"] for j in v["boxes"]["image"]["jobs"]], ["queued"] * 3)
        self.assertEqual(self.graphs, [None] * 4)
        self.finish("image", "one.png", "two.png")
        self.assertEqual([r["image"] for r in app.generator_view(self.pid)["boxes"]["image"]["results"]], ["one.png", "two.png"])

    def test_limits(self):
        v = app.generator_save(self.pid, {"image": {"prompt": "x" * 5000, "count": 99, "refs": ["a"] * 9}, "background": {"count": 0}, "middle": {"count": "seven"},
                                          "composed": {"refs": ["x.png", "y.png"]}})
        self.assertEqual((len(v["state"]["image"]["prompt"]), v["state"]["image"]["count"], len(v["state"]["image"]["refs"])), (3000, 10, 4))
        self.assertEqual((v["state"]["background"]["count"], v["state"]["middle"]["count"]), (1, 1))
        self.assertEqual(v["state"]["composed"]["refs"], [{"image": "x.png", "use": "keep exactly", "slot": 4, "text": ""}])      # one free slot, and it is always reference 4
        for bad in ("nope", None):
            with self.assertRaises(ValueError):
                app.generator_run(self.pid, bad)
        with self.assertRaises(ValueError) as e:
            app.generator_run(self.pid, "background", {"background": {"prompt": "   "}})
        self.assertIn("Write a prompt", str(e.exception))
        self.assertEqual(self.sent, [])

    def test_depth_generation_composes_the_three_applied_pictures_in_a_fixed_order(self):
        for layer, prompt in (("background", "Ship interior."), ("middle", "Misty floating."), ("foreground", "Dust and a canister.")):
            app.generator_run(self.pid, layer, {layer: {"prompt": prompt, "refs": [{"image": layer + "-ref.png", "use": "keep exactly"}], "count": 2}})
            self.finish(layer, layer + "1.png", layer + "2.png")
        self.assertEqual([(s, r) for s, _, r in self.sent][::2], [("background", ["background-ref.png"]), ("middle", ["middle-ref.png"]), ("foreground", ["foreground-ref.png"])])
        with self.assertRaises(ValueError) as e:
            app.generator_run(self.pid, "composed")
        self.assertIn("background, middle ground, foreground", str(e.exception))      # nothing applied yet, and it says which
        app.generator_apply(self.pid, "foreground", "foreground2.png")
        app.generator_apply(self.pid, "background", "background1.png")
        with self.assertRaises(ValueError) as e:
            app.generator_run(self.pid, "composed")
        self.assertIn("middle ground", str(e.exception)); self.assertNotIn("background", str(e.exception))
        app.generator_apply(self.pid, "middle", "middle2.png")
        self.sent.clear()
        app.generator_run(self.pid, "composed")
        self.assertEqual(self.sent, [("composed", generator.COMPOSE_PROMPT, ["background1.png", "middle2.png", "foreground2.png"])])      # the three layers add no sentence
        # A fourth reference and an edited prompt.
        self.sent.clear()
        app.generator_run(self.pid, "composed", {"composed": {"prompt": "Custom.", "refs": [{"image": "extra.png", "use": "keep exactly"}], "count": 2}})
        self.assertEqual(self.sent, [("composed", "Custom. Image 4: reproduce what it shows faithfully, with the same shape, proportions and colours.",
                                      ["background1.png", "middle2.png", "foreground2.png", "extra.png"])] * 2)
        self.sent.clear()                                                                # as a style guide the fourth picture is words, not an attachment
        app.generator_run(self.pid, "composed", {"composed": {"prompt": "Custom.", "refs": [{"image": "extra.png", "use": "style guide"}], "count": 1}})
        self.assertEqual(self.sent, [("composed", "Custom.", ["background1.png", "middle2.png", "foreground2.png"])])
        v = app.generator_save(self.pid, {"composed": {"refs": [{"image": "style.png", "use": "insert"}]}})
        self.assertEqual(v["state"]["composed"]["refs"][0]["use"], "keep exactly")       # the fourth reference cannot be inserted: images 1 to 3 are fixed
        self.assertEqual(app.generator_view(self.pid)["state"]["composed"]["applied"]["middle"], "middle2.png")       # saving the prompt kept the choices

    def test_only_a_followed_picture_is_sent_to_the_image_model(self):
        v = app.generator_view(self.pid)
        self.assertEqual([(u["id"], u["name"], u["described"]) for u in v["uses"]], [("insert", "Insert as it is", False), ("keep exactly", "Follow closely (redrawn)", False),
                                                                                    ("style guide", "Style guide", True), ("inspiration", "Inspiration", True)])
        refs = [{"image": "ship.png", "use": "keep exactly"}, {"image": "look.png", "use": "style guide"}, {"image": "mood.png", "use": "inspiration"}, {"image": "old.png", "use": "nonsense"}]
        app.generator_run(self.pid, "background", {"background": {"prompt": "A hangar.", "refs": refs}})
        slot, prompt, sent = self.sent[0]
        # A style guide or inspiration picture is never attached: attached, the image model copies it whatever the words say.
        self.assertEqual(sent, ["ship.png", "old.png"])
        self.assertEqual(prompt, "A hangar. Image 1: reproduce what it shows faithfully, with the same shape, proportions and colours. "
                                 "Image 2: reproduce what it shows faithfully, with the same shape, proportions and colours.")
        self.assertEqual(app.load_project(self.pid)["generator"]["background"]["prompt"], "A hangar.")      # what was typed is stored as typed

    def test_each_reference_keeps_its_number_for_as_long_as_it_is_there(self):
        v = app.generator_save(self.pid, {"image": {"refs": ["a.png", "b.png", "c.png"]}})
        self.assertEqual([(r["image"], r["slot"]) for r in v["state"]["image"]["refs"]], [("a.png", 1), ("b.png", 2), ("c.png", 3)])
        kept = [r for r in v["state"]["image"]["refs"] if r["image"] != "a.png"]                       # take the first one out
        v = app.generator_save(self.pid, {"image": {"refs": kept + [{"image": "d.png", "use": "keep exactly"}, {"image": "e.png", "use": "keep exactly"}]}})
        self.assertEqual([(r["image"], r["slot"]) for r in v["state"]["image"]["refs"]], [("b.png", 2), ("c.png", 3), ("d.png", 1), ("e.png", 4)])
        v = app.generator_save(self.pid, {"image": {"refs": [{"image": "x.png", "slot": 3}, {"image": "y.png", "slot": 3}, {"image": "z.png", "slot": 9}]}})
        self.assertEqual([r["slot"] for r in v["state"]["image"]["refs"]], [3, 1, 2])                    # a repeated or impossible number is replaced

    def test_words_a_reference_added_are_remembered_as_ranges_of_the_prompt(self):
        text = "Visual style: matte teal panels. A small frigate."
        v = app.generator_save(self.pid, {"image": {"prompt": text, "marks": [[0, 33, 3]], "refs": [{"image": "look.png", "use": "style guide", "slot": 3, "text": "Visual style: matte teal panels."}]}})
        self.assertEqual((v["state"]["image"]["marks"], v["state"]["image"]["refs"][0]["text"]), ([[0, 33, 3]], "Visual style: matte teal panels."))
        self.assertEqual(app.generator_save(self.pid, {"image": {"count": 2}})["state"]["image"]["marks"], [[0, 33, 3]])      # an unrelated save keeps them
        self.assertEqual(app.generator_save(self.pid, {"image": {"prompt": "Rewritten."}})["state"]["image"]["marks"], [])     # a new prompt without marks has none
        bad = [[5, 2, 1], [0, 4, 9], [0, 4, 1], [2, 6, 2], [6, 99, 1], "x", [1.5, 3, 1], [8, 10, 2]]
        self.assertEqual(app.generator_save(self.pid, {"image": {"prompt": "0123456789", "marks": bad}})["state"]["image"]["marks"], [[0, 4, 1], [8, 10, 2]])
        v = app.generator_save(self.pid, {"image": {"refs": [{"image": "look.png", "use": "keep exactly", "text": "left over"}, {"image": "b.png", "use": "inspiration", "text": "x" * 400}]}})
        self.assertEqual([len(r["text"]) for r in v["state"]["image"]["refs"]], [0, 300])                # only a described reference has words, and at most 300 characters

    def test_describing_a_reference_asks_the_language_model_and_caps_the_result(self):
        import assist
        asked, real_chat, real_bytes = [], assist.chat, app.comfy_bytes
        answer = {"text": "Matte teal and brushed platinum panels under soft studio light, clean stylized 3D render."}
        assist.chat = lambda system, user, schema, **k: asked.append((system, k.get("images"))) or {"description": answer["text"]}
        app.comfy_bytes = lambda path, timeout=60: b"PNGDATA"
        try:
            app.generator_save(self.pid, {"image": {"refs": [{"image": "look.png", "use": "style guide"}]}})
            got = app.generator_describe(self.pid, "look.png", "style guide")
            self.assertEqual(got["text"], "Visual style: " + answer["text"])
            self.assertIn("ONLY its visual style", asked[0][0]); self.assertIn("Do not mention the subject", asked[0][0])
            self.assertEqual(asked[0][1], ["UE5HREFUQQ=="])                               # the picture itself goes to the language model
            self.assertTrue(app.generator_describe(self.pid, "look.png", "inspiration")["text"].startswith("Loosely inspired by: "))
            self.assertIn("general terms", asked[1][0])
            answer["text"] = "First sentence about the palette and the materials used across the whole surface of the thing. " + "word " * 80
            long = app.generator_describe(self.pid, "look.png", "style guide")["text"]
            self.assertLessEqual(len(long), 300); self.assertTrue(long.endswith("."))
            answer["text"] = "nopunctuation " * 40
            self.assertLessEqual(len(app.generator_describe(self.pid, "look.png", "inspiration")["text"]), 300)
            for image, use in (("look.png", "keep exactly"), ("look.png", "insert"), ("not-in-this-project.png", "style guide"), (None, "style guide")):
                with self.assertRaises(ValueError):
                    app.generator_describe(self.pid, image, use)
            answer["text"] = "   "
            with self.assertRaises(ValueError):
                app.generator_describe(self.pid, "look.png", "style guide")
        finally:
            assist.chat, app.comfy_bytes = real_chat, real_bytes

    def test_insert_as_it_is_keeps_the_pictures_own_pixels_and_draws_around_it(self):
        import base64, struct, zlib
        def png(w, h):
            raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
            chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
            return "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")).decode()
        uploads, real = [], app.comfy_upload
        app.comfy_upload = lambda name, data: uploads.append(name) or name
        try:
            refs = [{"image": "logo.png", "use": "insert"}, {"image": "a.png", "use": "keep exactly"}, {"image": "b.png", "use": "insert"}, {"image": "c.png", "use": "keep exactly"}]
            state = {"image": {"prompt": "A ship hull.", "refs": refs}}
            v = app.generator_save(self.pid, state)
            self.assertEqual([r["use"] for r in v["state"]["image"]["refs"]], ["insert", "keep exactly", "keep exactly", "keep exactly"])      # one insert per box
            for bad in (None, {"image": "a.png", "canvas": png(1248, 720), "mask": png(1248, 720)}, {"image": "logo.png", "canvas": png(64, 64), "mask": png(1248, 720)},
                        {"image": "logo.png", "canvas": png(1248, 720), "mask": "data:image/png;base64,AAAA"}):
                with self.assertRaises(ValueError):
                    app.generator_run(self.pid, "image", None, bad)
            self.assertEqual((self.sent, uploads), ([], []))                              # a refused run stores nothing
            app.generator_run(self.pid, "image", None, {"image": "logo.png", "canvas": png(1248, 720), "mask": png(1248, 720)})
        finally:
            app.comfy_upload = real
        slot, prompt, sent = self.sent[0]
        self.assertEqual(sent, ["a.png", "b.png", "c.png"])                              # the kept picture is not also sent as a reference
        self.assertTrue(prompt.startswith("A ship hull. One element is already in the centre of the picture and must stay exactly as it is."))
        self.assertIn("Image 1: reproduce", prompt); self.assertIn("Image 2: reproduce", prompt); self.assertIn("Image 3: reproduce", prompt)
        graph = self.graphs[0]
        kinds = [n["class_type"] for n in graph.values()]
        self.assertIn("SetLatentNoiseMask", kinds)                                       # only the area around it is drawn
        loaded = [n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage"]
        self.assertEqual(sorted(loaded), sorted([uploads[0], uploads[1], "a.png", "b.png", "c.png"]))
        # The model numbers pictures in the order they are attached: the three others first, the kept picture last.
        def source(node_id):                                 # the file a reference latent was made from
            node = graph[node_id]
            return node["inputs"]["image"] if node["class_type"] == "LoadImage" else next(source(v[0]) for k, v in node["inputs"].items() if isinstance(v, list) and k != "vae")
        chain, node = [], next(n for n in graph.values() if n["class_type"] == "BasicGuider")["inputs"]["conditioning"][0]
        while graph[node]["class_type"] == "ReferenceLatent":
            chain.append(source(graph[node]["inputs"]["latent"][0])); node = graph[node]["inputs"]["conditioning"][0]
        self.assertEqual(chain[::-1], ["a.png", "b.png", "c.png", uploads[0]])

    def test_every_mode_has_its_own_asset_configuration(self):
        v = app.generator_view(self.pid)
        self.assertEqual(sorted(v["state"]["config"]), ["3d", "character", "depth", "image"])
        self.assertEqual([(m, v["state"]["config"][m]["type"]) for m in ("image", "character", "depth", "3d")],
                         [("image", "scene"), ("character", "actor"), ("depth", "scene"), ("3d", "prop")])
        c = v["state"]["config"]["image"]
        self.assertEqual((c["name"], c["rating"]), ("", "PG-13"))                        # the rating starts as the project's own
        self.assertEqual(c["models"], {"prompting": "auto", "image": "auto", "image_lora": "auto", "background_removal": "auto", "upscale": "auto"})
        self.assertEqual(c["workflow"], {"confirm_before_run": False, "approve_before_save": False, "keep_alternatives": True, "keep_history": True, "auto_model_recommendations": True})
        o = v["options"]
        self.assertEqual(([t["label"] for t in o["types"]], o["ratings"]), (["Actor", "Scene", "Prop", "World"], ["E", "PG-13", "R", "M", "X"]))
        self.assertEqual([r["label"] for r in o["roles"]], ["Prompting Model", "Image Model", "Image Model LoRA", "Background Removal Model", "Upscale Model"])
        self.assertEqual((o["in_use"]["image"]["name"], o["in_use"]["upscale"]["name"], o["in_use"]["background_removal"]["ready"]), ("FLUX.2 [dev]", "", False))
        # One mode's settings do not touch another's, and anything invalid keeps what was there.
        v = app.generator_save(self.pid, {"config": {"depth": {"name": "  Cockpit, damaged  ", "rating": "R", "type": "world", "workflow": {"approve_before_save": True, "keep_history": "yes"},
                                                               "models": {"image": "comfyui:other.safetensors", "upscale": 7}},
                                                     "image": {"rating": "PG", "type": "vehicle"}, "bogus": {"name": "x"}}})
        d, i = v["state"]["config"]["depth"], v["state"]["config"]["image"]
        self.assertEqual((d["name"], d["rating"], d["type"], d["workflow"]["approve_before_save"], d["workflow"]["keep_history"]), ("Cockpit, damaged", "R", "world", True, True))
        self.assertEqual((d["models"]["image"], d["models"]["upscale"]), ("comfyui:other.safetensors", "auto"))
        self.assertEqual((i["rating"], i["type"], i["name"]), ("PG-13", "scene", ""))
        self.assertNotIn("bogus", v["state"]["config"])
        v = app.generator_save(self.pid, {"image": {"prompt": "Unrelated edit."}})
        self.assertEqual(v["state"]["config"]["depth"]["name"], "Cockpit, damaged")      # saving something else keeps the configuration

    def test_a_new_asset_configuration_starts_at_the_projects_rating(self):
        with app.LOCK:
            p = app.load_project(self.pid); p["config"]["identity"]["rating"] = "R"; p.pop("generator"); app.save_project(p, touch=False)
        self.assertEqual(app.generator_view(self.pid)["state"]["config"]["character"]["rating"], "R")

    def test_approvals_are_kept_per_picture_and_dropped_with_the_picture(self):
        self.finish("image", "one.png", "two.png")
        v = app.generator_save(self.pid, {"approved": ["one.png", "one.png", "never-made", 5]})
        self.assertEqual(v["state"]["approved"], ["one.png"])
        self.assertEqual(app.generator_remove(self.pid, "one.png")["state"]["approved"], [])

    def test_apply_from_library_lists_every_picture_the_project_has_once_each(self):
        with app.LOCK:
            p = app.load_project(self.pid)
            p["actors"] = [{"id": "m", "name": "Misty", "description": "", "views": [{"id": "v", "image": "misty.png", "label": "waist-up"}]}]
            p["things"] = [{"id": "s", "name": "Ship", "kind": "scene", "context": "", "description": "", "views": [{"id": "w", "image": "ship.png", "label": "side"}]}]
            p["photos"] = [{"id": "p", "name": "Set photo", "image": "photo.png"}, {"id": "q", "name": "Same as the ship", "image": "ship.png"}]
            p["generated"] = [{"id": "g1", "image": "old.png", "kind": "shot", "label": "Opening frame", "created": 5},
                              {"id": "g2", "image": "new.png", "kind": "gen", "slot": "image", "label": "Asset Generator · Image", "created": 9}]
            p["segments"] = [dict(test_core.SEG if hasattr(test_core, "SEG") else {"name": "Intro", "start": 0, "end": 6, "type": "story", "runs": 1}, id="a", name="Intro", begin_image="old.png", end_image="end.png")]
            app.save_project(p, touch=False)
        got = [(x["group"], x["image"], x["label"]) for x in app.generator_library(self.pid)["pictures"]]
        self.assertEqual(got, [("Generated pictures", "new.png", "Asset Generator · Image"), ("Generated pictures", "old.png", "Opening frame"),
                               ("Actors", "misty.png", "Misty · waist-up"), ("Assets and props", "ship.png", "Ship · side"),
                               ("Photos", "photo.png", "Set photo"), ("Storyboard shots", "end.png", "1. Intro · end shot")])

    def test_reset_puts_one_mode_back_to_default_and_keeps_its_pictures_in_the_library(self):
        app.generator_save(self.pid, {"image": {"prompt": "A ship.", "refs": ["a.png"], "count": 4}, "background": {"prompt": "A hangar.", "count": 3},
                                      "composed": {"prompt": "Mine.", "refs": ["s.png"]},
                                      "config": {"image": {"name": "Ship", "rating": "R", "type": "prop", "workflow": {"confirm_before_run": True}}, "depth": {"name": "Cockpit"}}})
        self.finish("image", "one.png", "two.png"); self.finish("background", "bg.png")
        app.generator_apply(self.pid, "background", "bg.png")
        app.generator_save(self.pid, {"approved": ["one.png", "bg.png"]})
        v = app.generator_reset(self.pid, "image")
        self.assertEqual(v["moved"], 2)
        self.assertEqual(v["state"]["image"], {"prompt": "", "refs": [], "at": None, "marks": [], "count": 1})
        c = v["state"]["config"]["image"]
        self.assertEqual((c["name"], c["rating"], c["type"], c["workflow"]["confirm_before_run"]), ("", "PG-13", "scene", False))
        self.assertEqual(v["boxes"]["image"]["results"], [])
        self.assertEqual(v["state"]["approved"], ["bg.png"])
        # The other mode is untouched.
        self.assertEqual((v["state"]["background"]["prompt"], v["state"]["config"]["depth"]["name"], v["state"]["composed"]["applied"]["background"]), ("A hangar.", "Cockpit", "bg.png"))
        # The pictures are still the project's: on the Library tab and in Apply from Library.
        self.assertEqual(sorted(g["image"] for g in app.load_project(self.pid)["generated"]), ["bg.png", "one.png", "two.png"])
        self.assertEqual(sorted(x["image"] for x in app.generator_library(self.pid)["pictures"]), ["a.png" if False else "bg.png", "one.png", "two.png"])
        v = app.generator_reset(self.pid, "depth")
        self.assertEqual((v["moved"], v["state"]["background"]["prompt"], v["state"]["composed"]["prompt"], v["state"]["composed"]["refs"], v["state"]["composed"]["applied"]["background"]),
                         (1, "", generator.COMPOSE_PROMPT, [], None))
        self.assertEqual(app.generator_reset(self.pid, "depth")["moved"], 0)             # nothing left to reset is not an error
        with self.assertRaises(ValueError):
            app.generator_reset(self.pid, "everything")

    def test_reset_waits_for_pictures_that_are_still_being_made(self):
        app.generator_run(self.pid, "image", {"image": {"prompt": "A ship."}})
        with self.assertRaises(ValueError) as e:
            app.generator_reset(self.pid, "image")
        self.assertIn("still being generated", str(e.exception))
        self.assertEqual(app.load_project(self.pid)["generator"]["image"]["prompt"], "A ship.")
        app.generator_reset(self.pid, "depth")                                           # the other mode is free to reset

    def test_only_a_layers_own_pictures_can_be_applied_and_a_removed_one_is_no_longer_applied(self):
        self.finish("background", "bg.png"); self.finish("middle", "mid.png"); self.finish("foreground", "fg.png")
        for layer, image in (("background", "mid.png"), ("composed", "bg.png"), ("image", "bg.png"), ("middle", "never-made.png")):
            with self.assertRaises(ValueError):
                app.generator_apply(self.pid, layer, image)
        for layer, image in (("background", "bg.png"), ("middle", "mid.png"), ("foreground", "fg.png")):
            app.generator_apply(self.pid, layer, image)
        v = app.generator_remove(self.pid, "mid.png")
        self.assertEqual(v["state"]["composed"]["applied"], {"background": "bg.png", "middle": None, "foreground": "fg.png"})
        with self.assertRaises(ValueError):
            app.generator_run(self.pid, "composed")

    def test_saving_the_storyboard_does_not_lose_the_generator_and_the_other_way_round(self):
        app.generator_save(self.pid, {"image": {"prompt": "Keep me."}})
        p = app.load_project(self.pid)
        app.merge_project(self.pid, {"name": "Renamed", "segments": [], "things": [{"id": "t", "name": "Ship", "kind": "scene", "views": []}]})
        after = app.load_project(self.pid)
        self.assertEqual((after["name"], after["generator"]["image"]["prompt"], after["things"][0]["name"]), ("Renamed", "Keep me.", "Ship"))
        app.generator_save(self.pid, {"image": {"prompt": "Changed."}})
        self.assertEqual(app.load_project(self.pid)["things"][0]["name"], "Ship")

    def test_a_failed_run_is_cleared_when_the_box_is_run_again(self):
        app.generator_run(self.pid, "image", {"image": {"prompt": "A."}})
        with app.LOCK:
            p = app.load_project(self.pid); p["image_jobs"][0].update(status="error", error="out of memory"); app.save_project(p, touch=False)
        self.assertEqual(generator.view(app.load_project(self.pid))["boxes"]["image"]["jobs"], [{"id": "j0", "status": "error", "error": "out of memory"}])
        v = app.generator_run(self.pid, "image")
        self.assertEqual([j["status"] for j in v["boxes"]["image"]["jobs"]], ["queued"])


if __name__ == "__main__":
    unittest.main()
