# -*- coding: utf-8 -*-
"""debug_variants2.py — 新指纹 + 参数变体测试, 找老视频完整音频的匿名取流方式"""
import json, urllib.request, urllib.error, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get_retry(url, headers, tries=4):
    for i in range(tries):
        try:
            return OPENER.open(urllib.request.Request(url, headers=headers), timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 412 and i < tries - 1:
                w = 20 * (i + 1); print(f"  412, 等{w}s", flush=True); time.sleep(w)
            else:
                raise
    raise RuntimeError("重试耗尽")

def new_buvid():
    d = json.loads(get_retry("https://api.bilibili.com/x/frontend/finger/spi",
                             {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"}))
    return d["data"]["b_3"], d["data"]["b_4"]

b3, b4 = new_buvid()
HDRS = {"User-Agent": _UA, "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bilibili.com/",
        "Cookie": f"buvid3={b3}; buvid4={b4}; dpi=192"}
print("新指纹OK", flush=True)

BV = "BV1FJ4m1W71F"
v = json.loads(get_retry(f"https://api.bilibili.com/x/web-interface/view?bvid={BV}", HDRS))["data"]
CID = v["cid"]; DUR = v["duration"]
print(f"cid={CID} 应有时长={DUR}s", flush=True)
time.sleep(10)

VARIANTS = [
    ("html5默认",  f"fnval=0&platform=html5&high_quality=1&cid={CID}"),
    ("html5+qn64", f"fnval=0&platform=html5&high_quality=1&qn=64&cid={CID}"),
    ("pc+fnval0",  f"fnval=0&platform=pc&high_quality=0&cid={CID}"),
    ("pc+fnval1",  f"fnval=1&platform=pc&cid={CID}"),
    ("dash4048",   f"fnval=4048&platform=pc&cid={CID}"),
]
results = {}
for name, q in VARIANTS:
    time.sleep(10)
    try:
        d = json.loads(get_retry(
            f"https://api.bilibili.com/x/player/playurl?bvid={BV}&{q}", HDRS))
        data = d.get("data") or {}
        dash = data.get("dash")
        durl = data.get("durl") or []
        if dash and dash.get("audio"):
            print(f"[{name}] dash音频! q={data.get('quality')} 条数={len(dash['audio'])}")
            results[name] = {"type": "dash", "quality": data.get("quality")}
        elif durl:
            tl = sum(x.get("length", 0) for x in durl) / 1000
            ts = sum(x.get("size", 0) for x in durl) / 1048576
            print(f"[{name}] durl段数={len(durl)} 总时长={tl:.0f}s(目标{DUR}) 总大小={ts:.1f}MB q={data.get('quality')}")
            results[name] = {"type": "durl", "dur": tl, "segs": len(durl)}
        else:
            print(f"[{name}] code={d.get('code')} msg={d.get('message')} 空")
    except Exception as e:
        print(f"[{name}] EXC: {e}")

json.dump({"b3": b3, "b4": b4}, open(r"D:\视频观看agent编写\work\pipeline1\fresh_buvid.json", "w"))
print("done")
