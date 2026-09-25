import json
import os
import subprocess
import time
from pathlib import Path
from .common import save_json
from .contracts import PROGRAMMABLE, safe_path, validate_argv


def prepare_workspace(plan, root):
    root.mkdir(parents=True, exist_ok=True)
    for step in plan["steps"]:
        if step["action"] in {"write_file", "set_param"}:
            target = safe_path(root, step["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(step["content"], encoding="utf-8")


def _wsl_path(path):
    result = subprocess.run(["wsl", "-e", "wslpath", "-a", str(Path(path).resolve())],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    return result.stdout.decode("utf-8", "replace").replace("\x00", "").strip()


GODOT_EXE = Path(r"D:\godot\Godot_v4.6.1-stable_mono_win64\Godot_v4.6.1-stable_mono_win64"
                 r"\Godot_v4.6.1-stable_mono_win64_console.exe")


def sandbox_run(root, argv, timeout=120):
    validate_argv(argv)
    if argv[0] == "godot":
        # Godot runs on the Windows host: it is a native GUI/GPU app that the
        # WSL bwrap sandbox cannot execute, and the console build's headless
        # subcommands (--import / --script / --write-movie) are non-interactive.
        started = time.monotonic()
        try:
            result = subprocess.run([str(GODOT_EXE), *argv[1:]], capture_output=True,
                                    timeout=timeout, cwd=str(root))
        except subprocess.TimeoutExpired:
            raise
        except OSError as exc:
            raise RuntimeError(f"godot unavailable: {exc}") from None
        return {"argv": argv, "exit_code": result.returncode,
                "stdout": result.stdout.decode("utf-8", "replace").replace("\x00", ""),
                "stderr": result.stderr.decode("utf-8", "replace").replace("\x00", ""),
                "seconds": round(time.monotonic() - started, 2)}
    translated = ["python3" if argv[0] == "python" else argv[0], *argv[1:]]
    wsl_root = _wsl_path(root)
    command = ["wsl", "-e", "prlimit", "--nproc=64:64", "--as=1073741824:1073741824",
               "--cpu=120:120", "--fsize=268435456:268435456", "--nofile=128:128",
               "--", "bwrap", "--unshare-all",
               "--die-with-parent", "--new-session",
               "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
               "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp", "--bind", wsl_root, "/workspace", "--chdir", "/workspace",
               "--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--", *translated]
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise
    except OSError as exc:
        raise RuntimeError(f"sandbox unavailable: {exc}") from None
    return {"argv": argv, "exit_code": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace").replace("\x00", ""),
            "stderr": result.stderr.decode("utf-8", "replace").replace("\x00", ""),
            "seconds": round(time.monotonic() - started, 2)}


def _verify(root, spec):
    result = sandbox_run(root, spec["argv"], timeout=300)
    checks = [{"kind": "command_exit_zero", "expected": 0,
               "passed": result["exit_code"] == 0}]
    if spec.get("stdout_contains"):
        checks.append({"kind": "stdout_contains", "expected": spec["stdout_contains"],
                       "passed": spec["stdout_contains"] in result["stdout"]})
    for name in spec.get("files_exist", []):
        checks.append({"kind": "file_exists", "expected": name,
                       "passed": safe_path(root, name).exists()})
    result["checks"] = checks
    result["passed"] = all(x["passed"] for x in checks)
    return result


def execute(plan, root, log_path, grade="A"):
    if grade != "C":
        prepare_workspace(plan, root)
    else:
        root.mkdir(parents=True, exist_ok=True)
    records = []
    for step in plan["steps"]:
        record = {"id": step["id"], "action": step["action"], "status": "not_executed"}
        if grade == "C":
            record.update(status="manual",
                          reason="C-grade tutorials are analysis-only; automatic reproduction is disabled")
        elif step["action"] == "install_pkg":
            record.update(status="blocked", reason="v1 sandbox has no network; dependencies must be staged explicitly")
        elif step["action"] in {"ui_click", "draw_stroke"}:
            record.update(status="manual", reason="This action is outside the programmable executor")
        elif step["action"] in PROGRAMMABLE:
            try:
                if step["action"] == "run_command":
                    record["execution"] = sandbox_run(root, step["argv"])
                record["verification"] = _verify(root, step["verify"])
                record["status"] = "passed" if record["verification"]["passed"] else "failed"
            except RuntimeError as exc:
                record["status"] = "blocked"
                record["reason"] = str(exc)
        records.append(record)
        save_json(log_path, {"records": records})
    return records
