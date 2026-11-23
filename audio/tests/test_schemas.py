"""The audio data model: what a browser can and cannot change, and that time stays exact."""
import json
import unittest

from audio import schemas as S

A1, A2 = "a" * 12, "b" * 12


def clip(**k):
    return dict({"asset_id": A1, "start": 0, "offset": 0, "length": 48000}, **k)


class AssetTests(unittest.TestCase):
    def test_a_new_asset_is_a_complete_draft(self):
        a = S.new_asset("Rain on roof", "ambience", "generated")
        self.assertTrue(S.valid_id(a["id"]))
        self.assertEqual((a["kind"], a["origin"], a["approval"], a["parent_id"], a["generation"]), ("ambience", "generated", "draft", None, None))
        self.assertEqual(json.loads(json.dumps(a)), a)

    def test_a_browser_cannot_rewrite_the_facts_about_the_file_or_where_it_came_from(self):
        stored = S.clean_asset({"id": A1, "name": "Take 1", "origin": "generated", "file": {"format": "wav", "sample_rate": 48000, "channels": 2, "length": 96000, "sha256": "abc"}})
        edited = S.clean_asset({"id": A2, "name": "Renamed", "origin": "upload", "approval": "approved", "tags": ["rain", "", 7, "loop"],
                                "file": {"format": "mp3", "sample_rate": 8000, "length": 1}}, stored)
        self.assertEqual((edited["id"], edited["origin"], edited["file"]["format"], edited["file"]["length"]), (A1, "generated", "wav", 96000))
        self.assertEqual((edited["name"], edited["approval"], edited["tags"]), ("Renamed", "approved", ["rain", "loop"]))
        self.assertEqual(S.asset_seconds(edited), 2.0)

    def test_bad_values_fall_back(self):
        a = S.clean_asset({"kind": "explosion", "approval": "maybe", "name": 5, "generation": {"model": "x" * 500, "settings": "no", "seed": -1}})
        self.assertEqual((a["kind"], a["approval"], a["name"]), ("other", "draft", "Untitled sound"))
        self.assertEqual((len(a["generation"]["model"]), a["generation"]["settings"], a["generation"]["seed"]), (200, {}, None))
        self.assertIsNone(S.asset_seconds(a))


class TimelineTests(unittest.TestCase):
    def timeline(self, **k):
        return S.clean_timeline(dict({"project_id": "p1", "tracks": [{"name": "Voice", "kind": "dialogue", "clips": [clip(start=96000), clip(start=0, asset_id=A2)]}]}, **k))

    def test_time_is_whole_samples_and_clips_are_kept_in_order(self):
        t = self.timeline()
        self.assertEqual(t["sample_rate"], 48000)
        self.assertEqual([c["start"] for c in t["tracks"][0]["clips"]], [0, 96000])
        self.assertEqual((S.timeline_length(t), S.assets_used(t)), (144000, [A1, A2]))
        self.assertEqual(S.samples(1.5, 48000), 72000)
        self.assertEqual(S.seconds(S.samples(0.1, 48000) * 10, 48000), 1.0)        # ten clips of a tenth of a second meet exactly

    def test_fractions_and_nonsense_are_refused_not_rounded(self):
        t = S.clean_timeline({"tracks": [{"clips": [clip(length=0), clip(length=1.5), clip(asset_id="../x"), clip(start=-5), "junk", clip(start=2.7)]}, "junk"]})
        clips = t["tracks"][0]["clips"]
        self.assertEqual(len(t["tracks"]), 1)
        self.assertEqual([c["start"] for c in clips], [0, 0])                       # the two with a real length survive; bad starts go to zero

    def test_fades_cannot_cross_and_ranges_are_held(self):
        c = S.clean_clip(clip(length=1000, fade_in=800, fade_out=800, gain_db=99, speed=0, pitch=40, reverse="yes"), 48000)
        self.assertEqual((c["fade_in"], c["fade_out"], c["gain_db"], c["speed"], c["pitch"], c["reverse"]), (800, 200, 0, 1, 0, False))

    def test_the_sample_rate_is_fixed_once_set_and_revision_counts_saves(self):
        t = self.timeline(sample_rate=44100)
        again = S.clean_timeline({"sample_rate": 96000, "project_id": "other", "tracks": t["tracks"]}, t)
        self.assertEqual((again["sample_rate"], again["project_id"], t["revision"], again["revision"]), (44100, "p1", 0, 1))
        self.assertEqual(S.clean_timeline({"sample_rate": 12345})["sample_rate"], 48000)

    def test_effects_are_a_known_ordered_chain(self):
        fx = S.clean_effects([{"type": "reverb", "params": {"mix": 5, "decay_s": 3}}, {"type": "autotune"}, {"type": "eq", "on": False, "params": {"low_db": -6}}, "x"])
        self.assertEqual([f["type"] for f in fx], ["reverb", "eq"])
        self.assertEqual((fx[0]["params"]["mix"], fx[0]["params"]["decay_s"], fx[1]["on"], fx[1]["params"]["low_db"]), (0.2, 3, False, -6))

    def test_solo_wins_over_mute(self):
        t = S.clean_timeline({"tracks": [{"name": "A", "mute": True}, {"name": "B"}, {"name": "C", "solo": True, "mute": True}]})
        self.assertEqual([x["name"] for x in S.audible_tracks(t)], ["C"])
        t["tracks"][2]["solo"] = False
        self.assertEqual([x["name"] for x in S.audible_tracks(t)], ["B"])

    def test_links_markers_and_tempo(self):
        t = S.clean_timeline({"tracks": [{"clips": [clip(link={"kind": "segment", "id": "s1"}), clip(start=10, link={"kind": "nope", "id": "x"})]}],
                              "markers": [{"at": 96000, "name": "Chapter 2", "kind": "chapter"}, {"at": 0, "name": "Start"}, "x"],
                              "tempo": {"bpm": 120, "first_beat": 2400, "beats_per_bar": 3}})
        clips = t["tracks"][0]["clips"]
        self.assertEqual((clips[0]["link"], clips[1]["link"]), ({"kind": "segment", "id": "s1"}, None))
        self.assertEqual([(m["at"], m["kind"]) for m in t["markers"]], [(0, "marker"), (96000, "chapter")])
        self.assertEqual(t["tempo"], {"bpm": 120, "first_beat": 2400, "beats_per_bar": 3})

    def test_a_cleaned_timeline_is_stable(self):
        t = self.timeline()
        again = S.clean_timeline(t)
        for key in ("tracks", "master", "markers", "tempo", "sample_rate", "project_id"):
            self.assertEqual(again[key], t[key], key)


if __name__ == "__main__":
    unittest.main()
