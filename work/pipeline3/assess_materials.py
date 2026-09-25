"""Assess material sufficiency: classify all analysis.json steps by action type per page."""
import json
from pathlib import Path

ROOT = Path(r"D:\课程视频变操作agent\EchoNotes\work\pipeline3\runs\Godot游戏特效-入门至进阶实战课-2026-09-23")
PROGRAMMABLE = {"write_file", "set_param", "run_command"}
GUI = {"ui_click", "draw_stroke", "ui_operation", "install_pkg"}

print(f"{'P':<4}{'grade':<6}{'total':<7}{'可编程':<8}{'GUI/降级':<9}{'有参数值':<9}{'含代码/材质内容':<10}")
tot = prog_t = gui_t = val_t = cont_t = 0
for d in sorted(ROOT.glob("P*")):
    f = d / "analysis.json"
    if not f.exists():
        continue
    a = json.loads(f.read_text(encoding="utf-8"))
    steps = a.get("steps", [])
    prog = gui_s = vals = cont = 0
    for s in steps:
        act = s.get("action", "")
        if act in PROGRAMMABLE:
            prog += 1
            if s.get("content") or s.get("value") is not None:
                vals += 1
            c = (s.get("content") or "")
            if any(k in c for k in ("extends", "shader", "sub_resource", "GDScript", "func ")):
                cont += 1
        else:
            gui_s += 1
    g = a.get("classification", {}).get("grade", "-")
    print(f"P{int(d.name[1:3]):02d} {g:<6}{len(steps):<7}{prog:<8}{gui_s:<9}{vals:<9}{cont:<10}")
    tot += len(steps); prog_t += prog; gui_t += gui_s; val_t += vals; cont_t += cont
print(f"\n合计 {tot} 步：可编程 {prog_t}，GUI/降级 {gui_t}；带具体参数值 {val_t}；含代码/着色器内容 {cont_t}")
