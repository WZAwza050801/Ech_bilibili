#!/usr/bin/env python3
"""环境自检 —— 跑管线之前先执行它。

用法:
    python scripts/check_env.py                 # 全量检查（缺硬依赖时退出码 1）
    python scripts/check_env.py --ci            # 只校验 Python 版本与 pip 依赖（CI 用）
    python scripts/check_env.py -v              # 附带版本/路径细节
    python scripts/check_env.py -p youtube      # 只查某个平台 (bili / youtube / all，默认 all)

设计原则：环境问题不应该留给使用者去猜。缺什么、去哪装、装完怎么验证，一次说清。
"""

from __future__ import annotations

import argparse
import importlib
import io
import os
import shutil
import socket
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- 检查项声明 ----------------------------------------------------------
# (import 名, pip 名或 None)  —— 主线硬依赖；B 站核心刻意只用标准库，故为空
PIP_REQUIRED: list[tuple[str, str | None]] = []
# (import 名, 说明)          —— 缺了只影响对应功能
PIP_OPTIONAL = [
    ("faster_whisper", "本地 ASR（可装到独立 venv，用 ECHONOTES_ASR_PYTHON 指过去，见 requirements-asr.txt）"),
]
# 每个平台的可选依赖: 平台 -> [(import 名, 说明, pip install 提示)]
PIP_PLATFORM = {
    "bili": [],
    "youtube": [("yt_dlp", "YouTube 下载", "pip install -r Ech_youtube/requirements.txt")],
}
# (环境变量, 是否必需, 用途)
ENV_KEYS = [("DEEPSEEK_API_KEY", False, "口播稿 polish 整理，不配则跳过润色")]

MIN_PYTHON = (3, 10)
MIN_DISK_MB = 2048  # whisper small 模型 ~461MB + 音频 + 产物

OK, WARN, BAD = "[ OK ]", "[WARN]", "[FAIL]"


# ---- 输出对齐（中文按 2 列宽算，避免表格错位）----------------------------
def _w(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, n: int) -> str:
    return s + " " * max(0, n - _w(s))


def run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = (r.stdout or r.stderr or "").strip()
        return out.splitlines()[0] if out else ""
    except Exception:
        return ""


def _probe(host: str, port: int, timeout: float = 4.0) -> bool:
    """TCP 连通性探测（不走代理，直接看端口在不在）"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---- 单项检查 ------------------------------------------------------------
def check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return ok, f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})" + (
        "" if ok else f"  -> 需要 >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    )


def check_pip(name: str, pip_name: str | None) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "")
        return True, f"{pip_name or name} {ver}".strip()
    except Exception:
        hint = f"  -> pip install {pip_name}" if pip_name else ""
        return False, f"缺少 {pip_name or name}{hint}"


def check_tool(cmd: str) -> tuple[bool, str]:
    path = shutil.which(cmd)
    if not path:
        return False, f"PATH 中找不到 {cmd}"
    return True, path


def check_ffmpeg() -> tuple[bool, str]:
    """与管线同源的定位逻辑: FFMPEG 环境变量 > PATH，且校验指向的文件真的存在"""
    env = os.environ.get("FFMPEG")
    if env:
        if Path(env).exists():
            return True, f"{env}（来自 FFMPEG 环境变量）"
        return False, f"FFMPEG 指向的文件不存在: {env}  -> 改正它，或删掉让程序回退 PATH"
    path = shutil.which("ffmpeg")
    if not path:
        return False, ("PATH 中找不到 ffmpeg -> apt install ffmpeg / winget install Gyan.FFmpeg / "
                       "brew install ffmpeg；或设 FFMPEG=<ffmpeg 完整路径>")
    return True, f"{path}  ({run(['ffmpeg', '-version'])})"


def check_deno() -> tuple[bool, str]:
    local = ROOT / "Ech_youtube" / "bin"
    for name in ("deno.exe", "deno"):
        p = local / name
        if p.exists():
            return True, f"{p}（管线启动时自动加入 PATH）"
    found = shutil.which("deno")
    if found:
        return True, found
    return False, "未找到 deno -> yt-dlp 解 YouTube n-challenge 用，https://deno.com 下载后放 Ech_youtube/bin/"


def check_writable(p: Path) -> tuple[bool, str]:
    if not p.exists():
        return False, f"{p} 不存在"
    probe = p / ".ech_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, str(p)
    except OSError as e:
        return False, f"{p} 不可写: {e}"


def check_disk(p: Path) -> tuple[bool, str]:
    try:
        free_mb = shutil.disk_usage(p).free / 1048576
    except OSError as e:
        return False, f"无法读取磁盘信息: {e}"
    return free_mb >= MIN_DISK_MB, f"{free_mb / 1024:.1f} GB 可用（需要 ≥ {MIN_DISK_MB // 1024} GB）"


def check_model() -> tuple[bool, str]:
    """whisper 模型：平台本地目录 > 共享目录 > 环境变量；都没有则首次运行会联网下载"""
    bili_dir = Path(os.environ.get("ECH_BILI_DIR", ROOT / "Ech_bilibili"))
    yt_dir = Path(os.environ.get("ECH_YT_DIR", ROOT / "Ech_youtube"))
    candidates = [yt_dir / "models" / "faster-whisper-small",
                  bili_dir / "models" / "faster-whisper-small"]
    for key in ("ECH_MODEL_DIR", "ECHONOTES_ASR_MODEL", "ECH_MODEL"):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]))
    for d in candidates:
        try:
            if d.is_dir() and any(d.iterdir()):
                size = sum(f.stat().st_size for f in d.rglob("model.bin")) / 1048576
                return True, str(d) + (f"（model.bin {size:.0f}MB）" if size else "")
        except OSError:
            continue
    return False, ("未找到本地模型 -> 首次转写会联网下载 small；离线环境请先放好模型并设 "
                   "ECH_MODEL / ECHONOTES_ASR_MODEL 指定目录")


def check_bili_api() -> tuple[bool, str]:
    try:
        import urllib.request
        req = urllib.request.Request("https://api.bilibili.com/x/web-interface/view?bvid=BV1GbNH6hE8f",
                                     headers={"User-Agent": "Mozilla/5.0"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=8) as r:
            return True, f"HTTP {r.status}"
    except Exception as e:
        return False, f"请求失败: {str(e)[:80]}"


def check_youtube_net() -> tuple[bool, str]:
    proxy = os.environ.get("YT_PROXY", "http://127.0.0.1:12000")
    if proxy == "direct":
        ok = _probe("www.youtube.com", 443)
        return ok, "direct 直连可达" if ok else "direct 直连不可达 -> 改用代理并设 YT_PROXY=<代理地址>"
    host, _, port = proxy.replace("http://", "").replace("https://", "").partition(":")
    if _probe(host or "127.0.0.1", int(port or 80)):
        return True, f"代理 {proxy} 可达"
    return False, f"代理 {proxy} 不可达 -> 设 YT_PROXY=direct 直连，或换成本机可用的代理地址"


# ---- 分组执行 ------------------------------------------------------------
def run_group(title: str, checks: list[tuple[str, tuple[bool, str], bool]]) -> None:
    """checks: [(名称, (ok, detail), 是否必需)]"""
    print(f"-- {title} " + "-" * max(0, 46 - _w(title)))
    for name, (ok, detail), required in checks:
        if ok:
            print(f"{OK} {_pad(name, 22)}: {detail}")
        else:
            print(f"{BAD if required else WARN} {_pad(name, 22)}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", action="store_true", help="只校验 Python 与 pip 依赖")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true", help="只打印结论")
    ap.add_argument("-p", "--platform", choices=["bili", "youtube", "all"], default="all")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    buf = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, buf
    hard_fail = False
    try:
        print("\n=== Ech 系列管线 · 环境自检 ===")
        print(f"根目录 {ROOT}")
        print(f"平台 {sys.platform} · Python {sys.version.split()[0]} · 检查范围 {args.platform}")

        ok, info = check_python()
        print(f"{OK if ok else BAD} {_pad('Python 版本', 22)}: {info}")
        hard_fail |= not ok

        print("-- pip 依赖 " + "-" * 34)
        for name, pip_name in PIP_REQUIRED:
            ok, info = check_pip(name, pip_name)
            print(f"{OK if ok else BAD} {_pad(name, 22)}: {info}")
            hard_fail |= not ok
        for name, note in PIP_OPTIONAL:
            ok, info = check_pip(name, name)
            print(f"{OK if ok else WARN} {_pad(name, 22)}: {info if ok else '未安装（' + note + '）'}")
        for plat in (["bili", "youtube"] if args.platform == "all" else [args.platform]):
            for name, note, hint in PIP_PLATFORM.get(plat, []):
                ok, info = check_pip(name, name)
                print(f"{OK if ok else BAD} {_pad(name, 22)}: {info if ok else f'缺少 {name}（{note}） -> {hint}'}")
                hard_fail |= not ok

        if not args.ci:
            required_checks = [
                ("ffmpeg", check_ffmpeg(), True),
                ("磁盘剩余空间", check_disk(ROOT), True),
                ("Ech_bilibili 目录可写", check_writable(Path(os.environ.get("ECH_BILI_DIR", ROOT / "Ech_bilibili"))), True),
                ("Ech_youtube 目录可写", check_writable(Path(os.environ.get("ECH_YT_DIR", ROOT / "Ech_youtube"))), True),
            ]
            run_group("系统与通用", required_checks)
            hard_fail |= any((not ok) and req for _, (ok, _), req in required_checks)

            print("-- API 密钥 " + "-" * 34)
            for key, required, why in ENV_KEYS:
                val = os.environ.get(key)
                if val:
                    print(f"{OK} {_pad(key, 22)}: 已设置（{len(val)} 字符，不回显）")
                    continue
                secrets = Path(os.environ.get(
                    "ECHONOTES_SECRETS_FILE",
                    os.environ.get("ECH_SECRETS", r"D:\密码书\private\private-ai-api-secrets.json")))
                if secrets.exists():
                    print(f"{OK} {_pad(key, 22)}: 环境变量未设，但本机密码书存在，会回退读取")
                else:
                    print(f"{BAD if required else WARN} {_pad(key, 22)}: 未设置（{why}）")
                    hard_fail |= required

            if args.platform in ("all", "bili"):
                run_group("B 站（管线一 · 读书笔记）", [
                    ("faster-whisper", check_pip("faster_whisper", "faster-whisper"), False),
                    ("whisper 模型", check_model(), False),
                    ("B 站接口连通", check_bili_api(), False),
                ])
            if args.platform in ("all", "youtube"):
                run_group("YouTube（访谈 · 博客笔记）", [
                    ("yt-dlp", check_pip("yt_dlp", "yt-dlp"), False),
                    ("deno", check_deno(), False),
                    ("YouTube 网络", check_youtube_net(), False),
                ])

        print("-" * 52)
        if hard_fail:
            print("结论：存在必需项缺失，按上面 -> 提示补齐后再跑管线。")
            rc = 1
        else:
            print("结论：必需项齐备。可选未装项只影响对应功能，不影响主流程。")
            rc = 0
    finally:
        sys.stdout = real_stdout

    text = buf.getvalue()
    if args.quiet:
        for line in text.splitlines():
            if line.startswith("结论："):
                print(line)
    else:
        sys.stdout.write(text)
    return rc


if __name__ == "__main__":
    sys.exit(main())
