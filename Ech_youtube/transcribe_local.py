# -*- coding: utf-8 -*-
"""transcribe_local.py — Ech_youtube·语音层：本地 faster-whisper 转写
用法: python transcribe_local.py [lang]   lang=auto 时自动检测语言
输入: WORK/audio.wav   输出: WORK/transcript.json + transcript.txt
与 Ech_bilibili 同款参数: vad_filter, condition_on_previous_text=False 防幻觉, cpu_threads=4 防 OOM
模型与 Ech_bilibili 共享(不重复下载)。
"""
import json, os, sys, io, time
from pathlib import Path

if not getattr(sys.stdout, "_ech_wrapped", False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"); sys.stdout._ech_wrapped = True
if not getattr(sys.stderr, "_ech_wrapped", False):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"); sys.stderr._ech_wrapped = True

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ech_config import ECH_YT_DIR as work, ECH_MODEL_DIR
lang = sys.argv[1] if len(sys.argv) > 1 else "auto"

from faster_whisper import WhisperModel

# 模型定位: 平台本地 models/ > 共享目录 ECH_MODEL_DIR > 环境变量 > 触发下载的 "small"
_local_model = work / "models" / "faster-whisper-small"
if _local_model.exists():
    MODEL = str(_local_model)
elif Path(ECH_MODEL_DIR).exists():
    MODEL = str(ECH_MODEL_DIR)
else:
    MODEL = os.environ.get("ECHONOTES_ASR_MODEL") or os.environ.get("ECH_MODEL", "small")
    print(f"[asr] 未找到本地模型，将使用 {MODEL!r}（首次会联网下载，离线环境请先放好模型）")

t0 = time.time()
print(f"[asr] 加载模型 small / int8 (CPU, {MODEL}) ...")
model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=4)
print(f"[asr] 模型加载完成 {time.time()-t0:.1f}s，开始转写 (lang={lang})...")

t1 = time.time()
kwargs = dict(
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500},
    condition_on_previous_text=False,   # 防幻觉复读
    beam_size=5,
)
if lang and lang != "auto":
    kwargs["language"] = lang
segments, info = model.transcribe(str(work / "audio.wav"), **kwargs)
print(f"[asr] 检测语言: {info.language} (概率 {info.language_probability:.2f})")

segs = []
with open(work / "transcript.txt", "w", encoding="utf-8") as ftxt:
    for seg in segments:
        item = {"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()}
        segs.append(item)
        ftxt.write(item["text"] + "\n")
        if len(segs) % 20 == 0:
            print(f"[asr] 进度 t={seg.end:.0f}s 段数={len(segs)} 耗时{time.time()-t1:.0f}s", flush=True)

(work / "transcript.json").write_text(json.dumps({
    "language": info.language,
    "duration": info.duration,
    "segments": segs,
}, ensure_ascii=False, indent=1), encoding="utf-8")

chars = sum(len(s["text"]) for s in segs)
print(f"[asr] 完成: {len(segs)} 段 / {chars} 字 / 音频 {info.duration:.0f}s / 耗时 {time.time()-t1:.0f}s")
