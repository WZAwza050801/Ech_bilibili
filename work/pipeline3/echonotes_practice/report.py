import html
import json
from datetime import date
from pathlib import Path
from .common import stamp


def safe_markdown(text):
    import bleach
    import markdown
    rendered = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    tags = {
        "a", "blockquote", "code", "div", "em", "h1", "h2", "h3", "h4",
        "hr", "img", "li", "nav", "ol", "p", "pre", "strong", "table",
        "tbody", "td", "th", "thead", "tr", "ul",
    }
    return bleach.clean(
        rendered, tags=tags,
        attributes={"*": ["class", "id"], "a": ["href", "title"],
                    "img": ["src", "alt", "title"]},
        protocols={"http", "https", "mailto"}, strip=True)


def _table_rows(items):
    return "\n".join(
        f"| {i+1} | [{stamp(x['evidence_t'])}] | {x['title']} | `{x['action']}` | "
        f"{x['details']} | {x['expected']} |" for i, x in enumerate(items))


def render(meta, analysis, execution, run_dir):
    report_dir = run_dir / "outputs"
    report_dir.mkdir(parents=True, exist_ok=True)
    status = {x["id"]: x for x in execution}
    title = meta["title"]
    source_url = meta["url"]
    steps = analysis["steps"]
    prerequisites = "\n".join("- " + x for x in analysis.get("prerequisites", []))
    sections = "\n".join(
        f"- **{stamp(x['start'])}-{stamp(x['end'])}** {x['title']}：{x['notes']}"
        for x in analysis.get("sections", []))
    concepts = "\n".join(
        f"- **{x['name']}**（[{stamp(x['evidence_t'])}]）：{x['explanation']}"
        for x in analysis.get("concepts", []))
    gaps = "\n".join(
        f"- [{stamp(x['evidence_t'])}] {x['problem']}；影响：{x['impact']}"
        for x in analysis.get("gaps", [])) or "- 无已知缺口"
    manifest_path = run_dir / "evidence-frames" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []

    def evidence_for(step):
        if not manifest:
            return None
        return min(manifest, key=lambda item: abs(item["time"] - step["evidence_t"]))

    evidence_sections = []
    code_sections = []
    timestamp_repairs = []
    for step in steps:
        frame = evidence_for(step)
        if frame:
            evidence_sections.append(
                f"### [{stamp(step['evidence_t'])}] {step['title']}\n\n"
                f"![{step['title']}](../evidence-frames/{frame['file']})\n\n"
                f"- 画面证据：{step.get('visual_evidence', '未记录')}\n"
                f"- 口述证据：{step.get('narration_evidence', '未记录')}")
        if step.get("action") in {"write_file", "set_param"} and step.get("content"):
            language = "python" if step.get("path", "").endswith(".py") else "text"
            code_sections.append(
                f"### `{step['path']}`\n\n```{language}\n{step['content'].rstrip()}\n```")
        if step.get("timestamp_repair"):
            repair = step["timestamp_repair"]
            timestamp_repairs.append(
                f"- `{step['id']}`：模型原值 `{repair['original']}` 秒，"
                f"修复为 [{stamp(repair['repaired'])}]；依据：{repair['basis']}，"
                "并由该时间附近截图复核。")
    lecture = f"""---
title: "{title}"
source_url: "{source_url}"
platform: "bilibili"
creator: "{meta['owner']}"
date_processed: "{date.today().isoformat()}"
source_depth: "transcript + full-video Gemini analysis + timestamp screenshots"
domain: "programming"
orientation: "practice-reproduction"
classification_status: "confirmed"
tags: [python, tutorial, pipeline3]
---

# 完整课程讲义：{title}

## 课程目标

{analysis['summary']}

## 前置条件

{prerequisites}

## 结构与时间轴

{sections}

## 核心概念

{concepts}

## 可跟做步骤

| # | 证据时间 | 步骤 | 类型 | 操作 | 预期结果 |
|---:|---|---|---|---|---|
{_table_rows(steps)}

## 视频证据

{chr(10).join(evidence_sections)}

## 完整复刻代码

{chr(10).join(code_sections)}

## 证据缺口

{gaps}
"""
    report_lines = []
    for step in steps:
        record = status.get(step["id"], {})
        verify = record.get("verification", {})
        check_text = "; ".join(
            x["kind"] + "=" + str(x["passed"]) for x in verify.get("checks", []))
        report_lines.append(
            f"| {step['id']} | [{stamp(step['evidence_t'])}] | {step['title']} | "
            f"{record.get('status', 'missing')} | {verify.get('exit_code', '-')} | "
            f"{check_text or record.get('reason', '')} |")
    counts = {name: sum(x.get("status") == name for x in execution)
              for name in ["passed", "failed", "blocked", "manual"]}
    tutorial_issues = "\n".join(
        "- " + x for x in analysis.get("tutorial_issues", [])) or "- 无"
    execution_rows = "\n".join(report_lines)
    verification_appendix = []
    for step in steps:
        verify = status.get(step["id"], {}).get("verification", {})
        if verify.get("argv"):
            verification_appendix.append(
                f"### {step['id']} {step['title']}\n\n"
                f"```json\n{json.dumps(verify['argv'], ensure_ascii=False, indent=2)}\n```\n\n"
                f"- 退出码：`{verify.get('exit_code')}`\n"
                f"- 标准输出：\n\n```text\n{verify.get('stdout', '').rstrip()}\n```")
    experiment = f"""# 实验报告：{title}

## 1. 教程信息

- 来源：{source_url}
- UP 主：{meta['owner']}
- 时长：{stamp(meta['duration'])}
- 自动分级：**{analysis['classification']['grade']}**
- 分级理由：{analysis['classification']['reason']}

## 2. 复现环境

- 宿主：Windows
- 执行隔离：WSL `bubblewrap`，无网络、仅挂载本次作品目录
- 视频理解模型：`{analysis.get('analysis_model', 'unknown')}`
- 语音证据：本地 `faster-whisper small/int8`

## 3. 执行摘要

- 通过：{counts['passed']}
- 失败：{counts['failed']}
- 阻塞：{counts['blocked']}
- 人工步骤：{counts['manual']}

| 步骤 | 来源时间 | 内容 | 状态 | 退出码 | 验证 |
|---|---|---|---|---:|---|
{execution_rows}

## 4. 教程未说清的坑

{tutorial_issues}

## 5. 时间戳与证据修复

{chr(10).join(timestamp_repairs) or '- 无'}

## 6. 复刻作品

- 作品目录：`artifact/`
- 机器执行记录：`execution.json`
- 视频步骤证据截图：`evidence-frames/`

## 7. 验证命令与实际输出

{chr(10).join(verification_appendix)}

## 8. 结论

本报告只把实际验证通过的步骤标为成功。模型恢复但未执行、依赖网络被阻止、或需要 GUI/手工操作的步骤均单独标记，不计入复刻成功。
"""
    (report_dir / "课程讲义.md").write_text(lecture, encoding="utf-8")
    (report_dir / "实验报告.md").write_text(experiment, encoding="utf-8")
    lecture_body = lecture.split("---", 2)[-1].lstrip()
    combined = lecture_body + "\n\n---\n\n" + experiment
    body = safe_markdown("[TOC]\n\n" + combined)
    document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 复刻报告</title>
<style>
body{{margin:0;background:#f1f4f6;color:#17202a;font:16px/1.72 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:32px 34px 80px;background:white;min-height:100vh}}
h1,h2,h3{{line-height:1.28}} h2{{margin-top:2.2em;border-bottom:1px solid #dce3e7;padding-bottom:.35em}}
pre{{padding:14px;background:#132027;color:#edf5f6;overflow:auto;border-radius:6px}}
code{{font-family:ui-monospace,Consolas,monospace}} img{{display:block;max-width:100%;height:auto;border:1px solid #ccd6da}}
table{{width:100%;border-collapse:collapse;display:block;overflow-x:auto}} th,td{{border:1px solid #ccd6da;padding:7px 9px;text-align:left}}
.toc{{padding:16px 22px;background:#eef6f7;border-left:4px solid #087e8b}} a{{color:#08717d}}
.meta{{border-left:4px solid #087e8b;padding:10px 16px;background:#eef8f8}}
@media(max-width:640px){{main{{padding:22px 14px}}}}
</style></head><body><main><div class="meta">来源：<a href="{html.escape(source_url)}">{html.escape(source_url)}</a></div>
{body}</main></body></html>"""
    (report_dir / "讲义与实验报告.html").write_text(document, encoding="utf-8")
    return report_dir
