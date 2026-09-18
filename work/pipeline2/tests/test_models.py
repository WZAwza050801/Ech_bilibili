import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from work.pipeline2.core import write_json
from work.pipeline2.models import Chat, check_json_strings, load_chat


class ModelTests(unittest.TestCase):
    def test_explicit_registry_beats_stale_generic_environment_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.json"
            write_json(path, {"entries": [
                {"provider": "deepseek", "apiKey": "fixture-key",
                 "baseUrl": "https://api.deepseek.com", "models": ["deepseek-chat"]}]})
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "stale-fixture"}, clear=True):
                client = load_chat("text", path)
            self.assertEqual(client.api_key, "fixture-key")
            self.assertNotIn("fixture-key", repr(client))
            self.assertNotIn("fixture-key", json.dumps(client.identity))

    def test_invalid_math_json_gets_one_encoding_repair(self):
        outputs = [r'{"latex":"\lim_{x\to 0}x"}', json.dumps({"latex": r"\lim_{x\to 0}x"})]
        class Opener:
            calls = 0

            def open(self, request, timeout):
                output = outputs[self.calls]
                self.calls += 1
                data = {"choices": [{"finish_reason": "stop", "message": {"content": output}}]}
                return io.BytesIO(json.dumps(data).encode())
        opener = Opener()
        with patch("urllib.request.build_opener", return_value=opener):
            result = Chat("https://example.test", "fixture", "not-a-secret").json("JSON", {})
        self.assertEqual(result["latex"], r"\lim_{x\to 0}x")
        self.assertEqual(opener.calls, 2)

    def test_valid_json_cannot_silently_corrupt_math_escapes(self):
        for raw in [r'{"latex":"\frac{x}{y}"}', r'{"latex":"\nabla f"}', r'{"symbol":"\theta"}']:
            with self.assertRaises(ValueError):
                check_json_strings(json.loads(raw))


if __name__ == "__main__":
    unittest.main()
