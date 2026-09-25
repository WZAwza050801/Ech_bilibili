"""Parallel driver: run pages 5..12 directly via cli (no index writes).

run_course.py (already running) grinds P4; this driver does the rest so the
long tail finishes sooner. Analysis results are cached, so when run_course
reaches these pages it will skip the API calls and rebuild the index.
"""
import re
import subprocess
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent))
from echonotes_practice.source import Bilibili

BV = "BV1Mjt96uE44"
COURSE_TITLE = "Godot游戏特效-入门至进阶实战课"
SECRETS = Path(r"D:\密码书\private\private-ai-api-secrets.json")
ASR_MODEL = Path(r"D:\视频观看agent编写\Ech_bilibili\models\faster-whisper-small")
ROOT = Path(__file__).resolve().parent / "runs" / f"{COURSE_TITLE}-{date.today().isoformat()}"


def safe_name(text):
    return re.sub(r'[\\/:*?"<>| ]+', "-", text).strip("-")[:60]


def main():
    pages = {int(x) for x in sys.argv[1:] if x.isdigit()}
    bili = Bilibili()
    data = bili.api(f"x/web-interface/view?bvid={BV}")
    for part in data["pages"]:
        page = part["page"]
        if pages and page not in pages:
            continue
        run_dir = ROOT / f"P{page:02d}-{safe_name(part['part'])}"
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"=== P{page:02d} {part['part']} ({part['duration']/60:.1f} min)", flush=True)
        cmd = [sys.executable, "-m", "echonotes_practice", BV,
               "--run-dir", str(run_dir), "--secrets", str(SECRETS),
               "--asr-model", str(ASR_MODEL), "--page", str(page)]
        if "--frames" in sys.argv:
            cmd += ["--mode", "frames"]
        with (run_dir / "run.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=str(Path(__file__).resolve().parent))
        print(f"    exit={result.returncode}", flush=True)
    print("PAGES DONE", flush=True)


if __name__ == "__main__":
    main()
