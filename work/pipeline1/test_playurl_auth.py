# -*- coding: utf-8 -*-
"""test_playurl_auth.py — 带 SESSDATA 测 playurl, 看登录后是否解锁全量"""
import urllib.request, urllib.error, json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
jar = open(sys.argv[1], encoding="utf-8-sig").read()
cookie = "; ".join(l.split("\t")[5] + "=" + l.split("\t")[6] for l in jar.splitlines()
                   if l and not l.startswith("#") and l.count("\t") == 6).replace("\ufeff", "").strip()
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Cookie": cookie}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

TARGETS = [("BV1FJ4m1W71F", 1506032290, 590), ("BV1bH4aeAE7E", 25639982538, 1168), ("BV1o4421Q7KG", 1583971478, 1540)]
for bvid, cid, dur in TARGETS:
    for label, fnval in (("dash16", 16), ("dash4048", 4048)):
        try:
            u = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval={fnval}&fourk=1"
            req = urllib.request.Request(u, headers=HDRS)
            d = json.loads(OPENER.open(req, timeout=30).read())
            data = d.get("data") or {}
            dash = data.get("dash") or {}
            durl = data.get("durl") or []
            if dash.get("audio"):
                a = sorted(dash["audio"], key=lambda x: -x.get("bandwidth", 0))[0]
                print(f"[{bvid} {label}] dash音频! bandwidth={a.get('bandwidth')} qn={data.get('quality')} ✓✓")
            elif durl:
                tl = sum(x.get("length", 0) for x in durl) / 1000
                ts = sum(x.get("size", 0) for x in durl) / 1048576
                print(f"[{bvid} {label}] durl {len(durl)}段 总时长={tl:.0f}s(目标{dur}) {ts:.1f}MB {'✓全量' if tl>dur*0.95 else '✗试看'}")
            else:
                print(f"[{bvid} {label}] code={d.get('code')} msg={d.get('message')} 无流")
        except urllib.error.HTTPError as e:
            print(f"[{bvid} {label}] HTTP {e.code}")
        time.sleep(3)
