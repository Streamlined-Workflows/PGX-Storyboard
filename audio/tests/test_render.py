"""Exports, checked by measuring the files they make: where each sound lands, how loud, how long."""
import array
import math
import os
import shutil
import struct
import tempfile
import time
import unittest
import wave
import zipfile

from audio import api, media, render, schemas
from audio.exports import Exporter
from audio.storage import Library

R = 48000


def wav(samples, rate=R, channels=1):
    """A 16-bit WAV file, as bytes, from samples in -1..1."""
    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(round(32767 * s))) * channels for s in samples))
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


def flat(seconds, level=0.5, rate=R):
    return wav([level] * int(seconds * rate), rate)


def sine(seconds, hz=440.0, level=0.5, rate=R):
    return wav([level * math.sin(2 * math.pi * hz * i / rate) for i in range(int(seconds * rate))], rate)


def ramp(seconds, rate=R):
    n = int(seconds * rate)
    return wav([i / n for i in range(n)], rate)


def loudness(samples):
    return math.sqrt(sum(s * s for s in samples) / max(1, len(samples)))


def db(ratio):
    return 20 * math.log10(max(ratio, 1e-9))


@unittest.skipUnless(media.has_ffmpeg(), "needs ffmpeg")
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(self.tmp.name)
        self.exp = Exporter(self.lib)
        api.use_library(self.lib)
        self.n = 0

    def tearDown(self):
        api.use_library(None); self.tmp.cleanup()

    def sound(self, data, name=None):
        self.n += 1
        return self.lib.add(name or f"s{self.n}.wav", data, "p1")[0]["id"]

    def timeline(self, *tracks, **more):
        made = []
        for t in tracks:
            t = dict(t) if isinstance(t, dict) else {"clips": t}
            t["clips"] = [dict(c) for c in t["clips"]]
            made.append(t)
        return schemas.clean_timeline(dict({"project_id": "p1", "sample_rate": R, "tracks": made}, **more))

    def export(self, timeline, fmt="wav", bits=16, rate=None, **how):
        files = {a: (self.lib.file(a)[0], self.lib.load(a)["file"]["format"], self.lib.load(a)["file"]["channels"]) for a in schemas.assets_used(timeline)}
        job = render.build(timeline, files, how.pop("room", None) or (lambda size, decay: self.exp.room(size, decay, R)), out_rate=rate, **how)
        self.n += 1
        target = os.path.join(self.tmp.name, f"out{self.n}.{fmt}")
        self.result = render.run(job, target, fmt, bits)
        self.path = target
        return render.read(target)


class Placement(Base):
    def test_a_clip_lands_on_exactly_the_sample_it_was_placed_at(self):
        a = self.sound(flat(0.5))
        rate, left, right = self.export(self.timeline([{"asset_id": a, "start": 12345, "length": 24000}]))
        self.assertEqual((rate, len(left)), (R, 12345 + 24000))                 # as long as the timeline, to the sample
        self.assertEqual(max(abs(s) for s in left[:12345]), 0)
        self.assertAlmostEqual(left[12345], 0.5, 3)
        self.assertAlmostEqual(left[12345 + 23999], 0.5, 3)
        self.assertEqual(list(left), list(right))                              # a mono sound plays equally on both sides

    def test_the_part_of_the_sound_used_starts_where_the_clip_says(self):
        for kind in ("wav", "flac"):
            data = ramp(5.0)
            if kind == "flac":
                src = os.path.join(self.tmp.name, "r.wav"); open(src, "wb").write(data)
                os.system(f"ffmpeg -v error -y -i {src} {src[:-4]}.flac")
                data = open(src[:-4] + ".flac", "rb").read()
            a = self.sound(data, "ramp." + kind)
            offset = 3 * R + 777                                                # far enough in that the file is jumped into, not read from the start
            _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 100, "offset": offset, "length": 4800}]))
            self.assertAlmostEqual(left[100], offset / (5.0 * R), 4, kind)
            self.assertAlmostEqual(left[100 + 4799], (offset + 4799) / (5.0 * R), 4, kind)

    def test_a_sound_at_another_rate_is_still_placed_exactly(self):
        a = self.sound(flat(1.0, 0.5, 44100))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 5000, "length": 20000}]))
        self.assertEqual(len(left), 25000)
        self.assertEqual(max(abs(s) for s in left[:4990]), 0)
        self.assertAlmostEqual(left[5050], 0.5, 2)                               # at full level within a few samples of the start

    def test_a_clip_longer_than_its_sound_is_padded_with_silence_not_stretched(self):
        a = self.sound(flat(0.25))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 0, "length": 24000}]))
        self.assertEqual(len(left), 24000)
        self.assertAlmostEqual(left[11999], 0.5, 3)
        self.assertEqual(max(abs(s) for s in left[12000:]), 0)

    def test_the_same_timeline_gives_the_same_file_every_time(self):
        a, b = self.sound(sine(1.0)), self.sound(sine(1.0, 660))
        t = self.timeline({"clips": [{"asset_id": a, "start": 0, "length": R, "fade_in": 4800}], "effects": [{"type": "reverb"}]},
                          [{"asset_id": b, "start": 24000, "length": R, "speed": 1.5}])
        self.export(t); first = open(self.path, "rb").read()
        self.export(t); second = open(self.path, "rb").read()
        self.assertEqual(first, second)


class Levels(Base):
    def test_overlapping_sounds_add_together_and_nothing_is_turned_down_to_make_room(self):
        a = self.sound(flat(1.0, 0.25))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 0, "length": R}], [{"asset_id": a, "start": 24000, "length": R}]))
        self.assertAlmostEqual(left[1000], 0.25, 3)
        self.assertAlmostEqual(left[30000], 0.5, 3)
        self.assertAlmostEqual(left[60000], 0.25, 3)

    def test_clip_gain_track_volume_and_master_volume_each_apply(self):
        a = self.sound(flat(1.0, 0.5))
        half = db(0.5)
        t = self.timeline({"clips": [{"asset_id": a, "start": 0, "length": R, "gain_db": half}], "volume_db": half}, master={"volume_db": half})
        _, left, _ = self.export(t)
        self.assertAlmostEqual(left[1000], 0.0625, 3)

    def test_fades_run_in_a_straight_line_from_and_to_silence(self):
        a = self.sound(flat(1.0, 0.5))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 1000, "length": R, "fade_in": 4800, "fade_out": 9600}]))
        self.assertAlmostEqual(left[1000], 0.0, 3)
        self.assertAlmostEqual(left[1000 + 2400], 0.25, 2)
        self.assertAlmostEqual(left[1000 + 4800], 0.5, 3)
        self.assertAlmostEqual(left[1000 + R - 4800], 0.25, 2)
        self.assertAlmostEqual(left[1000 + R - 1], 0.0, 3)

    def test_mute_solo_and_muted_clips(self):
        a = self.sound(flat(1.0, 0.25))
        clip = {"asset_id": a, "start": 0, "length": R}
        level = lambda *tracks: round(self.export(self.timeline(*tracks))[1][1000], 3)
        self.assertEqual(level({"clips": [clip]}, {"clips": [clip], "mute": True}), 0.25)
        self.assertEqual(level({"clips": [clip]}, {"clips": [clip]}, {"clips": [clip], "solo": True}), 0.25)
        self.assertEqual(level({"clips": [clip], "solo": True, "mute": True}, {"clips": [clip]}), 0.25)        # solo wins over mute
        self.assertEqual(level({"clips": [clip, dict(clip, muted=True)]}), 0.25)

    def test_balance_lowers_the_other_side_and_leaves_this_side_alone(self):
        a = self.sound(flat(1.0, 0.5))
        _, left, right = self.export(self.timeline({"clips": [{"asset_id": a, "start": 0, "length": R}], "pan": 1}))
        self.assertEqual((round(left[1000], 3), round(right[1000], 3)), (0.0, 0.5))
        _, left, right = self.export(self.timeline({"clips": [{"asset_id": a, "start": 0, "length": R}], "pan": -0.5}))
        self.assertEqual((round(left[1000], 3), round(right[1000], 3)), (0.5, 0.25))

    def test_the_loudest_point_is_measured_before_anything_is_clipped(self):
        a = self.sound(flat(1.0, 0.75))
        clip = {"asset_id": a, "start": 0, "length": R}
        self.export(self.timeline([clip]))
        self.assertAlmostEqual(self.result["peak_db"], db(0.75), 1)
        self.export(self.timeline([clip], [clip]))
        self.assertAlmostEqual(self.result["peak_db"], db(1.5), 1)              # over full level, and reported as such


class Changes(Base):
    def test_reverse_plays_the_used_part_backwards(self):
        a = self.sound(ramp(1.0))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 0, "offset": 0, "length": 24000, "reverse": True}]))
        self.assertAlmostEqual(left[0], 23999 / R, 3)
        self.assertAlmostEqual(left[23999], 0.0, 3)

    def test_speed_changes_how_much_sound_fits_without_changing_its_pitch(self):
        a = self.sound(sine(2.0, 440))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 0, "length": R, "speed": 2}]))
        self.assertEqual(len(left), R)                                         # still exactly as long as the clip
        self.assertAlmostEqual(self.pitch(left[4800:-4800]), 440, delta=6)
        self.assertGreater(loudness(left[-9600:-2400]), 0.25)                   # sound right to the end: two seconds were fitted into one

    def test_pitch_changes_the_note_without_changing_the_length(self):
        a = self.sound(sine(1.0, 440))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 0, "length": R, "pitch": 12}]))
        self.assertEqual(len(left), R)
        self.assertAlmostEqual(self.pitch(left[4800:-4800]), 880, delta=12)
        self.assertGreater(loudness(left[-9600:-2400]), 0.25)

    def pitch(self, samples):
        crossings = sum(1 for x, y in zip(samples, samples[1:]) if x < 0 <= y)
        return crossings * R / len(samples)

    def test_eq_raises_what_it_is_aimed_at_and_leaves_the_rest(self):
        low, mid = self.sound(sine(1.0, 50)), self.sound(sine(1.0, 2000))
        fx = [{"type": "eq", "params": {"low_db": 12, "low_hz": 200}}]
        for asset, expect in ((low, 12), (mid, 0)):
            _, plain, _ = self.export(self.timeline([{"asset_id": asset, "start": 0, "length": R, "gain_db": -20}]))
            _, shaped, _ = self.export(self.timeline([{"asset_id": asset, "start": 0, "length": R, "gain_db": -20, "effects": fx}]))
            self.assertAlmostEqual(db(loudness(shaped[9600:]) / loudness(plain[9600:])), expect, delta=1.0)

    def test_an_effect_that_is_switched_off_or_set_flat_changes_nothing(self):
        a = self.sound(sine(1.0))
        clip = {"asset_id": a, "start": 0, "length": R}
        _, plain, _ = self.export(self.timeline([clip]))
        off = [{"type": "eq", "on": False, "params": {"low_db": 12}}, {"type": "eq"}, {"type": "compressor", "on": False}, {"type": "reverb", "params": {"mix": 0}}]
        _, same, _ = self.export(self.timeline({"clips": [dict(clip, effects=off)], "effects": off}, master={"effects": off}))
        self.assertEqual(list(plain), list(same))

    def test_the_compressor_turns_loud_sound_down_and_makeup_brings_it_back(self):
        a = self.sound(sine(2.0, 440, 0.9))
        clip = {"asset_id": a, "start": 0, "length": 2 * R}
        squeeze = {"type": "compressor", "params": {"threshold_db": -30, "ratio": 10, "attack_ms": 1, "release_ms": 50}}
        _, plain, _ = self.export(self.timeline([clip]))
        _, quiet, _ = self.export(self.timeline({"clips": [clip], "effects": [squeeze]}))
        _, lifted, _ = self.export(self.timeline({"clips": [clip], "effects": [dict(squeeze, params=dict(squeeze["params"], makeup_db=12))]}))
        drop = db(loudness(quiet[R:]) / loudness(plain[R:]))
        self.assertLess(drop, -12)
        self.assertAlmostEqual(db(loudness(lifted[R:]) / loudness(quiet[R:])), 12, delta=0.5)


class Reverb(Base):
    def room_file(self, at):
        """A room that is a single click `at` samples in: what comes out is what went in, that much later."""
        path = os.path.join(self.tmp.name, f"click{at}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(R)
            w.writeframes(struct.pack("<hh", 0, 0) * at + struct.pack("<hh", 32767, 32767) + struct.pack("<hh", 0, 0) * 50)
        return lambda size, decay: path

    def test_the_room_is_used_exactly_as_made_with_no_delay_and_no_change_of_level(self):
        a = self.sound(flat(0.5, 0.5))
        clip = {"asset_id": a, "start": 2000, "length": 12000, "effects": [{"type": "reverb", "params": {"mix": 1, "size": 0, "decay_s": 0.1}}]}
        _, left, _ = self.export(self.timeline([clip]), room=self.room_file(0))
        self.assertEqual(max(abs(s) for s in left[:2000]), 0)
        self.assertAlmostEqual(left[2000], 0.5, 3)
        self.assertAlmostEqual(left[2000 + 11999], 0.5, 3)
        _, left, _ = self.export(self.timeline([clip]), room=self.room_file(300))
        self.assertEqual(max(abs(s) for s in left[:2300]), 0)
        self.assertAlmostEqual(left[2300], 0.5, 3)
        self.assertAlmostEqual(left[2000 + 12299], 0.5, 3)                       # the sound carries on past the clip's end

    def test_mix_sets_how_much_is_room_and_how_much_is_the_sound_itself(self):
        a = self.sound(flat(0.5, 0.5))
        clip = {"asset_id": a, "start": 0, "length": 12000, "effects": [{"type": "reverb", "params": {"mix": 0.25, "size": 0, "decay_s": 0.1}}]}
        _, left, _ = self.export(self.timeline([clip]), room=self.room_file(300))
        self.assertAlmostEqual(left[100], 0.375, 3)                              # three quarters of the sound, the room not yet arrived
        self.assertAlmostEqual(left[5000], 0.5, 3)                               # both
        self.assertAlmostEqual(left[12100], 0.125, 3)                            # only the room is left

    def test_the_export_runs_on_until_the_reverb_has_died_away(self):
        a = self.sound(sine(0.5))
        clip = {"asset_id": a, "start": 0, "length": 24000}
        fx = [{"type": "reverb", "params": {"mix": 0.5, "size": 0.5, "decay_s": 1.0}}]
        _, plain, _ = self.export(self.timeline([clip]))
        _, wet, _ = self.export(self.timeline({"clips": [clip], "effects": fx}))
        self.assertEqual(len(plain), 24000)
        self.assertEqual(len(wet), 24000 + int(round((1.0 + 0.5 * render.PREDELAY) * R)))
        self.assertGreater(loudness(wet[24000:30000]), 0.001)                    # still ringing after the clip
        self.assertLess(loudness(wet[-2400:]), loudness(wet[24000:26400]) / 20)  # and all but gone by the end

    def test_the_room_sound_is_the_same_every_time_and_neither_adds_nor_removes_loudness(self):
        one = render.impulse(os.path.join(self.tmp.name, "a"), 0.3, 1.5, R)
        two = render.impulse(os.path.join(self.tmp.name, "b"), 0.3, 1.5, R)
        self.assertEqual(open(one, "rb").read(), open(two, "rb").read())
        _, left, right = render.read(one)
        self.assertAlmostEqual(sum(s * s for s in left), 1.0, 3)
        self.assertAlmostEqual(sum(s * s for s in right), 1.0, 3)
        self.assertEqual(len(left), int(0.3 * render.PREDELAY * R) + int(1.5 * R))


class Output(Base):
    def test_a_range_is_exactly_the_part_asked_for(self):
        a = self.sound(ramp(1.0))
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 10000, "length": R}]), span=(20000, 30000))
        self.assertEqual(len(left), 10000)
        self.assertAlmostEqual(left[0], 10000 / R, 3)
        _, left, _ = self.export(self.timeline([{"asset_id": a, "start": 10000, "length": R}]), span=(50000, 70000))
        self.assertEqual(len(left), 20000)                                      # a range past the end is filled with silence
        self.assertEqual(max(abs(s) for s in left[8000:]), 0)

    def test_formats_and_rates(self):
        a = self.sound(sine(1.0))
        t = self.timeline([{"asset_id": a, "start": 0, "length": R}])
        rate, left, _ = self.export(t, rate=44100)
        self.assertEqual((rate, len(left)), (44100, 44100))
        self.export(t, bits=24)
        with wave.open(self.path) as w:
            self.assertEqual((w.getsampwidth(), w.getnframes()), (3, R))
        rate, left, _ = self.export(t, "flac", 24)
        self.assertEqual((rate, len(left)), (R, R))
        self.assertAlmostEqual(loudness(left), 0.5 / math.sqrt(2), 3)
        if render.features()["mp3"]:
            rate, left, _ = self.export(t, "mp3")
            self.assertEqual(rate, R)
            self.assertAlmostEqual(len(left) / R, 1.0, delta=0.06)                # MP3 adds a few hundredths of a second of padding

    def test_nothing_to_export_says_so(self):
        with self.assertRaises(ValueError):
            self.export(self.timeline())


class Jobs(Base):
    def wait(self, record):
        for _ in range(600):
            record = self.exp.load("p1", record["id"])
            if record["state"] not in ("waiting", "running"):
                return record
            time.sleep(0.05)
        self.fail("the export never finished")

    def saved(self, *tracks, **more):
        return self.lib.save_timeline("p1", dict({"tracks": list(tracks)}, **more))

    def test_a_full_mix_through_the_api(self):
        a = self.sound(flat(1.0, 0.25))
        self.saved({"name": "Music", "clips": [{"asset_id": a, "start": 0, "length": R}]})
        record = api.handle("POST", "/api/audio/export", payload={"project": "p1", "format": "flac", "bits": 24, "name": "../My mix?"})
        self.assertEqual((record["state"], record["name"], record["bits"], record["sample_rate"]), ("waiting", "My mix", 24, R))
        done = self._wait_api(record)
        self.assertEqual((done["state"], done["progress"], done["seconds"], done["note"]), ("done", 1.0, 1.0, ""))
        self.assertAlmostEqual(done["peak_db"], db(0.25), 1)
        got = api.handle("GET", "/api/audio/export/file", {"project": "p1", "id": done["id"]})
        self.assertEqual((got.content_type, os.path.getsize(got.path)), ("audio/flac", done["bytes"]))
        self.assertEqual(len(render.read(got.path)[1]), R)
        self.assertEqual([e["id"] for e in api.handle("GET", "/api/audio/exports", {"project": "p1"})["exports"]], [done["id"]])
        api.handle("POST", "/api/audio/export/remove", payload={"project": "p1", "id": done["id"]})
        self.assertEqual(os.listdir(os.path.join(self.lib.root, "exports", "p1")), [])

    def _wait_api(self, record):
        self.exp = api.exporter()
        return self.wait(record)

    def test_stems_are_one_file_per_audible_track_all_the_same_length(self):
        a = self.sound(flat(1.0, 0.25))
        self.saved({"name": "Music", "clips": [{"asset_id": a, "start": 0, "length": R}]},
                   {"name": "Voice / lead", "volume_db": db(0.5), "clips": [{"asset_id": a, "start": 24000, "length": 12000}]},
                   {"name": "Muted", "mute": True, "clips": [{"asset_id": a, "start": 0, "length": R}]},
                   {"name": "Empty", "clips": []}, master={"volume_db": -20})
        done = self.wait(self.exp.start("p1", {"what": "stems"}))
        self.assertEqual(done["state"], "done", done["note"])
        self.assertTrue(done["file"].endswith(".zip"))
        out = os.path.join(self.tmp.name, "unzipped")
        with zipfile.ZipFile(self.exp.file("p1", done["id"])[0]) as z:
            self.assertEqual(z.namelist(), ["01 Music.wav", "02 Voice  lead.wav"])
            z.extractall(out)
        _, music, _ = render.read(os.path.join(out, "01 Music.wav"))
        _, voice, _ = render.read(os.path.join(out, "02 Voice  lead.wav"))
        self.assertEqual((len(music), len(voice)), (R, R))
        self.assertAlmostEqual(music[100], 0.25, 3)                              # the track as it sounds, before the master stage
        self.assertEqual((round(voice[100], 3), round(voice[30000], 3)), (0.0, 0.125))
        self.assertFalse(os.path.exists(os.path.join(self.lib.root, "exports", "p1", done["id"] + ".parts")))

    def test_a_mix_that_goes_over_full_level_is_reported_not_quietly_changed(self):
        a = self.sound(flat(1.0, 0.75))
        clip = {"asset_id": a, "start": 0, "length": R}
        self.saved({"clips": [clip]}, {"clips": [clip]})
        done = self.wait(self.exp.start("p1", {}))
        self.assertEqual(done["state"], "done")
        self.assertIn("3.5 dB over full level", done["note"])
        self.assertAlmostEqual(max(render.read(self.exp.file("p1", done["id"])[0])[1]), 1.0, 3)

    def test_a_range_and_the_things_that_are_refused(self):
        a = self.sound(flat(1.0, 0.25))
        self.saved({"clips": [{"asset_id": a, "start": 0, "length": R}]})
        done = self.wait(self.exp.start("p1", {"what": "range", "start": 12000, "end": 36000, "format": "wav", "sample_rate": 44100}))
        self.assertEqual((done["state"], done["seconds"], done["sample_rate"]), ("done", 0.5, 44100))
        self.assertEqual(len(render.read(self.exp.file("p1", done["id"])[0])[1]), 22050)
        for bad in ({"what": "range"}, {"what": "range", "start": 500, "end": 500}, {"what": "range", "start": 1.5, "end": 9}):
            with self.assertRaises(ValueError):
                self.exp.start("p1", bad)
        self.saved({"mute": True, "clips": [{"asset_id": a, "start": 0, "length": R}]})
        with self.assertRaises(ValueError):
            self.exp.start("p1", {})
        with self.assertRaises(ValueError):
            self.exp.file("p1", "0" * 12)
        with self.assertRaises(ValueError):
            self.exp.list("../p1")

    def test_a_missing_sound_fails_the_export_with_a_reason_and_leaves_no_file(self):
        a = self.sound(flat(1.0, 0.25))
        self.saved({"clips": [{"asset_id": a, "start": 0, "length": R}]})
        os.remove(self.lib.file(a)[0])
        done = self.wait(self.exp.start("p1", {}))
        self.assertEqual(done["state"], "failed")
        self.assertIn("missing from the library", done["note"])
        self.assertEqual([n for n in os.listdir(os.path.join(self.lib.root, "exports", "p1")) if not n.endswith(".json")], [])

    def test_an_export_cut_short_by_a_restart_is_marked_stopped(self):
        a = self.sound(flat(1.0, 0.25))
        self.saved({"clips": [{"asset_id": a, "start": 0, "length": R}]})
        done = self.wait(self.exp.start("p1", {}))
        done.update(state="running", progress=0.4); self.exp._save(done)
        fresh = Exporter(self.lib)                                              # as after the server starts again
        self.assertEqual([(e["state"], e["note"]) for e in fresh.list("p1")], [("stopped", "The server restarted before this finished.")])


if __name__ == "__main__":
    unittest.main()
