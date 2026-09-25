"""Pure-API OpenList client (no process spawning): search quark, download course files."""
import json
import sys
import urllib.request
from pathlib import Path

sys.stdout = open(r"D:\课程视频变操作agent\.workbuddy\fetch_run.log", "a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
print("=== client run ===")

BASE = "http://127.0.0.1:5244"
DEST = Path(r"D:\课程视频变操作agent\course-files")
OUT = Path(r"D:\课程视频变操作agent\.workbuddy\openlist_fetch_report.txt")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
report = []


def log(m):
    report.append(str(m))
    print(m)


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
assert lg.get("code") == 200, f"login failed: {lg}"
TOKEN = lg["data"]["token"]
log("login OK")


def ls(path):
    r = api("/api/fs/list", {"path": path, "page": 1, "per_page": 200,
                             "refresh": False, "password": ""}, TOKEN)
    if r.get("code") != 200:
        return None
    return r["data"].get("content") or []


def walk(path, depth, found, maxdepth=4):
    if depth > maxdepth:
        return
    items = ls(path)
    if items is None:
        log(f"  (list failed: {path})")
        return
    for it in items:
        name = it["name"]
        full = f"{path.rstrip('/')}/{name}"
        if it.get("is_dir"):
            log(f"DIR  {full}")
            walk(full, depth + 1, found, maxdepth)
        else:
            size_mb = it.get("size", 0) / 1e6
            log(f"FILE {full}  {size_mb:.1f}MB")
            low = name.lower()
            if low.endswith((".zip", ".rar", ".7z")) or "godot" in low or "vfx" in low:
                found.append((full, it.get("size", 0)))


found = []
walk("/quark", 0, found)
if not found:
    log("own drive empty of candidates; trying QuarkShare mount b209b9a2ac27")
    add = api("/api/admin/storage/create", {
        "mount_path": "/quark_share", "driver": "QuarkShare", "order": 1,
        "remark": "VFX course share", "cache_expiration": 30, "web_proxy": False,
        "addition": json.dumps({"root_folder_id": "", "order_by": "name",
                                "order_direction": "asc", "share_id": "b209b9a2ac27",
                                "share_passwd": ""}),
    }, TOKEN)
    log(f"storage create: code={add.get('code')} msg={add.get('message')}")
    if add.get("code") == 200:
        walk("/quark_share", 0, found)

log("---- candidates ----")
for full, size in found:
    log(f"{full}  {size/1e6:.1f}MB")

DEST.mkdir(parents=True, exist_ok=True)
for full, size in found:
    info = api("/api/fs/get", {"path": full}, TOKEN)
    if info.get("code") != 200:
        log(f"get info failed: {full}: {info.get('message')}")
        continue
    raw = (info["data"] or {}).get("raw_url")
    if not raw:
        log(f"no raw_url: {full}")
        continue
    name = full.rsplit("/", 1)[-1]
    target = DEST / name
    req = urllib.request.Request(raw, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with OPENER.open(req, timeout=300) as r, open(target, "wb") as f:
            n = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                n += len(chunk)
        log(f"DOWNLOADED {name}  {n/1e6:.1f}MB -> {target}")
    except Exception as exc:
        log(f"download failed {name}: {type(exc).__name__} {str(exc)[:200]}")

OUT.write_text("\n".join(report), encoding="utf-8")
print("client done")
