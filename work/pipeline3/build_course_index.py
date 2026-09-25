"""Build a course-level index (markdown + html) from course-index.json.

Usage: python build_course_index.py
Reads runs/Godot游戏特效-*/course-index.json written by run_course.py.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "runs"


def stamp(t):
    minute, second = divmod(int(t), 60)
    return f"{minute:02d}:{second:02d}"


def main():
    candidates = sorted(ROOT.glob("Godot游戏特效-*/course-index.json"))
    if not candidates:
        sys.exit("no course-index.json found")
    index_path = candidates[-1]
    course_dir = index_path.parent
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    lines = [f"# 课程索引：{course_dir.name}", ""]
    lines.append("| P | 标题 | 时长 | 分级 | 步骤数 | 状态 | 报告 |")
    lines.append("|---|---|---|---|---|---|---|")
    for entry in entries:
        run_dir = course_dir / entry.get("run_dir", "")
        report = run_dir / "outputs" / "讲义与实验报告.html"
        report_link = f"[打开]({entry.get('run_dir', '')}/outputs/讲义与实验报告.html)" if report.exists() else "-"
        lines.append(
            f"| P{entry['page']:02d} | {entry['title']} | {stamp(entry['duration_s'])} | "
            f"{entry.get('grade', '-')} | {entry.get('steps', '-')} | "
            f"{'完成' if entry.get('ok') else '失败'} | {report_link} |")
    lines.append("")
    (course_dir / "course-index.md").write_text("\n".join(lines), encoding="utf-8")
    rows = "\n".join(
        f"<tr><td>P{entry['page']:02d}</td><td>{html.escape(entry['title'])}</td>"
        f"<td>{stamp(entry['duration_s'])}</td><td>{entry.get('grade', '-')}</td>"
        f"<td>{entry.get('steps', '-')}</td><td>{'完成' if entry.get('ok') else '失败'}</td>"
        f"<td><a href=\"{entry.get('run_dir', '')}/outputs/讲义与实验报告.html\">报告</a></td></tr>"
        for entry in entries)
    (course_dir / "course-index.html").write_text(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(course_dir.name)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;color:#17202a}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #ccd6da;padding:8px 10px;text-align:left}}
th{{background:#eef6f7}} a{{color:#08717d}}</style></head><body>
<h1>{html.escape(course_dir.name)}</h1>
<table><tr><th>P</th><th>标题</th><th>时长</th><th>分级</th><th>步骤数</th><th>状态</th><th>报告</th></tr>
{rows}</table></body></html>""", encoding="utf-8")
    print(f"index written: {course_dir / 'course-index.md'}")


if __name__ == "__main__":
    main()
