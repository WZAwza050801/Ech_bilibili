# -*- coding: utf-8 -*-
"""debug_full_resp.py — 打印失败视频的完整 playurl 返回结构"""
import json, urllib.request, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
bu = json.load(open(r"D:\视频观看agent编写\work\pipeline1\fresh_buvid.json", encoding="utf-8"))
HDRS = {"User-Agent": _UA, "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bilibili.com/",
        "Cookie": f"buvid3={bu['buvid3']}; buvid4={bu['buvid4']}; dpi=192"}
bvid = "BV1FJ4m1W71F"
v = json.loads(OPENER.open(urllib.request.Request(
    f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=HDRS), timeout=30).read())["data"]
print(f"title={v['title']}")
print(f"rights={ {k:v2 for k,v2 in v['rights'].items() if v2} }")
cid = v["cid"]
time.sleep(1)
d = json.loads(OPENER.open(urllib.request.Request(
    f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&platform=pc&high_quality=1",
    headers=HDRS), timeout=30).read())
data = d.get("data") or {}
print(f"playurl keys: {sorted(data.keys())}")
print(f"quality={data.get('quality')} format={data.get('format')} is_preview={data.get('is_preview')}")
print(f"accept_desc={data.get('accept_description')}")
print(f"accept_quality={data.get('accept_quality')}")
durl = data.get("durl")
if durl:
    print(f"durl条数={len(durl)} size={durl[0].get('size')} length={durl[0].get('length')}ms")
dash = data.get("dash")
if dash:
    print(f"dash keys={sorted(dash.keys())} video={len(dash.get('video') or [])} audio={len(dash.get('audio') or [])}")
