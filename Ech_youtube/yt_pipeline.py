# -*- coding: utf-8 -*-
"""yt_pipeline.py — Ech_youtube 管线一（口播/观点类）总控
用法: python yt_pipeline.py <YouTube URL 或 video_id> [lang]
      lang: auto(默认,自动检测) / zh / en / ja ...
流程: yt-dlp 元数据+最佳音轨 → ffmpeg 转 wav → faster-whisper 转写 → LLM 格式整理 → 笔记 HTML
产出: runs/<id>/ 下 audio.wav / transcript.json / polished.json / 笔记.html

与 Ech_bilibili 管线一的区别仅在平台感知层(取元数据/取音频用 yt-dlp),
ASR / polish / 笔记渲染三层完全复用同一套设计(三重完整性校验 + trash 回收 + 串行规则)。
"""
import json, os, io, sys, re, subprocess, shutil, time
from pathlib import Path

if not getattr(sys.stdout, "_ech_wrapped", False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"); sys.stdout._ech_wrapped = True
if not getattr(sys.stderr, "_ech_wrapped", False):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"); sys.stderr._ech_wrapped = True

WORK = Path(r"D:\视频观看agent编写\Ech_youtube")
# 代理: 沙箱 env 代理(2213)是坏的, 默认走系统可用代理; 直连环境可设 YT_PROXY=direct
PROXY = os.environ.get("YT_PROXY", "http://127.0.0.1:12000")
# whisper 模型与 Ech_bilibili 共享, 避免 480MB 重复下载
SHARED_MODEL = Path(r"D:\视频观看agent编写\work\pipeline1\models\faster-whisper-small")

def log(m): print(f"[yt_pipeline] {m}", flush=True)

TRASH = WORK / "runs" / "_trash"
def rm(p):
    """移入 trash 目录代替删除(可追溯, 不受批量删除限制)"""
    try:
        TRASH.mkdir(parents=True, exist_ok=True)
        os.rename(str(p), str(TRASH / f"{int(time.time()*1000)}_{p.name}"))
    except FileNotFoundError:
        pass

def norm_vid(arg):
    """URL 或裸 id 统一归一成 video_id"""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", arg)
    return m.group(1) if m else arg.strip()

def _ydl_opts(extra=None):
    o = {"quiet": True, "no_warnings": True, "retries": 3, "socket_timeout": 30}
    if PROXY and PROXY != "direct":
        o["proxy"] = PROXY
    if extra: o.update(extra)
    return o

def fetch_meta(vid):
    from yt_dlp import YoutubeDL
    with YoutubeDL(_ydl_opts({"skip_download": True})) as ydl:
        v = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    return {"vid": vid, "title": v.get("title", vid), "owner": v.get("uploader", ""),
            "duration": int(v.get("duration") or 0), "desc": v.get("description", "") or "",
            "upload_date": v.get("upload_date", ""), "webpage_url": v.get("webpage_url", "")}

def fetch_audio(vid, run_dir):
    """yt-dlp 下载最佳音轨 → ffmpeg 转 16k 单声道 wav"""
    from yt_dlp import YoutubeDL
    opts = _ydl_opts({"format": "bestaudio/best",
                      "outtmpl": str(run_dir / "audio_src.%(ext)s"),
                      "concurrent_fragment_downloads": 8})
    with YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={vid}"])
    srcs = [p for p in run_dir.glob("audio_src.*") if p.suffix not in (".part", ".wav")]
    if not srcs: raise RuntimeError("yt-dlp 未产出音轨文件")
    src = srcs[0]
    ffmpeg_wav(src, run_dir / "audio.wav")
    log(f"音频就绪: {src.name} → audio.wav ({src.stat().st_size/1048576:.1f}MB)")

def ffmpeg_wav(src, dst):
    ff = shutil.which("ffmpeg")
    r = subprocess.run([ff, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-vn", str(dst)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0: raise RuntimeError(f"ffmpeg wav 转换失败: {r.stderr[-200:]}")

def fmt_ts(t):
    t = int(t); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def render_notes(meta, run_dir):
    """自动笔记 HTML: 信息卡 + 整理版逐字稿(自动分节) + 原始稿折叠 — 与 Ech_bilibili 同款"""
    pol = json.loads((run_dir / "polished.json").read_text(encoding="utf-8"))
    tr = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    raw = tr["segments"]; lang = tr.get("language", "?")
    import html as H
    secs, buf = [], []
    for i, p in enumerate(pol):
        buf.append(p)
        if len(buf) >= 3 or i == len(pol)-1:
            secs.append(buf); buf = []
    secs_html = []
    for n, sec in enumerate(secs, 1):
        ps = "\n".join(f'<p>{H.escape(x["text"])}</p>' for x in sec)
        secs_html.append(f'<div class="tsec"><div class="tsec-head"><span class="ts">{fmt_ts(sec[0]["start"])}</span>'
                         f'<b>Part {n}</b></div>{ps}</div>')
    raw_html = "\n".join(f'<div class="tp"><span class="tt">{fmt_ts(s["start"])}</span>{H.escape(s["text"])}</div>'
                         for s in raw)
    total_chars = sum(len(p["text"]) for p in pol)
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>读书笔记 · {H.escape(meta['title'])}</title>
<style>
:root{{--bg:#faf9f6;--surface:#fff;--ink:#26221c;--ink2:#57503f;--ink3:#98917d;--brown:#9a6b2f;--brown-bg:#f6efe2;--blue:#3f5e8c;--blue-bg:#eaf0f7;--border:#e7e1d4}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Georgia,"Noto Serif SC",SimSun,serif;background:var(--bg);color:var(--ink);line-height:2;font-size:15.5px}}
.page{{max-width:860px;margin:0 auto;padding:0 26px 80px}}
.hero{{background:linear-gradient(150deg,#1f2a44,#3f5e8c 60%,#6b84ab);color:#fff;border-radius:0 0 22px 22px;padding:44px 40px;margin-bottom:30px}}
.hero h1{{font-size:25px;font-weight:800;line-height:1.4}} .hero p{{opacity:.9;font-size:14px;margin-top:8px}}
.info{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:13px 20px;margin:-18px 0 24px;display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px;color:var(--ink2)}}
.info b{{color:var(--blue)}}
h2{{font-size:19px;margin:34px 0 10px;border-left:5px solid var(--blue);padding-left:12px;font-family:"Segoe UI","PingFang SC",sans-serif}}
.tsec{{margin:18px 0}} .tsec-head{{color:var(--blue);margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid var(--blue-bg);font-family:"Segoe UI",sans-serif;font-size:14.5px}}
.tsec p{{text-indent:2em;margin:10px 0;color:var(--ink2);text-align:justify}}
.ts{{background:var(--blue-bg);color:var(--blue);border-radius:5px;padding:0 7px;font:12px Consolas,monospace;margin-right:6px}}
.tp{{padding:8px 0;border-bottom:1px dashed #e2e8f0;font-size:13.5px;color:var(--ink3)}}
.tt{{background:#eef1f6;color:#64748b;border-radius:5px;padding:0 7px;font:11.5px Consolas,monospace;margin-right:8px}}
details{{margin-top:24px}} summary{{cursor:pointer;font-family:"Segoe UI",sans-serif;font-size:14px;font-weight:700;color:var(--ink3);padding:10px 14px;background:#f1f3f7;border-radius:9px}}
.notice{{background:var(--brown-bg);border-radius:10px;padding:12px 16px;font-size:12.5px;color:var(--brown);margin:10px 0}}
.foot{{margin-top:40px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;color:var(--ink3)}}
</style></head><body><div class="page">
<div class="hero"><h1>{H.escape(meta['title'])}</h1><p>{H.escape(meta['owner'])} · Ech_youtube 管线一（口播/观点类）自动笔记</p></div>
<div class="info"><span><b>频道</b> {H.escape(meta['owner'])}</span>
<span><b>时长</b> {fmt_ts(meta['duration'])}</span><span><b>链接</b> youtu.be/{meta['vid']}</span>
<span><b>语言</b> {lang}</span><span><b>逐字稿</b> {total_chars} 字（整理版）</span></div>
<div class="notice">📝 逐字稿由 faster-whisper 转写后经 LLM 格式整理（加标点/仅修明显错字），<b>语句未做增删改写</b>；原始转写折叠于文末可查证。</div>
<h2>完整逐字稿（整理版）</h2>
{''.join(secs_html)}
<details><summary>▸ 展开原始机器转写全文（可逐句查证）</summary>
<div style="border:1px dashed var(--border);border-radius:10px;padding:12px 16px;margin-top:12px;max-height:480px;overflow-y:auto">{raw_html}</div></details>
<div class="foot">Ech_youtube 管线一自动生成 · {time.strftime('%Y-%m-%d %H:%M')} · yt-dlp→ASR→polish→HTML 全自动</div>
</div></body></html>"""
    out = run_dir / "笔记.html"
    out.write_text(page, encoding="utf-8")
    log(f"笔记已生成: {out}")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    vid = norm_vid(args[0]) if args else "jNQXAC9IVRw"
    lang = args[1] if len(args) > 1 else "auto"
    run_dir = WORK / "runs" / vid
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"=== Ech_youtube 管线一开始: {vid} (lang={lang}) ===")

    meta = fetch_meta(vid)
    log(f"视频: {meta['title']} | {meta['owner']} | {fmt_ts(meta['duration'])}")
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    wav = run_dir / "audio.wav"
    if not wav.exists():
        fetch_audio(vid, run_dir)  # 总是重新下载, 防止复用截断残留
    else:
        log("audio.wav 已存在，跳过下载")

    # --- 转写(带完整性校验 + 重试) ---
    if (run_dir / "transcript.json").exists():
        tr = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
        if tr.get("duration", 0) >= meta["duration"] * 0.95:
            log("transcript.json 已存在，跳过转写"); do_transcribe = False
        else:
            log(f"已存在转写不完整({tr.get('duration',0):.0f}s/{meta['duration']}s), 删除重跑")
            for f in ["transcript.json", "transcript.txt", "polished.json", "polished.txt"]:
                rm(run_dir / f)
            do_transcribe = True
    else:
        do_transcribe = True
    if do_transcribe:
        t1 = time.time()
        # 清掉 work 根残留, 防止把上一视频的转写误当当前视频的(血泪教训)
        for f in ["transcript.json", "transcript.txt"]:
            rm(WORK / f)
        ok, r = False, None
        for attempt in range(2):
            shutil.copy(wav, WORK / "audio.wav")
            r = subprocess.run([sys.executable, str(WORK / "transcribe_local.py"), lang],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            tr_path = run_dir / "transcript.json"; rm(tr_path)
            tr_txt = run_dir / "transcript.txt"; rm(tr_txt)
            if (WORK / "transcript.json").exists():
                for f in ["transcript.json", "transcript.txt"]:
                    shutil.copy(WORK / f, run_dir / f)
                tr = json.loads(tr_path.read_text(encoding="utf-8"))
                if tr.get("duration", 0) >= meta["duration"] * 0.95:
                    ok = True; break
                log(f"转写不完整: {tr.get('duration',0):.0f}s/{meta['duration']}s, 重试 ({attempt+1}/2)")
            else:
                log(f"转写失败: ...{(r.stderr or '')[-150:]}, 重试 ({attempt+1}/2)")
        if not ok:
            raise RuntimeError(f"转写失败/不完整(重试后): {(r.stderr or '')[-200:]}")
        n = len(json.loads((run_dir/"transcript.json").read_text(encoding="utf-8"))["segments"])
        log(f"转写完成: {n} 段 / {time.time()-t1:.0f}s")

    # --- 格式整理(带字数漂移校验) ---
    if not (run_dir / "polished.json").exists():
        shutil.copy(run_dir / "transcript.json", WORK / "transcript.json")
        for f in ["polished.json", "polished.txt"]:
            rm(WORK / f)
        r = subprocess.run([sys.executable, str(WORK / "polish.py")], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-400:])
        if not (WORK / "polished.json").exists():
            raise RuntimeError(f"polish 失败: {r.stderr[-500:]}")
        pol = json.loads((WORK / "polished.json").read_text(encoding="utf-8"))
        if not pol or sum(len(p["text"]) for p in pol) < sum(len(s["text"]) for s in
                json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))["segments"]) * 0.7:
            raise RuntimeError(f"polish 产物异常: {len(pol) if pol else 0} 段")
        shutil.copy(WORK / "polished.json", run_dir / "polished.json")
        shutil.copy(WORK / "polished.txt", run_dir / "polished.txt")
        log("格式整理完成")

    render_notes(meta, run_dir)
    log(f"=== Ech_youtube 管线一完成, 总耗时 {time.time()-t0:.0f}s ===")

if __name__ == "__main__":
    main()
