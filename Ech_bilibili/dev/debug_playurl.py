# -*- coding: utf-8 -*-
"""debug_playurl.py — 诊断 3 个失败视频的 playurl 返回"""
import json, urllib.request, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
HDRS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bilibili.com/",
    "Cookie": ("buvid3=FD0E1A9D-8D6B-4E0C-9B7E-2C3D4E5F6A7Binfoc; "
               "b_nut=1726400000; "
               "buvid4=9A8B7C6D-5E4F-3A2B-1C0D-9E8F7A6B5C4D-1240000000; "
               "b_lsid=ABC12DEF_198ABC12; "
               "enable_web_push=DISABLE; "
               "header_theme_version=CUSTOM; "
               "home_feed_column=5; "
               "dpi=192"),
}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

TARGETS = [
    ("BV1bH4aeAE7E", "嬉皮夜话"),
    ("BV1o4421Q7KG", "漫谈杨德昌"),
    ("BV1FJ4m1W71F", "昆德拉好笑的爱"),
    ("BV1u693Y9EEy", "对照组-2018互联网精神童年(成功过的)"),
]

for bvid, name in TARGETS:
    try:
        v = json.loads(OPENER.open(urllib.request.Request(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=HDRS), timeout=30).read())
        if v.get("code") != 0:
            print(f"[{name} {bvid}] view API code={v.get('code')} msg={v.get('message')}")
            continue
        cid = v["data"]["cid"]
        d = json.loads(OPENER.open(urllib.request.Request(
            f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&platform=pc&high_quality=1",
            headers=HDRS), timeout=30).read())
        data = d.get("data") or {}
        dash = data.get("dash")
        if dash:
            aud = dash.get("audio") or []
            flac = dash.get("flac") or {}
            dolby = dash.get("dolby") or {}
            print(f"[{name} {bvid}] code={d.get('code')} dash有音频={len(aud)}条 flac={bool(flac)} dolby={bool(dolby.get('audio'))} quality={data.get('quality')} format={data.get('format_description')}")
        else:
            print(f"[{name} {bvid}] code={d.get('code')} msg={d.get('message')} 无dash, keys={list(data.keys())[:8]} accept_desc={data.get('accept_description')}")
    except Exception as e:
        print(f"[{name} {bvid}] EXC: {e}")
