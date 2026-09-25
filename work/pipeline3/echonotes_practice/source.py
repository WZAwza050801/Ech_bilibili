"""Pipeline-one acquisition/ASR conventions, with all outputs scoped to this run."""
import http.cookiejar
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from .common import read_json, run, save_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


class Bilibili:
    def __init__(self):
        self.headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Origin": "https://www.bilibili.com", "Referer": "https://www.bilibili.com/"}
        if os.getenv("BILIBILI_COOKIE"):
            self.headers["Cookie"] = os.environ["BILIBILI_COOKIE"]
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, url, destination=None):
        for attempt in range(3):
            try:
                with self.opener.open(urllib.request.Request(url, headers=self.headers), timeout=120) as response:
                    if destination:
                        tmp = Path(str(destination) + ".part")
                        with tmp.open("wb") as output:
                            shutil.copyfileobj(response, output, 1024 * 1024)
                        os.replace(tmp, destination)
                        return
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code not in {412, 429, 500, 502, 503} or attempt == 2:
                    raise RuntimeError(f"Bilibili HTTP {exc.code}; check authorized browser cookies") from None
                time.sleep(2 * (attempt + 1))

    def api(self, endpoint):
        data = json.loads(self.request("https://api.bilibili.com/" + endpoint))
        if data.get("code") != 0:
            raise RuntimeError(f"Bilibili API code {data.get('code')}")
        return data["data"]

    def bootstrap(self):
        # Public homepage sets the complete browser cookie group, rather than invented IDs.
        self.request("https://www.bilibili.com/")

    def acquire(self, bvid, root, page=1):
        root.mkdir(parents=True, exist_ok=True)
        self.bootstrap()
        data = self.api(f"x/web-interface/view?bvid={bvid}")
        if not 1 <= page <= len(data["pages"]):
            raise ValueError("Selected video page does not exist")
        part = data["pages"][page - 1]
        meta = {k: data[k] for k in ["bvid", "title", "desc"]}
        meta.update(owner=data["owner"]["name"], cid=part["cid"], page=page,
                    duration=part["duration"], part_title=part["part"],
                    url=f"https://www.bilibili.com/video/{bvid}/?p={page}")
        save_json(root / "meta.json", meta)
        streams = self.api(f"x/player/playurl?bvid={bvid}&cid={part['cid']}&fnval=16&qn=80")
        dash = streams.get("dash") or {}
        for kind, target in [("audio", "audio.m4s"), ("video", "video.m4s")]:
            if (root / target).exists():
                continue
            choices = dash.get(kind) or []
            if not choices:
                raise RuntimeError(f"No authorized {kind} stream available")
            if kind == "video":
                avc = [x for x in choices if x.get("codecid") == 7]
                choices = avc or choices
            best = max(choices, key=lambda x: (x.get("height", 0), x.get("bandwidth", 0)))
            for url in [best.get("baseUrl") or best.get("base_url")] + (best.get("backupUrl") or []):
                try:
                    self.request(url, root / target)
                    break
                except RuntimeError:
                    continue
            if not (root / target).exists():
                raise RuntimeError(f"All {kind} stream downloads failed")
        if not (root / "source.mp4").exists():
            run(["ffmpeg", "-y", "-i", root / "video.m4s", "-i", root / "audio.m4s",
                 "-c", "copy", root / "source.mp4"])
        if not (root / "audio.wav").exists():
            run(["ffmpeg", "-y", "-i", root / "audio.m4s", "-ar", "16000", "-ac", "1", root / "audio.wav"])
        return meta


def transcribe(root, model_path, cpu_threads=8, chunk_seconds=600):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    audio_path = root / "audio.wav"
    duration = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", audio_path]).stdout.decode().strip())
    # The feature extractor allocates the full-audio STFT at once (~0.5 GiB per
    # 30 min); long files are transcribed in chunks with time offsets instead.
    chunks = [(0.0, duration, audio_path)]
    if duration > chunk_seconds:
        chunks_dir = root / "asr-chunks"
        chunks_dir.mkdir(exist_ok=True)
        chunks, start, index = [], 0.0, 1
        while start < duration - 1:
            end = min(duration, start + chunk_seconds)
            target = chunks_dir / f"chunk-{index:02d}.wav"
            if not target.exists():
                run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}",
                     "-to", f"{end:.2f}", "-i", audio_path,
                     "-ar", "16000", "-ac", "1", target])
            chunks.append((start, end, target))
            start, index = end, index + 1
    result = []
    for start, end, path in chunks:
        segments, info = model.transcribe(str(path), language="zh", vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}, condition_on_previous_text=False, beam_size=5)
        for segment in segments:
            result.append({"start": round(segment.start + start, 2),
                           "end": round(segment.end + start, 2),
                           "text": segment.text.strip()})
        print(f"ASR {end:.0f}/{duration:.0f}s", flush=True)
    save_json(root / "transcript.json", {"language": info.language, "duration": duration, "segments": result})
    (root / "transcript.txt").write_text("\n".join(x["text"] for x in result), encoding="utf-8")


def polish(root, client):
    segments = read_json(root / "transcript.json")["segments"]
    output = []
    for offset in range(0, len(segments), 60):
        batch = segments[offset:offset + 60]
        response = client.json_call(
            "只整理ASR标点、简体、明确同音错字。禁止概括、增删内容。保留时间戳与逐段对应。"
            '返回JSON {"texts":["第1段整理文本", ...]}。',
            json.dumps(batch, ensure_ascii=False))
        texts = response.get("texts", [])
        if len(texts) != len(batch):
            raise ValueError("Polish changed segment count")
        for original, text in zip(batch, texts):
            if not isinstance(text, str) or not 0.45 <= len(text) / max(1, len(original["text"])) <= 2.2:
                raise ValueError("Polish text drift exceeds limit")
            output.append({**original, "text": text})
    save_json(root / "polished.json", output)


def parse_bvid(value):
    match = re.search(r"BV[0-9A-Za-z]{10}", value)
    if not match:
        raise ValueError("Expected a Bilibili BV ID or URL")
    return match[0]
