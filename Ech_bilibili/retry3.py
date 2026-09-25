# -*- coding: utf-8 -*-
"""retry3.py — 用 yt-dlp(Firefox 登录态) 补跑 3 个老视频: 下载全量音频 → wav → pipeline1 后续
老视频匿名只能拿 180s 试看流, 登录态才有全量; 下载后删掉残缺 transcript 让管线重转写
"""
import json, subprocess, sys, io, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_VENV = r"C:\Users\31168\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
VENV = os.environ.get("ECH_PY") or (_VENV if Path(_VENV).exists() else sys.executable)
WORK = Path(os.environ.get("ECH_BILI_DIR") or Path(__file__).resolve().parent)
FFMPEG = os.environ.get("FFMPEG") or "ffmpeg"

TARGETS = [
    ("BV1bH4aeAE7E", 1168),  # 嬉皮夜话 19:28
    ("BV1o4421Q7KG", 1540),  # 漫谈杨德昌 25:40
    ("BV1FJ4m1W71F", 590),   # 昆德拉 09:50
]

def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)

for bvid, dur in TARGETS:
    rd = WORK / "runs" / bvid
    rd.mkdir(parents=True, exist_ok=True)
    print(f"=== {bvid} (应有时长 {dur}s) ===", flush=True)
    # 1) yt-dlp 下载最佳音轨 (B 站登录态 cookie)
    r = run([VENV, "-m", "yt_dlp", "--cookies", str(WORK / "bili_cookies.txt"),
             "-f", "bestaudio/best", "-o", str(rd / "audio_dlp.%(ext)s"),
             "--no-playlist", f"https://www.bilibili.com/video/{bvid}"])
    files = list(rd.glob("audio_dlp.*"))
    if not files:
        print(f"  yt-dlp 失败: {(r.stderr or r.stdout)[-300:]}")
        continue
    src = files[0]
    print(f"  下载: {src.name} {src.stat().st_size/1048576:.1f}MB", flush=True)
    # 2) ffmpeg → 16kHz mono wav
    wav = rd / "audio.wav"
    r2 = run([FFMPEG, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-vn", str(wav)])
    if r2.returncode != 0 or not wav.exists():
        print(f"  ffmpeg 失败: {(r2.stderr or '')[-200:]}")
        continue
    # 3) 验时长 ≥95%
    r3 = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=noprint_wrappers=1:nokey=1", str(wav)])
    try:
        wdur = float(r3.stdout.strip())
    except Exception:
        print("  ffprobe 无法读时长"); continue
    ratio = wdur / dur
    print(f"  wav 时长 {wdur:.0f}s / {dur}s = {ratio:.1%}", flush=True)
    if ratio < 0.95:
        print("  音频仍不完整, 跳过该视频"); continue
    # 4) 清掉残缺 transcript, 跑管线 (audio.wav 已存在会跳过下载)
    for p in ("transcript.json", "transcript.txt"):
        q = rd / p
        if q.exists():
            q.unlink()
    r4 = run([VENV, str(WORK / "pipeline1.py"), bvid], timeout=3600)
    ok = (rd / "笔记.html").exists()
    tail = ((r4.stdout or "") + (r4.stderr or ""))[-200:].replace("\n", " | ")
    print(f"  管线: {'成功' if ok else '失败'} {tail}", flush=True)
    src.unlink(missing_ok=True)  # 清理中间音频

print("=== retry3 结束 ===")
