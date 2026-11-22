"""From brief and references to concept jobs, and from a finished job back to a stored picture."""
import os
import tempfile
import unittest

from identity_studio import api, generate
from identity_studio.storage import Store
from identity_studio.tests.test_jobs import FakeComfy
from identity_studio.tests.test_references import GOOD_SVG, PNG

P = "/api/identity/"


def fake_image(prompt, refs, seed, width=0, height=0, prefix=""):
    return {"1": {"class_type": "Image", "inputs": {"text": prompt, "refs": list(refs), "seed": seed, "w": width, "h": height, "prefix": prefix}}}


def fake_fix(image, mask, prompt, seed, width, height, prefix):
    return {"1": {"class_type": "Fix", "inputs": {"image": image, "mask": mask, "text": prompt, "w": width, "h": height, "prefix": prefix}}}


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.comfy = FakeComfy()
        self.store = Store(self.tmp.name)
        api.use_store(self.store, self.comfy)
        api.jobs().start = lambda: None
        self.freed = []
        api.configure(build_image=fake_image, build_fix=fake_fix, before=lambda: self.freed.append(1))
        self.pid = api.handle("POST", P + "projects", payload={"name": "Icon"})["id"]

    def tearDown(self):
        api.use_store(None); api.configure(); self.tmp.cleanup()

    def brief(self, **settings):
        api.handle("PUT", P + "project", {"id": self.pid}, {"settings": settings})

    def project(self):
        return api.handle("GET", P + "project", {"id": self.pid})

    def run_all(self):
        """Let every queued job run to the end, one at a time, as ComfyUI would."""
        for _ in range(20):
            api.jobs().tick()
            if self.comfy.pending:
                pid = self.comfy.pending[0]; self.comfy.begin(pid); self.comfy.finish(pid)

    def test_an_empty_brief_is_refused(self):
        with self.assertRaises(ValueError):
            api.handle("POST", P + "concepts/generate", payload={"project": self.pid})
        self.assertEqual(api.jobs().list(), [])

    def test_generation_is_off_until_the_host_connects_it(self):
        api.configure()
        self.brief(app_name="SWIFT Director")
        self.assertFalse(api.handle("GET", P + "info")["ready"]["generation"])
        with self.assertRaises(ValueError):
            api.handle("POST", P + "concepts/generate", payload={"project": self.pid})

    def test_a_round_queues_the_briefs_count_and_stores_the_pictures(self):
        self.brief(app_name="SWIFT Director", description="a clapperboard", concept_count=3, palette=["#22c55e"], layout="icon only")
        out = api.handle("POST", P + "concepts/generate", payload={"project": self.pid, "direction": "rounder corners"})
        self.assertEqual(out["queued"], 3)
        self.assertEqual(self.freed, [1])
        jobs = api.jobs().list()
        self.assertEqual(len({j["meta"]["concept"] for j in jobs}), 3)
        self.assertTrue(all(c["state"] == "waiting" for c in self.project()["concepts"]))
        self.comfy.running = ["video-1"]; api.jobs().tick()
        self.assertEqual([x for x in self.comfy.log if x[0] == "submit"], [])        # still behind the render
        self.comfy.running = []; self.run_all()
        concepts = self.project()["concepts"]
        self.assertEqual([c["state"] for c in concepts], ["done"] * 3)
        self.assertEqual((concepts[0]["width"], concepts[0]["height"]), (1024, 1024))
        self.assertEqual(len({c["seed"] for c in concepts}), 3)
        f = api.handle("GET", P + "concept", {"project": self.pid, "id": concepts[0]["id"]})
        self.assertEqual(os.path.dirname(f.path), self.store.concept_dir(self.pid))   # our own copy, not ComfyUI's
        prompt = concepts[0]["prompt"]
        for part in ("SWIFT Director", "a clapperboard", "rounder corners", "#22c55e", "No text"):
            self.assertIn(part, prompt)

    def test_only_switched_on_references_are_sent_and_svg_needs_its_flat_copy(self):
        self.brief(app_name="SWIFT")
        q = {"project": self.pid}
        svg = api.handle("POST", P + "references", dict(q, name="i.svg"), raw=GOOD_SVG)
        png = api.handle("POST", P + "references", dict(q, name="style.png"), raw=PNG)
        off = api.handle("POST", P + "references", dict(q, name="old.png"), raw=PNG)
        api.handle("PUT", P + "reference", dict(q, id=off["id"]), {"enabled": False})
        api.handle("PUT", P + "reference", dict(q, id=svg["id"]), {"note": "the dot is a drop", "use": "keep exactly"})
        with self.assertRaises(ValueError):                                           # the model cannot read an SVG
            api.handle("POST", P + "concepts/generate", payload=q)
        self.assertEqual(api.jobs().list(), [])
        with self.assertRaises(ValueError):
            api.handle("POST", P + "reference/flat", dict(q, id=svg["id"]), raw=b"<svg/>")   # must be a PNG
        api.handle("POST", P + "reference/flat", dict(q, id=svg["id"]), raw=PNG + b"flat")
        self.brief(concept_count=1)
        out = api.handle("POST", P + "concepts/generate", payload=q)
        names = [f"identity_{self.pid}_{svg['id']}.png", f"identity_{self.pid}_{png['id']}.png"]
        self.assertEqual(sorted(self.comfy.uploads), sorted(names))
        self.assertEqual(self.comfy.uploads[names[0]], PNG + b"flat")                 # the flat copy, not the SVG
        concept = self.project()["concepts"][0]
        self.assertEqual(concept["references"], [svg["id"], png["id"]])
        self.assertIn("Reference image 1 is an existing mark", concept["prompt"])
        self.assertIn("the dot is a drop", concept["prompt"])
        self.assertIn("style of reference image 2", concept["prompt"])
        self.assertTrue(any("keep exactly" in n for n in out["notes"]))

    def png(self, w, h):
        import base64, struct
        return "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", w, h) + b"\x08\x06" + b"\x00" * 12).decode()

    def test_insert_keeps_the_reference_and_draws_around_it(self):
        self.brief(app_name="SWIFT Director", description="a movie reel", concept_count=2)
        q = {"project": self.pid}
        cutout = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x10" * 2 + b"\x08\x06" + b"\x00" * 12     # a PNG with transparency
        mark = api.handle("POST", P + "references", dict(q, name="Swift-Icon.png"), raw=cutout)
        photo = api.handle("POST", P + "references", dict(q, name="style.png"), raw=PNG)
        self.assertEqual((mark["use"], photo["use"]), ("insert", "style guide"))    # a cut-out starts as insert
        with self.assertRaises(ValueError):                                          # the page must send the placed picture
            api.handle("POST", P + "concepts/generate", payload=q)
        for bad in ({"reference": mark["id"], "canvas": self.png(512, 512), "mask": self.png(1024, 1024)},      # wrong size
                    {"reference": mark["id"], "canvas": "data:image/png;base64,AAAA", "mask": self.png(1024, 1024)},
                    {"reference": photo["id"], "canvas": self.png(1024, 1024), "mask": self.png(1024, 1024)}):   # not an insert reference
            with self.assertRaises(ValueError):
                api.handle("POST", P + "concepts/generate", payload=dict(q, insert=bad))
        self.assertEqual(api.jobs().list(), [])
        out = api.handle("POST", P + "concepts/generate", payload=dict(q, direction="film strip circling it",
                         insert={"reference": mark["id"], "canvas": self.png(1024, 1024), "mask": self.png(1024, 1024)}))
        self.assertEqual(out["queued"], 2)
        self.assertEqual(sorted(self.comfy.uploads), sorted([f"identity_{self.pid}_{mark['id']}_canvas.png", f"identity_{self.pid}_{mark['id']}_around.png"]))
        concept = self.project()["concepts"][0]
        self.assertEqual((concept["inserted"], concept["references"]), (mark["id"], [mark["id"]]))
        for part in ("stays exactly as it is", "a movie reel", "film strip circling it"):
            self.assertIn(part, concept["prompt"])
        self.assertNotIn("Reference image 1", concept["prompt"])                    # the model is not asked to redraw anything
        self.assertTrue(any("not used" in n for n in out["notes"]))                 # says the style reference sat this round out
        self.run_all()
        self.assertEqual([c["state"] for c in self.project()["concepts"]], ["done", "done"])
        api.handle("PUT", P + "reference", dict(q, id=mark["id"]), {"enabled": False})   # switched off: an ordinary round again
        api.handle("POST", P + "concepts/generate", payload=q)
        self.assertIn("style of reference image 1", self.project()["concepts"][-1]["prompt"])

    def test_more_than_four_references_uses_four_and_says_so(self):
        self.brief(app_name="SWIFT", concept_count=1)
        for i in range(6):
            api.handle("POST", P + "references", {"project": self.pid, "name": f"{i}.png"}, raw=PNG)
        out = api.handle("POST", P + "concepts/generate", payload={"project": self.pid})
        self.assertEqual(len(self.project()["concepts"][0]["references"]), 4)
        self.assertTrue(any("first 4" in n for n in out["notes"]))

    def test_failure_stop_and_retry_show_on_the_concept(self):
        self.brief(app_name="SWIFT", concept_count=1)
        api.handle("POST", P + "concepts/generate", payload={"project": self.pid})
        api.jobs().tick(); self.comfy.clear_all(); api.jobs().tick()                  # "Stop all renders"
        self.assertEqual(self.project()["concepts"][0]["state"], "stopped")
        api.handle("POST", P + "jobs/retry", payload={"id": api.jobs().list()[0]["id"]})
        self.assertEqual(self.project()["concepts"][0]["state"], "waiting")
        self.run_all()
        self.assertEqual(self.project()["concepts"][0]["state"], "done")

    def test_fix_makes_a_new_concept_and_keeps_the_original(self):
        self.brief(app_name="SWIFT", concept_count=1)
        api.handle("POST", P + "concepts/generate", payload={"project": self.pid}); self.run_all()
        first = self.project()["concepts"][0]
        q = {"project": self.pid, "id": first["id"]}
        for bad in (dict(q, prompt=""), dict(q, prompt="x", id="ffffffffffff")):
            with self.assertRaises(ValueError):
                api.handle("POST", P + "concepts/fix", bad, raw=PNG)
        with self.assertRaises(ValueError):
            api.handle("POST", P + "concepts/fix", dict(q, prompt="smooth the curve"), raw=b"not a png")
        api.handle("POST", P + "concepts/fix", dict(q, prompt="smooth the curve"), raw=PNG)
        job = api.jobs().list()[-1]
        self.assertEqual(job["kind"], "fix")
        self.run_all()
        concepts = self.project()["concepts"]
        self.assertEqual([(c["kind"], c["state"], c["parent"]) for c in concepts], [("concept", "done", None), ("fix", "done", first["id"])])
        self.assertTrue(os.path.isfile(api.handle("GET", P + "concept", q).path))     # the original is untouched

    def test_removing_a_waiting_concept_cancels_its_job(self):
        self.brief(app_name="SWIFT", concept_count=2)
        ids = api.handle("POST", P + "concepts/generate", payload={"project": self.pid})["concepts"]
        api.handle("POST", P + "concepts/remove", payload={"project": self.pid, "id": ids[1]})
        self.assertEqual([j["state"] for j in api.jobs().list()], ["waiting", "cancelled"])
        self.run_all()
        api.handle("POST", P + "concepts/remove", payload={"project": self.pid, "id": ids[0]})
        self.assertEqual(self.project()["concepts"], [])
        self.assertTrue(any("concept" in n for n in os.listdir(self.store.trash)))

    def test_a_concept_says_when_it_is_the_one_being_rendered(self):
        self.brief(app_name="SWIFT", concept_count=2)
        api.handle("POST", P + "concepts/generate", payload={"project": self.pid})
        api.jobs().tick(); self.comfy.begin("ident-1"); api.jobs().tick()
        self.assertEqual([c["state"] for c in self.project()["concepts"]], ["running", "waiting"])
        self.comfy.finish("ident-1"); api.jobs().tick()
        self.assertEqual([c["state"] for c in self.project()["concepts"]], ["done", "waiting"])

    def test_lock_protects_a_concept_and_clean_up_erases_the_rest(self):
        self.brief(app_name="SWIFT", concept_count=3)
        ids = api.handle("POST", P + "concepts/generate", payload={"project": self.pid})["concepts"]
        self.run_all()
        api.handle("POST", P + "concepts/generate", payload={"project": self.pid})          # three more, still waiting
        q = {"project": self.pid}
        api.handle("POST", P + "concepts/lock", payload=dict(q, id=ids[0], locked=True))
        with self.assertRaises(ValueError):
            api.handle("POST", P + "concepts/remove", payload=dict(q, id=ids[0]))
        api.handle("POST", P + "concepts/remove", payload=dict(q, id=ids[1]))               # goes to the trash folder
        self.assertTrue(any("concept" in n for n in os.listdir(self.store.trash)))
        kept_file = api.handle("GET", P + "concept", dict(q, id=ids[0])).path
        gone_file = api.handle("GET", P + "concept", dict(q, id=ids[2])).path
        out = api.handle("POST", P + "concepts/clean", payload=q)
        self.assertEqual((out["removed"], out["kept"]), (1, 4))                              # one unlocked finished; the locked one and three waiting stay
        self.assertGreater(out["bytes"], 0)
        self.assertTrue(os.path.isfile(kept_file)); self.assertFalse(os.path.exists(gone_file))
        self.assertFalse(any("concept" in n for n in os.listdir(self.store.trash)))         # the trashed picture is erased too
        self.assertEqual([c["state"] for c in self.project()["concepts"]], ["done", "waiting", "waiting", "waiting"])
        api.handle("POST", P + "concepts/lock", payload=dict(q, id=ids[0], locked=False))
        api.handle("POST", P + "concepts/remove", payload=dict(q, id=ids[0]))

    def test_prompt_wording_follows_layout_and_background(self):
        s = dict(self.project()["settings"], app_name="Folio", tagline="Cards, fast", layout="icon and text", background="dark", style="custom", style_notes="thin lines")
        text = generate.concept_prompt(s, [])
        for part in ('the name "Folio"', 'the tagline "Cards, fast"', "solid black background", "thin lines"):
            self.assertIn(part, text)
        self.assertNotIn("No text", text)
        self.assertEqual(generate.png_size(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x06\x00\x00\x00\x03\x00"), (1536, 768))


if __name__ == "__main__":
    unittest.main()
