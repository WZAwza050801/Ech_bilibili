"""Batch driver: run every page (P) of a Bilibili course through pipeline 3.

Usage:
    python run_course.py            # all pages
    python run_course.py 1 2        # only pages 1 and 2 (smoke test)

Each page gets its own run dir; completed artifacts are reused on re-run.
Progress and per-page results are written to course-index.json incrementally,
so the whole course can be resumed after an interruption.
"""
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from echonotes_practice.source import Bilibili

BV = "BV1Mjt96uE44"
COURSE_TITLE = "Godot游戏特效-入门至进阶实战课"
SECRETS = Path(r"D:\密码书\private\private-ai-api-secrets.json")
ASR_MODEL = Path(r"D:\视频观看agent编写\Ech_bilibili\models\faster-whisper-small")
PROXY = "http://127.0.0.1:12000"
ROOT = Path(__file__).resolve().parent / "runs" / f"{COURSE_TITLE}-{date.today().isoformat()}"


def safe_name(text):
    return re.sub(r'[\\/:*?"<>| ]+', "-", text).strip("-")[:60]


def main():
    raw_args = sys.argv[1:]
    prepare = "--prepare" in raw_args
    only = {int(x) for x in raw_args if x.isdigit()} or None
    bili = Bilibili()
    data = bili.api(f"x/web-interface/view?bvid={BV}")
    pages = data["pages"]
    total_min = sum(p["duration"] for p in pages) / 60
    print(f"course: {data['title']} | UP: {data['owner']['name']} | "
          f"{len(pages)} pages, {total_min:.0f} min total", flush=True)
    index_path = ROOT / "course-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    done_pages = {entry["page"] for entry in index if entry.get("ok")}
    for part in pages:
        page = part["page"]
        if only and page not in only:
            continue
        if page in done_pages:
            print(f"--- P{page:02d} already done, skip", flush=True)
            continue
        run_dir = ROOT / f"P{page:02d}-{safe_name(part['part'])}"
        run_dir.mkdir(parents=True, exist_ok=True)
        minutes = part["duration"] / 60
        print(f"=== P{page:02d} {part['part']} ({minutes:.1f} min)", flush=True)
        cmd = [sys.executable, "-m", "echonotes_practice", BV,
               "--run-dir", str(run_dir),
               "--secrets", str(SECRETS),
               "--asr-model", str(ASR_MODEL),
               "--page", str(page),
               "--proxy", PROXY]
        if prepare:
            cmd.append("--prepare-only")
        log_path = run_dir / "run.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=str(Path(__file__).resolve().parent))
        entry = {"page": page, "title": part["part"], "duration_s": part["duration"],
                 "url": f"https://www.bilibili.com/video/{BV}/?p={page}",
                 "exit": result.returncode,
                 "ok": result.returncode == 0 and not prepare}
        if prepare:
            entry["prepared"] = result.returncode == 0
        analysis_path = run_dir / "analysis.json"
        if analysis_path.exists():
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            entry["grade"] = analysis.get("classification", {}).get("grade")
            entry["steps"] = len(analysis.get("steps", []))
            entry["run_dir"] = run_dir.name
        index = [x for x in index if x.get("page") != page] + [entry]
        index.sort(key=lambda x: x["page"])
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    exit={result.returncode} grade={entry.get('grade')} steps={entry.get('steps')}", flush=True)
    print("COURSE DONE", flush=True)


if __name__ == "__main__":
    main()
