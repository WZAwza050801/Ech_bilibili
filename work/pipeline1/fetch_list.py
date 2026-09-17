# -*- coding: utf-8 -*-
"""fetch_list.py — 拉取UP主全部视频列表（wbi 签名）
输出: video_list.json [{bvid, title, duration, pubdate, aid}]
"""
import json, io, sys, time, hashlib, urllib.request, urllib.parse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
MID = 694125286  # 江左道卡卡
OUT = Path(__file__).parent / "video_list.json"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
HDRS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": f"https://space.bilibili.com/{MID}/video",
    "Cookie": ("buvid3=FD0E1A9D-8D6B-4E0C-9B7E-2C3D4E5F6A7Binfoc; "
               "b_nut=1726400000; "
               "buvid4=9A8B7C6D-5E4F-3A2B-1C0D-9E8F7A6B5C4D-1240000000; "
               "b_lsid=ABC12DEF_198ABC12; "
               "enable_web_push=DISABLE; header_theme_version=CUSTOM; "
               "home_feed_column=5; dpi=192"),
}

MIXIN_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,
             19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,
             51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]

def get_wbi_keys():
    d = json.loads(OPENER.open(urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav", headers=HDRS), timeout=15).read())
    img = d["data"]["wbi_img"]
    img_key = img["img_url"].rsplit("/", 1)[1].split(".")[0]
    sub_key = img["sub_url"].rsplit("/", 1)[1].split(".")[0]
    return img_key, sub_key

def wbi_sign(params: dict, img_key: str, sub_key: str):
    mixin = "".join((img_key + sub_key)[i] for i in MIXIN_TAB)[:32]
    params = dict(params, wts=int(time.time()))
    params = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in sorted(params.items())}
    q = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return params

def get_real_cookies():
    """访问B站主页拿真实下发的 buvid3/buvid4/b_nut（伪造 cookie 过不了 space 风控）"""
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent": _UA}), timeout=15)
    cookies = {c.name: c.value for c in jar}
    got = [k for k in ("buvid3", "buvid4", "b_nut") if k in cookies]
    print(f"[list] 主页下发 cookie: {got}")
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if k in ("buvid3","buvid4","b_nut","b_lsid","enable_web_push","header_theme_version","home_feed_column","dpi"))

def main():
    real = get_real_cookies()
    hdrs = dict(HDRS)
    hdrs["Cookie"] = real or HDRS["Cookie"]
    img_key, sub_key = get_wbi_keys()
    print(f"[list] wbi keys ok: {img_key[:6]}.../{sub_key[:6]}...")
    videos, pn = [], 1
    while True:
        p = wbi_sign({"mid": MID, "ps": 30, "pn": pn, "order": "pubdate"}, img_key, sub_key)
        url = "https://api.bilibili.com/x/space/wbi/arc/search?" + urllib.parse.urlencode(p)
        d = json.loads(OPENER.open(urllib.request.Request(url, headers=hdrs), timeout=15).read())
        if d.get("code") != 0:
            raise RuntimeError(f"arc/search: {d.get('message')}")
        vlist = d["data"]["list"]["vlist"]
        for v in vlist:
            videos.append({"bvid": v["bvid"], "title": v["title"], "aid": v["aid"],
                           "duration": v["length"], "created": v["created"]})
        total = d["data"]["page"]["count"]
        print(f"[list] 第{pn}页: +{len(vlist)} / 共{total}")
        if len(videos) >= total or not vlist: break
        pn += 1
        time.sleep(1.5)
    OUT.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[list] 完成: {len(videos)} 个视频 → {OUT}")

if __name__ == "__main__":
    main()
