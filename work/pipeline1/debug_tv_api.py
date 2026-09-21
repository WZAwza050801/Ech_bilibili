# -*- coding: utf-8 -*-
"""debug_tv_api.py — B 站 TV 端(云视听小电视)匿名 playurl, 社区已知可拿全量流"""
import hashlib, json, time, urllib.request, urllib.error, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

APPKEY = "4409e2ce8ffd12b8"
SECRET = "59b43e04ad6965f34319062b478f83dd"
UA = "Mozilla/5.0 (Linux; Android 9; BNTV400 Build) AppleWebKit/537.36 Chrome/84.0.4147.125 Safari/537.36 bilibili/tv/106500"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

TARGETS = [
    ("BV1bH4aeAE7E", "嬉皮夜话", 1168, 25639982538),
    ("BV1o4421Q7KG", "杨德昌", 1540, 1583971478),
    ("BV1FJ4m1W71F", "昆德拉", 590, 1506032290),
]

def signed_url(endpoint, params):
    params = dict(params, appkey=APPKEY, ts=int(time.time()))
    qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sign = hashlib.md5((qs + SECRET).encode()).hexdigest()
    return f"{endpoint}?{qs}&sign={sign}"

for bvid, name, dur, cid in TARGETS:
    try:
        pu = signed_url("https://api.bilibili.com/x/tv/playurl", {
            "build": 106500, "cid": cid, "mobi_app": "android_tv_yst",
            "platform": "android", "qn": 64, "device": "android"})
        req = urllib.request.Request(pu, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        d = json.loads(OPENER.open(req, timeout=30).read())
        data = d.get("data") or {}
        dash = data.get("dash")
        durl = data.get("durl") or []
        if dash and dash.get("audio"):
            print(f"[{name}] TV dash音频={len(dash['audio'])}条 qn={data.get('quality')} ✓")
        elif durl:
            tl = sum(x.get("length", 0) for x in durl) / 1000
            ts = sum(x.get("size", 0) for x in durl) / 1048576
            print(f"[{name}] TV durl段数={len(durl)} 总时长={tl:.0f}s(目标{dur}) 大小={ts:.1f}MB qn={data.get('quality')} {'✓全量' if tl > dur*0.95 else '✗试看'}")
        else:
            print(f"[{name}] code={d.get('code')} msg={d.get('message')} 空")
    except urllib.error.HTTPError as e:
        print(f"[{name}] HTTP {e.code}")
    except Exception as e:
        print(f"[{name}] EXC: {e}")
    time.sleep(5)
