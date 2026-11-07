from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SubtitleEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edl = load_module("build_edl", "skills/sc-video-subtitle-editor/scripts/build_edl.py")
        cls.retime = load_module("retime_srt", "skills/sc-video-subtitle-editor/scripts/retime_srt.py")
        cls.candidates = load_module("find_edit_candidates", "skills/sc-video-subtitle-editor/scripts/find_edit_candidates.py")

    def test_long_silence_gets_breathing_padding(self):
        keep = self.edl.build_keep_segments(
            [{"from": 2000, "to": 5000, "type": "long_silence"}], 10.0
        )
        self.assertEqual(keep, [(0.0, 2.3), (4.7, 10.0)])

    def test_filler_cut_has_no_padding(self):
        keep = self.edl.build_keep_segments(
            [{"from": 2000, "to": 2300, "type": "filler_word"}], 5.0
        )
        self.assertEqual(keep, [(0.0, 2.0), (2.3, 5.0)])

    def test_srt_time_mapping_and_rounding(self):
        map_time = self.retime.build_map_time([[0.0, 2.0], [4.0, 8.0]])
        self.assertEqual(map_time(5.0), 3.0)
        self.assertEqual(map_time(3.0), 2.0)
        self.assertEqual(self.retime.fmt_ts(1.9996), "00:00:02,000")

    def test_candidate_detection_filters_internal_tokens(self):
        payload = {
            "result": {"language": "zh"},
            "transcription": [
                {
                    "tokens": [
                        {"text": "[_TT_100]", "offsets": {"from": 0, "to": 100}},
                        {"text": "嗯", "offsets": {"from": 3000, "to": 3300}},
                        {"text": "好", "offsets": {"from": 6000, "to": 6300}},
                        {"text": "好", "offsets": {"from": 6350, "to": 6650}}
                    ]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tokens, language = self.candidates.load_tokens(path)
        self.assertEqual(language, "zh")
        self.assertEqual([token["text"] for token in tokens], ["嗯", "好", "好"])
        found = self.candidates.find_candidates(tokens, {"嗯"}, 2500, 10000)
        self.assertEqual(
            {item["type"] for item in found},
            {"long_silence", "filler_word", "repeat_candidate"},
        )


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_module("validate_final", "skills/sc-localize-video-publish/scripts/validate_final.py")
        cls.pacing = load_module("analyze_pacing", "skills/sc-localize-video-publish/scripts/analyze_pacing.py")

    def test_srt_parser_accepts_utf8_bom(self):
        text = "\ufeff1\n00:00:00,100 --> 00:00:01,200\n你好\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.srt"
            path.write_text(text, encoding="utf-8")
            cues = self.validator.parse_srt(path)
        self.assertEqual(len(cues), 1)
        self.assertAlmostEqual(cues[0]["start"], 0.1)
        self.assertAlmostEqual(cues[0]["end"], 1.2)

    def test_pace_labels_cover_expected_ranges(self):
        self.assertEqual(self.pacing.pace_label(0.93), "舒缓")
        self.assertEqual(self.pacing.pace_label(1.0), "自然")
        self.assertEqual(self.pacing.pace_label(1.07), "强调加快")


if __name__ == "__main__":
    unittest.main()
