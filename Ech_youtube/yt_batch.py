# -*- coding: utf-8 -*-
"""yt_batch.py — Ech_youtube 批量跑批 → 笔记卡文件夹 + 卡片墙
用法: 把 YouTube URL 或 video_id 每行一个放进 WORK/videos.txt，然后 python yt_batch.py [输出文件夹名]
断点续跑: 输出目录里同名笔记卡已存在的自动跳过。串行执行（OOM 防线，禁止并发）。
"""
import json, io, sys, os, re, time, shutil, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WORK = Path(r"D:\视频观看agent编写\Ech_youtube")
OUT = WORK / (sys.argv[1] if len(sys.argv) > 1 else "笔记输出")
LOG = OUT / "batch_log.txt"

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:60]

def norm_vid(arg):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", arg)
    return m.group(1) if m else arg.strip()

def render_index(done, total, items):
    cards = []
    for i, it in enumerate(items, 1):
        href = f"{i:02d}-{safe_name(it['title'])}.html"
        cards.append(f"""
<a class="card" href="{href}"><div class="num">{i:02d}</div>
<div class="t">{it['title']}</div><div class="m">{it['length']} · youtu.be/{it['vid']}</div></a>""")
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Ech_youtube · 读书笔记卡</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Segoe UI","PingFang SC",sans-serif;background:#faf9f6;color:#26221c;padding:40px 24px}}
.head{{max-width:900px;margin:0 auto 28px}}
.head h1{{font-size:26px}} .head p{{color:#98917d;margin-top:6px;font-size:13.5px}}
.grid{{max-width:900px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}
.card{{display:block;background:#fff;border:1px solid #e7e1d4;border-radius:12px;padding:16px 18px;text-decoration:none;color:inherit;transition:.15s}}
.card:hover{{border-color:#3f5e8c;box-shadow:0 4px 14px rgba(63,94,140,.12);transform:translateY(-2px)}}
.num{{font:700 13px Consolas,monospace;color:#3f5e8c;margin-bottom:6px}}
.t{{font-size:14.5px;font-weight:600;line-height:1.5;margin-bottom:8px}}
.m{{font-size:11.5px;color:#98917d;font-family:Consolas,monospace}}
</style></head><body>
<div class="head"><h1>Ech_youtube · 读书笔记卡</h1>
<p>管线一（口播/观点类）· 已完成 {done}/{total} · 全部逐字稿由 ASR 转写 + LLM 格式整理，原始稿在各笔记底部可查证</p></div>
<div class="grid">{"".join(cards)}</div></body></html>"""
    (OUT / "index.html").write_text(page, encoding="utf-8")

def main():
    OUT.mkdir(exist_ok=True)
    lines = [l.strip() for l in (WORK / "videos.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    vids = [norm_vid(l) for l in lines]
    log(f"=== Ech_youtube 批量开始: 共 {len(vids)} 个视频 ===")
    done_items, failed = [], []
    for i, vid in enumerate(vids, 1):
        meta_p = WORK / "runs" / vid / "meta.json"
        note_src = WORK / "runs" / vid / "笔记.html"
        title = vid
        if meta_p.exists():
            try: title = json.loads(meta_p.read_text(encoding="utf-8"))["title"]
            except Exception: pass
        # 断点: run 目录里已有笔记 → 直接复制卡片(不改名规则按当前序号)
        existing = list(OUT.glob(f"*-{safe_name(title)}.html"))
        if existing:
            log(f"[{i}/{len(vids)}] 跳过(已完成): {title}")
            done_items.append({"vid": vid, "title": title,
                               "length": fmt_len(meta_p), "id": vid})
            continue
        log(f"[{i}/{len(vids)}] 开始: {title} ({vid})")
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(WORK / "yt_pipeline.py"), vid],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200)
            tail = (r.stdout or "")[-300:].replace("\n", " | ")
            if not note_src.exists():
                err_all = ((r.stdout or "") + (r.stderr or ""))
                if re.search(r"Unable to allocate|mkl_malloc|MemoryError", err_all):
                    for retry in range(2):
                        log(f"[{i}/{len(vids)}] OOM, 冷却 180s 后重试 ({retry+1}/2)")
                        time.sleep(180)
                        r = subprocess.run([sys.executable, str(WORK / "yt_pipeline.py"), vid],
                                           capture_output=True, text=True, encoding="utf-8",
                                           errors="replace", timeout=7200)
                        if note_src.exists(): break
                if not note_src.exists():
                    raise RuntimeError(f"产物缺失. tail: {tail} err: {(r.stderr or '')[-200:]}")
            title = json.loads(meta_p.read_text(encoding="utf-8"))["title"] if meta_p.exists() else vid
            dst = OUT / f"{i:02d}-{safe_name(title)}.html"
            shutil.copy(note_src, dst)
            done_items.append({"vid": vid, "title": title,
                               "length": fmt_len(meta_p), "id": vid})
            log(f"[{i}/{len(vids)}] 完成 {time.time()-t0:.0f}s → {dst.name}")
        except Exception as e:
            failed.append({"vid": vid, "title": title, "err": str(e)[:200]})
            log(f"[{i}/{len(vids)}] 失败: {str(e)[:150]}")
        render_index(len(done_items), len(vids), done_items)

    render_index(len(done_items), len(vids), done_items)
    log(f"=== 批量结束: 成功 {len(done_items)}/{len(vids)}, 失败 {len(failed)} ===")
    if failed:
        (OUT / "failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding="utf-8")
        log("失败清单: failed.json (可重跑本脚本自动续跑)")

def fmt_len(meta_p):
    try:
        d = int(json.loads(meta_p.read_text(encoding="utf-8"))["duration"])
        h, r = divmod(d, 3600); m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    except Exception:
        return "?"

if __name__ == "__main__":
    main()
