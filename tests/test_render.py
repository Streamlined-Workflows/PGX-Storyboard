"""Rendering rules: queueing, holding a continuing shot, releasing it, reading results back, and locked key frames.
ComfyUI is replaced by a stand-in that records what it was sent."""
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from tests import test_core            # sets DATA_DIR before the app is imported
import app
import assist

SEG = test_core.SEG


class FakeComfy:
    def __init__(self):
        self.sent, self.running, self.pending, self.history = [], [], [], {}

    def __call__(self, path, payload=None, timeout=30):
        if path == "/prompt":
            self.sent.append(payload)
            return {"prompt_id": f"p{len(self.sent)}"}
        if path == "/queue":
            return {"queue_running": [[0, p] for p in self.running], "queue_pending": [[0, p] for p in self.pending]}
        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[-1]
            return {pid: self.history[pid]} if pid in self.history else {}
        return {}


class Base(unittest.TestCase):
    def setUp(self):
        self.comfy = FakeComfy()
        self.saved = (app.comfy_json, assist.unload, app.import_output)
        app.comfy_json, assist.unload = self.comfy, lambda: None
        app.import_output = lambda file, name: "imported_" + name

    def tearDown(self):
        app.comfy_json, assist.unload, app.import_output = self.saved

    def project(self, segments, **more):
        p = app.empty_project("Render"); p["song"] = {"filename": "song.wav", "duration": 60}; p["segments"] = segments; p.update(more)
        return app.save_project(app.normalize(p))

    def seg(self, pid, i):
        return app.load_project(pid)["segments"][i]


class QueueTests(Base):
    def test_a_segment_with_a_begin_shot_queues_its_runs(self):
        p = self.project([dict(SEG, runs=3, results=[])])
        made = app.render_segment(p["id"], "s1")
        self.assertEqual((len(made), len(self.comfy.sent)), (3, 3))
        self.assertEqual({r["status"] for r in self.seg(p["id"], 0)["results"]}, {"queued"})
        self.assertEqual(self.comfy.sent[0]["client_id"], "storyboard")
        self.assertEqual(len({r["seed"] for r in made}), 3)

    def test_a_continuing_shot_waits_for_a_picked_clip_then_starts_from_its_last_frame(self):
        p = self.project([dict(SEG, id="a", results=[{"id": "r1", "status": "done", "last_image": "last_a.png", "files": []}]),
                          dict(SEG, id="b", start=16.0, end=22.0, begin_image=None, results=[])])
        held = app.render_segment(p["id"], "b")
        self.assertEqual((held[0]["status"], len(self.comfy.sent)), ("waiting", 0))            # nothing sent yet
        self.assertIn("pick a clip", held[0]["wait"])
        app.merge_project(p["id"], {"segments": [dict(SEG, id="a", chosen="r1"), dict(SEG, id="b", start=16.0, end=22.0, begin_image=None)]})
        app.refresh_statuses(p["id"])                                                           # the release happens on the next status check
        b = self.seg(p["id"], 1)["results"][0]
        self.assertEqual((b["status"], b["begin"]), ("queued", "last_a.png"))
        self.assertEqual(len(self.comfy.sent), 1)

    def test_a_continuing_shot_uses_the_previous_end_shot_straight_away(self):
        p = self.project([dict(SEG, id="a", end_image="end_a.png", results=[]), dict(SEG, id="b", start=16.0, end=22.0, begin_image=None, results=[])])
        made = app.render_segment(p["id"], "b")
        self.assertEqual((made[0]["status"], made[0]["begin"]), ("queued", "end_a.png"))

    def test_render_all_skips_what_would_have_to_wait_and_says_why(self):
        p = self.project([dict(SEG, id="a", results=[]), dict(SEG, id="b", start=16.0, end=22.0, begin_image=None, results=[]),
                          dict(SEG, id="c", start=22.0, end=28.0, begin_image=None, type="singing", results=[])])
        out = app.render_all(p["id"])
        self.assertEqual((out["queued"], [s["name"] for s in out["skipped"]]), (1, ["Verse", "Verse"]))
        self.assertIn("no picked clip", out["skipped"][0]["reason"])
        self.assertEqual(self.seg(p["id"], 1)["results"], [])                                   # skipped, not held

    def test_the_first_segment_needs_its_own_begin_shot(self):
        p = self.project([dict(SEG, begin_image=None, results=[])])
        with self.assertRaises(ValueError):
            app.render_segment(p["id"], "s1")

    def test_a_rejected_job_explains_itself(self):
        app.comfy_json = lambda path, payload=None, timeout=30: {"_http_error": 400, "node_errors": {"3": "unet_name: 'x.safetensors' not in list"}}
        p = self.project([dict(SEG, results=[])])
        with self.assertRaises(ValueError) as e:
            app.render_segment(p["id"], "s1")
        self.assertIn("not on the server yet", str(e.exception))


class StatusTests(Base):
    def test_results_follow_comfyui(self):
        p = self.project([dict(SEG, runs=4, results=[])])
        app.render_segment(p["id"], "s1")
        self.comfy.running, self.comfy.pending = ["p1"], ["p2"]
        self.comfy.history["p3"] = {"status": {"status_str": "success"}, "outputs": {"9": {"images": [{"filename": "clip.mp4", "subfolder": "storyboard", "type": "output"}]},
                                                                                   "10": {"images": [{"filename": "last.png", "subfolder": "storyboard", "type": "output"}]}}}
        self.comfy.history["p4"] = {"status": {"status_str": "error", "messages": [["execution_error", {"node_type": "KSampler", "exception_message": "out of memory"}]]}}
        app.refresh_statuses(p["id"])
        r = {x["prompt_id"]: x for x in self.seg(p["id"], 0)["results"]}
        self.assertEqual([r[k]["status"] for k in ("p1", "p2", "p3", "p4")], ["running", "queued", "done", "error"])
        self.assertEqual(r["p3"]["last_image"], "imported_last.png")                             # kept so the next segment can continue
        self.assertEqual([f["filename"] for f in r["p3"]["files"]], ["clip.mp4"])
        self.assertIn("out of memory", r["p4"]["error"])

    def test_a_job_comfyui_forgot_becomes_an_error_after_a_minute(self):
        p = self.project([dict(SEG, results=[{"id": "x", "status": "queued", "prompt_id": "gone", "created": time.time() - 120, "files": []},
                                             {"id": "y", "status": "queued", "prompt_id": "new", "created": time.time(), "files": []}])])
        app.refresh_statuses(p["id"])
        self.assertEqual([r["status"] for r in self.seg(p["id"], 0)["results"]], ["error", "queued"])


class KeyFrameTests(Base):
    def setUp(self):
        super().setUp()
        self.queued, self.real_still = [], app.queue_still
        app.queue_still = lambda project, prompt, refs, stem, graph=None, **f: self.queued.append((f.get("segment_id"), f.get("slot"))) or {"id": "j"}

    def tearDown(self):
        app.queue_still = self.real_still
        super().tearDown()

    def plan(self, **first):
        segs = [dict(SEG, id="a"), dict(SEG, id="b", start=16.0, end=22.0, type="singing"), dict(SEG, id="c", start=22.0, end=28.0)]
        frame = lambda text, **k: dict({"text": text, "who": [], "what": []}, **k)
        shots = {"first": frame("Opening.", **first), "ends": [
            dict(frame("End of a.", locked=True), segment_id="a", start="new", begin=frame("Opening.")),
            dict(frame("End of b."), segment_id="b", start="continue", begin=frame("")),
            dict(frame("End of c."), segment_id="c", start="new", begin=frame("Begin of c."))]}
        story = {"title": "T", "logline": "L", "style": "S", "beats": ["", "", ""], "segment_ids": ["a", "b", "c"]}
        return self.project(segs, assist={"analysis": {"tempo": 120}, "story": story, "story_draft": story, "shots": shots})

    def test_generate_all_skips_locked_frames_and_singing_end_shots(self):
        p = self.plan()
        app.assist_shot_images(p["id"], None)
        self.assertEqual(self.queued, [("a", "begin_image"), ("c", "begin_image"), ("c", "end_image")])

    def test_a_locked_frame_is_still_made_when_asked_for_by_name(self):
        p = self.plan(locked=True)
        app.assist_shot_images(p["id"], ["a"])
        self.assertEqual(self.queued, [("a", "end_image")])
        self.queued.clear()
        app.assist_shot_images(p["id"], None)
        self.assertNotIn(("a", "begin_image"), self.queued)                                      # the locked opening frame is left alone


    def test_a_picture_uses_only_the_actors_and_assets_ticked_for_it(self):
        segs = [dict(SEG, id="a")]
        frame = lambda text, **k: dict({"text": text, "who": [], "what": []}, **k)
        shots = {"first": frame("The ship drifts dark in a debris field.", who=["Misty"]),
                 "ends": [dict(frame("The ship, lights out.", who=["Misty"]), segment_id="a", start="new", begin=frame("The ship drifts dark in a debris field."))]}
        story = {"title": "T", "logline": "L", "style": "S", "beats": [""], "segment_ids": ["a"]}
        p = self.project(segs, actors=[{"id": "m", "name": "Misty", "description": "teal suit", "views": [{"image": "misty.png", "label": "waist-up"}]}],
                         things=[{"id": "s", "name": "Ship", "kind": "scene", "context": "", "description": "", "views": [{"image": "ship.png"}]}],
                         assist={"analysis": {"tempo": 120}, "story": story, "story_draft": story, "cast": [{"actor_id": "m", "role": "pilot"}], "shots": shots})
        sent = []
        app.queue_still = lambda project, prompt, refs, stem, graph=None, **f: sent.append((f.get("slot"), prompt, refs)) or {"id": "j"}
        app.assist_shot_images(p["id"], ["first"])
        self.assertEqual(sent[0][2], ["misty.png"])                          # as the language model planned it: the actor is in the exterior
        self.assertIn("Misty is the character in reference image 1", sent[0][1])
        # Untick the actor and tick the ship on the opening frame; leave the end frame as it was.
        edited = {"first": {"text": shots["first"]["text"], "who": [], "what": ["Ship", "Someone deleted"]}, "ends": [{"segment_id": "a", "text": "The ship, lights out."}]}
        saved = app.assist_shots_save(p["id"], edited)["assist"]["shots"]
        self.assertEqual((saved["first"]["who"], saved["first"]["what"]), ([], ["Ship"]))          # a name that is not an asset is dropped
        self.assertEqual(saved["ends"][0]["who"], ["Misty"])                                       # not sent, so not changed
        sent.clear()
        app.assist_shot_images(p["id"], ["first", "a"])
        opening, end = sent
        self.assertEqual(opening[2], ["ship.png"])
        self.assertNotIn("Misty", opening[1])
        self.assertIn("Ship is the subject shown in reference image 1", opening[1])
        self.assertEqual(end[2], ["misty.png"])
        # Nothing ticked: the picture comes from the description and style alone.
        app.assist_shots_save(p["id"], {"first": {"who": [], "what": []}, "ends": []})
        sent.clear(); app.assist_shot_images(p["id"], ["first"])
        self.assertEqual(sent[0][2], [])
        self.assertTrue(sent[0][1].startswith("The ship drifts dark in a debris field. Visual style: S."))


class HttpTests(Base):
    """A few requests through the real request handler, for the rules that live in it."""

    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        super().tearDown()

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_duplicate_keeps_finished_clips_and_drops_unfinished_jobs(self):
        p = self.project([dict(SEG, results=[{"id": "d", "status": "done", "files": []}, {"id": "q", "status": "queued", "prompt_id": "p9", "files": []}])],
                         lore=["abc12345"], things=[{"id": "t", "kind": "prop", "name": "Mic", "views": []}])
        status, copy = self.call("/api/projects/duplicate", {"id": p["id"]})
        self.assertEqual(status, 200)
        self.assertNotEqual(copy["id"], p["id"])
        self.assertEqual(([r["id"] for r in copy["segments"][0]["results"]], copy["lore"], len(copy["things"]), copy["config"]), (["d"], ["abc12345"], 1, p["config"]))
        self.assertEqual(len(app.load_project(p["id"])["segments"][0]["results"]), 2)            # the original is untouched

    def test_delete_moves_the_project_to_the_trash(self):
        p = self.project([])
        self.assertEqual(self.call("/api/projects/delete", {"id": p["id"]})[0], 200)
        with self.assertRaises(ValueError):
            app.load_project(p["id"])
        self.assertTrue(any(n.startswith(p["id"]) for n in os.listdir(app.TRASH_DIR)))
        self.assertEqual(self.call("/api/projects/delete", {"id": p["id"]})[0], 400)

    def test_errors_are_readable_and_config_info_is_complete(self):
        status, body = self.call("/api/project?id=../../etc/passwd")
        self.assertIn(status, (400, 404)); self.assertIn("error", body)          # refused with words, never a crash
        status, info = self.call("/api/config/info")
        self.assertEqual((status, info["schema"], len(info["in_use"]), info["used"]), (200, 2, 9, ["identity.music.subtype", "production.storyboard_detail"]))


if __name__ == "__main__":
    unittest.main()


class PromptLengthTests(Base):
    def test_a_key_frame_reports_what_it_adds_to_its_description(self):
        segs = [dict(SEG, id="a")]
        frame = lambda text, **k: dict({"text": text, "who": [], "what": []}, **k)
        shots = {"first": frame("The ship drifts.", who=["Misty"]),
                 "ends": [dict(frame("Lights out."), segment_id="a", start="new", begin=frame("The ship drifts.", what=["Ship"]))]}
        story = {"title": "T", "logline": "L", "style": "Painted", "beats": [""], "segment_ids": ["a"]}
        p = self.project(segs, actors=[{"id": "m", "name": "Misty", "description": "teal suit", "views": [{"image": "misty.png", "label": "waist-up"}]}],
                         things=[{"id": "s", "name": "Ship", "kind": "scene", "context": "", "description": "", "views": [{"image": "ship.png"}]}],
                         assist={"analysis": {"tempo": 120}, "story": story, "story_draft": story, "cast": [{"actor_id": "m", "role": "pilot"}], "shots": shots})
        got = app.assist_shot_lengths(p["id"])["frames"]
        self.assertEqual(sorted(got), ["a", "begin:a", "first"])
        cast = app.cast_members(app.load_project(p["id"]))
        # The page shows description + added. That must equal the length of what is really sent.
        sent = len(app.assist.shot_prompt("The ship drifts.", "Painted", cast))
        self.assertEqual(len("The ship drifts") + 1 + got["first"], sent)
        plain = len(app.assist.shot_prompt("Lights out.", "Painted", []))
        self.assertEqual(len("Lights out") + 1 + got["a"], plain)
        self.assertGreater(got["first"], got["a"])                             # a ticked actor adds a sentence
        self.assertGreater(got["begin:a"], got["a"])                           # so does a ticked asset

    def test_prompt_limits_name_the_model_and_say_how_much_it_reads(self):
        import workflows
        self.assertEqual(sorted(workflows.PROMPT_LIMITS), ["image", "video"])
        for limit in workflows.PROMPT_LIMITS.values():
            self.assertEqual((limit["tokens"], limit["characters"]), (512, 2000))
