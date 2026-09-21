# -*- coding: utf-8 -*-
"""debug_patient.py — 慢速诊断: 新指纹 + 大间隔, 拿 3 个失败视频的 rights 和 playurl 结构"""
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
                wait = 25 * (i + 1)
                print(f"  412, 等 {wait}s 重试", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("重试耗尽")

def new_buvid():
    d = json.loads(get_retry("https://api.bilibili.com/x/frontend/finger/spi",
                             {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"}))
    return d["data"]["b_3"], d["data"]["b_4"]

def hdrs_with(b3, b4):
    return {"User-Agent": _UA, "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9", "Origin": "https://www.bilibili.com",
            "Referer": "https://www.bilibili.com/",
            "Cookie": f"buvid3={b3}; buvid4={b4}; b_nut={int(time.time())}; dpi=192"}

TARGETS = [("BV1bH4aeAE7E", "嬉皮夜话"), ("BV1o4421Q7KG", "杨德昌"), ("BV1FJ4m1W71F", "昆德拉")]
out = {}
b3, b4 = new_buvid()
print("新指纹就绪", flush=True)
for bvid, name in TARGETS:
    time.sleep(15)
    try:
        v = json.loads(get_retry(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", hdrs_with(b3, b4)))["data"]
        rights = {k: v2 for k, v2 in v["rights"].items() if v2}
        out[name] = {"title": v["title"], "rights": rights}
        print(f"[{name}] {v['title']}")
        print(f"  rights(非零): {rights}", flush=True)
        time.sleep(15)
        d = json.loads(get_retry(
            f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={v['cid']}&fnval=16&platform=pc&high_quality=1",
            hdrs_with(b3, b4)))
        data = d.get("data") or {}
        info = {"quality": data.get("quality"), "is_preview": data.get("is_preview"),
                "accept_desc": data.get("accept_description"), "keys": sorted(data.keys())}
        dash = data.get("dash")
        if dash:
            info["dash_video"] = len(dash.get("video") or [])
            info["dash_audio"] = len(dash.get("audio") or [])
        if data.get("durl"):
            info["durl_len"] = len(data["durl"])
            info["durl_size"] = data["durl"][0].get("size")
        out[name]["playurl"] = info
        print(f"  playurl: {json.dumps(info, ensure_ascii=False)}", flush=True)
    except Exception as e:
        print(f"[{name}] EXC: {e}", flush=True)
        out[name] = {"err": str(e)}

with open(r"D:\视频观看agent编写\work\pipeline1\debug_patient_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("done -> debug_patient_out.json")
