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
    from faster_whisper.audio import decode_audio
    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=args.cpu_threads, num_workers=1)
    # Long lectures blow up memory if transcribe() STFTs the whole file at once
    # (~1 GiB complex64 for a 2 h audio). Decode once, then transcribe in
    # fixed slices, shifting timestamps back onto the global timeline.
    audio = decode_audio(str(args.audio), sampling_rate=16000)
    sample_rate = 16000
    chunk_samples = int(os.getenv("ECHONOTES_ASR_CHUNK_SECONDS", "600")) * sample_rate
    segments = []
    offset = 0.0
    for start in range(0, audio.shape[0], chunk_samples):
        piece = audio[start:start + chunk_samples]
        if piece.shape[0] < sample_rate // 2:
            break
        iterator, info = model.transcribe(piece, language=args.language,
                                         vad_filter=True, condition_on_previous_text=False)
        for segment in iterator:
            segments.append({"start": segment.start + offset, "end": segment.end + offset,
                             "text": segment.text.strip()})
            if len(segments) % 50 == 0:
                save(args.output.with_suffix(".partial.json"), {
                    "language": info.language, "duration": offset + piece.shape[0] / sample_rate,
                    "source": "local_whisper_partial", "segments": segments})
                print(f"[asr] {segment.end + offset:.0f}s / {len(segments)} segments", flush=True)
        offset += piece.shape[0] / sample_rate
    data = {"language": args.language, "duration": offset,
            "source": "local_whisper", "segments": segments}
    save(args.output, data)
    args.output.with_suffix(".partial.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
