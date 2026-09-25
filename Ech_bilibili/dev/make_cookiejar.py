# -*- coding: utf-8 -*-
"""make_cookiejar.py — 从 agent-browser cookies 输出生成 Netscape cookies.txt"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
src, dst = sys.argv[1], sys.argv[2]
exp = int(time.time()) + 86400 * 180
lines = ["# Netscape HTTP Cookie File"]
for ln in open(src, encoding="utf-8-sig", errors="replace"):
    ln = ln.strip()
    if not ln or ln.startswith("#") or "=" not in ln:
        continue
    name, _, val = ln.partition("=")
    name = name.strip().replace("\ufeff", "")
    if not name or " " in name:
        continue
    lines.append(f".bilibili.com\tTRUE\t/\tTRUE\t{exp}\t{name}\t{val}")
open(dst, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"导出 {len(lines)-1} 条 -> {dst}")
