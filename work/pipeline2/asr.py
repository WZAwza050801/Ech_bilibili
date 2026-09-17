"""Isolated worker so an existing faster-whisper environment can be reused."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="zh")
    args = parser.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=max(1, min(8, (os.cpu_count() or 2) // 2)))
    iterator, info = model.transcribe(str(args.audio), language=args.language,
                                     vad_filter=True, condition_on_previous_text=False)
    segments = []
    for segment in iterator:
        segments.append({"start": segment.start, "end": segment.end, "text": segment.text.strip()})
        if len(segments) % 100 == 0:
            print(f"[asr] {segment.end:.0f}s / {len(segments)} segments", flush=True)
    data = {"language": info.language, "duration": info.duration,
            "source": "local_whisper", "segments": segments}
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
