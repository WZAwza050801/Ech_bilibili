# -*- coding: utf-8 -*-
"""cleanup_fake.py — 删除截断假产物对应的 NOTES 笔记"""
import json, os, re

WORK = r"D:\视频观看agent编写\work\pipeline1"
NOTES = r"D:\视频观看agent编写\江左道卡卡-读书笔记"

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:60]

bad_bv = []
for d in sorted(os.listdir(os.path.join(WORK, "runs"))):
    meta_p = f"{WORK}/runs/{d}/meta.json"
    tr_p = f"{WORK}/runs/{d}/transcript.json"
    if not (os.path.exists(meta_p) and os.path.exists(tr_p)):
        continue
    meta = json.load(open(meta_p, encoding="utf-8"))
    tr = json.load(open(tr_p, encoding="utf-8"))
    if tr.get("duration", 0) < meta["duration"] * 0.95:
        bad_bv.append(d)
print("假产物视频:", len(bad_bv))

vl = json.load(open(os.path.join(WORK, "video_list.json"), encoding="utf-8"))
removed = []
for i, v in enumerate(vl, 1):
    if v["bvid"] in bad_bv:
        f = f"{NOTES}/{i:02d}-{safe_name(v['title'])}.html"
        if os.path.exists(f):
            os.remove(f)
            removed.append(i)
print("已删除假笔记:", removed)
