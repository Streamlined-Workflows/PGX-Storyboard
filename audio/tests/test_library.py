"""The audio library and timeline storage: real files in a temporary folder."""
import json
import math
import os
import struct
import tempfile
import unittest
import wave

from audio import api, media, schemas
from audio.storage import Conflict, Library

P = "/api/audio/"


def tone(seconds=1.0, rate=48000, channels=1, hz=440.0, level=0.5):
    """A WAV file in memory."""
    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(32767 * level * math.sin(2 * math.pi * hz * i / rate))) * channels for i in range(int(seconds * rate))))
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(self.tmp.name)
        api.use_library(self.lib)

    def tearDown(self):
        api.use_library(None); api.configure(); self.tmp.cleanup()


class AssetTests(Base):
    def test_adding_a_file_records_its_facts_and_makes_its_waveform(self):
        asset, existed = self.lib.add("C:\\songs\\My Song.wav", tone(2.0, 44100, 2), "p1", "music")
        f = asset["file"]
        self.assertFalse(existed)
        self.assertEqual((asset["name"].split("\\")[-1], f["format"], f["sample_rate"], f["channels"], f["length"]), ("My Song", "wav", 44100, 2, 88200))
        self.assertEqual((asset["kind"], asset["origin"], asset["approval"], asset["projects"]), ("music", "upload", "draft", ["p1"]))
        folder = os.path.join(self.lib.assets_dir, asset["id"])
        self.assertEqual(sorted(os.listdir(folder)), ["asset.json", "original.wav", "peaks.bin"])       # our names on disk, never the upload's
        rate, pairs = media.read_peaks(open(self.lib.peaks_file(asset["id"])[0], "rb").read())
        self.assertEqual((rate, len(pairs)), (100, 200))
        self.assertTrue(all(55 <= hi <= 64 and -65 <= lo <= -55 for lo, hi in pairs[5:-5]))            # half level is about 63 of 127

    def test_the_same_file_is_stored_once_and_shared(self):
        data = tone()
        first, _ = self.lib.add("a.wav", data, "p1")
        second, existed = self.lib.add("renamed.wav", data, "p2")
        self.assertTrue(existed)
        self.assertEqual((second["id"], second["projects"]), (first["id"], ["p1", "p2"]))
        self.assertEqual(len(os.listdir(self.lib.assets_dir)), 1)
        self.assertEqual(self.lib.remove_from(first["id"], "p1")["kept_for"], 1)                       # still used by p2
        self.assertEqual([a["id"] for a in self.lib.for_project("p2")], [first["id"]])
        self.lib.remove_from(first["id"], "p2")                                                        # now nobody uses it
        self.assertEqual(os.listdir(self.lib.assets_dir), [])
        self.assertEqual(len(os.listdir(self.lib.trash)), 1)                                           # moved, not erased

    def test_things_that_are_not_sound_leave_nothing_behind(self):
        for name, data in (("notes.txt", b"hello"), ("fake.wav", b"RIFF0000WAVEjunk"), ("empty.wav", b""), ("page.html", b"<script>alert(1)</script>")):
            with self.assertRaises(ValueError):
                self.lib.add(name, data, "p1")
        self.assertEqual(os.listdir(self.lib.assets_dir) if os.path.isdir(self.lib.assets_dir) else [], [])

    def test_the_original_is_never_changed_and_lost_peaks_are_remade(self):
        data = tone()
        asset, _ = self.lib.add("a.wav", data, "p1")
        path = self.lib.file(asset["id"])[0]
        self.lib.update(asset["id"], {"name": "Renamed", "approval": "approved", "file": {"length": 1}})
        os.remove(os.path.join(os.path.dirname(path), "peaks.bin"))
        self.lib.peaks_file(asset["id"])
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)
        after = self.lib.load(asset["id"])
        self.assertEqual((after["name"], after["approval"], after["file"]["length"]), ("Renamed", "approved", 48000))

    def test_bad_ids_cannot_reach_outside_the_library(self):
        for bad in ("../../etc", "", None, "a/b", "A" * 12):
            with self.assertRaises(ValueError):
                self.lib.load(bad)
            with self.assertRaises(ValueError):
                self.lib.file(bad)
        for bad in ("../x", "", "a/b", None):
            with self.assertRaises(ValueError):
                self.lib.timeline(bad)

    @unittest.skipUnless(media.has_ffmpeg(), "needs ffmpeg")
    def test_other_formats_are_read_with_the_audio_tools(self):
        import subprocess
        wav = os.path.join(self.tmp.name, "t.wav")
        with open(wav, "wb") as f:
            f.write(tone(1.0, 44100))
        for ext, codec in (("mp3", "libmp3lame"), ("flac", "flac")):
            out = os.path.join(self.tmp.name, "t." + ext)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", codec, out], check=True)
            with open(out, "rb") as f:
                asset, _ = self.lib.add("t." + ext, f.read(), "p1")
            self.assertEqual((asset["file"]["format"], asset["file"]["sample_rate"]), (ext, 44100))
            self.assertAlmostEqual(schemas.asset_seconds(asset), 1.0, delta=0.06)


class TimelineTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.lib.add("a.wav", tone(), "p1")[0]["id"]

    def clip(self, **k):
        return dict({"asset_id": self.a, "start": 0, "offset": 0, "length": 48000}, **k)

    def test_a_new_project_has_an_empty_timeline_and_nothing_is_written_until_saved(self):
        t = self.lib.timeline("p1")
        self.assertEqual((t["tracks"], t["sample_rate"], t["revision"]), ([], 48000, 0))
        self.assertFalse(os.path.exists(self.lib.timelines_dir))

    def test_save_reload_and_revisions(self):
        t = self.lib.save_timeline("p1", {"tracks": [{"name": "Music", "kind": "music", "clips": [self.clip(start=24000)]}]}, 0)
        self.assertEqual((t["revision"], t["project_id"]), (1, "p1"))
        t2 = self.lib.save_timeline("p1", dict(t, tracks=t["tracks"] + [{"name": "Voice"}]), 1)
        self.assertEqual((t2["revision"], len(t2["tracks"]), self.lib.timeline("p1")["tracks"][0]["clips"][0]["start"]), (2, 2, 24000))

    def test_a_stale_save_is_refused_so_one_window_cannot_undo_another(self):
        self.lib.save_timeline("p1", {"tracks": [{"name": "A"}]}, 0)
        self.lib.save_timeline("p1", {"tracks": [{"name": "A"}, {"name": "B"}]}, 1)
        with self.assertRaises(Conflict):
            self.lib.save_timeline("p1", {"tracks": []}, 1)                                            # this window still thinks it is at revision 1
        self.assertEqual(len(self.lib.timeline("p1")["tracks"]), 2)

    def test_clips_pointing_at_missing_sounds_are_dropped_and_used_sounds_join_the_project(self):
        other = self.lib.add("b.wav", tone(hz=220), "elsewhere")[0]["id"]
        t = self.lib.save_timeline("p1", {"tracks": [{"clips": [self.clip(), self.clip(asset_id=other, start=5), self.clip(asset_id="f" * 12, start=9)]}]}, 0)
        self.assertEqual([c["asset_id"] for c in t["tracks"][0]["clips"]], [self.a, other])
        self.assertEqual(sorted(self.lib.load(other)["projects"]), ["elsewhere", "p1"])

    def test_the_last_twenty_versions_are_kept_for_recovery(self):
        for i in range(25):
            t = self.lib.save_timeline("p1", {"tracks": [{"name": f"v{i}"}]})
        history = os.listdir(os.path.join(self.lib.timelines_dir, "p1.history"))
        self.assertEqual((len(history), t["revision"]), (20, 25))
        with open(os.path.join(self.lib.timelines_dir, "p1.history", sorted(history)[-1])) as f:
            self.assertEqual(json.load(f)["tracks"][0]["name"], "v23")

    def test_no_temporary_files_are_left_and_a_damaged_file_is_reported(self):
        self.lib.save_timeline("p1", {"tracks": []})
        self.assertFalse([n for n in os.listdir(self.lib.timelines_dir) if n.endswith(".tmp")])
        with open(os.path.join(self.lib.timelines_dir, "p1.json"), "w") as f:
            f.write('{"tracks": [')
        with self.assertRaises(ValueError) as e:
            self.lib.timeline("p1")
        self.assertIn("history", str(e.exception))


class ApiTests(Base):
    def test_routes(self):
        info = api.handle("GET", P + "info")
        self.assertEqual((info["sample_rate"], info["peak_rate"]), (48000, 100))
        a = api.handle("POST", P + "assets", {"project": "p1", "name": "rain.wav", "kind": "ambience"}, raw=tone())
        self.assertEqual((a["kind"], a["already_there"]), ("ambience", False))
        self.assertEqual(len(api.handle("GET", P + "assets", {"project": "p1"})["assets"]), 1)
        self.assertEqual(api.handle("GET", P + "assets", {"project": "p2"})["assets"], [])
        self.assertEqual(api.handle("GET", P + "asset/file", {"id": a["id"]}).content_type, "audio/wav")
        self.assertTrue(api.handle("GET", P + "asset/peaks", {"id": a["id"]}).path.endswith("peaks.bin"))
        self.assertEqual(api.handle("PUT", P + "asset", {"id": a["id"]}, {"name": "Heavy rain"})["name"], "Heavy rain")
        t = api.handle("PUT", P + "timeline", {"project": "p1"}, {"timeline": {"tracks": [{"clips": [{"asset_id": a["id"], "start": 0, "offset": 0, "length": 100}]}]}, "based_on": 0})
        self.assertEqual(api.handle("GET", P + "timeline", {"project": "p1"})["tracks"], t["tracks"])
        with self.assertRaises(Conflict):
            api.handle("PUT", P + "timeline", {"project": "p1"}, {"timeline": {"tracks": []}, "based_on": 7})
        for call in (("GET", P + "assets", {}), ("GET", P + "timeline", {"project": ""}), ("POST", P + "assets", {"project": "p1", "name": "x.txt"})):
            with self.assertRaises(ValueError):
                api.handle(*call, raw=b"text") if call[0] == "POST" else api.handle(*call)
        with self.assertRaises(LookupError):
            api.handle("GET", P + "nothing")

    def test_adopt_brings_in_a_projects_earlier_audio_once(self):
        song = tone(1.5)
        api.configure(project_audio=lambda pid: [("song.wav", song), ("broken.wav", b"nope")])
        out = api.handle("POST", P + "assets/adopt", payload={"project": "p1"})
        self.assertEqual((len(out["brought"]), len(out["problems"])), (1, 1))
        again = api.handle("POST", P + "assets/adopt", payload={"project": "p1"})
        self.assertEqual(again["brought"], out["brought"])                                             # the same sound, not a second copy
        self.assertEqual(len(api.handle("GET", P + "assets", {"project": "p1"})["assets"]), 1)


if __name__ == "__main__":
    unittest.main()
