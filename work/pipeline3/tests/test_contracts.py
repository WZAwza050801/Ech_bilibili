import tempfile
import unittest
from pathlib import Path

from echonotes_practice.contracts import (
    classify, normalize_timestamps, safe_path, validate_plan)
from echonotes_practice.gemini import extract_json, interaction_text
from echonotes_practice.report import safe_markdown


class ContractsTest(unittest.TestCase):
    def test_route_uses_actions_not_title(self):
        self.assertEqual(classify([{"action": "write_file"}])["grade"], "A")
        self.assertEqual(classify([{"action": "ui_click"}, {"action": "write_file"}])["grade"], "B")
        self.assertEqual(classify([{"action": "draw_stroke"}])["grade"], "C")
        self.assertEqual(classify([{"action": "mystery"}])["grade"], "B")

    def test_paths_cannot_leave_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ["../escape", "/etc/passwd", "C:/secret", r"..\escape", "a:stream"]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_path(Path(directory), name)

    def test_evidence_and_verification_are_required(self):
        step = {"id": "s1", "action": "write_file", "path": "main.py",
                "content": "print(2)", "evidence_t": 12, "expected": "prints 2",
                "verify": {"argv": ["python", "main.py"], "stdout_contains": "2"}}
        validate_plan({"steps": [step]}, duration=30)
        for update in [{"evidence_t": 99}, {"verify": {}}, {"path": "../bad"}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_plan({"steps": [{**step, **update}]}, duration=30)

    def test_json_can_be_unwrapped_from_markdown(self):
        self.assertEqual(extract_json('```json\n{"steps":[]}\n```'), {"steps": []})

    def test_interactions_step_output_is_supported(self):
        response = {"steps": [{"type": "thought"}, {"type": "model_output",
                    "content": [{"type": "text", "text": '{"ok":true}'}]}]}
        self.assertEqual(interaction_text(response), '{"ok":true}')

    def test_invalid_step_time_is_repaired_from_matching_section(self):
        plan = {
            "sections": [
                {"start": 50, "end": 300, "title": "方法一：函数版"},
                {"start": 350, "end": 466, "title": "方法二：直接运算版"},
            ],
            "steps": [{"id": "s2", "title": "编写方法二：直接运算版",
                       "action": "write_file", "evidence_t": 703}],
        }
        normalize_timestamps(plan, 465.4)
        self.assertEqual(plan["steps"][0]["evidence_t"], 459.4)
        self.assertEqual(plan["steps"][0]["timestamp_repair"]["original"], 703)
        self.assertEqual(plan["sections"][1]["end"], 465.4)

    def test_report_markdown_removes_active_html(self):
        rendered = safe_markdown('# T\n<script>alert(1)</script><img src="x" onerror="bad()">')
        self.assertNotIn("<script", rendered)
        self.assertNotIn("onerror", rendered)


if __name__ == "__main__":
    unittest.main()
