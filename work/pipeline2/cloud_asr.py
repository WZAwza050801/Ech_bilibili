"""Timestamped chunk fallback for OpenAI-compatible audio transcription APIs."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "work.pipeline2"

from .core import read_json, write_json
from .media import command


def registry_key(path, provider, label=None):
    entries = read_json(path).get("entries", [])
    candidates = [e for e in entries if e.get("provider") == provider and e.get("apiKey")]
    if label:
        candidates = [e for e in candidates if e.get("label") == label]
    if not candidates:
        raise ValueError(f"No usable {provider} API key in the external registry")
    return candidates[0]["apiKey"]


def multipart(fields, file_path):
    boundary = "----EchoNotes" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    filename = file_path.name.replace('"', "")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
             f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n").encode()
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def transcribe_chunk(endpoint, key, model, path):
    data, content_type = multipart({"model": model}, path)
    request = urllib.request.Request(
        endpoint, data=data,
        headers={"Authorization": "Bearer " + key, "Content-Type": content_type})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read())
            if not isinstance(result.get("text"), str):
                raise ValueError("ASR response has no text")
            return result
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise RuntimeError(f"Cloud ASR HTTP {error.code}") from None
        except (OSError, TimeoutError):
            if attempt == 3:
                raise RuntimeError("Cloud ASR network request failed") from None
        time.sleep(3 * (attempt + 1))


def load_checkpoint(path, chunk_count):
    state = read_json(path) if path.exists() else {}
    segments = state.get("segments", [])
    next_chunk = state.get("next_chunk", len(segments))
    if (not isinstance(segments, list) or not isinstance(next_chunk, int)
            or next_chunk < len(segments) or next_chunk > chunk_count):
        raise ValueError("Partial ASR checkpoint does not match current chunks")
    return segments, next_chunk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--secrets", type=Path, required=True)
    parser.add_argument("--provider", default="siliconflow")
    parser.add_argument("--key-label")
    parser.add_argument("--endpoint", default="https://api.siliconflow.cn/v1/audio/transcriptions")
    parser.add_argument("--model", default="TeleAI/TeleSpeechASR")
    parser.add_argument("--chunk-seconds", type=int, default=30)
    args = parser.parse_args()
    if not args.audio.is_file() or args.chunk_seconds < 5:
        parser.error("audio must exist and chunk seconds must be at least 5")
    key = os.getenv("ECHONOTES_CLOUD_ASR_API_KEY") or registry_key(
        args.secrets, args.provider, args.key_label)
    chunk_dir = args.output.parent / (args.output.stem + "-chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(chunk_dir.glob("chunk-*.wav"))
    if not existing:
        command(["ffmpeg", "-y", "-i", str(args.audio), "-f", "segment",
                 "-segment_time", str(args.chunk_seconds), "-reset_timestamps", "1",
                 "-c:a", "pcm_s16le", str(chunk_dir / "chunk-%04d.wav")])
    chunks = sorted(chunk_dir.glob("chunk-*.wav"))
    if not chunks:
        raise RuntimeError("ffmpeg produced no ASR chunks")
    partial = args.output.with_suffix(".partial.json")
    done, next_chunk = load_checkpoint(partial, len(chunks))
    for index, chunk in enumerate(chunks[next_chunk:], start=next_chunk):
        result = transcribe_chunk(args.endpoint, key, args.model, chunk)
        duration = float(result.get("duration") or args.chunk_seconds)
        start = index * args.chunk_seconds
        text = result["text"].strip()
        if text:
            done.append({"start": start, "end": start + duration, "text": text})
        write_json(partial, {"source": f"{args.provider}:{args.model}",
                             "timestamp_precision": f"{args.chunk_seconds}s_chunk",
                             "next_chunk": index + 1,
                             "segments": done})
        print(f"[cloud-asr] {index + 1}/{len(chunks)} {start:.0f}-{start + duration:.0f}s",
              flush=True)
    write_json(args.output, {"source": f"{args.provider}:{args.model}",
                             "timestamp_precision": f"{args.chunk_seconds}s_chunk",
                             "segments": done})
    partial.unlink(missing_ok=True)
    shutil.rmtree(chunk_dir)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"[error] {error}", file=sys.stderr)
        sys.exit(1)
