"""Isolated worker so an existing faster-whisper environment can be reused."""
import argparse
import json
import os
from pathlib import Path


def save(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--cpu-threads", type=int, default=int(os.getenv("ECHONOTES_ASR_CPU_THREADS", "2")))
    parser.add_argument("--beam-size", type=int, default=int(os.getenv("ECHONOTES_ASR_BEAM_SIZE", "3")))
    args = parser.parse_args()
    if args.cpu_threads < 1 or args.beam_size < 1:
        parser.error("cpu threads and beam size must be positive")
    # CTranslate2/MKL may allocate a large scratch arena per CPU thread.
    os.environ.setdefault("OMP_NUM_THREADS", str(args.cpu_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(args.cpu_threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(args.cpu_threads))
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=args.cpu_threads, num_workers=1)
    iterator, info = model.transcribe(str(args.audio), language=args.language,
                                     vad_filter=True, condition_on_previous_text=False)
    segments = []
    for segment in iterator:
        segments.append({"start": segment.start, "end": segment.end, "text": segment.text.strip()})
        if len(segments) % 50 == 0:
            save(args.output.with_suffix(".partial.json"), {
                "language": info.language, "duration": info.duration,
                "source": "local_whisper_partial", "segments": segments})
            print(f"[asr] {segment.end:.0f}s / {len(segments)} segments", flush=True)
    data = {"language": info.language, "duration": info.duration,
            "source": "local_whisper", "segments": segments}
    save(args.output, data)
    args.output.with_suffix(".partial.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
