# -*- coding: utf-8 -*-
"""copy_locked.py — 反复尝试拷贝被 Chrome 锁住的 cookie 库（抓 Chrome 释放句柄的窗口）"""
import shutil, time, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
for i in range(1, 41):
    try:
        shutil.copy2(src, dst)
        print(f"第{i}次: 成功")
        sys.exit(0)
    except Exception as e:
        if i % 5 == 0:
            print(f"第{i}次: {e}", flush=True)
        time.sleep(3)
print("40 次全失败")
sys.exit(1)
