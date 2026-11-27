"""Providers, admission, order and stopping (3d_Phase_19, 3d_Phase_20, 3d_Phase_21). The AI providers here are stand-ins."""
import shutil
import tempfile
import threading
import unittest

from studio3d import jobs


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [1000.0]
        self.ran = []
        self.reg = jobs.Registry()
        self.reg.register(jobs.Provider("reader", "Director FBX reader", "1", ["geometry.import"], lambda r, c: self.ran.append(r["label"]) or {"artifacts": ["a1"]}))
        for name in ("A", "B"):
            self.reg.register(jobs.Provider("model" + name, "Model " + name, "1.0", ["geometry.generate"], lambda r, c: self.ran.append(r["label"]) or {"artifacts": [r["label"]]}, kind="ai", model=name, rank=2 if name == "A" else 1))
        self.ledger = jobs.Ledger(self.dir, self.reg, clock=self.tick)

    def tick(self):
        self.now[0] += 1
        return self.now[0]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Providers(Base):
    def test_auto_takes_the_best_ready_provider_and_says_why_others_are_out(self):   # MPV-002, MPV-007
        self.assertEqual(self.reg.select("geometry.generate").id, "modelA")
        self.assertEqual(self.reg.select("geometry.generate", "modelB").id, "modelB")              # a compatible override
        with self.assertRaises(jobs.Refused) as e:
            self.reg.select("geometry.generate", "reader")                                         # an override that cannot do it
        self.assertEqual(e.exception.kind, "unsupported")
        self.reg.providers["modelA"].qualified = False                                             # updated but not yet tested on this machine
        self.assertEqual(self.reg.select("geometry.generate").id, "modelB")
        self.reg.providers["modelB"].enabled = False
        with self.assertRaises(jobs.Refused) as e:
            self.reg.select("geometry.generate")
        self.assertIn("has not passed a test", str(e.exception)); self.assertIn("switched off", str(e.exception))

    def test_capabilities_with_nothing_behind_them_say_so(self):
        table = {t["capability"]: t for t in self.reg.table()}
        self.assertTrue(table["geometry.import"]["available"])
        self.assertEqual((table["texture.generate"]["available"], table["texture.generate"]["providers"]), (False, []))
        self.assertIn("No provider is set up", table["character.landmarks"]["reason"])
        with self.assertRaises(jobs.Refused):
            self.ledger.submit("uv.unwrap", {})
        self.assertEqual(self.ledger.requests, [])


class Admission(Base):
    def test_the_same_request_twice_is_one_request_and_a_different_one_is_refused(self):   # GQV-001
        a = self.ledger.submit("geometry.generate", {}, key="k1", scope="geometry", label="first")
        self.assertEqual(self.ledger.submit("geometry.generate", {}, key="k1", scope="geometry")["id"], a["id"])
        with self.assertRaises(jobs.Refused) as e:
            self.ledger.submit("geometry.generate", {}, key="k2", scope="geometry", label="second")
        self.assertEqual((e.exception.kind, e.exception.request["id"], len(self.ledger.requests)), ("locked", a["id"], 1))
        self.ledger.submit("geometry.import", {}, label="import")                                  # unrelated work may wait
        self.ledger.run_pending()
        self.assertEqual(self.ledger.submit("geometry.generate", {}, key="k2", scope="geometry", label="second")["state"], "waiting")   # the lock went with the finish

    def test_order_keeps_the_loaded_model_before_switching(self):                    # GQV-007
        for label, override in (("A1", "modelA"), ("B1", "modelB"), ("A2", "modelA")):
            self.ledger.submit("geometry.generate", {}, override=override, label=label)
        self.assertEqual([r["label"] for r in self.ledger.run_pending()], ["A1", "A2", "B1"])
        self.assertEqual(self.ledger.loaded, "B")

    def test_one_job_at_a_time(self):                                                # HRV-001
        started, release, peak = threading.Event(), threading.Event(), []
        running = [0]

        def slow(r, c):
            running[0] += 1; peak.append(running[0]); started.set(); release.wait(5); running[0] -= 1
            return {}
        self.reg.register(jobs.Provider("slow", "Slow", "1", ["geometry.generate"], slow, kind="ai", model="S", rank=9))
        self.ledger.submit("geometry.generate", {}, label="one"); self.ledger.submit("geometry.import", {}, label="heavy")
        t = threading.Thread(target=self.ledger.run_next); t.start(); started.wait(5)
        self.assertIsNone(self.ledger.run_next())                                                  # the slot is held
        self.assertEqual([r["state"] for r in self.ledger.requests], ["running", "waiting"])
        release.set(); t.join(5)
        self.assertEqual((self.ledger.run_next()["label"], max(peak)), ("heavy", 1))


class Outcomes(Base):
    def test_a_failure_is_contained_and_classified(self):                            # MPV-004, GQM-007
        def bad(r, c):
            raise ValueError("The output had no mesh in it.")
        self.reg.register(jobs.Provider("bad", "Bad", "1", ["geometry.generate"], bad, kind="ai", model="X", rank=9))
        r = self.ledger.submit("geometry.generate", {}, scope="geometry")
        self.ledger.run_pending()
        self.assertEqual((r["state"], r["error"]["class"], r["error"]["message"], r["result"]), ("failed", "invalid input", "The output had no mesh in it.", None))
        self.assertIsNone(self.ledger.locked("geometry"))
        again = self.ledger.retry(r["id"])
        self.assertNotEqual(again["id"], r["id"]); self.assertEqual(again["state"], "waiting")

    def test_cancelling(self):                                                       # GQV-003, GQV-006, GQV-008
        waiting = self.ledger.submit("geometry.import", {}, label="never runs")
        self.assertEqual(self.ledger.cancel(waiting["id"])["state"], "cancelled")
        started, release = threading.Event(), threading.Event()

        def stubborn(r, c):
            started.set(); release.wait(5)
            return {"artifacts": ["late"]}                                                         # ignores the request to stop
        self.reg.register(jobs.Provider("stub", "Stubborn", "1", ["geometry.generate"], stubborn, kind="ai", model="S", rank=9))
        r = self.ledger.submit("geometry.generate", {}, scope="geometry")
        t = threading.Thread(target=self.ledger.run_next); t.start(); started.wait(5)
        self.assertEqual(self.ledger.cancel(r["id"])["state"], "cancelling")
        self.now[0] += 60; self.ledger.check_stops()
        self.assertEqual(r["state"], "awaiting force-stop confirmation")
        self.assertEqual(self.ledger.force(r["id"], False)["state"], "awaiting force-stop confirmation")          # declining forces nothing
        self.assertIn("cannot be force-stopped", self.ledger.force(r["id"], True)["stage"])
        self.assertIsNotNone(self.ledger.locked("geometry")); self.assertIsNone(self.ledger.run_next())           # the slot stays held
        release.set(); t.join(5)
        self.assertEqual((r["state"], r["result"]), ("cancelled", None))                                          # what arrived late was discarded
        self.assertEqual(self.ran, [])

    def test_a_restart_marks_running_work_interrupted_and_keeps_waiting_work(self):  # GQV-004
        a = self.ledger.submit("geometry.generate", {}, scope="geometry", label="was running")
        b = self.ledger.submit("geometry.import", {}, label="had not started")
        a["state"] = "running"; self.ledger._save()
        again = jobs.Ledger(self.dir, self.reg, clock=self.tick)
        states = {r["label"]: r["state"] for r in again.requests}
        self.assertEqual(states, {"was running": "interrupted", "had not started": "waiting"})
        self.assertIsNone(again.locked("geometry"))
        self.assertEqual([r["label"] for r in again.run_pending()], ["had not started"])           # nothing was rerun by itself
        self.assertEqual(self.ran, ["had not started"])

    def test_a_changed_provider_is_not_silently_swapped_in(self):                    # MPA-004
        r = self.ledger.submit("geometry.generate", {}, override="modelB")
        self.reg.register(jobs.Provider("modelB", "Model B", "2.0", ["geometry.generate"], lambda r, c: {}, kind="ai", model="B2"))
        self.ledger.run_pending()
        self.assertEqual((r["state"], r["error"]["class"]), ("failed", "unavailable"))

    def test_deleted_work_leaves_no_history(self):                                   # AVP-005
        self.ledger.submit("geometry.import", {}, asset="asset_1", label="x"); self.ledger.run_pending()
        self.assertEqual(len(self.ledger.requests), 1)
        self.ledger.forget(artifacts=["a1"])
        self.assertEqual(self.ledger.requests, [])


if __name__ == "__main__":
    unittest.main()
