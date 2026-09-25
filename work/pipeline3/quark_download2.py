"""Download the three VFX_GodotCourse zips from /quark root via OpenList."""
import json
import sys
import urllib.request
from pathlib import Path

sys.stdout = open(r"D:\课程视频变操作agent\.workbuddy\fetch_run.log", "a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
print("=== download v2 ===")

BASE = "http://127.0.0.1:5244"
DEST = Path(r"D:\课程视频变操作agent\course-files")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DEST.mkdir(parents=True, exist_ok=True)


def api(path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with OPENER.open(req, timeout=60) as r:
        return json.loads(r.read())


lg = api("/api/auth/login", {"username": "admin", "password": "tklOjXSG"})
TOKEN = lg["data"]["token"]
r = api("/api/fs/list", {"path": "/quark", "page": 1, "per_page": 200,
                         "refresh": True, "password": ""}, TOKEN)
targets = [(it["name"], it.get("size", 0))
           for it in (r["data"].get("content") or [])
           if not it.get("is_dir") and "VFX_Godot" in it["name"]
           and it["name"].lower().endswith(".zip")]
print(f"targets: {[(n, round(s/1e6, 1)) for n, s in targets]}")

for name, size in targets:
    info = api("/api/fs/get", {"path": f"/quark/{name}"}, TOKEN)
    raw = (info.get("data") or {}).get("raw_url")
    if not raw:
        print(f"no raw_url: {name}: {str(info)[:150]}")
        continue
    target = DEST / name
    req = urllib.request.Request(raw, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with OPENER.open(req, timeout=240) as resp, open(target, "wb") as f:
            n = 0
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                n += len(chunk)
        print(f"DOWNLOADED {name} {n/1e6:.1f}MB (expect {size/1e6:.1f}MB)")
    except Exception as exc:
        print(f"download failed {name}: {type(exc).__name__} {str(exc)[:200]}")
print("download v2 done")
