# -*- coding: utf-8 -*-
"""gen_tv_url.py — 生成 TV 端 playurl 签名链接, 供浏览器内 fetch"""
import hashlib, json, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
APPKEY = "4409e2ce8ffd12b8"
SECRET = "59b43e04ad6965f34319062b478f83dd"
cid = sys.argv[1]
params = {"appkey": APPKEY, "build": 106500, "cid": cid, "device": "android",
          "mobi_app": "android_tv_yst", "platform": "android", "qn": 64, "ts": int(time.time())}
qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
sign = hashlib.md5((qs + SECRET).encode()).hexdigest()
print(f"https://api.bilibili.com/x/tv/playurl?{qs}&sign={sign}")
