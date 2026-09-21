# -*- coding: utf-8 -*-
"""重建 LexFridman-博客笔记 卡片墙 index.html(扫描 01-*.html 卡片)"""
import json, re
from pathlib import Path

OUT = Path(r"D:\视频观看agent编写\Ech_youtube\LexFridman-博客笔记")
cards = []
for f in sorted(OUT.glob("[0-9][0-9]-*.html")):
    m = re.match(r"(\d+)-(.+)\.html", f.name)
    title = m.group(2).replace("_", " ")
    cards.append(f"""<a class="card" href="{f.name}"><div class="num">{m.group(1)}</div>
<div class="t">{title}</div></a>""")
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
</style></head><body>
<div class="head"><h1>Lex Fridman 播客 · 访谈博客笔记</h1>
<p>Ech_youtube 访谈管线（说话人标注 + 中英对照）· 大佬优先排序 · 已完成 {len(cards)} 期</p></div>
<div class="grid">{''.join(cards)}</div></body></html>"""
(OUT / "index.html").write_text(page, encoding="utf-8")
print("index rebuilt:", len(cards), "cards")
