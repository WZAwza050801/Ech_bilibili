# -*- coding: utf-8 -*-
"""yt_blog.py — Ech_youtube·访谈/播客类博客笔记管线
用法: python yt_blog.py <video_id 或 URL> [--host "Lex Fridman"] [--guest "Terence Tao"]
流程: yt-dlp 元数据(含章节)+音轨 → wav → faster-whisper 转写(en)
      → LLM 说话人标注(语义区分, 双人访谈) → LLM 分批翻译(英→中)
      → 中英对照博客笔记 HTML
产出: runs/<id>/ 下 transcript.json / speakers.json / translation.json / 博客笔记.html

设计说明:
- 说话人区分不用 pyannote(需 HF token + torch, CPU 慢), 用 LLM 语义标注:
  双人访谈里"提问/承接/引述"与"回答/第一人称研究叙事"内容特征极强, 可靠性足够;
  无法判定的段落沿用上一段说话人(对话连续性假设)。
- 每阶段独立缓存 + 完整性校验, 断点续跑。
"""
import json, os, io, sys, re, time, shutil
from pathlib import Path

if not getattr(sys.stdout, "_ech_wrapped", False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"); sys.stdout._ech_wrapped = True
if not getattr(sys.stderr, "_ech_wrapped", False):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"); sys.stderr._ech_wrapped = True

WORK = Path(r"D:\视频观看agent编写\Ech_youtube")
sys.path.insert(0, str(WORK))
from yt_pipeline import fetch_audio, fmt_ts, rm, log, TRASH  # 复用平台感知层工具

# ---- LLM (与 polish.py 同款) ----
secrets = json.load(open(r"D:\密码书\private\private-ai-api-secrets.json", encoding="utf-8"))
_entry = next(e for e in secrets["entries"] if e.get("label") == "Environment DEEPSEEK_API_KEY")
API_KEY, BASE_URL, MODEL = _entry["apiKey"], (_entry.get("baseUrl") or "https://api.deepseek.com").rstrip("/"), "deepseek-chat"

def call_llm(system, user, temp=0.2, retry=3, timeout=300):
    import urllib.request
    body = json.dumps({"model": MODEL, "temperature": temp, "stream": False,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode("utf-8")
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {API_KEY}",
                                                  "Content-Type": "application/json"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            return json.loads(opener.open(req, timeout=timeout).read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last = e; time.sleep(3 * (i + 1))
    raise RuntimeError(f"LLM 调用失败: {last}")

# ---- 元数据(含章节) ----
def fetch_meta_blog(vid):
    from yt_dlp import YoutubeDL
    proxy = os.environ.get("YT_PROXY", "http://127.0.0.1:12000")
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "proxy": proxy}) as ydl:
        v = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    return {"vid": vid, "title": v.get("title", vid), "owner": v.get("uploader", ""),
            "duration": int(v.get("duration") or 0), "webpage_url": v.get("webpage_url", ""),
            "chapters": [{"title": c["title"], "start": float(c["start_time"])} for c in (v.get("chapters") or [])]}

# ---- 转写(进程内, 参数与 B 站版一致) ----
def transcribe(run_dir, lang="en"):
    from faster_whisper import WhisperModel
    model_dir = Path(r"D:\视频观看agent编写\work\pipeline1\models\faster-whisper-small")
    t0 = time.time()
    log("[asr] 加载 small/int8 (cpu_threads=4)...")
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", cpu_threads=4)
    segments, info = model.transcribe(str(run_dir / "audio.wav"), language=lang,
                                      vad_filter=True, vad_parameters={"min_silence_duration_ms": 500},
                                      condition_on_previous_text=False, beam_size=5)
    segs = []
    for seg in segments:
        segs.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()})
        if len(segs) % 50 == 0:
            log(f"[asr] t={seg.end/60:.0f}min 段数={len(segs)} 耗时{time.time()-t0:.0f}s")
    (run_dir / "transcript.json").write_text(json.dumps(
        {"language": info.language, "duration": info.duration, "segments": segs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[asr] 完成: {len(segs)} 段 / {info.duration/60:.0f}min / 耗时 {time.time()-t0:.0f}s")
    return info.duration

# ---- 合并成小段(18s, 减少单段跨说话人) ----
def make_paras(segs, span=18.0):
    paras, buf, start = [], [], None
    for s in segs:
        if start is None: start = s["start"]
        buf.append(s["text"])
        if s["end"] - start >= span:
            paras.append({"start": round(start, 1), "text": "".join(buf)})
            buf, start = [], None
    if buf: paras.append({"start": round(start or 0, 1), "text": "".join(buf)})
    return paras

# ---- 章节归属 ----
def assign_chapters(paras, chapters):
    if not chapters:
        return [["全程", p] for p in paras]
    out = []
    for p in paras:
        cur = chapters[0]["title"]
        for c in chapters:
            if p["start"] >= c["start"] - 1: cur = c["title"]
        out.append([cur, p])
    return out

# ---- 说话人标注 ----
def label_speakers(paras, host, guest):
    SYS = (f"你在标注一档双人访谈播客的说话人。主持人是 {host}，嘉宾是 {guest}。\n"
           "判断依据：\n"
           f"- 提问、话题引入、过渡总结、复述嘉宾观点、广告口播、节目开场白 → {host}\n"
           f"- 回答问题、第一人称研究/工作叙事、专业论述 → {guest}\n"
           "- 结合上下文连贯性：一个问题之后通常是对方的回答。\n"
           "用户会给你带编号 [n] 的段落（含前文已标注内容作参考）。"
           "输出每段编号与说话人，一行一段，格式严格为 `[n] 名字`（名字只能是 "
           f"{host} 或 {guest}）。不要任何解释。")
    names = [host, guest]
    out, prev_ctx = [], []
    for bi in range(0, len(paras), 10):
        batch = paras[bi:bi + 10]
        ctx = "\n".join(f"[{x['idx']}] {x['speaker']}: {x['text'][:120]}" for x in prev_ctx[-3:])
        numbered = "\n".join(f"[{p['idx']}] {p['text']}" for p in batch)
        text = (f"前文（已标注）:\n{ctx}\n\n待标注:\n{numbered}") if ctx else numbered
        got = {}
        for line in call_llm(SYS, text, temp=0.1).splitlines():
            m = re.match(r"^\[(\d+)\]\s*(.+)$", line.strip())
            if m:
                n = int(m.group(1)); who = m.group(2).strip()
                if who in names: got[n] = who
        last = out[-1]["speaker"] if out else guest
        for p in batch:
            who = got.get(p["idx"]) or last   # 漏标沿用上一说话人
            out.append({"idx": p["idx"], "start": p["start"], "speaker": who, "text": p["text"]})
            last = who
        prev_ctx = out[-3:]
        log(f"[diarize] {min(bi+10,len(paras))}/{len(paras)} 段")
    return out

# ---- 翻译 ----
GLOSSARY = ("专有名词对照（务必遵守）：Terence Tao=陶哲轩；Lex Fridman=莱克斯·弗里德曼。"
            "数学/物理专业术语首次出现时中文后括注英文，如：纳维-斯托克斯方程（Navier-Stokes）。")
SYS_TR = ("你是专业的播客访谈译者。把英文对话段落翻译成自然流畅的简体中文书面语（博客阅读风格）。要求：\n"
          "1. 忠实原意，不增删观点，可以适度意译让中文通顺；\n"
          "2. 口语冗余（um, you know, I mean）可省略；\n"
          "3. " + GLOSSARY + "\n"
          "4. 人名、例子、数字必须保留；\n"
          "5. 输入每段以 [n] 开头，输出同样以 [n] 开头、一行一段、顺序不变。只输出译文。")

def translate(spk_items):
    out = [dict(x) for x in spk_items]
    for bi in range(0, len(out), 5):
        batch = out[bi:bi + 5]
        numbered = "\n".join(f"[{p['idx']}] {p['text']}" for p in batch)
        got = {}
        for line in call_llm(SYS_TR, numbered, temp=0.3).splitlines():
            m = re.match(r"^\[(\d+)\]\s*(.+)$", line.strip())
            if m: got[int(m.group(1))] = m.group(2).strip()
        for p in batch:
            zh = got.get(p["idx"], "")
            if not zh:  # 单段重试
                m2 = re.search(r"\[(\d+)\]\s*(.+)", call_llm(SYS_TR, f"[{p['idx']}] {p['text']}", temp=0.3))
                zh = m2.group(2).strip() if m2 else ""
            p["zh"] = zh
        done = min(bi + 5, len(out))
        log(f"[translate] {done}/{len(out)} 段")
    return out

# ---- 渲染 ----
def render(meta, run_dir, chapters, host, guest):
    import html as H
    items = json.loads((run_dir / "translation.json").read_text(encoding="utf-8"))
    raw = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))["segments"]
    # 按章节分组
    chap_order, groups = [], {}
    for it in items:
        cur = chapters[0]["title"] if chapters else "全程"
        for c in chapters:
            if it["start"] >= c["start"] - 1: cur = c["title"]
        if cur not in groups:
            groups[cur] = []; chap_order.append((cur, chapters[[c["title"] for c in chapters].index(cur)]["start"] if chapters else 0))
        groups[cur].append(it)
    def chip(spk):
        cls = "tao" if spk == guest else "lex"
        name = "陶哲轩" if spk == guest else ("莱克斯" if spk == host else H.escape(spk))
        return f'<span class="who {cls}">{name}</span>'
    zh_secs, pair_secs, toc = [], [], []
    for n, (title, st) in enumerate(chap_order, 1):
        its = groups[title]
        anchor = f"ch{n}"
        toc.append(f'<a href="#{anchor}">{n:02d} {H.escape(title)}</a>')
        zh_html = "".join(
            f'<p>{chip(i["speaker"])}<span class="ts">{fmt_ts(i["start"])}</span>{H.escape(i["zh"] or "（翻译缺失）")}</p>'
            for i in its)
        zh_secs.append(f'<div class="ch" id="{anchor}"><h3>{n:02d} · {H.escape(title)}</h3>{zh_html}</div>')
        pair_html = "".join(
            f'<div class="pair"><div class="en">{chip(i["speaker"])}{H.escape(i["text"])}</div>'
            f'<div class="zh">{H.escape(i["zh"] or "（翻译缺失）")}</div></div>' for i in its)
        pair_secs.append(f'<div class="ch"><h3>{n:02d} · {H.escape(title)}</h3>{pair_html}</div>')
    raw_html = "\n".join(f'<div class="tp"><span class="tt">{fmt_ts(s["start"])}</span>{H.escape(s["text"])}</div>' for s in raw)
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>博客笔记 · {H.escape(meta['title'])}</title>
<style>
:root{{--bg:#faf9f6;--ink:#26221c;--ink2:#57503f;--ink3:#98917d;--blue:#3f5e8c;--blue-bg:#eaf0f7;--amber:#9a6b2f;--amber-bg:#f6efe2;--border:#e7e1d4}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Georgia,"Noto Serif SC",SimSun,serif;background:var(--bg);color:var(--ink);line-height:2;font-size:15.5px}}
.page{{max-width:900px;margin:0 auto;padding:0 26px 80px}}
.hero{{background:linear-gradient(150deg,#1f2a44,#3f5e8c 60%,#6b84ab);color:#fff;border-radius:0 0 22px 22px;padding:44px 40px;margin-bottom:24px}}
.hero h1{{font-size:24px;font-weight:800;line-height:1.45}} .hero p{{opacity:.9;font-size:14px;margin-top:8px}}
.info{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:13px 20px;margin:-14px 0 24px;display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px;color:var(--ink2)}}
.info b{{color:var(--blue)}}
.toc{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:14px 20px;margin-bottom:10px;font-family:"Segoe UI",sans-serif;font-size:13.5px}}
.toc a{{display:inline-block;margin:3px 14px 3px 0;color:var(--blue);text-decoration:none}} .toc a:hover{{text-decoration:underline}}
.notice{{background:var(--amber-bg);border-radius:10px;padding:12px 16px;font-size:12.5px;color:var(--amber);margin:14px 0 4px}}
h2{{font-size:19px;margin:38px 0 12px;border-left:5px solid var(--blue);padding-left:12px;font-family:"Segoe UI","PingFang SC",sans-serif}}
.ch{{margin:26px 0}} .ch h3{{font-size:16.5px;color:var(--blue);font-family:"Segoe UI","PingFang SC",sans-serif;border-bottom:1px solid var(--blue-bg);padding-bottom:6px;margin-bottom:10px}}
.ch p{{margin:10px 0;text-align:justify;color:var(--ink2)}}
.who{{font:600 12px "Segoe UI","PingFang SC",sans-serif;border-radius:6px;padding:1px 8px;margin-right:8px;white-space:nowrap}}
.who.tao{{background:var(--amber-bg);color:var(--amber)}} .who.lex{{background:var(--blue-bg);color:var(--blue)}}
.ts{{background:#eef1f6;color:#64748b;border-radius:5px;padding:0 7px;font:11.5px Consolas,monospace;margin-right:8px}}
.pair{{margin:14px 0;padding:12px 16px;background:#fff;border:1px solid var(--border);border-radius:10px}}
.pair .en{{color:var(--ink2);font-size:14px;line-height:1.9}}
.pair .zh{{margin-top:8px;padding-top:8px;border-top:1px dashed var(--border);color:var(--ink);font-size:14.5px}}
details{{margin-top:26px}} summary{{cursor:pointer;font-family:"Segoe UI",sans-serif;font-size:14px;font-weight:700;color:var(--ink3);padding:10px 14px;background:#f1f3f7;border-radius:9px}}
.tp{{padding:6px 0;border-bottom:1px dashed #e2e8f0;font-size:12.5px;color:var(--ink3)}}
.foot{{margin-top:40px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;color:var(--ink3)}}
</style></head><body><div class="page">
<div class="hero"><h1>{H.escape(meta['title'])}</h1>
<p>{H.escape(meta['owner'])} · Ech_youtube 访谈类博客笔记（说话人标注 + 中英对照）</p></div>
<div class="info"><span><b>频道</b> {H.escape(meta['owner'])}</span><span><b>嘉宾</b> 陶哲轩 Terence Tao</span>
<span><b>时长</b> {fmt_ts(meta['duration'])}</span><span><b>链接</b> youtu.be/{meta['vid']}</span></div>
<div class="toc">{''.join(toc)}</div>
<div class="notice">📝 说明：逐字稿由 faster-whisper 转写；<b>说话人由 LLM 依据对话内容语义标注</b>（双人访谈，非声学分离，极少数段落可能归属存疑）；译文由 LLM 翻译（陶哲轩/莱克斯·弗里德曼等专名已按对照表统一）。文末附<b>中英对照全文</b>与原始机器转写折叠。</div>
<h2>一、中文译读版</h2>
{''.join(zh_secs)}
<h2>二、中英对照全文</h2>
{''.join(pair_secs)}
<details><summary>▸ 展开原始机器转写全文（英文 ASR，可查证）</summary>
<div style="border:1px dashed var(--border);border-radius:10px;padding:12px 16px;margin-top:12px;max-height:480px;overflow-y:auto">{raw_html}</div></details>
<div class="foot">Ech_youtube 管线（访谈类）自动生成 · {time.strftime('%Y-%m-%d %H:%M')} · yt-dlp→ASR→diarize→translate→HTML</div>
</div></body></html>"""
    out = run_dir / "博客笔记.html"
    out.write_text(page, encoding="utf-8")
    log(f"博客笔记已生成: {out}")

def main():
    # deno (JS runtime) 供 yt-dlp 解 n-challenge, 必须在 PATH 里
    deno_bin = WORK / "bin"
    if (deno_bin / "deno.exe").exists():
        os.environ["PATH"] = str(deno_bin) + os.pathsep + os.environ["PATH"]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    vid = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", args[0]).group(1) if args and "http" in args[0] else (args[0] if args else "HUkBz-cdB-k")
    host = "Lex Fridman"; guest = "Terence Tao"
    if "--host" in sys.argv: host = sys.argv[sys.argv.index("--host") + 1]
    if "--guest" in sys.argv: guest = sys.argv[sys.argv.index("--guest") + 1]
    run_dir = WORK / "runs" / vid
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"=== Ech_youtube 访谈管线开始: {vid} (host={host}, guest={guest}) ===")

    meta = fetch_meta_blog(vid)
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    chapters = meta["chapters"]
    log(f"视频: {meta['title']} | {fmt_ts(meta['duration'])} | 章节 {len(chapters)} 个")

    wav = run_dir / "audio.wav"
    if not wav.exists():
        fetch_audio(vid, run_dir)

    # 转写(带完整性校验)
    need = True
    if (run_dir / "transcript.json").exists():
        tr = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
        if tr.get("duration", 0) >= meta["duration"] * 0.95:
            log("transcript.json 缓存命中"); need = False
        else:
            log(f"转写不完整({tr.get('duration',0):.0f}s), 重跑"); rm(run_dir / "transcript.json")
    if need:
        dur = transcribe(run_dir, lang="en")
        if dur < meta["duration"] * 0.95:
            raise RuntimeError(f"转写时长不足: {dur:.0f}s / {meta['duration']}s")

    # 说话人标注(缓存+校验)
    segs = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))["segments"]
    paras = make_paras(segs)
    for i, p in enumerate(paras): p["idx"] = i
    log(f"合并为 {len(paras)} 段 (~18s/段)")
    if (run_dir / "speakers.json").exists():
        spk = json.loads((run_dir / "speakers.json").read_text(encoding="utf-8"))
        if len(spk) == len(paras):
            log("speakers.json 缓存命中"); need = False
        else:
            need = True
    else:
        need = True
    if need:
        spk = label_speakers(paras, host, guest)
        (run_dir / "speakers.json").write_text(json.dumps(spk, ensure_ascii=False, indent=1), encoding="utf-8")
    n_host = sum(1 for x in spk if x["speaker"] == host)
    log(f"说话人分布: {host} {n_host} 段 / {guest} {len(spk)-n_host} 段")

    # 翻译(缓存+校验: 全部段落都有译文才算过)
    if (run_dir / "translation.json").exists():
        tr_items = json.loads((run_dir / "translation.json").read_text(encoding="utf-8"))
        ok = len(tr_items) == len(spk) and all(x.get("zh") for x in tr_items)
        if ok:
            log("translation.json 缓存命中")
        else:
            log("翻译缓存不完整, 重翻")
            tr_items = None
    else:
        tr_items = None
    if tr_items is None:
        tr_items = translate(spk)
        miss = sum(1 for x in tr_items if not x.get("zh"))
        if miss > max(2, len(tr_items) * 0.02):
            raise RuntimeError(f"翻译缺失 {miss}/{len(tr_items)} 段")
        (run_dir / "translation.json").write_text(json.dumps(tr_items, ensure_ascii=False, indent=1), encoding="utf-8")

    render(meta, run_dir, chapters, host, guest)
    log(f"=== 访谈管线完成, 总耗时 {(time.time()-t0)/60:.1f}min ===")

if __name__ == "__main__":
    main()
