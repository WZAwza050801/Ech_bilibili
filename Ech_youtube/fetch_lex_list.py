# -*- coding: utf-8 -*-
"""fetch_lex_list.py — 拉取 Lex Fridman 播客全目录(扁平枚举, 只取 id+标题)
输出: Ech_youtube/lex_episodes.json
"""
import json, os, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = Path(r"D:\视频观看agent编写\Ech_youtube")
os.environ["PATH"] = str(WORK / "bin") + os.pathsep + os.environ["PATH"]

from yt_dlp import YoutubeDL

PLAYLISTS = [
    ("podcast_full", "https://www.youtube.com/playlist?list=PLrAXtmErZgOdP_8GztsuKi9nrraNbKKp4"),
    ("channel_videos", "https://www.youtube.com/@lexfridman/videos"),
]

out = None
for name, url in PLAYLISTS:
    try:
        opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                "proxy": os.environ.get("YT_PROXY", "http://127.0.0.1:12000"),
                "socket_timeout": 30, "retries": 3, "playlistend": 800}
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = [{"vid": e["id"], "title": e.get("title", "")}
                   for e in info.get("entries") or [] if e.get("id")]
        if entries:
            out = {"source": name, "count": len(entries), "entries": entries}
            print(f"[ok] {name}: {len(entries)} 条")
            break
    except Exception as e:
        print(f"[fail] {name}: {str(e)[:150]}")

if out:
    (WORK / "lex_episodes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved lex_episodes.json")
else:
    print("ALL_FAILED")
