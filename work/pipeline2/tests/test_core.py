import unittest

from work.pipeline2.core import align_windows, choose_times, correct_segments, normalize_segments, validate_map
from work.pipeline2.render import math_tex, prose_tex


class EvidenceTests(unittest.TestCase):
    def test_uniform_backbone_survives_scene_budget(self):
        times = choose_times(100, [1, 2, 3, 51, 52], 30, 6)
        self.assertEqual(len(times), 6)
        self.assertTrue({0, 30, 60, 90}.issubset(times))
        with self.assertRaises(ValueError):
            choose_times(1000, [], 10, 5)

    def test_boundary_overlap_and_frame_budget_do_not_drop_evidence(self):
        segs = [{"id": "s1", "start": 8, "end": 12, "text": "crossing"}]
        frames = [{"id": f"f{i}", "actual_t": i * 2} for i in range(10)]
        windows = align_windows(segs, frames, 20, 10, 2)
        self.assertEqual({f["id"] for w in windows for f in w["frames"]},
                         {f["id"] for f in frames})
        self.assertTrue(all(len(w["frames"]) <= 2 for w in windows))
        self.assertGreaterEqual(sum(bool(w["segments"]) for w in windows), 2)

    def test_hotfix_preserves_raw_and_timestamps(self):
        raw = [{"id": "s1", "start": 0, "end": 3, "text": "特正值"}]
        got = correct_segments(raw, {"特正值": "特征值"})
        self.assertEqual(raw[0]["text"], "特正值")
        self.assertEqual(got[0]["text"], "特征值")
        self.assertEqual(got[0]["end"], 3)

    def test_transcript_past_video_end_is_not_silently_inverted(self):
        with self.assertRaises(ValueError):
            normalize_segments({"segments": [{"start": 10.1, "end": 10.4, "text": "past end"}]}, 10)

    def test_model_cannot_invent_evidence(self):
        window = {"segments": [{"id": "s1"}], "frames": [{"id": "f1"}]}
        result = {"title": "导数", "blocks": [{
            "kind": "definition", "title": "定义", "text": "定义内容",
            "segment_ids": ["s1"], "frame_ids": ["f9"],
            "formulas": [], "symbols": [], "uncertainties": []}]}
        with self.assertRaises(ValueError):
            validate_map(result, window)

    def test_tex_escapes_prose_and_restricts_math(self):
        self.assertEqual(prose_tex("50% & x_1"), r"50\% \& x\_1")
        self.assertIn(r"\(x^2\)", prose_tex(r"计算 \(x^2\) 的导数"))
        self.assertEqual(math_tex(r"\frac{a}{b}"), r"\frac{a}{b}")
        for bad in [r"\input{private}", r"\write18{whoami}", r"\csname input\endcsname",
                    r"\def\x{a}", r"\includegraphics{secret}", r"\frac{a}{b"]:
            with self.assertRaises(ValueError, msg=bad):
                math_tex(bad)


if __name__ == "__main__":
    unittest.main()
