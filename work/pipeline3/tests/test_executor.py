import tempfile
import unittest
from pathlib import Path

from echonotes_practice.executor import execute, prepare_workspace


class ExecutorTest(unittest.TestCase):
    def test_prepare_workspace_writes_only_declared_files(self):
        plan = {"steps": [
            {"id": "write", "action": "write_file", "path": "src/main.py",
             "content": "print('ok')", "evidence_t": 1, "expected": "file",
             "verify": {"argv": ["python3", "src/main.py"], "stdout_contains": "ok"}}
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_workspace(plan, root)
            self.assertEqual((root / "src/main.py").read_text(), "print('ok')")

    def test_c_grade_does_not_create_reproduction_files(self):
        plan = {"steps": [
            {"id": "draw", "action": "write_file", "path": "claimed.py",
             "content": "print('not a real reproduction')"}
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = execute(plan, root, root / "execution.json", grade="C")
            self.assertFalse((root / "claimed.py").exists())
            self.assertEqual(records[0]["status"], "manual")


if __name__ == "__main__":
    unittest.main()
