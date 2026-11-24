"""The speech service and the model list's side of it, with a stand-in for the model itself.

The real models need the server's graphics card, so these tests cover everything around them: what is
downloaded and when, loading one model at a time, letting go of memory, and what is refused.
"""
import base64
import importlib.util
import json
import math
import os
import struct
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.request
import wave
from http.server import ThreadingHTTPServer

from tests import test_core            # sets DATA_DIR before the app is imported
import models
import usage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("speech_service", os.path.join(ROOT, "speech-service", "service.py"))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

# Stands in for worker.py: answers in the same way, and writes a tone instead of speech.
FAKE_WORKER = textwrap.dedent('''
    import json, math, os, struct, sys, wave
    engine, folder = sys.argv[1], sys.argv[2]
    if os.path.exists(os.path.join(folder, "broken")):
        print(json.dumps({"ready": False, "error": "RuntimeError: no kernel image is available"}), flush=True); sys.exit(1)
    print(json.dumps({"ready": True, "speakers": ["aiden", "serena"], "memory": 2100000000}), flush=True)
    for line in sys.stdin:
        r = json.loads(line)
        if "crash" in r["text"]:
            sys.exit(3)
        if "refuse" in r["text"]:
            print(json.dumps({"ok": False, "error": "ValueError: cannot say that"}), flush=True); continue
        with wave.open(r["out"], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(i / 8))) for i in range(12000)))
        with open(os.path.join(folder, "last.json"), "w") as f:
            json.dump(r, f)
        print(json.dumps({"ok": True, "sample_rate": 24000, "seconds": 0.5, "took": 0.01, "memory": 2200000000}), flush=True)
''')


def tone(seconds=1.0):
    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 5))) for i in range(int(16000 * seconds))))
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        worker = os.path.join(self.tmp.name, "fake_worker.py")
        with open(worker, "w") as f:
            f.write(FAKE_WORKER)
        self.saved = {k: getattr(service, k) for k in ("MODELS_DIR", "WORKER", "PYTHON", "MING_FAILED", "MING_LOG", "published", "fetch", "_gpu")}
        service.MODELS_DIR, service.WORKER = os.path.join(self.tmp.name, "models"), worker
        service.PYTHON = {"qwen": sys.executable, "ming": sys.executable}
        service.MING_FAILED, service.MING_LOG = os.path.join(self.tmp.name, "ming.failed"), os.path.join(self.tmp.name, "ming.log")
        service._gpu = {"ok": True, "detail": "test"}
        self.fetched = []
        service.published = lambda repo: {"revision": self.revision, "bytes": 3000}
        service.fetch = self.fetch
        self.revision = "rev1"
        service.DOWNLOADS.clear(); service.MEASURED.clear()

    def tearDown(self):
        service.unload()
        for k, v in self.saved.items():
            setattr(service, k, v)
        self.tmp.cleanup()

    def fetch(self, repo, revision, target):
        self.fetched.append((repo, revision))
        with open(os.path.join(target, "weights.bin"), "wb") as f:
            f.write(b"x" * 3000)

    def install(self, mid):
        service.install(mid)
        for _ in range(200):
            if not service.DOWNLOADS.get(mid, {}).get("state") == "running":
                break
            time.sleep(0.02)
        return next(m for m in service.listing()["models"] if m["id"] == mid)


class ServiceTests(Base):
    def test_nothing_is_downloaded_until_install_is_asked_for(self):
        listed = service.listing()
        self.assertEqual([m["installed"] for m in listed["models"]], [False] * 4)
        self.assertEqual(self.fetched, [])
        with self.assertRaises(ValueError) as e:
            service.speak({"id": "qwen_design", "text": "Hello", "mode": "design", "instruct": "warm"})
        self.assertIn("not been downloaded", str(e.exception))
        self.assertEqual(self.fetched, [])
        entry = self.install("qwen_design")
        self.assertEqual(self.fetched, [("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "rev1")])
        self.assertEqual((entry["installed"], entry["revision"], entry["bytes"] >= 3000), (True, "rev1", True))

    def test_a_failed_download_says_why_and_is_not_marked_installed(self):
        def broken(repo, revision, target):
            raise OSError("connection reset")
        service.fetch = broken
        entry = self.install("ming")
        self.assertEqual((entry["installed"], entry["error"]), (False, "connection reset"))

    def test_speaking_loads_the_model_and_returns_sound(self):
        self.install("qwen_design")
        wav, facts = service.speak({"id": "qwen_design", "text": "Hello there", "mode": "design", "instruct": "A warm narrator"})
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(facts, {"seconds": 0.5, "took": 0.01, "sample_rate": 24000})
        entry = next(m for m in service.listing()["models"] if m["id"] == "qwen_design")
        self.assertEqual((entry["loaded"], entry["memory"], entry["speakers"]), (True, 2200000000, ["aiden", "serena"]))

    def test_only_one_model_is_loaded_at_a_time_and_unload_ends_its_process(self):
        self.install("qwen_design"); self.install("qwen_preset")
        service.speak({"id": "qwen_design", "text": "One", "mode": "design", "instruct": "warm"})
        first = service.loaded["process"]
        service.speak({"id": "qwen_preset", "text": "Two", "mode": "preset"})
        self.assertIsNotNone(first.poll())                               # the first model's process has ended
        self.assertEqual(service.loaded["id"], "qwen_preset")
        second = service.loaded["process"]
        self.assertTrue(service.unload())
        self.assertIsNotNone(second.poll())
        self.assertIsNone(service.loaded)
        self.assertFalse(service.unload())                               # nothing left to unload

    def test_a_copied_voice_gets_the_recording_as_a_plain_wav_and_it_is_not_kept(self):
        self.install("qwen_clone")
        service.speak({"id": "qwen_clone", "text": "Copy me", "mode": "clone", "ref_audio": base64.b64encode(tone()).decode(), "ref_text": "the words"})
        with open(os.path.join(service.folder("qwen_clone"), "last.json")) as f:
            asked = json.load(f)
        self.assertEqual((asked["mode"], asked["ref_text"], os.path.basename(asked["ref_audio"])), ("clone", "the words", "reference.wav"))
        self.assertFalse(os.path.exists(os.path.dirname(asked["ref_audio"])))     # the working folder, recording included, is gone

    def test_what_is_refused(self):
        self.install("qwen_clone"); self.install("qwen_design")
        for bad, why in (({"id": "nope", "text": "x", "mode": "design"}, "Unknown"),
                         ({"id": "qwen_clone", "text": "x", "mode": "design", "instruct": "y"}, "cannot do that"),
                         ({"id": "qwen_design", "text": "  ", "mode": "design", "instruct": "y"}, "no text"),
                         ({"id": "qwen_design", "text": "x" * 5001, "mode": "design", "instruct": "y"}, "too much text"),
                         ({"id": "qwen_design", "text": "x", "mode": "design"}, "Describe the voice"),
                         ({"id": "qwen_clone", "text": "x", "mode": "clone"}, "recording"),
                         ({"id": "qwen_clone", "text": "x", "mode": "clone", "ref_audio": base64.b64encode(b"not sound").decode()}, "could not be read"),
                         ({"id": "qwen_design", "text": "please refuse", "mode": "design", "instruct": "y"}, "cannot say that")):
            with self.assertRaises(ValueError) as e:
                service.speak(bad)
            self.assertIn(why, str(e.exception))

    def test_a_model_that_will_not_load_reports_the_reason_and_holds_nothing(self):
        self.install("ming")
        open(os.path.join(service.folder("ming"), "broken"), "w").close()
        with self.assertRaises(ValueError) as e:
            service.speak({"id": "ming", "text": "Hello", "mode": "design", "instruct": "warm"})
        self.assertIn("no kernel image is available", str(e.exception))
        self.assertIsNone(service.loaded)

    def test_a_model_that_dies_mid_sentence_is_unloaded(self):
        self.install("qwen_design")
        with self.assertRaises(ValueError) as e:
            service.speak({"id": "qwen_design", "text": "crash now", "mode": "design", "instruct": "warm"})
        self.assertIn("stopped unexpectedly", str(e.exception))
        self.assertIsNone(service.loaded)

    def test_an_engine_that_failed_to_build_is_reported_and_the_other_still_works(self):
        open(service.MING_FAILED, "w").close()
        with open(service.MING_LOG, "w") as f:
            f.write("Collecting torch\nERROR: No matching distribution found for onnxruntime\n")
        self.install("ming"); self.install("qwen_design")
        entry = next(m for m in service.listing()["models"] if m["id"] == "ming")
        self.assertFalse(entry["engine_ready"])
        self.assertIn("No matching distribution found for onnxruntime", entry["engine_problem"])
        with self.assertRaises(ValueError):
            service.speak({"id": "ming", "text": "Hello", "mode": "design", "instruct": "warm"})
        self.assertEqual(service.speak({"id": "qwen_design", "text": "Hello", "mode": "design", "instruct": "warm"})[0][:4], b"RIFF")

    def test_without_the_graphics_card_it_says_so_instead_of_trying(self):
        self.install("qwen_design")
        service._gpu = {"ok": False, "detail": "CUDA driver too old"}
        with self.assertRaises(ValueError) as e:
            service.speak({"id": "qwen_design", "text": "Hello", "mode": "design", "instruct": "warm"})
        self.assertIn("CUDA driver too old", str(e.exception))

    def test_installing_a_newer_version_unloads_the_old_one(self):
        self.install("qwen_design")
        service.speak({"id": "qwen_design", "text": "Hello", "mode": "design", "instruct": "warm"})
        self.revision = "rev2"
        entry = next(m for m in service.listing(check=True)["models"] if m["id"] == "qwen_design")
        self.assertEqual((entry["revision"], entry["published_revision"]), ("rev1", "rev2"))
        self.assertEqual(self.install("qwen_design")["revision"], "rev2")
        self.assertIsNone(service.loaded)


class ThroughTheApplication(Base):
    """models.py and usage.py talking to the real service over HTTP."""
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.urls = (models.SPEECH, usage.SPEECH)
        models.SPEECH = usage.SPEECH = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.status = dict(models.STATUS)

    def tearDown(self):
        models.SPEECH, usage.SPEECH = self.urls
        models.STATUS.clear(); models.STATUS.update(self.status)
        self.server.shutdown(); self.server.server_close()
        super().tearDown()

    def state(self, mid):
        models.check_voice(models.BY_ID[mid])
        return models.STATUS[mid]["state"], models.STATUS[mid]["detail"]

    def test_the_model_list_shows_licence_and_follows_install_and_updates(self):
        row = next(m for g in models.listing()["groups"] if g["id"] == "voice" for m in g["models"] if m["id"] == "ming")
        self.assertEqual((row["licence"], row["maker"], row["voice"], row["copies"], row["optional"]), ("MIT (commercial use allowed)", "Ant Group", True, True, True))
        state, detail = self.state("qwen_clone")
        self.assertEqual(state, "missing"); self.assertIn("Not downloaded.", detail)
        models.update_voice(models.BY_ID["qwen_clone"])
        self.assertEqual(models.STATUS["qwen_clone"]["state"], "current")
        self.assertEqual(self.state("qwen_clone")[0], "current")
        self.revision = "rev2"
        self.assertEqual(self.state("qwen_clone"), ("outdated", "Qwen/Qwen3-TTS-12Hz-1.7B-Base has published a newer version."))

    def test_test_voice_picks_what_each_model_can_do(self):
        for mid in ("qwen_design", "qwen_preset", "qwen_clone", "ming"):
            models.update_voice(models.BY_ID[mid])
        wav, did = models.test_voice("qwen_design")
        self.assertEqual(wav[:4], b"RIFF"); self.assertIn("designed from", did)
        self.assertIn("built-in speaker", models.test_voice("qwen_preset")[1])
        with self.assertRaises(ValueError) as e:
            models.test_voice("qwen_clone")
        self.assertIn("Choose a short recording", str(e.exception))
        self.assertIn("copy of the voice", models.test_voice("qwen_clone", tone(), "hello")[1])
        with self.assertRaises(ValueError):
            models.test_voice("qwen_design", tone())                     # it does not copy voices
        with self.assertRaises(ValueError):
            models.test_voice("flux2")                                   # not a speech model
        self.assertIn("measured here", self.state("ming")[1] if models.test_voice("ming") else "")

    def test_changing_tabs_and_free_memory_release_the_voice_model(self):
        models.update_voice(models.BY_ID["qwen_design"])
        models.test_voice("qwen_design")
        self.assertEqual(service.loaded["id"], "qwen_design")
        real = usage._unload_llm; usage._unload_llm = lambda: False
        try:
            comfy = lambda path, payload=None, timeout=30: {"queue_running": [], "queue_pending": []} if path == "/queue" else {}
            self.assertEqual(usage.release_for_view(comfy, "system"), {"released": [], "left": []})      # looking at memory changes nothing
            self.assertIsNotNone(service.loaded)
            self.assertIn("speech", usage.release_for_view(comfy, "audio")["released"])
            self.assertIsNone(service.loaded)
            self.assertNotIn("speech", usage.release_for_view(comfy, "audio")["released"])                # nothing was loaded this time
        finally:
            usage._unload_llm = real

    def test_with_no_speech_service_the_list_explains_and_nothing_else_breaks(self):
        models.SPEECH = usage.SPEECH = "http://127.0.0.1:9"
        state, detail = self.state("qwen_clone")
        self.assertEqual(state, "error"); self.assertIn("speech service is not running", detail)
        with self.assertRaises(ValueError):
            models.test_voice("qwen_clone", tone())
        self.assertFalse(usage._unload_speech())


if __name__ == "__main__":
    unittest.main()
