"""Asset Generator: what is stored, what each box sends to the image model, and the depth workflow's rules."""
import unittest

from tests import test_core            # sets DATA_DIR before the app is imported
import app
import generator


class GeneratorTests(test_core.Base if hasattr(test_core, "Base") else unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.sent, self.real = [], app.queue_still

        def fake(project, prompt, refs, stem, graph=None, **f):
            job = {"id": f"j{len(self.sent)}", "prompt_id": "p", "status": "queued", "created": 0, **f}
            project["image_jobs"].append(job); self.sent.append((f.get("slot"), prompt, list(refs)))
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
        state = {"image": {"prompt": "  A ship in a debris field.  ", "refs": ["a.png", "b.png", "c.png", "d.png", "e.png"], "count": 3}}
        v = app.generator_run(self.pid, "image", state)
        self.assertEqual(self.sent, [("image", "A ship in a debris field.", ["a.png", "b.png", "c.png", "d.png"])] * 3)
        self.assertEqual([j["status"] for j in v["boxes"]["image"]["jobs"]], ["queued"] * 3)
        self.finish("image", "one.png", "two.png")
        self.assertEqual([r["image"] for r in app.generator_view(self.pid)["boxes"]["image"]["results"]], ["one.png", "two.png"])

    def test_limits(self):
        v = app.generator_save(self.pid, {"image": {"prompt": "x" * 5000, "count": 99, "refs": ["a"] * 9}, "background": {"count": 0}, "middle": {"count": "seven"},
                                          "composed": {"refs": ["x.png", "y.png"]}})
        self.assertEqual((len(v["state"]["image"]["prompt"]), v["state"]["image"]["count"], len(v["state"]["image"]["refs"])), (3000, 10, 4))
        self.assertEqual((v["state"]["background"]["count"], v["state"]["middle"]["count"]), (1, 1))
        self.assertEqual(v["state"]["composed"]["refs"], ["x.png"])                  # one free slot: the fourth reference
        for bad in ("nope", None):
            with self.assertRaises(ValueError):
                app.generator_run(self.pid, bad)
        with self.assertRaises(ValueError) as e:
            app.generator_run(self.pid, "background", {"background": {"prompt": "   "}})
        self.assertIn("Write a prompt", str(e.exception))
        self.assertEqual(self.sent, [])

    def test_depth_generation_composes_the_three_applied_pictures_in_a_fixed_order(self):
        for layer, prompt in (("background", "Ship interior."), ("middle", "Misty floating."), ("foreground", "Dust and a canister.")):
            app.generator_run(self.pid, layer, {layer: {"prompt": prompt, "refs": [layer + "-ref.png"], "count": 2}})
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
        self.assertEqual(self.sent, [("composed", generator.COMPOSE_PROMPT, ["background1.png", "middle2.png", "foreground2.png"])])
        # A fourth reference and an edited prompt.
        self.sent.clear()
        app.generator_run(self.pid, "composed", {"composed": {"prompt": "Custom. Use image 4 as the style.", "refs": ["style.png"], "count": 2}})
        self.assertEqual(self.sent, [("composed", "Custom. Use image 4 as the style.", ["background1.png", "middle2.png", "foreground2.png", "style.png"])] * 2)
        self.assertEqual(app.generator_view(self.pid)["state"]["composed"]["applied"]["middle"], "middle2.png")       # saving the prompt kept the choices

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
