# -*- coding: utf-8 -*-
"""make_browser_js.py — 预生成签名URL，生成浏览器 fetch 循环 JS"""
import json, time, hashlib, urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

MID = 694125286
HERE = Path(__file__).parent

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
op.open(urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent": UA}), timeout=15)
d = json.loads(op.open(urllib.request.Request("https://api.bilibili.com/x/web-interface/nav",
    headers={"User-Agent": UA, "Cookie": "; ".join(f"{c.name}={c.value}" for c in jar)}), timeout=15).read())
wbi = d["data"]["wbi_img"]
img_key = wbi["img_url"].rsplit("/", 1)[1].split(".")[0]
sub_key = wbi["sub_url"].rsplit("/", 1)[1].split(".")[0]

TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
mixin = "".join((img_key + sub_key)[i] for i in TAB)[:32]

urls = []
for pn in range(1, 16):  # 最多 15 页 / 450 个视频
    p = {"mid": MID, "ps": 30, "pn": pn, "order": "pubdate", "platform": "web",
         "web_location": "1550505", "order_avoided": "true", "wts": int(time.time())}
    p = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in sorted(p.items())}
    q = urllib.parse.urlencode(p)
    p["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    urls.append("https://api.bilibili.com/x/space/wbi/arc/search?" + urllib.parse.urlencode(p))

js = """(async () => {
  const urls = %s;
  const videos = [];
  for (const u of urls) {
    try {
      const r = await (await fetch(u, {credentials: 'include'})).json();
      if (r.code !== 0) { window.__lastErr = r.code + ':' + r.message; continue; }
      const vl = r.data.list.vlist;
      for (const v of vl) videos.push({bvid: v.bvid, title: v.title, length: v.length, created: v.created, aid: v.aid});
      if (videos.length >= r.data.page.count || vl.length === 0) break;
    } catch (e) { window.__lastErr = String(e); }
    await new Promise(res => setTimeout(res, 800));
  }
  return JSON.stringify({count: videos.length, videos: videos, err: window.__lastErr || null});
})()""" % json.dumps(urls)

(HERE / "browser_list.js").write_text(js, encoding="utf-8")
print(f"browser_list.js generated: {len(urls)} pre-signed page urls")
