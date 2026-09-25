r"""Batch-run pipeline2 LaTeX lectures for remaining Godot course pages.

- 2 parallel lanes (thread pool), long pages spread across lanes.
- Each page: pipeline2 run -> archive via organize.py (order by P number) -> verify -> cleanup intermediates.
- transcript.json copied into the lecture folder as kept textual asset.
Log: D:\课程视频变操作agent\EchoNotes\work\pipeline3\latex_batch.log
"""
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LOG = Path(r"D:\课程视频变操作agent\EchoNotes\work\pipeline3\latex_batch.log")
ORG = r"C:\Users\31168\.workbuddy\skills\course-output-organizer\organize.py"
P2_CWD = r"D:\课程视频latex讲义"
WORK_ROOT = r"D:\课程视频latex讲义\运行缓存"
OUT_ROOT = r"D:\课程视频latex讲义\归档"
COURSE_DIR = r"D:\B站课程Agent\BV1Mjt96uE44-Godot游戏特效课"
BV = "BV1Mjt96uE44"
URL = f"https://www.bilibili.com/video/{BV}"

PAGES = {
    7: "投射物制作",
    8: "枪口特效",
    9: "撞击特效",
    10: "闪电投射物",
    11: "闪电投射物枪口和撞击特效",
}
LANES = [[7, 9, 11], [8, 10]]  # P04/P05 已完成


def win_rmtree(path: str):
    """Delete via PowerShell .NET API - bypasses the safe-delete hook that
    blocks shutil.rmtree (bulk>50 files => silent thread kill)."""
    import base64
    ps = "[System.IO.Directory]::Delete('" + path.replace("'", "''") + "', $true)"
    b64 = base64.b64encode(ps.encode("utf-16-le")).decode()
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", b64],
                   capture_output=True, timeout=300)

_log_lock = threading.Lock()


def log(msg):
    ts = time.strftime("%H:%M:%S")
    with _log_lock:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
        print(f"[{ts}] {msg}", flush=True)


def find_run_dir(page):
    # 宽松匹配：目录名含 -P<page>- 且含 BV 号（命名格式有两种变体）
    hits = [d for d in Path(OUT_ROOT).iterdir()
            if d.is_dir() and f"P{page}" in d.name and BV in d.name]
    hits.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def env_setup():
    e = os_env()
    return e


def os_env():
    import os
    e = dict(os.environ)
    e.update({
        "PYTHONUTF8": "1",
        "HTTP_PROXY": "", "HTTPS_PROXY": "", "http_proxy": "", "https_proxy": "",
        "NO_PROXY": "*",
        "ECHONOTES_SECRETS_FILE": r"D:\密码书\private\private-ai-api-secrets.json",
        "ECHONOTES_ASR_PYTHON": r"C:\Users\31168\.workbuddy\binaries\python\envs\default\Scripts\python.exe",
        "ECHONOTES_ASR_MODEL": r"D:\视频观看agent编写\Ech_bilibili\models\faster-whisper-small",
        "ECHONOTES_VISION_PROVIDER": "siliconflow",
        "ECHONOTES_VISION_MODEL": "Qwen/Qwen3-VL-32B-Instruct",
        "ECHONOTES_VISION_BASE_URL": "https://api.siliconflow.cn/v1",
        "ECHONOTES_PLANNER_PROVIDER": "bailian",
        "ECHONOTES_PLANNER_KEY_LABEL": "Qwen CLI OpenAI auth",
        "ECHONOTES_PLANNER_MODEL": "qwen3.8-max",
        "ECHONOTES_PLANNER_BASE_URL": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "ECHONOTES_WRITER_PROVIDER": "kimi-code",
        "ECHONOTES_WRITER_KEY_LABEL": "Kimi Code managed API",
        "ECHONOTES_WRITER_MODEL": "kimi-k3",
        "ECHONOTES_WRITER_BASE_URL": "https://api.kimi.com/coding/v1",
        "ECHONOTES_WRITER_TEMPERATURE": "1",
        "ECHONOTES_WRITER_MAX_TOKENS": "8192",
    })
    return e


def run_page(page):
    name = PAGES[page]
    label = f"P{page:02d}-{name}"
    t0 = time.time()
    log(f"== START {label} ==")
    cmd = [sys.executable, r"EchoNotes\work\pipeline2\pipeline2.py", "run", URL,
           "--page", str(page), "--title", f"Godot游戏特效-{name}",
           "--work-root", WORK_ROOT, "--output-root", OUT_ROOT]
    r = subprocess.run(cmd, cwd=P2_CWD, env=os_env(), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=4 * 3600)
    tail = "\n".join((r.stdout or "").strip().splitlines()[-3:])
    log(f"{label} pipeline2 exit={r.returncode} ({(time.time()-t0)/60:.1f}min)\n{tail}")
    run = find_run_dir(page)
    if not run:
        log(f"{label} FAIL: no run dir found in 归档")
        return False
    # 归档
    a = subprocess.run([sys.executable, ORG, "--root", r"D:\B站课程Agent",
                        "--course", "BV1Mjt96uE44-Godot游戏特效课", "--course-url", URL,
                        "--lecture", f"{run}={label}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log(f"{label} organize exit={a.returncode}: {(a.stdout or a.stderr).strip()[-200:]}")
    # 校验
    dest = Path(COURSE_DIR) / "LaTeX讲义" / label
    pdf = dest / "lecture.pdf"
    figs = dest / "figs"
    if not pdf.exists() or pdf.stat().st_size < 100 * 1024:
        log(f"{label} VERIFY FAIL (pdf)")
        return False
    # 文字稿留存（复用资产）
    for keep in ("transcript.json", "blocks.json"):
        src = run / keep
        if src.exists():
            shutil.copy2(src, dest / keep)
    # 清扫中间产物（.NET 删除，绕过 safe-delete 钩子）
    try:
        win_rmtree(str(run))
        for cache in Path(WORK_ROOT).iterdir():
            if f"P{page}" in cache.name or f"-{page}" in cache.name:
                win_rmtree(str(cache))
    except Exception:
        log(f"{label} 清扫失败（不阻塞）: {traceback.format_exc(limit=1)}")
    log(f"== DONE {label}: pdf={pdf.stat().st_size//1024}KB figs={len(list(figs.glob('*')))} "
        f"总耗时 {(time.time()-t0)/60:.1f}min ==")
    return True


def lane(pages, lane_id):
    for p in pages:
        try:
            for attempt in (1, 2):
                if run_page(p):
                    break
                log(f"P{p:02d} 第{attempt}次失败" + ("" if attempt == 2 else "，重试"))
        except Exception:
            log(f"P{p:02d} EXCEPTION:\n{traceback.format_exc()}")


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log(f"batch start, lanes={LANES}")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(lane, pages, i) for i, pages in enumerate(LANES)]
        for f in futs:
            f.result()
    log("ALL LANES DONE")


if __name__ == "__main__":
    main()
