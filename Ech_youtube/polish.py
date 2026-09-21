# -*- coding: utf-8 -*-
"""polish.py — Ech_youtube·格式整理模块（自动化，替代人工整理）
输入: transcript.json (faster-whisper 段落, 含 language 字段)
输出: polished.json (带时间戳的整理后段落) + polished.txt
与 Ech_bilibili 同款设计: 便宜快速模型分批处理, [n] 序号对应 + 字数校验, 禁止改写。
区别: 按转写语言分两套 prompt — 中文(标点/繁转简/同音错字+热修词典) / 其他语言(仅标点+大小写)。
"""
import json, io, sys, time, re
from pathlib import Path
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ech_config import ECH_YT_DIR as work, llm_credentials

# ---- LLM 凭据(ech_config: 环境变量优先, 回退密码书; 不在日志中打印 key) ----
API_KEY, BASE_URL, MODEL = llm_credentials()

SYS_ZH = (
"你是一个 ASR 转写稿格式整理器。用户会给你视频口播的语音转写片段（可能无标点、繁简混杂、有同音错字）。"
"你的任务【只有格式整理】，严格遵守：\n"
"1. 添加中文标点（，。？！、；：「」……），按语气和逻辑断句；\n"
"2. 繁体字统一转换为简体字；\n"
"3. 修正明显的 ASR 同音错字，只修正有把握的，没把握的保留原词；\n"
"4. 【绝对禁止】改写句式、增删任何词语、概括总结、把口语改书面语、修正语序；\n"
"5. 口语的重复、语气词、省略全部原样保留；\n"
"6. 输入中的每一段（以 [n] 开头）在输出中必须以相同 [n] 开头、一一对应、顺序不变，"
"每段输出为单独一行；除格式整理外不得有任何增减。\n"
"直接输出整理后的段落，不要任何解释、不要 markdown 代码块。"
)

SYS_OTHER = (
"You are an ASR transcript formatter. The user gives you speech-to-text segments from a video "
"(possibly lacking punctuation and capitalization). Your task is ONLY formatting, strictly:\n"
"1. Add correct punctuation and capitalization, split into sentences by logic and intonation;\n"
"2. Fix only OBVIOUS speech-to-text misrecognitions you are confident about; otherwise keep the original word;\n"
"3. NEVER rewrite sentences, add or remove any words, summarize, or make spoken language formal;\n"
"4. Keep repetitions, filler words and ellipses exactly as they are;\n"
"5. Every input segment starts with [n]; each output segment must start with the SAME [n], "
"one per line, same order, no additions or removals beyond formatting.\n"
"Output only the formatted segments, no explanations, no markdown code blocks."
)

def call_llm(batch_text: str, retry=3):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": batch_text}],
        "temperature": 0.2,
        "stream": False,
    }).encode("utf-8")
    last_err = None
    for i in range(retry):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/chat/completions", data=body,
                headers={"Authorization": f"Bearer {API_KEY}",
                         "Content-Type": "application/json"})
            # deepseek 国内直连, 禁用代理防 502
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            resp = json.loads(opener.open(req, timeout=180).read().decode("utf-8"))
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_err = e
            print(f"[polish] 批次失败({i+1}/{retry}): {e}", flush=True)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"LLM 调用失败: {last_err}")

def parse_numbered(text: str):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^\[(\d+)\]\s*(.*)$", line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out

def load_hotfix():
    """热修词典（仅中文稿启用）：已确认的高频 ASR 错字"""
    p = work / "hotfix.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("fixes", {})
    return {}

def apply_hotfix(text: str, fixes: dict):
    for k, v in fixes.items():
        if k in text:
            text = text.replace(k, v)
    return text

def main():
    data = json.loads((work / "transcript.json").read_text(encoding="utf-8"))
    segs = data["segments"]
    global SYS
    is_zh = str(data.get("language", "zh")).lower().startswith("zh")
    SYS = SYS_ZH if is_zh else SYS_OTHER
    fixes = load_hotfix() if is_zh else {}
    print(f"[polish] 语言={data.get('language')} → {'中文模式(含热修词典)' if is_zh else '通用模式(仅标点)'}")

    # 合并成 ~40s 大段，保留时间戳
    paras, buf, start = [], [], None
    for s in segs:
        if start is None: start = s["start"]
        buf.append(s["text"])
        if s["end"] - start >= 40:
            paras.append({"start": start, "text": "".join(buf)})
            buf, start = [], None
    if buf: paras.append({"start": start or 0, "text": "".join(buf)})
    for i, p in enumerate(paras):
        p["idx"] = i

    BATCH = 5
    for p in paras:   # 双端应用: 输入端先修 + 输出端再修
        p["text"] = apply_hotfix(p["text"], fixes)
    results = {}
    t0 = time.time()
    total_in = sum(len(p["text"]) for p in paras)
    for bi in range(0, len(paras), BATCH):
        batch = paras[bi:bi + BATCH]
        numbered = "\n".join(f'[{p["idx"]}] {p["text"]}' for p in batch)
        out = call_llm(numbered)
        got = parse_numbered(out)
        for p in batch:
            t = got.get(p["idx"], "").strip()
            if not t:  # 该段漏了 → 单段重试
                t = parse_numbered(call_llm(f'[{p["idx"]}] {p["text"]}')).get(p["idx"], "")
            results[p["idx"]] = t
        done = min(bi + BATCH, len(paras))
        print(f"[polish] 进度 {done}/{len(paras)} 段 | 耗时 {time.time()-t0:.0f}s", flush=True)

    polished = []
    for p in paras:
        t = apply_hotfix(results[p["idx"]], fixes)
        polished.append({"start": round(p["start"], 1), "text": t})
    total_out = sum(len(p["text"]) for p in polished)
    (work / "polished.json").write_text(json.dumps(polished, ensure_ascii=False, indent=1), encoding="utf-8")
    (work / "polished.txt").write_text("\n".join(p["text"] for p in polished), encoding="utf-8")
    print(f"[polish] 完成: {len(polished)} 段 | 输入 {total_in} 字 → 输出 {total_out} 字 "
          f"(漂移 {(total_out-total_in)/max(total_in,1)*100:+.1f}%) | 耗时 {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
