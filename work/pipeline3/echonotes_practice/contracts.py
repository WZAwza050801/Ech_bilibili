import math
import re
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath

PROGRAMMABLE = {"write_file", "run_command", "install_pkg", "set_param"}
MANUAL = {"ui_click", "ui_operation"}
CRAFT = {"draw_stroke", "craft"}


def safe_path(root: Path, name: str) -> Path:
    """Reject absolute paths, traversal, Windows alternate streams, and symlinks."""
    if not isinstance(name, str) or not name or ":" in name or "\\" in name:
        raise ValueError(f"Unsafe relative path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {name!r}")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise ValueError("Path escapes workspace")
    return target


def classify(steps: list) -> dict:
    actions = {s.get("action") for s in steps}
    if not steps or actions - PROGRAMMABLE - MANUAL - CRAFT:
        return {"grade": "B", "reason": "存在未识别操作，保守转为手册，不自动执行。"}
    if actions & CRAFT:
        return {"grade": "C", "reason": "含手工技法；只提供观察分析与练习，不宣称复刻。"}
    if actions & MANUAL:
        return {"grade": "B", "reason": "含 GUI 操作；仅独立且明确标记的脚本步骤可执行。"}
    return {"grade": "A", "reason": "所有提取步骤均可编程；是否复刻成功以实际验证为准。"}


def normalize_timestamps(plan, duration):
    for section in plan.get("sections", []):
        section["start"] = min(duration, max(0.0, float(section.get("start", 0))))
        section["end"] = min(duration, max(section["start"], float(section.get("end", duration))))
    for step in plan.get("steps", []):
        value = step.get("evidence_t")
        if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= duration:
            continue
        sections = plan.get("sections", [])
        if not sections:
            continue
        best = max(sections, key=lambda section: SequenceMatcher(
            None, step.get("title", ""), section.get("title", "")).ratio())
        if step.get("action") in {"write_file", "set_param"}:
            repaired = round(max(best["start"], best["end"] - 6), 2)
        else:
            repaired = round((best["start"] + best["end"]) / 2, 2)
        step["timestamp_repair"] = {
            "original": value,
            "repaired": repaired,
            "basis": f"matched section: {best.get('title', '')}",
        }
        step["evidence_t"] = repaired


def validate_argv(argv):
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        raise ValueError("argv must be a nonempty string list (no shell expansion)")
    if len(argv) > 128 or any(len(x) > 8192 for x in argv):
        raise ValueError("Command exceeds execution limits")
    if argv[0] not in {"python", "python3", "ffmpeg", "node"}:
        raise ValueError("Executable not in supported sandbox tool set")


def validate_plan(plan: dict, duration: float) -> None:
    steps = plan.get("steps", [])
    if not steps:
        raise ValueError("Plan has no evidence-backed steps")
    if len(steps) > 200:
        raise ValueError("Plan has too many steps")
    ids = set()
    for step in steps:
        sid = step.get("id", "")
        if not isinstance(sid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", sid) or sid in ids:
            raise ValueError("Step IDs must be safe and unique")
        ids.add(sid)
        t = step.get("evidence_t")
        if not isinstance(t, (int, float)) or not math.isfinite(t) or not 0 <= t <= duration:
            raise ValueError("Missing/out-of-range source timestamp")
        if not step.get("expected"):
            raise ValueError("Missing expected result")
        if step.get("action") in {"write_file", "set_param"}:
            safe_path(Path.cwd(), step.get("path", ""))
            if not isinstance(step.get("content"), str):
                raise ValueError("File content must be a string")
            if len(step["content"].encode("utf-8")) > 2 * 1024 * 1024:
                raise ValueError("Generated file exceeds 2 MiB")
        if step.get("action") == "run_command":
            validate_argv(step.get("argv"))
        if step.get("action") == "install_pkg":
            packages = step.get("packages", [])
            if not packages or any(not re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", p) for p in packages):
                raise ValueError("Dependencies require exact name==version; no URLs or pip flags")
        if step.get("action") in PROGRAMMABLE:
            verify = step.get("verify", {})
            validate_argv(verify.get("argv"))
            if not (verify.get("stdout_contains") or verify.get("files_exist") or verify.get("assertions")):
                raise ValueError("Verification must assert an observable result")
            for name in verify.get("files_exist", []):
                safe_path(Path.cwd(), name)
    for step in steps:
        deps = step.get("depends_on", [])
        earlier = [s["id"] for s in steps[:steps.index(step)]]
        if any(dep not in earlier for dep in deps):
            raise ValueError("Dependencies must refer to earlier steps")
