# -*- coding: utf-8 -*-
"""transcribe_local.py — 管线一·语音层：本地 faster-whisper 转写
输出: transcript.json（带时间戳段落）+ transcript.txt（纯文本）
参数参考 let-ai-read-video: vad_filter, condition_on_previous_text=False 防幻觉
"""
import json, sys, io, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

work = Path(r"D:\视频观看agent编写\Ech_bilibili")

from faster_whisper import WhisperModel

t0 = time.time()
print("[asr] 加载模型 small / int8 (CPU)...")
model = WhisperModel(str(work / "models" / "faster-whisper-small"), device="cpu", compute_type="int8", cpu_threads=4)
print(f"[asr] 模型加载完成 {time.time()-t0:.1f}s，开始转写...")

t1 = time.time()
segments, info = model.transcribe(
    str(work / "audio.wav"),
    language="zh",
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500},
    condition_on_previous_text=False,   # 防幻觉复读（let-ai 同款参数）
    beam_size=5,
)
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
