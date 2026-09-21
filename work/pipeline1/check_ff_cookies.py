# -*- coding: utf-8 -*-
"""check_ff_cookies.py — 只列出 Firefox 中 B 站 cookie 的名字和 host, 不打印值"""
import sqlite3, shutil, sys, io, os, tempfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

profdir = Path(os.environ["APPDATA"]) / "Mozilla" / "Firefox" / "Profiles"
found_any = False
for prof in profdir.iterdir():
    ck = prof / "cookies.sqlite"
    if not ck.exists():
        continue
    tmp = Path(tempfile.gettempdir()) / f"ffck_{int(__import__('time').time())}.sqlite"
    shutil.copy2(ck, tmp)
    con = sqlite3.connect(str(tmp))
    rows = con.execute("SELECT name, host FROM moz_cookies WHERE host LIKE '%bilibili%'").fetchall()
    con.close()
    tmp.unlink()
    names = sorted(set(n for n, h in rows))
    has_sess = any("SESSDATA" in n for n in names)
    print(f"profile={prof.name}: bilibili cookies={len(rows)} 条, SESSDATA={'有' if has_sess else '无'}")
    for n in names:
        print(f"  - {n}")
    if rows:
        found_any = True
if not found_any:
    print("Firefox 所有 profile 都没有 bilibili cookie")
