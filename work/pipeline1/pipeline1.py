# -*- coding: utf-8 -*-
"""pipeline1.py — 管线一（口播/观点类）总控
用法: python pipeline1.py BV1GbNH6hE8f
流程: B站音频直取 → ffmpeg 转wav → faster-whisper 转写 → LLM格式整理(polish) → 自动笔记HTML
产出: runs/<BV>/ 下 audio.wav / transcript.json / polished.json / 笔记.html
"""
import json, os, io, sys, re, subprocess, shutil, time
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WORK = Path(r"D:\视频观看agent编写\work\pipeline1")
VENV_PY = r"C:\Users\31168\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# 优先使用 fresh_buvid.json 现场申请的真指纹（假 buvid 连跑一批后会被 412 拉黑）
_b3, _b4 = "FD0E1A9D-8D6B-4E0C-9B7E-2C3D4E5F6A7Binfoc", "9A8B7C6D-5E4F-3A2B-1C0D-9E8F7A6B5C4D-1240000000"
try:
    _fb = json.loads((WORK / "fresh_buvid.json").read_text(encoding="utf-8"))
    _b3, _b4 = _fb["buvid3"], _fb["buvid4"]
except Exception:
    pass
HDRS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.bilibili.com",
    "Referer": "https://www.bilibili.com/",
    # 关键: 完整 cookie 组（仅 buvid3 一项会被 412 风控拦截）
    "Cookie": (f"buvid3={_b3}; "
               f"buvid4={_b4}; "
               "b_nut=1726400000; "
               "b_lsid=ABC12DEF_198ABC12; "
               "enable_web_push=DISABLE; "
               "header_theme_version=CUSTOM; "
               "home_feed_column=5; "
               "dpi=192"),
}

def log(m): print(f"[pipeline1] {m}", flush=True)

TRASH = WORK / "runs" / "_trash"
def rm(p):
    """移入 trash 目录代替删除(可追溯, 且不受批量删除限制)"""
    try:
        TRASH.mkdir(parents=True, exist_ok=True)
        os.rename(str(p), str(TRASH / f"{int(time.time()*1000)}_{p.name}"))
    except FileNotFoundError:
        pass

# 禁系统代理直连（系统代理对 api.bilibili.com 会返回 412，与 deepseek 调用同款写法）
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def http_get(url, headers, timeout=30, retries=3):
    """禁代理 GET，412/5xx 指数退避重试"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            return OPENER.open(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (412, 429, 500, 502, 503) and i < retries - 1:
                wait = 25 * (i + 1) if e.code == 412 else 3 * (i + 1)
                log(f"HTTP {e.code}，{wait}s 后重试 ({i+1}/{retries-1})")
                time.sleep(wait)
            else:
                raise
    raise last

def fetch_meta(bvid):
    d = json.loads(http_get(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", HDRS).decode("utf-8"))
    if d.get("code") != 0: raise RuntimeError(f"view API: {d.get('message')}")
    v = d["data"]
    return {"bvid": bvid, "title": v["title"], "owner": v["owner"]["name"],
            "owner_mid": v["owner"]["mid"], "duration": v["duration"], "cid": v["cid"],
            "desc": v["desc"], "pubdate": v["pubdate"]}

def fetch_audio(bvid, cid, dst):
    url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&platform=pc&high_quality=1"
    d = json.loads(http_get(url, HDRS).decode("utf-8"))
    data = d.get("data") or {}
    # 新转码视频走 dash(音视频分离); 老视频只回 durl(单文件流, 音频内嵌), 用 ffmpeg 照样能抽
    dash_audios = (data.get("dash") or {}).get("audio") or []
    if dash_audios:
        dash_audios.sort(key=lambda a: -a.get("bandwidth", 0))
        best = dash_audios[0]
    else:
        durl = data.get("durl") or []
        if not durl:
            raise RuntimeError(f"playurl 既无 dash 音频也无 durl (code={d.get('code')}, msg={d.get('message')})")
        best = durl[0]
        log(f"无 dash, 回退 durl 模式 ({data.get('format')}, {best.get('size', 0)/1048576:.1f}MB)")
    def _cands(b):
        out = []
        for k in ("baseUrl", "base_url"):
            if b.get(k): out.append(b[k]); break
        for k in ("backupUrl", "backup_url"):
            v = b.get(k)
            if isinstance(v, list): out.extend(v)
            elif v: out.append(v)
        for k in ("url",):
            v = b.get(k)
            if isinstance(v, list): out.extend(v)
            elif v and not out: out.append(v)
        return out or [None]
    for attempt in _cands(best):
        try:
            req = urllib.request.Request(attempt, headers=HDRS)
            tmp = str(dst) + ".part"
            with OPENER.open(req, timeout=180) as r:
                total = r.headers.get("Content-Length")
                got = 0
                with open(tmp, "wb") as f:
                    while True:
                        c = r.read(1024 * 256)
                        if not c: break
                        f.write(c); got += len(c)
            # 完整性校验: 截断的 m4s 会让 ffmpeg 炸掉
            if total and got < int(total) * 0.98:
                log(f"下载不完整 {got/1048576:.1f}/{int(total)/1048576:.1f}MB, 换源重试")
                os.path.exists(tmp) and os.remove(tmp)
                continue
            os.replace(tmp, str(dst))
            log(f"音频下载 {got/1048576:.1f}MB (bandwidth={best.get('bandwidth', 'durl')})")
            return
        except Exception as e:
            log(f"下载失败回退: {e}")
            time.sleep(5)
    raise RuntimeError("音频下载失败")

def ffmpeg_wav(src, dst):
    ff = shutil.which("ffmpeg")
    r = subprocess.run([ff, "-y", "-i", src, "-ar", "16000", "-ac", "1", "-vn", dst],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0: raise RuntimeError("ffmpeg wav 转换失败")

def fmt_ts(t):
    t = int(t); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def render_notes(meta, run_dir):
    """自动笔记 HTML: 信息卡 + 整理版逐字稿(自动分节) + 原始稿折叠"""
    pol = json.loads((run_dir / "polished.json").read_text(encoding="utf-8"))
    raw = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))["segments"]
    import html as H
    # 自动分节: 每 ~3 段一节
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
.hero{{background:linear-gradient(150deg,#3f3423,#7a5a2e 60%,#9a6b2f);color:#fff;border-radius:0 0 22px 22px;padding:44px 40px;margin-bottom:30px}}
.hero h1{{font-size:25px;font-weight:800;line-height:1.4}} .hero p{{opacity:.9;font-size:14px;margin-top:8px}}
.info{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:13px 20px;margin:-18px 0 24px;display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px;color:var(--ink2)}}
.info b{{color:var(--brown)}}
h2{{font-size:19px;margin:34px 0 10px;border-left:5px solid var(--brown);padding-left:12px;font-family:"Segoe UI","PingFang SC",sans-serif}}
.tsec{{margin:18px 0}} .tsec-head{{color:var(--brown);margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid var(--brown-bg);font-family:"Segoe UI",sans-serif;font-size:14.5px}}
.tsec p{{text-indent:2em;margin:10px 0;color:var(--ink2);text-align:justify}}
.ts{{background:var(--blue-bg);color:var(--blue);border-radius:5px;padding:0 7px;font:12px Consolas,monospace;margin-right:6px}}
.tp{{padding:8px 0;border-bottom:1px dashed #eee6d6;font-size:13.5px;color:var(--ink3)}}
.tt{{background:#eef1f6;color:#64748b;border-radius:5px;padding:0 7px;font:11.5px Consolas,monospace;margin-right:8px}}
details{{margin-top:24px}} summary{{cursor:pointer;font-family:"Segoe UI",sans-serif;font-size:14px;font-weight:700;color:var(--ink3);padding:10px 14px;background:#f4f1ea;border-radius:9px}}
.notice{{background:var(--blue-bg);border-radius:10px;padding:12px 16px;font-size:12.5px;color:var(--blue);margin:10px 0}}
.foot{{margin-top:40px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;color:var(--ink3)}}
</style></head><body><div class="page">
<div class="hero"><h1>{H.escape(meta['title'])}</h1><p>{H.escape(meta['owner'])} · 管线一（口播/观点类）自动笔记</p></div>
<div class="info"><span><b>UP主</b> {H.escape(meta['owner'])} (mid {meta['owner_mid']})</span>
<span><b>时长</b> {fmt_ts(meta['duration'])}</span><span><b>链接</b> bilibili.com/video/{meta['bvid']}</span>
<span><b>逐字稿</b> {total_chars} 字（整理版）</span></div>
<div class="notice">📝 逐字稿由 faster-whisper 转写后经 LLM 格式整理（加标点/繁转简）+ 热修词典（ASR 同音错字），<b>语句未做增删改写</b>；原始转写折叠于文末可查证。观点笔记与章节脉络由人工/AI 精读后补充。</div>
<h2>完整逐字稿（整理版）</h2>
{''.join(secs_html)}
<details><summary>▸ 展开原始机器转写全文（可逐句查证）</summary>
<div style="border:1px dashed var(--border);border-radius:10px;padding:12px 16px;margin-top:12px;max-height:480px;overflow-y:auto">{raw_html}</div></details>
<div class="foot">管线一自动生成 · {time.strftime('%Y-%m-%d %H:%M')} · 音频直取→ASR→polish→HTML 全自动</div>
</div></body></html>"""
    out = run_dir / "笔记.html"
    out.write_text(page, encoding="utf-8")
    log(f"笔记已生成: {out}")

def main():
    bvid = sys.argv[1] if len(sys.argv) > 1 else "BV1GbNH6hE8f"
    run_dir = WORK / "runs" / bvid
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"=== 管线一开始: {bvid} ===")

    meta = fetch_meta(bvid)
    log(f"视频: {meta['title']} | {meta['owner']} | {fmt_ts(meta['duration'])}")
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    m4s = run_dir / "audio.m4s"; wav = run_dir / "audio.wav"
    if not wav.exists():
        fetch_audio(bvid, meta["cid"], m4s)  # 总是重新下载, 防止复用上次截断的残留 m4s
        ffmpeg_wav(m4s, wav); log("wav 转换完成")
    else:
        log("audio.wav 已存在，跳过下载")

    if not (run_dir / "transcript.json").exists():
        t1 = time.time()
        do_transcribe = True
    else:
        # 缓存命中也要校验完整性(防截断假产物)
        tr = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
        if tr.get("duration", 0) >= meta["duration"] * 0.95:
            log("transcript.json 已存在，跳过转写"); do_transcribe = False
        else:
            log(f"已存在的转写不完整({tr.get('duration',0):.0f}s/{meta['duration']}s), 删除重跑")
            rm(run_dir / "transcript.json"); rm(run_dir / "transcript.txt")
            rm(run_dir / "polished.json"); rm(run_dir / "polished.txt")
            do_transcribe = True
    if do_transcribe:
        t1 = time.time()
        # 清掉 work 根残留, 防止把上一视频的转写误当当前视频的
        for f in ["transcript.json", "transcript.txt"]:
            rm(WORK / f)
        ok = False
        for attempt in range(2):  # 失败自动重试一次
            shutil.copy(wav, WORK / "audio.wav")
            r = subprocess.run([VENV_PY, str(WORK / "transcribe_local.py")], cwd=str(WORK),
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            tr_path = run_dir / "transcript.json"
            rm(tr_path); tr_txt = run_dir / "transcript.txt"; rm(tr_txt)
            if (WORK / "transcript.json").exists():
                for f in ["transcript.json", "transcript.txt"]:
                    shutil.copy(WORK / f, run_dir / f)
                tr = json.loads(tr_path.read_text(encoding="utf-8"))
                # 完整性校验: 转写时长必须覆盖视频时长的 95%+
                if tr.get("duration", 0) >= meta["duration"] * 0.95:
                    ok = True; break
                log(f"转写不完整: {tr.get('duration',0):.0f}s/{meta['duration']}s, 重试 ({attempt+1}/2)")
            else:
                log(f"转写失败: ...{(r.stderr or '')[-150:]}, 重试 ({attempt+1}/2)")
        if not ok:
            raise RuntimeError(f"转写失败/不完整(重试后): {(r.stderr or '')[-200:]}")
        n = len(json.loads((run_dir/"transcript.json").read_text(encoding="utf-8"))["segments"])
        log(f"转写完成: {n} 段 / {time.time()-t1:.0f}s")

    if not (run_dir / "polished.json").exists():
        shutil.copy(run_dir / "transcript.json", WORK / "transcript.json")
        for f in ["polished.json", "polished.txt"]:
            rm(WORK / f)  # 清掉上次残留，防误回收旧产物
        r = subprocess.run([sys.executable, str(WORK / "polish.py")], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-400:])
        if not (WORK / "polished.json").exists():
            raise RuntimeError(f"polish 失败: {r.stderr[-500:]}")
        # 完整性校验: 字数漂移超过 ±30% 视为异常
        pol = json.loads((WORK / "polished.json").read_text(encoding="utf-8"))
        if not pol or sum(len(p["text"]) for p in pol) < sum(len(s["text"]) for s in
                json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))["segments"]) * 0.7:
            raise RuntimeError(f"polish 产物异常: {len(pol) if pol else 0} 段")
        shutil.copy(WORK / "polished.json", run_dir / "polished.json")
        shutil.copy(WORK / "polished.txt", run_dir / "polished.txt")
        log("格式整理完成")

    render_notes(meta, run_dir)
    log(f"=== 管线一完成, 总耗时 {time.time()-t0:.0f}s ===")

if __name__ == "__main__":
    main()
