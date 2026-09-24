"""Package a finished run into the clean per-course deliverable folder.

output_root 下每门课一个文件夹（BV号-P页-课程名），只保留成品：
讲义 PDF、LaTeX 源码、lecture.json（证据链 + 学习讲义模式输入）、
讲义用到的去重图片集合，以及 README。编译中间产物不进成品夹；
完整过程证据留在 work_root 的运行目录里。
"""
import shutil
from pathlib import Path

from .core import read_json


def safe_name(title):
    import re
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", title).strip(" .")[:65]
    return value or "未命名课程"


def course_folder_name(meta):
    parts = [meta.get("bvid") or "local"]
    page = meta.get("page")
    if page and f"P{page}" not in meta["title"]:
        parts.append(f"P{page}")
    parts.append(safe_name(meta["title"]))
    return "-".join(parts)


def package(lecture, run_dir, out_root):
    """Copy the deliverable set into output_root/<course>/ and write README."""
    run_dir = Path(run_dir)
    meta = lecture["meta"]
    folder = Path(out_root).resolve() / course_folder_name(meta)
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("lecture.pdf", "lecture.tex", "lecture.json"):
        source, target = run_dir / name, folder / name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    frames_dir = folder / "frames"
    frames_dir.mkdir(exist_ok=True)
    for path in sorted({f["path"] for f in lecture["frames"]}):
        source, target = run_dir / path, frames_dir / Path(path).name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    write_readme(folder, lecture, run_dir)
    return folder


def repackage(lecture_path, out_root):
    """Repackage an existing run directory (or old fat archive) into the clean folder."""
    lecture_path = Path(lecture_path)
    return package(read_json(lecture_path), lecture_path.parent, out_root)


def write_readme(folder, lecture, run_dir):
    meta = lecture["meta"]
    models = lecture.get("models", {})
    blocks = lecture.get("blocks", [])
    formulas = sum(len(b.get("formulas", [])) for b in blocks)
    uncertain = sum(1 for b in blocks for f in b.get("formulas", []) if f.get("uncertain"))
    quality = lecture.get("quality", {})
    duration = meta.get("duration") or 0
    lines = [
        f"# {meta['title']}",
        "",
        f"- 来源：{meta.get('url', '本地文件')}" + (f"（UP主：{meta['owner']}）" if meta.get("owner") else ""),
        f"- 生成日期：{meta.get('date', '未知')}",
        f"- 视频时长：{duration / 60:.0f} 分钟",
        f"- 采样：{len(lecture['frames'])} 帧（30 秒间隔 + 场景检测，去重后 {len({f['path'] for f in lecture['frames']})} 张唯一画面）",
        f"- 转写：{len(lecture.get('segments', []))} 段；知识块：{len(blocks)} 个；公式：{formulas} 条（其中 {uncertain} 条标记不确定）",
        "",
        "## 模型配置",
        "",
    ]
    for role, identity in models.items():
        lines.append(f"- {role}：{identity.get('model')}（{identity.get('base_url')}）")
    lines += [
        "",
        "## 文件说明",
        "",
        "| 文件 | 说明 |",
        "| --- | --- |",
        "| lecture.pdf | 编译好的讲义（截图 + 转写整理 + LaTeX 笔记 + 批注） |",
        "| lecture.tex | 讲义 LaTeX 源码（重新编译需要同目录 frames/） |",
        "| frames/ | 讲义引用的视频截图（已去重，文件名即采样时间序号） |",
        "| lecture.json | 全部证据链：每段文字/每条公式可下钻到原视频时间戳与截图 |",
        "",
        "## 使用边界",
        "",
        "- 引用覆盖率不等于内容覆盖率；视觉复查不证明数学正确。",
        "- 正式使用前请对照原视频复核标记为不确定的公式。",
        "- 完整过程证据（原始转写、逐窗视觉记录、编译日志）保留在管线运行目录；"
        "若运行目录已清理，lecture.json 内嵌了转写、知识块与质量报告的全部内容。",
        "",
        "## 生成学习讲义（出版版 + 卡片版）",
        "",
        "```powershell",
        ".\\运行课程讲义.ps1 -Study `",
        f"  -Source '{Path(run_dir).resolve() / 'lecture.json'}'",
        "```",
        "",
    ]
    if quality.get("unreferenced_segments"):
        lines.append(f"- 未被讲义引用的转写段 {len(quality['unreferenced_segments'])} 条，"
                     "多为片头片尾或闲聊；完整口语记录见 lecture.json 的 segments 字段。")
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
