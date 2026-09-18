import re
from pathlib import Path
from .common import run, save_json


def duration(path):
    output = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nw=1:nk=1", path]).stdout.decode().strip()
    return float(output)


def scene_times(video, threshold=0.12):
    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, timeout=600)
    text = result.stderr.decode("utf-8", "replace")
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", text)]


def merged_times(video, interval=30, threshold=0.12, min_gap=2, limit=48):
    total = duration(video)
    values = [0.0, max(0.0, total - 0.2)]
    values.extend(float(x) for x in range(interval, int(total), interval))
    values.extend(scene_times(video, threshold))
    selected = []
    for value in sorted(set(round(x, 2) for x in values if 0 <= x <= total)):
        if not selected or value - selected[-1] >= min_gap:
            selected.append(value)
    if len(selected) > limit:
        stride = (len(selected) - 1) / (limit - 1)
        selected = [selected[round(i * stride)] for i in range(limit)]
    return selected


def extract(video, root, times):
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, value in enumerate(times, 1):
        name = f"frame-{index:03d}-{value:08.2f}s.jpg"
        target = root / name
        if not target.exists():
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(value),
                 "-i", video, "-frames:v", "1", "-q:v", "2", target])
        manifest.append({"index": index, "time": value, "file": name})
    save_json(root / "manifest.json", manifest)
    return manifest


def evidence_frames(video, root, steps):
    times = sorted(set(round(float(x["evidence_t"]), 2) for x in steps))
    return extract(video, root, times)
