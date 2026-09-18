"""Real ffmpeg/XeLaTeX integration, with an explicitly fake model boundary."""
import tempfile
import unittest
from pathlib import Path

from work.pipeline2.core import cached, read_json, validate_outline, write_json
from work.pipeline2.media import Bilibili
from work.pipeline2.pipeline2 import parser, run
from work.pipeline2.writing import outline


class ContractTests(unittest.TestCase):
    def test_cache_invalidates_on_settings_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            self.assertEqual(cached(path, {"model": "a"}, lambda: 1), 1)
            self.assertEqual(cached(path, {"model": "a"}, lambda: 2), 1)
            self.assertEqual(cached(path, {"model": "b"}, lambda: 2), 2)

    def test_reduce_cannot_drop_or_duplicate_blocks(self):
        blocks = [{"id": "b1"}, {"id": "b2"}]
        for ids in [["b1"], ["b1", "b2", "b1"], ["b1", "invented"]]:
            with self.assertRaises(ValueError):
                validate_outline({"sections": [{"title": "标题", "block_ids": ids}]}, blocks)

    def test_final_reduce_repairs_singleton_sections(self):
        blocks = [
            {"id": f"b{i}", "kind": "explanation", "title": f"主题 {i}",
             "start": i, "end": i + 1, "text": "摘要"}
            for i in range(3)
        ]

        class RepairingChat:
            identity = {"model": "fixture"}

            def json(self, _system, payload, images=()):
                if isinstance(payload, list):
                    return {"sections": [
                        {"title": "主体", "block_ids": ["b0", "b1"]},
                        {"title": "零散主题", "block_ids": ["b2"]},
                    ]}
                if "draft" in payload:
                    return {"sections": [
                        {"title": "合并主题", "block_ids": ["b0", "b1", "b2"]},
                    ]}
                return {"sections": payload["candidate_sections"]}

        with tempfile.TemporaryDirectory() as directory:
            result = outline(blocks, RepairingChat(), Path(directory))
        self.assertEqual(result["sections"], [
            {"title": "合并主题", "block_ids": ["b0", "b1", "b2"]},
        ])

    def test_multi_part_uses_selected_cid_and_duration(self):
        api = Bilibili()
        api.api = lambda *a: {"title": "Course", "owner": {"name": "Lecturer"},
                              "pages": [{"cid": 1, "duration": 10, "part": "Intro"},
                                        {"cid": 2, "duration": 20, "part": "Proof"}]}
        meta = api.metadata("https://www.bilibili.com/video/BV1GbNH6hE8f?p=2")
        self.assertEqual((meta["cid"], meta["duration"], meta["page"]), (2, 20, 2))
        with self.assertRaises(ValueError):
            api.metadata("https://evil.example/video/BV1GbNH6hE8f")
        with self.assertRaises(ValueError):
            api.metadata("BV1GbNH6hE8f", 3)


class FixtureChat:
    identity = {"model": "OFFLINE-FIXTURE-NOT-A-REAL-MODEL"}

    def __init__(self):
        self.calls = 0

    def json(self, system, payload, images=()):
        self.calls += 1
        if isinstance(payload, dict) and "candidate_sections" in payload:
            return {"sections": payload["candidate_sections"]}
        if isinstance(payload, dict):
            second = payload["start"] >= 12
            formula = r"\lim_{h\to 0}\frac{(x+h)^2-x^2}{h}=2x" if second else r"f'(x)=\lim_{h\to 0}\frac{f(x+h)-f(x)}{h}"
            return {"title": "导数", "blocks": [{
                "kind": "example" if second else "definition",
                "title": "平方函数的导数" if second else "从变化率到导数",
                "text": ("取 \\(f(x)=x^2\\)。先展开分子，再约去非零增量 \\(h\\)，"
                         "得到 \\(2x+h\\)。令 \\(h\\) 趋于零，极限为 \\(2x\\)。"
                         if second else
                         "差商刻画区间上的平均变化率。固定自变量的取值，让非零增量趋于零；"
                         "若差商的极限存在，就把这个极限定义为该点的导数。存在性是定义的前提。"),
                "segment_ids": [s["id"] for s in payload["segments"]],
                "frame_ids": [f["id"] for f in payload["frames"]],
                "formulas": [{"latex": formula, "frame_id": payload["frames"][0]["id"], "uncertain": False}],
                "symbols": [{"symbol": "h", "meaning": "自变量的非零增量"}], "uncertainties": []}]}
        if payload and "summary" in payload[0]:
            return {"sections": [{"title": "导数的定义与计算", "block_ids": [b["id"] for b in payload]}]}
        if payload and "latex" in payload[0]:
            return {"checks": [{"id": f["id"], "status": "unclear",
                                "note": "离线测试使用固定响应，未进行真实视觉核验"} for f in payload]}
        return {"segments": payload}


def make_fixture(directory):
    from PIL import Image, ImageDraw, ImageFont
    from work.pipeline2.media import command
    directory.mkdir(parents=True, exist_ok=True)
    # Raster slides are programmatic test data, not generated lecture evidence.
    font_path = Path("C:/Windows/Fonts/cambria.ttc")
    font = ImageFont.truetype(str(font_path), 44) if font_path.exists() else ImageFont.load_default(size=36)
    rows = [
        ["TEST FIXTURE / 01", "Derivative = limit of difference quotient",
         "f'(x) = lim [ f(x+h) - f(x) ] / h", "                  h -> 0",
         "The limit must exist."],
        ["TEST FIXTURE / 02", "Example: f(x) = x^2",
         "[(x+h)^2 - x^2] / h = 2x + h", "As h -> 0, the limit is 2x.",
         "Therefore f'(x) = 2x."],
    ]
    for index, texts in enumerate(rows):
        image = Image.new("RGB", (1280, 720), (247, 247, 242))
        draw = ImageDraw.Draw(image)
        for n, line in enumerate(texts):
            draw.text((55, 65 + n * 115), line, fill=(35, 48, 58), font=font)
        image.save(directory / f"slide{index}.jpg")
    command(["ffmpeg", "-y", "-framerate", "1/12", "-i", str(directory / "slide%d.jpg"),
             "-r", "2", "-t", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(directory / "course.mp4")])
    write_json(directory / "transcript.json", {"source": "synthetic_test_fixture", "segments": [
        {"start": 0, "end": 11.8, "text": "导数定义为差商的极限，需要极限存在。"},
        {"start": 12, "end": 23.8, "text": "平方函数展开差商得到二x加h，极限为二x。"}]})
    return directory / "course.mp4"


def integration_demo(root):
    video = make_fixture(root / "fixture")
    args = parser().parse_args([
        "run", str(video), "--transcript", str(video.parent / "transcript.json"),
        "--title", "导数定义与平方函数示例（离线流程测试）",
        "--work-root", str(root / "runs"), "--output-root", str(root / "archive"),
        "--interval", "6", "--max-frames", "8", "--window-seconds", "12", "--max-images", "4",
    ])
    fake = FixtureChat()
    archive = run(args, clients=(fake, fake))
    before = fake.calls
    again = run(args, clients=(fake, fake))
    assert again == archive and fake.calls == before, "Second run must reuse cached model responses"
    data = read_json(archive / "lecture.json")
    assert len(data["blocks"]) == 2
    assert all(abs(f["actual_t"] - f["requested_t"]) <= .5 for f in data["frames"])
    assert any(f["duplicate_of"] for f in data["frames"]), "Static frames should be deduplicated"
    assert len(list((archive / "frames").glob("*.jpg"))) == 2
    assert (archive / "lecture.pdf").stat().st_size > 1000
    return archive


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        print(integration_demo(Path(sys.argv[1]).resolve()))
    else:
        unittest.main()
