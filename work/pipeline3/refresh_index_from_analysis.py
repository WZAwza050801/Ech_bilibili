"""Refresh course-index.json entries from each page's analysis.json.

Why: run_course.py exited before P09 finished, and P04/P05/P10/P11 were marked
ok=false due to evidence-frame ffmpeg OOM even though analysis.json exists.
This syncs grade/steps/ok/run_dir from the authoritative analysis.json files.
"""
import json
from pathlib import Path

COURSE = Path(__file__).resolve().parent / "runs" / "Godot游戏特效-入门至进阶实战课-2026-09-23"
index_path = COURSE / "course-index.json"
entries = json.loads(index_path.read_text(encoding="utf-8"))

by_page = {e["page"]: e for e in entries}
for run_dir in sorted(COURSE.glob("P*")):
    analysis = run_dir / "analysis.json"
    if not analysis.exists():
        continue
    page = int(run_dir.name[1:3])
    data = json.loads(analysis.read_text(encoding="utf-8"))
    entry = by_page.setdefault(page, {
        "page": page, "title": run_dir.name[4:], "duration_s": 0,
        "url": f"https://www.bilibili.com/video/BV1Mjt96uE44/?p={page}",
        "exit": 0, "ok": True})
    entry["run_dir"] = run_dir.name
    entry["grade"] = data.get("classification", {}).get("grade", "-")
    entry["steps"] = len(data.get("steps", []))
    entry["ok"] = True
    entry["exit"] = 0
    entry.setdefault("duration_s", round(float(data.get("duration", 0))))

index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
for e in entries:
    print(f"P{e['page']:02d} grade={e.get('grade','-')} steps={e.get('steps','-')} ok={e.get('ok')}")
