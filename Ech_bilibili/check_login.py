# -*- coding: utf-8 -*-
"""check_login.py — 验证 cookie 是否有效登录"""
import urllib.request, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
jar = open(sys.argv[1], encoding="utf-8-sig").read()
cookie = "; ".join(l.split("\t")[5] + "=" + l.split("\t")[6] for l in jar.splitlines()
                   if l and not l.startswith("#") and l.count("\t") == 6).replace("\ufeff", "").strip()
req = urllib.request.Request("https://api.bilibili.com/x/web-interface/nav",
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
                                      "Referer": "https://www.bilibili.com/",
                                      "Cookie": cookie})
d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
print(f"isLogin={d['data']['isLogin']} uname={d['data'].get('uname')!r} mid={d['data'].get('mid')}")
