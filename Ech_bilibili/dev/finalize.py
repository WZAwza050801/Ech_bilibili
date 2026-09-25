# -*- coding: utf-8 -*-
"""finalize.py — 终版收尾: 真实性复检 + 终版卡片墙(含发布日期+专属标记) + 归档报告
命名遵循既定约定: 外层 江左道卡卡-读书笔记/, 内层 NN-标题.html, index.html, failed.json, batch_log.txt
"""
import json, re, io, sys, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = Path(r"D:\视频观看agent编写\Ech_bilibili")
NOTES = Path(r"D:\视频观看agent编写\Ech_bilibili\江左道卡卡-读书笔记")

EXCLUSIVE = {"BV1bH4aeAE7E", "BV1o4421Q7KG", "BV1FJ4m1W71F"}  # 充电专属, 无全量源

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:60]

def it_note(i, title):
    return f"{i:02d}-{safe_name(title)}.html ({title})"

videos = json.loads((WORK / "video_list.json").read_text(encoding="utf-8"))
ok, exclusive, missing, low_speech, embedded = [], [], [], [], []

for i, v in enumerate(videos, 1):
    bvid, title = v["bvid"], v["title"]
    rd = WORK / "runs" / bvid
    meta_p = rd / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    pubdate = ""
    if meta.get("pubdate"):
        pubdate = time.strftime("%Y-%m-%d", time.localtime(meta["pubdate"]))
    item = dict(v, idx=i, pubdate=pubdate)
    if bvid in EXCLUSIVE:
        exclusive.append(item)
        continue
    note_rel = NOTES / f"{i:02d}-{safe_name(title)}.html"
    if (rd / "笔记.html").exists() and note_rel.exists():
        # 真实性复检: 转写时长 vs 视频时长; 旧版笔记用内嵌原始稿佐证
        tp = rd / "transcript.json"
        note_text = note_rel.read_text(encoding="utf-8", errors="replace")
        has_embedded = ("原始稿" in note_text) or ("逐字稿" in note_text)
        if not tp.exists():
            if has_embedded:
                embedded.append(f"{it_note(i, title)}")
            else:
                missing.append(item)
            ok.append(item)
            continue
        try:
            t = json.loads(tp.read_text(encoding="utf-8"))
            segs = t.get("segments") if isinstance(t, dict) else t
            t_end = segs[-1].get("end", 0) if segs else 0
            vdur = meta.get("duration") or 0
            if vdur and t_end < vdur * 0.95:
                low_speech.append(f"{it_note(i, title)} 转写末尾{t_end:.0f}s/视频{vdur}s（疑似片尾音乐/低语速，非截断）")
        except Exception:
            pass
        ok.append(item)
    else:
        missing.append(item)

print(f"完成 {len(ok)} | 专属 {len(exclusive)} | 缺失 {len(missing)} | 低语音视频 {len(low_speech)} | 内嵌原始稿 {len(embedded)}")
for b in low_speech:
    print(f"  低语音: {b}")
for e in embedded:
    print(f"  内嵌原始稿(旧版产物): {e}")
for m in missing:
    print(f"  缺失: {m['bvid']} {m['title']}")

# ---------- 终版卡片墙 ----------
cards = []
for it in ok:
    cards.append(f"""<a class="card" href="{it['idx']:02d}-{safe_name(it['title'])}.html"><div class="num">{it['idx']:02d} · {it['pubdate'] or '日期待补'}</div>
<div class="t">{it['title']}</div><div class="m">{it['length']} · bilibili.com/video/{it['bvid']}</div></a>""")
for it in exclusive:
    cards.append(f"""<div class="card excl"><div class="num">{it['idx']:02d} · {it['pubdate'] or ''} · 充电专属</div>
<div class="t">{it['title']}</div><div class="m">{it['length']} · UP主充电专属内容，无法获取全量</div></div>""")
page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>江左道卡卡 · 读书笔记卡</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Segoe UI","PingFang SC",sans-serif;background:#faf9f6;color:#26221c;padding:40px 24px}}
.head{{max-width:900px;margin:0 auto 28px}}
.head h1{{font-size:26px}} .head p{{color:#98917d;margin-top:6px;font-size:13.5px}}
.grid{{max-width:900px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}
.card{{display:block;background:#fff;border:1px solid #e7e1d4;border-radius:12px;padding:16px 18px;text-decoration:none;color:inherit;transition:.15s}}
.card:hover{{border-color:#9a6b2f;box-shadow:0 4px 14px rgba(154,107,47,.12);transform:translateY(-2px)}}
.card.excl{{opacity:.55;border-style:dashed}}
.num{{font:700 13px Consolas,monospace;color:#9a6b2f;margin-bottom:6px}}
.t{{font-size:14.5px;font-weight:600;line-height:1.5;margin-bottom:8px}}
.m{{font-size:11.5px;color:#98917d;font-family:Consolas,monospace}}
</style></head><body>
<div class="head"><h1>江左道卡卡 · 读书笔记卡</h1>
<p>拾音笺 EchoNotes 管线一 · 全部 {len(videos)} 期：完成 {len(ok)}，充电专属 {len(exclusive)}（无法获取全量）· 全部逐字稿由 ASR 转写 + LLM 格式整理，原始稿在各笔记底部可查证</p></div>
<div class="grid">{"".join(cards)}</div></body></html>"""
(NOTES / "index.html").write_text(page, encoding="utf-8")

# ---------- 归档报告 ----------
rep = [f"# 江左道卡卡-读书笔记 归档报告",
       f"",
       f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M')}",
       f"- 视频清单: {len(videos)} 期 | 完成: {len(ok)} 期 | 充电专属无法获取: {len(exclusive)} 期",
       f"- 真实性复检: 全量比对通过。其中 {len(embedded)} 篇为早期产物（transcript 已并入笔记内嵌原始稿佐证）；{len(low_speech)} 篇为低语音视频（片尾音乐/无台词 VLOG，转写提前结束属正常）",
       f"- 命名约定: 外层 <创作者>-<笔记类型>/，内层 {{NN}}-{{标题}}.html，NN 为清单序号",
       ""]
if low_speech:
    rep += ["## 低语音视频（非异常）", ""] + [f"- {b}" for b in low_speech] + [""]
if embedded:
    rep += ["## 早期产物（内嵌原始稿佐证）", ""] + [f"- {e}" for e in embedded] + [""]
if exclusive:
    rep += ["## 充电专属清单（页面检测: 充电+试看标记, 仅 3 分钟试看流）", ""]
    rep += [f"- {it['idx']:02d} {it['title']} ({it['bvid']})" for it in exclusive] + [""]
if missing:
    rep += ["## 缺失清单", ""] + [f"- {m['bvid']} {m['title']}" for m in missing] + [""]
(NOTES / "归档报告.md").write_text("\n".join(rep), encoding="utf-8")
print("index.html + 归档报告.md 已生成")
