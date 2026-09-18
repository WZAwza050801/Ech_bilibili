"""Bilibili direct streams and ffmpeg PTS-grounded frame extraction."""
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .core import choose_times, write_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def headers(cookie=""):
    result = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
              "Accept-Language": "zh-CN,zh;q=0.9", "Origin": "https://www.bilibili.com",
              "Referer": "https://www.bilibili.com/"}
    if cookie:
        result["Cookie"] = cookie
    return result


class Bilibili:
    def __init__(self, cookie=""):
        self.headers = headers(cookie)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, url, destination=None):
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers=self.headers)
                with self.opener.open(request, timeout=180) as response:
                    if destination is None:
                        return response.read()
                    destination = Path(destination)
                    temporary = destination.with_suffix(destination.suffix + ".part")
                    with temporary.open("wb") as output:
                        shutil.copyfileobj(response, output)
                    if not temporary.stat().st_size:
                        raise RuntimeError("Empty media response")
                    temporary.replace(destination)
                    return
            except urllib.error.HTTPError as error:
                if error.code not in {412, 429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f"Bilibili HTTP {error.code}; check cookie/access") from None
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise RuntimeError("Bilibili network download failed") from None
            time.sleep(3 * (attempt + 1))

    def api(self, route, params):
        result = json.loads(self.get("https://api.bilibili.com/" + route + "?" +
                                     urllib.parse.urlencode(params)))
        if result.get("code") != 0:
            raise RuntimeError(f"Bilibili API error code {result.get('code')}")
        return result["data"]

    def metadata(self, source, page=None):
        if re.fullmatch(r"BV[0-9A-Za-z]{10}", source):
            bvid, requested_page = source, 1
        else:
            url = urllib.parse.urlparse(source)
            if url.scheme != "https" or url.hostname not in {"www.bilibili.com", "bilibili.com"}:
                raise ValueError("Use a full https://www.bilibili.com/video/BV... link or BV ID")
            match = re.fullmatch(r"/video/(BV[0-9A-Za-z]{10})/?", url.path)
            if not match:
                raise ValueError("Invalid Bilibili video URL")
            bvid = match[1]
            requested_page = int(urllib.parse.parse_qs(url.query).get("p", ["1"])[0])
        page = page if page is not None else requested_page
        video = self.api("x/web-interface/view", {"bvid": bvid})
        if not 1 <= page <= len(video["pages"]):
            raise ValueError("Selected page is outside the video collection")
        part = video["pages"][page - 1]
        return {"bvid": bvid, "cid": part["cid"], "page": page, "owner": video["owner"]["name"],
                "title": video["title"] + (f" - P{page} {part['part']}" if len(video["pages"]) > 1 else ""),
                "duration": part["duration"],
                "url": f"https://www.bilibili.com/video/{bvid}?p={page}"}

    def download(self, meta, run):
        data = self.api("x/player/playurl", {"bvid": meta["bvid"], "cid": meta["cid"],
                        "fnval": 16, "platform": "pc", "high_quality": 1, "qn": 80})
        dash = data.get("dash") or {}
        videos = dash.get("video") or []
        audios = dash.get("audio") or []
        if not videos or not audios:
            raise RuntimeError("No DASH audio/video; check access/login or supply a local video")
        # Prefer AVC and at most 1080p. Do not persist signed CDN URLs.
        avc = [v for v in videos if v.get("codecid") == 7] or videos
        video = max([v for v in avc if v.get("height", 0) <= 1080] or avc,
                    key=lambda v: (v.get("height", 0), v.get("bandwidth", 0)))
        audio = max(audios, key=lambda a: a.get("bandwidth", 0))
        for stream, name in ((video, "video.m4s"), (audio, "audio.m4s")):
            target = run / name
            if target.exists() and target.stat().st_size:
                continue
            urls = [stream.get("baseUrl") or stream.get("base_url")]
            urls += stream.get("backupUrl") or stream.get("backup_url") or []
            for url in urls:
                try:
                    self.get(url, target)
                    break
                except RuntimeError:
                    continue
            else:
                raise RuntimeError(f"All CDN alternatives failed for {name}")
        target = run / "source.mp4"
        temporary = run / "source.partial.mp4"
        command(["ffmpeg", "-y", "-i", str(run / "video.m4s"), "-i", str(run / "audio.m4s"),
                 "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", str(temporary)])
        temporary.replace(target)
        return target


def command(args, timeout=1800):
    if not shutil.which(args[0]):
        raise RuntimeError(f"Required executable not found: {args[0]}")
    process = subprocess.run(args, capture_output=True, encoding="utf-8",
                             errors="replace", timeout=timeout)
    if process.returncode:
        raise RuntimeError(f"{args[0]} failed: {process.stderr[-1800:]}")
    return process


def probe(path):
    data = json.loads(command(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                              "-of", "json", str(path)]).stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Input must have a video stream")
    return {"duration": float(video.get("duration", data["format"]["duration"])),
            "start_time": float(video.get("start_time", 0)),
            "audio_start": next((float(s.get("start_time", 0)) for s in data["streams"]
                                 if s["codec_type"] == "audio"), None)}


def make_wav(source, target, info):
    if info["audio_start"] is None:
        raise ValueError("No audio stream; provide --transcript for a silent source")
    offset = info["audio_start"] - info["start_time"]
    filters = "asetpts=PTS-STARTPTS"
    if offset > 0:
        filters += f",adelay={round(offset * 1000)}:all=1"
    elif offset < 0:
        filters += f",atrim=start={-offset},asetpts=PTS-STARTPTS"
    temporary = target.with_name("audio.partial.wav")
    command(["ffmpeg", "-y", "-i", str(source), "-vn", "-af", filters,
             "-t", str(info["duration"]), "-ar", "16000", "-ac", "1", str(temporary)])
    temporary.replace(target)


def scene_times(source, origin, threshold=0.12):
    process = command(["ffmpeg", "-hide_banner", "-copyts", "-i", str(source), "-an",
                       "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
                       "-fps_mode", "vfr", "-f", "null", "-"])
    return [float(t) - origin for t in re.findall(r"pts_time:([-\d.e+]+)", process.stderr)]


def difference_hash(image):
    gray = image.convert("L").resize((9, 8))
    pixels = list(gray.getdata())
    return sum((pixels[y * 9 + x] > pixels[y * 9 + x + 1]) << (y * 8 + x)
               for y in range(8) for x in range(8))


def extract_frames(source, run, info, interval=30, budget=240, threshold=0.12):
    origin = info["start_time"]
    scenes = scene_times(source, origin, threshold)
    times = choose_times(info["duration"], scenes, interval, budget)
    directory = run / "frames"
    directory.mkdir(exist_ok=True)
    result, previous, previous_hash, canonical = [], None, None, None
    for index, requested in enumerate(times):
        target = directory / f"f{index:05d}.jpg"
        # -copyts makes showinfo retain the original stream timestamp despite input seek.
        process = command(["ffmpeg", "-y", "-hide_banner", "-copyts", "-ss", str(requested),
                           "-i", str(source), "-an", "-frames:v", "1",
                           "-vf", "showinfo,scale=min(1920\\,iw):-2", "-q:v", "2", str(target)])
        pts = re.findall(r"pts_time:([-\d.e+]+)", process.stderr)
        if not pts or not target.exists():
            raise RuntimeError(f"No decoded frame at {requested:.3f}s")
        actual = float(pts[0]) - origin
        if actual < -0.01 or actual >= info["duration"] or abs(actual - requested) > 2:
            raise RuntimeError(f"Unexpected PTS: requested={requested}, decoded={actual}")
        with Image.open(target) as opened:
            image = opened.convert("RGB").resize((320, 180))
        hashed = difference_hash(image)
        duplicate = (previous is not None and (hashed ^ previous_hash).bit_count() <= 2
                     and sum(ImageStat.Stat(ImageChops.difference(image, previous)).mean) / 765 < .003)
        record = {"id": f"f{index:05d}", "requested_t": requested,
                  "pts": float(pts[0]), "actual_t": max(0, actual),
                  "path": target.relative_to(run).as_posix(), "duplicate_of": None}
        if duplicate:
            record["duplicate_of"] = canonical["id"]
            record["path"] = canonical["path"]
            target.unlink()  # Only this newly generated redundant frame.
        else:
            canonical = record
            previous, previous_hash = image, hashed
        result.append(record)
        print(f"[frames] {index + 1}/{len(times)} decoded={actual:.3f}s", flush=True)
    write_json(run / "sampling.json", {"scene_candidates": len(scenes), "selected": len(times),
               "unique_images": sum(f["duplicate_of"] is None for f in result),
               "interval": interval, "budget": budget, "threshold": threshold,
               "note": "Conservative dHash + pixel difference; occurrences retain their own PTS. Brief board changes may be missed."})
    return result
