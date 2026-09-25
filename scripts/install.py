# -*- coding: utf-8 -*-
"""install.py — 一键装环境：ffmpeg → .venv → 依赖 → 自检

用法:
    python scripts/install.py                 # 全自动（推荐）
    python scripts/install.py --skip-ffmpeg   # 不动系统包管理器，只装 Python 依赖
    python scripts/install.py --no-venv       # 装到当前解释器（服务器/已激活的 venv 里常用）
    python scripts/install.py --asr           # 额外装本地语音转写依赖（requirements-asr.txt）

设计原则：把「装环境」从使用者手里拿走。任何一步失败都给出可直接复制的命令，
最后由 check_env.py 兜底说明缺什么。
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYS = platform.system()
MIN_PY = (3, 10)
REQ_MAIN = ROOT / "requirements.txt"
REQ_ASR = ROOT / "requirements-asr.txt"


def step(msg: str) -> None:
    print(f"\n▶ {msg}", flush=True)


def info(msg: str) -> None:
    print(f"  {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"  ! {msg}", flush=True)


def die(msg: str, hint: str = "") -> None:
    print(f"\n✗ {msg}", flush=True)
    if hint:
        print(f"  → {hint}", flush=True)
    sys.exit(1)


def run(cmd: list[str], **kw) -> int:
    """执行命令并实时回显；失败返回 returncode 而不抛异常"""
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run([str(c) for c in cmd], **kw).returncode


def check_python() -> None:
    step("检查 Python 版本")
    ver = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info < MIN_PY:
        die(f"Python {ver} 过低（需要 {MIN_PY[0]}.{MIN_PY[1]}+）",
            "Windows: winget install Python.Python.3.12   macOS: brew install python@3.12")
    info(f"Python {ver}  OK")


def ensure_ffmpeg(skip: bool) -> bool:
    step("检查 ffmpeg（转码与抽音轨必需）")
    found = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if found:
        info(f"已就绪: {found}")
        return True
    if skip:
        warn("ffmpeg 缺失，且已按参数跳过安装")
        return False

    if SYS == "Windows":
        if shutil.which("winget"):
            info("用 winget 安装 Gyan.FFmpeg（可能需要几十秒）…")
            if run(["winget", "install", "--id", "Gyan.FFmpeg", "-e",
                    "--accept-source-agreements", "--accept-package-agreements"]) == 0:
                warn("ffmpeg 装好了，但当前终端读不到新 PATH —— 请重开一个终端再跑管线")
                return True
        warn("winget 安装失败或不可用")
        info("手动方案: winget install Gyan.FFmpeg，或下载解压后设 FFMPEG=<ffmpeg.exe 路径>")
    elif SYS == "Darwin":
        if shutil.which("brew"):
            info("用 Homebrew 安装 …")
            if run(["brew", "install", "ffmpeg"]) == 0:
                return True
        warn("没找到 brew")
        info("手动方案: 先装 Homebrew（https://brew.sh）再 brew install ffmpeg")
    else:
        warn("Linux 装系统包需要 sudo，交给使用者执行更安全")
        info("手动方案: sudo apt install ffmpeg   （或 dnf install ffmpeg / pacman -S ffmpeg）")
    return False


def ensure_venv(use_venv: bool) -> str:
    """返回后续要用的 python 解释器路径"""
    step("准备 Python 环境")
    if not use_venv:
        info(f"按参数使用当前解释器: {sys.executable}")
        return sys.executable
    if sys.prefix != sys.base_prefix and Path(sys.prefix, "pyvenv.cfg").exists():
        info(f"当前已在虚拟环境里，直接复用: {sys.executable}")
        return sys.executable

    venv_dir = ROOT / ".venv"
    py = venv_dir / ("Scripts/python.exe" if SYS == "Windows" else "bin/python")
    if not py.exists():
        info(f"创建虚拟环境 {venv_dir} …")
        if run([sys.executable, "-m", "venv", str(venv_dir)]) != 0:
            die("创建虚拟环境失败", "确认 Python 带 venv 模块（Debian/Ubuntu 需 apt install python3-venv）")
    else:
        info(f"复用已存在的虚拟环境 {venv_dir}")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    return str(py)


def install_deps(py: str, skip: bool, want_asr: bool) -> None:
    step("安装 Python 依赖")
    if skip:
        warn("按参数跳过")
        return
    targets = [REQ_MAIN]
    if want_asr and REQ_ASR.exists():
        targets.append(REQ_ASR)
    for req in targets:
        if not req.exists():
            warn(f"未找到 {req.name}，跳过")
            continue
        info(req.name)
        if run([py, "-m", "pip", "install", "-r", str(req)]) != 0:
            die(f"依赖安装失败: {req.name}", f"手动执行: {py} -m pip install -r {req}")
    if not want_asr and REQ_ASR.exists():
        info("（未装本地语音转写；需要就加 --asr）")


def main() -> int:
    ap = argparse.ArgumentParser(description="Ech 系列管线一键安装")
    ap.add_argument("--no-venv", action="store_true", help="不建虚拟环境，装到当前解释器")
    ap.add_argument("--skip-deps", action="store_true", help="跳过 pip 安装")
    ap.add_argument("--skip-ffmpeg", action="store_true", help="不碰系统包管理器")
    ap.add_argument("--asr", action="store_true", help="额外安装本地语音转写依赖")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    print("Ech 系列管线 · 一键安装")
    print(f"仓库根目录 {ROOT}    平台 {SYS}")

    check_python()
    ff_ok = ensure_ffmpeg(args.skip_ffmpeg)
    py = ensure_venv(not args.no_venv)
    install_deps(py, args.skip_deps, args.asr)

    step("环境自检")
    rc = subprocess.run([py, str(ROOT / "scripts" / "check_env.py")]).returncode

    print("\n" + "─" * 52)
    if rc == 0:
        if not ff_ok:
            print("依赖装好了，但 ffmpeg 还缺 —— 补齐后即可开始：")
        else:
            print("安装完成，可以开始跑了：")
        print("  python Ech_bilibili/pipeline1.py BV1GbNH6hE8f")
        print("  python Ech_youtube/yt_blog.py https://www.youtube.com/watch?v=HUkBz-cdB-k")
    else:
        print("安装流程结束，但仍有问题项 —— 看上面自检输出，修完再跑管线。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
