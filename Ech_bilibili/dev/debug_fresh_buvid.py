# -*- coding: utf-8 -*-
"""debug_fresh_buvid.py — 向 B 站申请新的 buvid3/buvid4 真设备指纹, 再测 playurl"""
import json, urllib.request, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(url, headers, timeout=30):
    return OPENER.open(urllib.request.Request(url, headers=headers), timeout=timeout).read()

# 1) 申请全新设备指纹
base = {"User-Agent": _UA, "Accept": "application/json", "Referer": "https://www.bilibili.com/"}
spi = json.loads(get("https://api.bilibili.com/x/frontend/finger/spi", base))
if spi.get("code") != 0:
    print(f"spi 失败: code={spi.get('code')} msg={spi.get('message')}")
    sys.exit(1)
b3 = spi["data"]["b_3"]
b4 = spi["data"]["b_4"]
print(f"新指纹: buvid3={b3[:18]}... buvid4={b4[:18]}...")

HDRS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.bilibili.com",
    "Referer": "https://www.bilibili.com/",
    "Cookie": f"buvid3={b3}; buvid4={b4}; b_nut={int(time.time())}; "
              "enable_web_push=DISABLE; header_theme_version=CUSTOM; home_feed_column=5; dpi=192",
}

# 2) 用新指纹测 view + playurl
TARGETS = [
    ("BV1bH4aeAE7E", "嬉皮夜话"),
    ("BV1o4421Q7KG", "漫谈杨德昌"),
    ("BV1FJ4m1W71F", "昆德拉好笑的爱"),
    ("BV1u693Y9EEy", "对照组"),
]
ok = []
for bvid, name in TARGETS:
    try:
        v = json.loads(get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", HDRS))
        if v.get("code") != 0:
            print(f"[{name}] view code={v.get('code')} msg={v.get('message')}")
            continue
        cid = v["data"]["cid"]
        time.sleep(2)
        d = json.loads(get(
            f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&platform=pc&high_quality=1",
            HDRS))
        data = d.get("data") or {}
        dash = data.get("dash")
        if dash and (dash.get("audio") or dash.get("flac")):
            n = len(dash.get("audio") or [])
            print(f"[{name}] OK! dash音频={n}条 flac={bool(dash.get('flac'))} quality={data.get('quality')}")
            ok.append((bvid, name))
        else:
            print(f"[{name}] playurl code={d.get('code')} msg={d.get('message')} 无音频dash")
    except urllib.error.HTTPError as e:
        print(f"[{name}] HTTP {e.code}")
    except Exception as e:
        print(f"[{name}] EXC: {e}")
    time.sleep(2)

print(f"\n可用: {len(ok)}/4")
with open(r"D:\视频观看agent编写\Ech_bilibili\fresh_buvid.json", "w", encoding="utf-8") as f:
    json.dump({"buvid3": b3, "buvid4": b4, "ts": int(time.time())}, f)
print("新指纹已存 Ech_bilibili/fresh_buvid.json")
