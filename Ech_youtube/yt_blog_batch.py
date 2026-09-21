# -*- coding: utf-8 -*-
"""yt_blog_batch.py — Lex Fridman 播客批量跑批(大佬优先) → 笔记卡文件夹 + 卡片墙
队列: lex_queue.json (fame 降序)。断点续跑: 输出文件夹已有同名笔记卡自动跳过。
串行铁律: 每期一个独立子进程(内存隔离), 一次只跑一期。
用法: python yt_blog_batch.py [输出文件夹名] [限跑期数]
"""
import json, io, sys, os, re, time, shutil, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WORK = Path(r"D:\视频观看agent编写\Ech_youtube")
OUT = WORK / (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else "LexFridman-博客笔记")
LIMIT = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 9999
LOG = OUT / "batch_log.txt"
HOST = "Lex Fridman"

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s)[:60]

def render_index(done, total, items):
    import html as H
    cards = []
    for i, it in enumerate(items, 1):
        href = f"{i:02d}-{safe_name(it['title'])}.html"
        cards.append(f"""
<a class="card" href="{href}"><div class="num">{i:02d} · #{it['num']} {H.escape(it['guest'])}</div>
<div class="t">{H.escape(it['title'])}</div><div class="m">youtu.be/{it['vid']}</div></a>""")
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Lex Fridman · 访谈博客笔记</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Segoe UI","PingFang SC",sans-serif;background:#faf9f6;color:#26221c;padding:40px 24px}}
.head{{max-width:940px;margin:0 auto 28px}}
.head h1{{font-size:26px}} .head p{{color:#98917d;margin-top:6px;font-size:13.5px}}
.grid{{max-width:940px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
.card{{display:block;background:#fff;border:1px solid #e7e1d4;border-radius:12px;padding:16px 18px;text-decoration:none;color:inherit;transition:.15s}}
.card:hover{{border-color:#3f5e8c;box-shadow:0 4px 14px rgba(63,94,140,.12);transform:translateY(-2px)}}
.num{{font:700 12.5px Consolas,monospace;color:#3f5e8c;margin-bottom:6px}}
.t{{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:8px}}
.m{{font-size:11.5px;color:#98917d;font-family:Consolas,monospace}}
</style></head><body>
<div class="head"><h1>Lex Fridman 播客 · 访谈博客笔记</h1>
<p>Ech_youtube 访谈管线（说话人标注 + 中英对照）· 大佬优先排序 · 已完成 {done}/{total}</p></div>
<div class="grid">{"".join(cards)}</div></body></html>"""
    (OUT / "index.html").write_text(page, encoding="utf-8")

def main():
    OUT.mkdir(exist_ok=True)
    queue = json.loads((WORK / "lex_queue.json").read_text(encoding="utf-8"))[:LIMIT]
    # #472 陶哲轩已跑过, 若在队列中直接补卡片
    log(f"=== Lex Fridman 批量开始: 队列 {len(queue)} 期 (大佬优先) ===")
    done_items, failed = [], []
    for i, ep in enumerate(queue, 1):
        vid, title, guest = ep["vid"], ep["title"], ep["guest"]
        note_src = WORK / "runs" / vid / "博客笔记.html"
        existing = list(OUT.glob(f"{i:02d}-*.html"))
        if existing:
            log(f"[{i}/{len(queue)}] 跳过(卡片已存在): #{ep['num']} {guest}")
            done_items.append(ep)
            continue
        log(f"[{i}/{len(queue)}] 开始: #{ep['num']} {guest} ({vid}) fame={ep['fame']}")
        t0 = time.time()
        try:
            if not note_src.exists():
                r = subprocess.run([sys.executable, str(WORK / "yt_blog.py"), vid,
                                    "--guest", guest, "--host", HOST],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=6 * 3600)
                tail = (r.stdout or "")[-300:].replace("\n", " | ")
                if not note_src.exists():
                    raise RuntimeError(f"产物缺失. tail: {tail} err: {(r.stderr or '')[-300:]}")
            dst = OUT / f"{i:02d}-{safe_name(title)}.html"
            shutil.copy(note_src, dst)
            done_items.append(ep)
            log(f"[{i}/{len(queue)}] 完成 {time.time()-t0:.0f}s → {dst.name}")
        except Exception as e:
            failed.append({"vid": vid, "num": ep["num"], "guest": guest, "err": str(e)[:300]})
            log(f"[{i}/{len(queue)}] 失败: {str(e)[:200]}")
        render_index(len(done_items), len(queue), done_items)
        # 席位顺延: 失败的不占卡位, 已有卡片重编号可能导致 glob 断点错位 — 接受(卡片按完成顺序编号)

    render_index(len(done_items), len(queue), done_items)
    log(f"=== 批量结束(或中断): 成功 {len(done_items)}/{len(queue)}, 失败 {len(failed)} ===")
    if failed:
        (OUT / "failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
