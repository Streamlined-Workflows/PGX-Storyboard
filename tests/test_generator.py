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
        self.assertEqual(v["state"]["image"], {"prompt": "", "refs": [], "at": None, "count": 1})
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
        self.assertEqual(v["state"]["composed"]["refs"], [{"image": "x.png", "use": "keep exactly"}])      # one free slot: the fourth reference
        for bad in ("nope", None):
            with self.assertRaises(ValueError):
                app.generator_run(self.pid, bad)
        with self.assertRaises(ValueError) as e:
            app.generator_run(self.pid, "background", {"background": {"prompt": "   "}})
        self.assertIn("Write a prompt", str(e.exception))
        self.assertEqual(self.sent, [])

    def test_depth_generation_composes_the_three_applied_pictures_in_a_fixed_order(self):
        for layer, prompt in (("background", "Ship interior."), ("middle", "Misty floating."), ("foreground", "Dust and a canister.")):
            app.generator_run(self.pid, layer, {layer: {"prompt": prompt, "refs": [{"image": layer + "-ref.png", "use": "inspiration"}], "count": 2}})
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
        app.generator_run(self.pid, "composed", {"composed": {"prompt": "Custom.", "refs": [{"image": "style.png", "use": "style guide"}], "count": 2}})
        self.assertEqual(self.sent, [("composed", "Custom. Image 4 is a style guide: match its visual style, colour treatment and lighting, not what it shows.",
                                      ["background1.png", "middle2.png", "foreground2.png", "style.png"])] * 2)
        v = app.generator_save(self.pid, {"composed": {"refs": [{"image": "style.png", "use": "insert"}]}})
        self.assertEqual(v["state"]["composed"]["refs"][0]["use"], "keep exactly")       # the fourth reference cannot be inserted: images 1 to 3 are fixed
        self.assertEqual(app.generator_view(self.pid)["state"]["composed"]["applied"]["middle"], "middle2.png")       # saving the prompt kept the choices

    def test_each_reference_says_how_it_is_used_and_adds_one_sentence_the_page_can_show(self):
        v = app.generator_view(self.pid)
        self.assertEqual([(u["id"], u["name"]) for u in v["uses"]], [("insert", "Insert as it is"), ("keep exactly", "Follow closely (redrawn)"),
                                                                     ("style guide", "Style guide"), ("inspiration", "Inspiration")])      # the same four, same words, as Identity Studio
        refs = [{"image": "ship.png", "use": "keep exactly"}, {"image": "look.png", "use": "style guide"}, {"image": "mood.png", "use": "inspiration"}, {"image": "old.png", "use": "nonsense"}]
        app.generator_run(self.pid, "background", {"background": {"prompt": "A hangar.", "refs": refs}})
        slot, prompt, sent = self.sent[0]
        self.assertEqual(sent, ["ship.png", "look.png", "mood.png", "old.png"])
        self.assertEqual(prompt, "A hangar. Image 1: reproduce what it shows faithfully, with the same shape, proportions and colours. "
                                 "Image 2 is a style guide: match its visual style, colour treatment and lighting, not what it shows. "
                                 "Take loose inspiration from image 3. Image 4: reproduce what it shows faithfully, with the same shape, proportions and colours.")
        self.assertEqual(app.load_project(self.pid)["generator"]["background"]["prompt"], "A hangar.")      # what was typed is stored as typed

    def test_insert_as_it_is_keeps_the_pictures_own_pixels_and_draws_around_it(self):
        import base64, struct, zlib
        def png(w, h):
            raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
            chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
            return "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")).decode()
        uploads, real = [], app.comfy_upload
        app.comfy_upload = lambda name, data: uploads.append(name) or name
        try:
            refs = [{"image": "logo.png", "use": "insert"}, {"image": "a.png", "use": "style guide"}, {"image": "b.png", "use": "insert"}, {"image": "c.png", "use": "inspiration"}]
            state = {"image": {"prompt": "A ship hull.", "refs": refs}}
            v = app.generator_save(self.pid, state)
            self.assertEqual([r["use"] for r in v["state"]["image"]["refs"]], ["insert", "style guide", "keep exactly", "inspiration"])      # one insert per box
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
        self.assertIn("Image 1 is a style guide", prompt); self.assertIn("Image 2: reproduce", prompt); self.assertIn("inspiration from image 3", prompt)
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
