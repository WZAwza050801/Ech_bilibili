"""SiliconFlow video-understanding client (OpenAI-compatible, Qwen3-VL series).

Replaces the Gemini Files-API upload path: local video chunks are sent as
base64 data URLs with `video_url`; the model samples frames itself (fps /
max_frames) and aligns text to per-second timestamps. Audio is not needed
here -- the ASR transcript travels inside the prompt, exactly like before.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


def api_key_from(secrets_path=None):
    if os.getenv("SILICONFLOW_API_KEY"):
        return os.environ["SILICONFLOW_API_KEY"]
    if not secrets_path:
        raise RuntimeError("Set SILICONFLOW_API_KEY or pass --secrets")
    data = json.loads(Path(secrets_path).read_text(encoding="utf-8-sig"))
    matches = [x for x in data.get("entries", [])
               if x.get("provider") == "siliconflow" and x.get("apiKey")]
    if not matches:
        raise RuntimeError("No siliconflow entry in the secrets file")
    return matches[0]["apiKey"]


def encode_chunk(source, target, start, end):
    """Re-encode a chunk for VL input. Keep native 1080p detail at high quality,
    but the transport silently kills oversized requests (>~8MB observed), so
    high-motion chunks fall back to 960p automatically."""
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
         "-i", str(source), "-vf", "scale=1920:-2", "-an", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", str(target)])
    if target.stat().st_size > 8 * 1024 * 1024:
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
             "-i", str(source), "-vf", "scale=960:-2", "-an", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "28", str(target)])


def run(argv):
    import subprocess
    result = subprocess.run(argv, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode('utf-8', 'replace')[:500]}")


class SiliconFlow:
    def __init__(self, key, model="Qwen/Qwen3-VL-30B-A3B-Instruct",
                 base="https://api.siliconflow.cn/v1", fps=2.0, max_frames=600):
        self.key, self.model, self.base = key, model, base.rstrip("/")
        self.fps, self.max_frames = fps, max_frames

    def _request(self, url, body, timeout=900, retries=8):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        for attempt in range(retries):
            try:
                request = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < retries:
                    time.sleep(min(120, 3 * 2 ** attempt))
                    continue
                raise RuntimeError(f"SiliconFlow HTTP {exc.code}: {raw[:800]}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt + 1 < retries:
                    time.sleep(min(120, 3 * 2 ** attempt))
                    continue
                raise RuntimeError(f"SiliconFlow network error: {exc}") from None

    def video_part(self, path):
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        # NOTE: no "detail" field here -- SiliconFlow rejects it with HTTP 400/20015
        # even though the docs mention it. fps must be an INT: 1.0 also 400s.
        return {"type": "video_url", "video_url": {
            "url": "data:video/mp4;base64," + encoded,
            "fps": int(self.fps), "max_frames": int(self.max_frames)}}

    def analyze_video(self, chunk_path, prompt):
        body = {"model": self.model, "max_tokens": 16000, "temperature": 0.1,
                "messages": [{"role": "user", "content": [
                    self.video_part(chunk_path),
                    {"type": "text", "text": prompt}]}]}
        payload = self._request(self.base + "/chat/completions", body)
        choice = (payload.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        if not text:
            raise RuntimeError(f"SiliconFlow returned no text: {str(payload)[:500]}")
        usage = payload.get("usage", {})
        return text, {"model": self.model, "text": text, "usage": usage}

    def analyze_framelist(self, content, max_tokens=16000):
        """High-fidelity mode: caller supplies content parts (labeled frames +
        prompt). Consumes ~20x more visual tokens than video_url, which the
        server caps hard regardless of input resolution/fps."""
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.1,
                "messages": [{"role": "user", "content": content}]}
        payload = self._request(self.base + "/chat/completions", body)
        choice = (payload.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        if not text:
            raise RuntimeError(f"SiliconFlow returned no text: {str(payload)[:500]}")
        usage = payload.get("usage", {})
        return text, {"model": self.model + "+framelist", "text": text, "usage": usage}


def frame_content(source, start, end, fps=0.5, width=1024, quality=7, work_dir=None):
    """Extract labeled JPEG frames for one time window and build message parts.
    Each frame is preceded by a text label with its exact timestamp, which both
    grounds the model and gives precise evidence_t anchoring."""
    import tempfile
    out_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="frames_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f*.jpg"):
        old.unlink()
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
         "-i", str(source), "-vf", f"fps={fps},scale={width}:-2", "-q:v", str(quality),
         str(out_dir / "f%04d.jpg")])
    frames = sorted(out_dir.glob("f*.jpg"))
    content = []
    for i, frame in enumerate(frames):
        t = start + i / fps
        content.append({"type": "text", "text": f"[frame t={t:.1f}s]"})
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(frame.read_bytes()).decode("ascii")}})
    return content, len(frames)
