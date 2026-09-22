# -*- coding: utf-8 -*-
"""make_notes.py — 管线一·写作层：transcript.json → 读书笔记
结构：视频信息 → 一句话总结 → 内容脉络（时间轴表）→ 核心观点笔记 → 完整逐字稿 → 整理者点评
"""
import json, io, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
work = Path(r"D:\视频观看agent编写\Ech_bilibili")
data = json.loads((work / "transcript.json").read_text(encoding="utf-8"))
segs = data["segments"]

def fmt(t):
    t = int(t); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

# 逐字稿：按 ~40s 合并为大段，每段带起始时间戳
paras, buf, start = [], [], None
for s in segs:
    if start is None: start = s["start"]
    buf.append(s["text"])
    if s["end"] - start >= 40:
        paras.append({"t": fmt(start), "text": "".join(buf)})
        buf, start = [], None
if buf: paras.append({"t": fmt(start or 0), "text": "".join(buf)})

full_text = "".join(s["text"] for s in segs)
(work / "fulltext.txt").write_text(full_text, encoding="utf-8")
print(f"段落合并: {len(segs)} → {len(paras)} 段, 全文 {len(full_text)} 字")
print("CHARS_PER_PARA:", [len(p["text"]) for p in paras][:20])
# 供下一步模型精读的分段输出
(work / "paras.json").write_text(json.dumps(paras, ensure_ascii=False, indent=1), encoding="utf-8")
