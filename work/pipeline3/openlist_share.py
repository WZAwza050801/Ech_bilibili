"""Mount the quark share b209b9a2ac27 via QuarkShare driver, list it, download VFX files."""
import json
import sys
import urllib.request
from pathlib import Path

sys.stdout = open(r"D:\课程视频变操作agent\.workbuddy\fetch_run.log", "a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
print("=== share mount run ===")

BASE = "http://127.0.0.1:5244"
DEST = Path(r"D:\课程视频变操作agent\course-files")
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
    try:
        with OPENER.open(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:300]
        return {"code": exc.code, "message": f"HTTP {exc.code}: {raw}"}
    except json.JSONDecodeError:
        return {"code": -1, "message": "non-json response"}


lg = api("/api/auth/login", {"username": "admin", "password": "tklOjXSG"})
assert lg.get("code") == 200 and lg.get("data"), f"login failed: {str(lg)[:200]}"
TOKEN = lg["data"]["token"]
log("login OK")

# list existing storages to see driver names available / avoid duplicates
mounts = []
try:
    admins = api("/api/admin/storage/list", TOKEN)
    mounts = [s.get("mount_path") for s in (admins.get("data") or {}).get("content", [])]
except Exception as exc:
    log(f"storage/list GET failed: {type(exc).__name__} {str(exc)[:120]}")
    try:
        admins = api("/api/admin/storage/list", {}, TOKEN)
        mounts = [s.get("mount_path") for s in (admins.get("data") or {}).get("content", [])]
    except Exception as exc2:
        log(f"storage/list POST failed: {type(exc2).__name__} {str(exc2)[:120]}")
log(f"existing mounts: {mounts}")

if "/quark_share" not in mounts:
    add = api("/api/admin/storage/create", {
        "mount_path": "/quark_share", "driver": "QuarkShare", "order": 1,
        "remark": "VFX course share b209b9a2ac27", "cache_expiration": 30,
        "web_proxy": False, "addition": json.dumps({
            "root_folder_id": "", "order_by": "name", "order_direction": "asc",
            "share_id": "b209b9a2ac27", "share_passwd": ""}),
    }, TOKEN)
    log(f"storage create: code={add.get('code')} msg={add.get('message')}")
    if add.get("code") != 200:
        # try known alternate driver naming
        add = api("/api/admin/storage/create", {
            "mount_path": "/quark_share", "driver": "QuarkShare2", "order": 1,
            "remark": "VFX course share", "cache_expiration": 30, "web_proxy": False,
            "addition": json.dumps({"share_id": "b209b9a2ac27", "share_passwd": ""}),
        }, TOKEN)
        log(f"storage create alt: code={add.get('code')} msg={add.get('message')}")

def ls(path):
    r = api("/api/fs/list", {"path": path, "page": 1, "per_page": 200,
                             "refresh": True, "password": ""}, TOKEN)
    if r.get("code") != 200:
        log(f"  list {path} -> {r.get('code')} {str(r.get('message'))[:120]}")
        return None
    return r["data"].get("content") or []


found = []


def walk(path, depth, maxdepth=5):
    if depth > maxdepth:
        return
    items = ls(path)
    if items is None:
        return
    for it in items:
        name = it["name"]
        full = f"{path.rstrip('/')}/{name}"
        if it.get("is_dir"):
            log(f"DIR  {full}")
            walk(full, depth + 1, maxdepth)
        else:
            log(f"FILE {full}  {it.get('size', 0)/1e6:.1f}MB")
            found.append((full, it.get("size", 0)))


walk("/quark_share", 0)
log("---- share files ----")
for full, size in found:
    log(f"{full}  {size/1e6:.1f}MB")
Path(r"D:\课程视频变操作agent\.workbuddy\openlist_fetch_report.txt").write_text(
    "\n".join(report), encoding="utf-8")
print("client done")
