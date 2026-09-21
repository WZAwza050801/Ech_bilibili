# -*- coding: utf-8 -*-
"""dl_browser_stream.py — 用浏览器截获的真实流地址下载视频(带 Referer), 校验时长"""
import urllib.request, sys, io, subprocess, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

url, dst = sys.argv[1], sys.argv[2]
expect = int(sys.argv[3]) if len(sys.argv) > 3 else None  # 期望时长秒
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request(url, headers=HDRS)
tmp = dst + ".part"
t0 = time.time()
with OPENER.open(req, timeout=60) as r:
    total = int(r.headers.get("Content-Length") or 0)
    got = 0
    with open(tmp, "wb") as f:
        while True:
            c = r.read(1024 * 512)
            if not c:
                break
            f.write(c)
            got += len(c)
            if got % (4 * 1048576) < 524288:
                print(f"  已下载 {got/1048576:.0f}/{total/1048576:.0f}MB {time.time()-t0:.0f}s", flush=True)
if total and got < total * 0.98:
    print(f"不完整 {got}/{total}")
    sys.exit(1)
Path(tmp).replace(dst)
print(f"下载完成 {got/1048576:.1f}MB 用时 {time.time()-t0:.0f}s")
r2 = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", dst],
                    capture_output=True, text=True)
dur = float(r2.stdout.strip())
print(f"实际时长 {dur:.0f}s" + (f", 期望 {expect}s ({dur/expect:.1%})" if expect else ""))
