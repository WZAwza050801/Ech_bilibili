# -*- coding: utf-8 -*-
"""extract_media_url.py — 从网络日志中提取 bilivideo 媒体流地址"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
txt = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"\[\d+\.\d+\] GET (https://[^\s]*bilivideo\.com[^\s]*) \(Media\) 206", txt)
if not m:
    print("未找到媒体流地址")
    sys.exit(1)
print(m.group(1))
