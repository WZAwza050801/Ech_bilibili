import tempfile
import unittest
from pathlib import Path

from work.pipeline2.media import command, extract_frames, probe


class TimestampIntegrationTests(unittest.TestCase):
    def test_nonzero_stream_pts_are_normalized_to_video_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "offset.mp4"
            command(["ffmpeg", "-y", "-f", "lavfi", "-i",
                     "testsrc2=size=320x180:rate=2:duration=3", "-c:v", "libx264",
                     "-output_ts_offset", "5", str(source)])
            info = probe(source)
            frames = extract_frames(source, directory, info, interval=1, budget=3, threshold=.8)
            self.assertEqual(info["start_time"], 5)
            self.assertEqual([f["pts"] for f in frames], [5, 6, 7])
            self.assertEqual([f["actual_t"] for f in frames], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
