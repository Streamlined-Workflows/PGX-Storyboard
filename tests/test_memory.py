"""Freeing memory: what each tab keeps, and that a running job or a model mid-answer is never disturbed."""
import unittest

from tests import test_core            # sets DATA_DIR before the app is imported
import app
import assist
import usage


class Comfy:
    def __init__(self, busy=0):
        self.busy, self.freed = busy, 0

    def __call__(self, path, payload=None, timeout=30):
        if path == "/queue":
            return {"queue_running": [[0, "p"]] * self.busy, "queue_pending": []}
        if path == "/free":
            self.freed += 1
        return {}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.real, self.unloads = usage._unload_llm, 0
        usage._unload_llm = lambda: setattr(self, "unloads", self.unloads + 1) or True

    def tearDown(self):
        usage._unload_llm = self.real

    def test_each_tab_keeps_only_what_it_uses(self):
        expect = {"storyboard": (0, 1), "identity": (0, 1), "assist": (0, 0), "assets": (0, 0), "projects": (1, 1), "library": (1, 1), "lore": (1, 1)}
        for view, (comfy_freed, llm_unloaded) in expect.items():
            comfy, self.unloads = Comfy(), 0
            usage.release_for_view(comfy, view)
            self.assertEqual((comfy.freed, self.unloads), (comfy_freed, llm_unloaded), view)

    def test_looking_at_system_status_or_an_unknown_tab_changes_nothing(self):
        for view in ("system", "nonsense", None):
            comfy = Comfy()
            self.assertEqual(usage.release_for_view(comfy, view), {"released": [], "left": []})
            self.assertEqual((comfy.freed, self.unloads), (0, 0))

    def test_comfyui_is_never_freed_while_a_job_is_running_or_waiting(self):
        comfy = Comfy(busy=1)
        out = usage.release_for_view(comfy, "library")
        self.assertEqual(comfy.freed, 0)
        self.assertEqual(out["released"], ["llm"])
        self.assertIn("rendering", out["left"][0])
        with self.assertRaises(ValueError):                         # the Free memory button says so instead of doing half the job
            usage.free(comfy)

    def test_the_language_model_is_never_unloaded_mid_answer(self):
        out = usage.release_for_view(Comfy(), "library", llm_busy=True)
        self.assertEqual((self.unloads, out["released"]), (0, ["comfy"]))

    def test_room_is_made_before_the_language_model_writes_and_it_counts_as_busy_while_it_does(self):
        seen, real_inner, real_hook = {}, assist._chat_with_retry, assist.before_chat
        assist._chat_with_retry = lambda *a, **k: seen.update(active=assist.active) or {"ok": 1}
        assist.before_chat = lambda: seen.update(hook=True)
        try:
            self.assertEqual(assist.chat("s", "u", {}), {"ok": 1})
            self.assertEqual((seen["hook"], seen["active"], assist.active), (True, 1, 0))
            assist.before_chat = lambda: 1 / 0                      # a failure to make room never blocks the request
            self.assertEqual(assist.chat("s", "u", {}), {"ok": 1})
        finally:
            assist._chat_with_retry, assist.before_chat = real_inner, real_hook

    def test_making_room_frees_comfyui_only_when_it_is_idle(self):
        real, real_sleep = app.comfy_json, app.time.sleep
        app.time.sleep = lambda s: None
        try:
            for busy, freed in ((0, 1), (1, 0)):
                app.comfy_json = Comfy(busy)
                app.make_room_for_language_model()
                self.assertEqual((app.comfy_json.freed, self.unloads), (freed, 0), busy)     # and never unloads the model it is making room for
        finally:
            app.comfy_json, app.time.sleep = real, real_sleep


if __name__ == "__main__":
    unittest.main()
