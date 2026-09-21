# -*- coding: utf-8 -*-
"""debug_variants.py — 尝试多种 playurl 参数拿老视频完整音频"""
import json, urllib.request, urllib.error, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
bu = json.load(open(r"D:\视频观看agent编写\work\pipeline1\fresh_buvid.json", encoding="utf-8"))
HDRS = {"User-Agent": _UA, "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bilibili.com/",
        "Cookie": f"buvid3={bu['buvid3']}; buvid4={bu['buvid4']}; dpi=192"}
BV, CID = "BV1FJ4m1W71F", None
v = json.loads(OPENER.open(urllib.request.Request(
    f"https://api.bilibili.com/x/web-interface/view?bvid={BV}", headers=HDRS), timeout=30).read())
CID = v["data"]["cid"]
print(f"cid={CID} 时长={v['data']['duration']}s")

VARIANTS = [
    ("dash默认",   "fnval=16&platform=pc&high_quality=1"),
    ("fnval全开",  "fnval=4048&platform=pc&high_quality=1"),
    ("flv旧格式",  "fnval=0&platform=pc&high_quality=1"),
    ("mp4旧格式",  "fnval=1&platform=pc&high_quality=1"),
    ("html5端",    "fnval=0&platform=html5&high_quality=1"),
    ("html5+mp4",  "fnval=1&platform=html5&high_quality=1"),
]
for name, q in VARIANTS:
    time.sleep(8)
    try:
        d = json.loads(OPENER.open(urllib.request.Request(
            f"https://api.bilibili.com/x/player/playurl?bvid={BV}&cid={CID}&{q}",
            headers=HDRS), timeout=30).read())
        data = d.get("data") or {}
        dash = data.get("dash")
        durl = data.get("durl") or []
        if dash and dash.get("audio"):
            seg = dash["audio"][0].get("baseUrl", "")[:60]
            print(f"[{name}] dash音频! quality={data.get('quality')} audio条数={len(dash['audio'])}")
        elif durl:
            total_len = sum(x.get("length", 0) for x in durl)
            total_size = sum(x.get("size", 0) for x in durl)
            print(f"[{name}] durl段数={len(durl)} 总时长={total_len/1000:.0f}s 总大小={total_size/1048576:.1f}MB q={data.get('quality')}")
            if len(durl) > 1:
                print(f"   首段长度={durl[0].get('length',0)/1000:.0f}s (多段=可拼接完整!)")
        else:
            print(f"[{name}] code={d.get('code')} msg={d.get('message')} 空数据")
    except Exception as e:
        print(f"[{name}] EXC: {e}")
