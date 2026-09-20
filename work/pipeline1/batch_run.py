# -*- coding: utf-8 -*-
"""batch_run.py — 批量跑江左道卡卡全部视频 → 读书笔记卡文件夹 + 卡片墙
断点续跑: runs/<BV>/笔记.html 已存在的自动跳过
"""
import json, io, sys, os, re, time, shutil, subprocess, traceback
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WORK = Path(r"D:\视频观看agent编写\work\pipeline1")
NOTES = Path(r"D:\视频观看agent编写\江左道卡卡-读书笔记")
LOG = NOTES / "batch_log.txt"

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:60]

def render_index(done, total, items):
    """卡片墙 index.html"""
    cards = []
    for i, it in enumerate(items, 1):
        href = f"{i:02d}-{safe_name(it['title'])}.html"
        cards.append(f"""
<a class="card" href="{href}"><div class="num">{i:02d}</div>
<div class="t">{it['title']}</div><div class="m">{it['length']} · bilibili.com/video/{it['bvid']}</div></a>""")
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
.num{{font:700 13px Consolas,monospace;color:#9a6b2f;margin-bottom:6px}}
.t{{font-size:14.5px;font-weight:600;line-height:1.5;margin-bottom:8px}}
.m{{font-size:11.5px;color:#98917d;font-family:Consolas,monospace}}
.pending{{opacity:.45}}
</style></head><body>
<div class="head"><h1>江左道卡卡 · 读书笔记卡</h1>
<p>拾音笺 EchoNotes 管线一 · 已完成 {done}/{total} · 全部逐字稿由 ASR 转写 + LLM 格式整理，原始稿在各笔记底部可查证</p></div>
<div class="grid">{"".join(cards)}</div></body></html>"""
    (NOTES / "index.html").write_text(page, encoding="utf-8")

def main():
    NOTES.mkdir(exist_ok=True)
    videos = json.loads((WORK / "video_list.json").read_text(encoding="utf-8"))
    log(f"=== 批量开始: 共 {len(videos)} 个视频 ===")
    done_items, failed = [], []
    for i, v in enumerate(videos, 1):
        bvid, title = v["bvid"], v["title"]
        note_src = WORK / "runs" / bvid / "笔记.html"
        note_dst = NOTES / f"{i:02d}-{safe_name(title)}.html"
        if note_dst.exists():
            log(f"[{i}/{len(videos)}] 跳过(已完成): {title}")
            done_items.append(v)
            continue
        log(f"[{i}/{len(videos)}] 开始: {title} ({bvid}, {v.get('length','?')})")
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(WORK / "pipeline1.py"), bvid],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
            tail = (r.stdout or "")[-300:].replace("\n", " | ")
            if not note_src.exists():
                err_all = ((r.stdout or "") + (r.stderr or ""))
                # OOM 类错误 → 冷却后轮内重试(内存低谷期常见, 等一等就好)
                if re.search(r"Unable to allocate|mkl_malloc|MemoryError", err_all):
                    for retry in range(2):
                        log(f"[{i}/{len(videos)}] OOM, 冷却 180s 后重试 ({retry+1}/2)")
                        time.sleep(180)
                        r = subprocess.run([sys.executable, str(WORK / "pipeline1.py"), bvid],
                                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
                        if note_src.exists(): break
                if not note_src.exists():
                    raise RuntimeError(f"产物缺失. tail: {tail} err: {(r.stderr or '')[-200:]}")
            shutil.copy(note_src, note_dst)
            done_items.append(v)
            log(f"[{i}/{len(videos)}] 完成 {time.time()-t0:.0f}s → {note_dst.name}")
        except Exception as e:
            failed.append({"bvid": bvid, "title": title, "err": str(e)[:200]})
            log(f"[{i}/{len(videos)}] 失败: {str(e)[:150]}")
        render_index(len(done_items), len(videos), done_items)

    render_index(len(done_items), len(videos), done_items)
    log(f"=== 批量结束: 成功 {len(done_items)}/{len(videos)}, 失败 {len(failed)} ===")
    if failed:
        (NOTES / "failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding="utf-8")
        log("失败清单: failed.json (可重跑本脚本自动续跑)")

if __name__ == "__main__":
    main()
