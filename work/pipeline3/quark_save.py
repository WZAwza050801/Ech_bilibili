"""Save the quark share b209b9a2ac27 into the user's own quark drive via quark API."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout = open(r"D:\课程视频变操作agent\.workbuddy\fetch_run.log", "a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
print("=== quark share save run ===")

BASE = "http://127.0.0.1:5244"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SHARE_PWD_ID = "b209b9a2ac27"
PASSCODE = ""


def oapi(path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with OPENER.open(req, timeout=60) as r:
        return json.loads(r.read())


lg = oapi("/api/auth/login", {"username": "admin", "password": "tklOjXSG"})
TOKEN = lg["data"]["token"]
stores = oapi("/api/admin/storage/list", token=TOKEN)["data"]["content"]
quark = [s for s in stores if s["mount_path"] == "/quark"][0]
cookie = json.loads(quark["addition"])["cookie"]
print(f"cookie loaded: {len(cookie)} chars")

QH = {"Content-Type": "application/json", "Cookie": cookie,
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuarkPC/4.x"}


def qapi(path, body=None):
    url = "https://drive-pc.quark.cn" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=QH,
                                 method="POST" if data else "GET")
    with OPENER.open(req, timeout=60) as r:
        return json.loads(r.read())


# 1. share stoken
tok = qapi("/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc",
           {"pwd_id": SHARE_PWD_ID, "passcode": PASSCODE})
assert tok.get("status") == 200, f"token failed: {str(tok)[:300]}"
stoken = tok["data"]["stoken"]
print("stoken OK")

# 2. walk share detail tree (top 3 levels)
all_items = []


def detail(pdir_fid, path, depth):
    page = 1
    while True:
        qs = urllib.parse.urlencode({
            "pr": "ucpro", "fr": "pc", "pwd_id": SHARE_PWD_ID, "stoken": stoken,
            "pdir_fid": pdir_fid, "_page": page, "_size": 100,
            "fetch_share": 1, "fetch_total": 1, "sort_by": "file_type",
            "order": "asc"})
        d = qapi(f"/1/clouddrive/share/sharepage/detail?{qs}")
        if d.get("status") != 200:
            print(f"detail failed at {path}: {str(d)[:300]}")
            return
        for it in (d["data"].get("list") or []):
            full = f"{path}/{it['file_name']}"
            if it.get("dir"):
                print(f"DIR  {full}")
                if depth < 3:
                    detail(it["fid"], full, depth + 1)
            else:
                print(f"FILE {full}  {it.get('size', 0)/1e6:.1f}MB")
            all_items.append(it)
        total = d["data"].get("_total", 0)
        metadata = d["data"].get("_metadata", {})
        if page * 100 >= int(metadata.get("_total", total) or 0):
            break
        page += 1


detail("0", "", 0)
print(f"total items: {len(all_items)}")

# 3. save everything into a target folder in user's drive
save_body = {
    "fid_list": [it["fid"] for it in all_items if it.get("share_fid_token")],
    "fid_token_list": [it["share_fid_token"] for it in all_items if it.get("share_fid_token")],
    "to_pdir_fid": "0", "pwd_id": SHARE_PWD_ID, "stoken": stoken,
    "pdir_fid": "0", "path": "/", "scene": "link",
}
sv = qapi("/1/clouddrive/share/sharepage/save?pr=ucpro&fr=pc", save_body)
print(f"save resp: {str(sv)[:400]}")
if sv.get("data", {}).get("task_id"):
    tid = sv["data"]["task_id"]
    for i in range(30):
        time.sleep(2)
        tr = qapi(f"/1/clouddrive/task?pr=ucpro&fr=pc&task_id={tid}&retry_index={i}")
        st = (tr.get("data") or {}).get("status")
        print(f"task {tid} status={st}")
        if st in (2, 400):
            break
print("save run done")
