import sys
import traceback
from pathlib import Path

LOG = Path(r"D:\课程视频变操作agent\.workbuddy\fetch_run.log")
LOG.write_text("runner starts\n", encoding="utf-8")
sys.stdout = LOG.open("a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout

OUT = Path(r"D:\课程视频变操作agent\.workbuddy\openlist_fetch_report.txt")
src = Path(r"D:\课程视频变操作agent\EchoNotes\work\pipeline3\openlist_fetch.py").read_text(encoding="utf-8")
print("src loaded", len(src))
g = {"__name__": "__main__",
     "__file__": r"D:\课程视频变操作agent\EchoNotes\work\pipeline3\openlist_fetch.py"}
try:
    exec(compile(src, "openlist_fetch.py", "exec"), g)
    print("runner done")
except SystemExit as e:
    print(f"[SystemExit] {e}")
except BaseException:
    print("[TRACEBACK]")
    traceback.print_exc()
