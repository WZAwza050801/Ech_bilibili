import json
import tempfile
import unittest
from pathlib import Path

from work.pipeline2.cloud_asr import load_checkpoint, multipart, registry_key
from work.pipeline2.core import write_json


class CloudAsrTests(unittest.TestCase):
    def test_registry_label_selects_key_without_exposing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.json"
            write_json(path, {"entries": [
                {"provider": "test", "label": "first", "apiKey": "key-one"},
                {"provider": "test", "label": "second", "apiKey": "key-two"}]})
            self.assertEqual(registry_key(path, "test", "second"), "key-two")

    def test_multipart_contains_model_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            path.write_bytes(b"RIFFfixture")
            body, content_type = multipart({"model": "fixture-model"}, path)
            self.assertIn(b'fixture-model', body)
            self.assertIn(b'filename="audio.wav"', body)
            self.assertIn(b"RIFFfixture", body)
            self.assertTrue(content_type.startswith("multipart/form-data; boundary="))

    def test_checkpoint_tracks_processed_empty_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.partial.json"
            write_json(path, {
                "next_chunk": 2,
                "segments": [{"start": 0, "end": 30, "text": "第一段"}],
            })
            segments, next_chunk = load_checkpoint(path, 3)
            self.assertEqual(len(segments), 1)
            self.assertEqual(next_chunk, 2)


if __name__ == "__main__":
    unittest.main()
