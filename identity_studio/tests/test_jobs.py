"""The queue manners: identity jobs wait for renders, and never stop anything but themselves."""
import tempfile
import unittest

from identity_studio import api, jobs as J
from identity_studio.storage import Store

PID = "abcdef123456"
GRAPH = {"1": {"class_type": "Anything", "inputs": {}}}


class FakeComfy:
    """Just enough of ComfyUI: a running list, a waiting list, a history, and a log of what was asked."""

    def __init__(self):
        self.running, self.pending, self.done, self.log = [], [], {}, []
        self.down = False
        self.n = 0
        self.uploads = {}
        self.picture = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x04\x00\x00\x00\x04\x00" + b"\x00" * 20

    def _up(self):
        if self.down:
            raise J.ComfyDown("down")

    def queue(self):
        self._up(); return list(self.running), list(self.pending)

    def submit(self, graph):
        self._up(); self.n += 1; pid = f"ident-{self.n}"; self.pending.append(pid); self.log.append(("submit", pid)); return pid

    def history(self, pid):
        self._up(); return self.done.get(pid)

    def remove(self, pid):
        self._up(); self.log.append(("remove", pid))
        if pid in self.pending: self.pending.remove(pid)

    def interrupt(self, pid):
        self._up(); self.log.append(("interrupt", pid))
        if pid in self.running: self.running.remove(pid)

    def upload(self, name, data):
        self._up(); self.uploads[name] = data; self.log.append(("upload", name)); return name

    def view(self, file):
        return self.picture

    # helpers for the tests
    def begin(self, pid): self.pending.remove(pid); self.running.append(pid)
    def finish(self, pid, record=None):
        self.running.remove(pid)
        self.done[pid] = record or {"status": {"status_str": "success"}, "outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}}
    def clear_all(self): self.running, self.pending = [], []          # what "Stop all renders" does


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.comfy = FakeComfy()
        self.jobs = J.Jobs(self.tmp.name, self.comfy)
        self.jobs.start = lambda: None            # tests call tick() themselves; no background thread

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, job):
        return next(j for j in self.jobs.list() if j["id"] == job["id"])["state"]

    def test_waits_while_a_render_is_running_or_queued(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.comfy.running, self.comfy.pending = ["video-1"], ["video-2"]
        for _ in range(3):
            self.jobs.tick()
        self.assertEqual(self.state(job), J.WAITING)
        self.assertEqual(self.comfy.log, [])                                  # nothing was sent to ComfyUI
        self.assertIn("2 jobs", self.jobs.note)
        self.comfy.running = []; self.jobs.tick()
        self.assertEqual(self.state(job), J.WAITING)                          # one render still queued
        self.comfy.pending = []; self.jobs.tick()
        self.assertEqual(self.state(job), J.SUBMITTED)

    def test_only_one_identity_job_is_in_comfy_at_a_time(self):
        a, b = (self.jobs.add(PID, "concept", n, GRAPH) for n in "ab")
        self.jobs.tick(); self.jobs.tick()
        self.assertEqual([self.state(a), self.state(b)], [J.SUBMITTED, J.WAITING])
        self.comfy.begin("ident-1"); self.jobs.tick()
        self.assertEqual([self.state(a), self.state(b)], [J.RUNNING, J.WAITING])
        self.comfy.finish("ident-1"); self.jobs.tick()
        self.assertEqual(self.state(a), J.DONE)
        self.assertEqual(self.jobs.list()[0]["outputs"][0]["filename"], "a.png")
        self.assertEqual(self.state(b), J.SUBMITTED)

    def test_a_render_queued_in_between_goes_first_for_the_next_identity_job(self):
        a, b = (self.jobs.add(PID, "concept", n, GRAPH) for n in "ab")
        self.jobs.tick(); self.comfy.begin("ident-1"); self.comfy.pending.append("video-9")
        self.comfy.finish("ident-1"); self.jobs.tick()
        self.assertEqual([self.state(a), self.state(b)], [J.DONE, J.WAITING])

    def test_cancel_never_touches_someone_elses_job(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.jobs.tick()
        self.comfy.running = ["video-1"]                                      # a render is running; ours is queued behind it
        self.jobs.cancel(job["id"])
        self.assertEqual(self.state(job), J.CANCELLED)
        self.assertEqual(self.comfy.log[1:], [("remove", "ident-1")])         # removed ours, no interrupt
        self.assertEqual(self.comfy.running, ["video-1"])

    def test_cancel_interrupts_only_when_ours_is_the_running_job(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.jobs.tick(); self.comfy.begin("ident-1"); self.jobs.tick()
        self.jobs.cancel(job["id"])
        self.assertIn(("interrupt", "ident-1"), self.comfy.log)
        waiting = self.jobs.add(PID, "concept", "two", GRAPH)
        self.jobs.cancel(waiting["id"])
        self.assertEqual(len(self.comfy.log), 3)                              # a waiting job never reaches ComfyUI at all

    def test_stop_all_renders_marks_the_job_stopped_and_it_does_not_restart_itself(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.jobs.tick(); self.comfy.begin("ident-1"); self.comfy.clear_all()
        for _ in range(3):
            self.jobs.tick()
        self.assertEqual(self.state(job), J.STOPPED)
        self.assertEqual(len([x for x in self.comfy.log if x[0] == "submit"]), 1)
        self.jobs.retry(job["id"]); self.jobs.tick()
        self.assertEqual(self.state(job), J.SUBMITTED)

    def test_a_failed_job_keeps_comfys_reason(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.jobs.tick(); self.comfy.begin("ident-1")
        self.comfy.finish("ident-1", {"status": {"status_str": "error", "messages": [["execution_error", {"node_type": "KSampler", "exception_message": "out of memory"}]]}})
        self.jobs.tick()
        self.assertEqual(self.jobs.list()[0]["error"], "KSampler: out of memory")
        self.assertEqual(self.state(job), J.FAILED)

    def test_comfy_being_down_changes_nothing(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.comfy.down = True
        self.jobs.tick()
        self.assertEqual(self.state(job), J.WAITING)
        self.assertFalse(self.jobs.status()["comfy"])
        self.jobs.cancel(job["id"])                                           # still possible
        self.assertEqual(self.state(job), J.CANCELLED)

    def test_jobs_survive_a_restart_and_the_graph_is_never_sent_to_the_browser(self):
        job = self.jobs.add(PID, "concept", "one", GRAPH)
        self.jobs.tick()
        again = J.Jobs(self.tmp.name, self.comfy)
        self.assertEqual(again.list()[0]["prompt_id"], "ident-1")
        self.assertNotIn("graph", again.list()[0])
        self.assertNotIn("graph", job)
        self.comfy.begin("ident-1"); self.comfy.finish("ident-1"); again.tick()
        self.assertEqual(again.list()[0]["state"], J.DONE)

    def test_bad_input_is_refused(self):
        for args in (("../x", "c", "l", GRAPH), (PID, "c", "l", {}), (PID, "c", "l", "graph")):
            with self.assertRaises(ValueError):
                self.jobs.add(*args)
        with self.assertRaises(ValueError):
            self.jobs.cancel("000000000000")


class JobApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.comfy = FakeComfy()
        api.use_store(Store(self.tmp.name), self.comfy)
        api.jobs().start = lambda: None

    def tearDown(self):
        api.use_store(None); self.tmp.cleanup()

    def test_routes_and_no_way_to_post_a_graph(self):
        p = api.handle("POST", "/api/identity/projects", payload={"name": "Icon"})
        job = api.jobs().add(p["id"], "concept", "one", GRAPH)
        self.comfy.running = ["video-1"]; api.jobs().tick()
        q = api.handle("GET", "/api/identity/queue")
        self.assertEqual((q["comfy"], q["other_jobs"], q["identity_active"]), (True, 1, 1))
        self.assertEqual(len(api.handle("GET", "/api/identity/jobs", {"project": p["id"]})["jobs"]), 1)
        self.assertEqual(api.handle("GET", "/api/identity/jobs", {"project": "ffffffffffff"})["jobs"], [])
        with self.assertRaises(LookupError):
            api.handle("POST", "/api/identity/jobs", payload={"project_id": p["id"], "graph": GRAPH})
        with self.assertRaises(ValueError):
            api.handle("GET", "/api/identity/jobs", {"project": "../x"})
        self.assertEqual(api.handle("POST", "/api/identity/jobs/cancel", payload={"id": job["id"]})["state"], J.CANCELLED)

    def test_deleting_a_project_cancels_its_jobs(self):
        p = api.handle("POST", "/api/identity/projects", payload={"name": "Icon"})
        api.jobs().add(p["id"], "concept", "one", GRAPH); api.jobs().tick()
        api.handle("POST", "/api/identity/projects/delete", payload={"id": p["id"]})
        self.assertEqual(api.jobs().list()[0]["state"], J.CANCELLED)
        self.assertIn(("remove", "ident-1"), self.comfy.log)


if __name__ == "__main__":
    unittest.main()
