"""Phase C: per-deliverable blind-vs-groundtruth reconciliation report."""
import json
import re
from pathlib import Path

HW = Path(r"D:\课程视频变操作agent\homework\VFX_Course_Homework")
manifest = json.loads((HW / "manifest.json").read_text(encoding="utf-8"))
out = ["# 作业对账报告：盲写版 vs 标准答案", "",
       "盲写版 = 仅凭视频分析生成（未看答案）；修正版 = 按标准答案补齐艺术分层与参数。",
       "对账展示两者差距，即 agent 真实理解力边界。", ""]

rows = []
for m in manifest:
    blind = (HW / "Blind" / Path(m["blind"]).name).read_text(encoding="utf-8")
    fixed = Path(m["fixed"]).read_text(encoding="utf-8")

    def metrics(t):
        return {
            "粒子层": len(re.findall(r'type=.GPUParticles3D', t)) or
                     len(re.findall(r'type=.MeshInstance3D', t)),
            "子资源数": len(re.findall(r'^\[sub_resource', t, re.M)),
            "贴图引用": len(re.findall(r'Texture2D', t)),
            "湍流": "turbulence_enabled = true" in t,
            "one_shot": "one_shot = true" in t,
        }

    bm, fm = metrics(blind), metrics(fixed)
    stem = Path(m["rel"]).stem
    gaps = []
    for k in bm:
        if bm[k] != fm[k]:
            gaps.append(f"{k}: 盲写 {bm[k]} vs 标准 {fm[k]}")
    score = sum(1 for k in bm if bm[k] == fm[k]) / len(bm)
    rows.append((m["page"], stem, bm, fm, gaps, score))
    out.append(f"## P{m['page']:02d} · {stem}")
    out.append("")
    out.append(f"- 盲写: {json.dumps(bm, ensure_ascii=False)}")
    out.append(f"- 标准: {json.dumps(fm, ensure_ascii=False)}")
    out.append(f"- 指标命中率: {score:.0%}")
    if gaps:
        out.append(f"- 差距: {'；'.join(gaps)}")
    else:
        out.append("- 盲写指标与标准一致")
    out.append("")

avg = sum(r[5] for r in rows) / len(rows)
out.insert(4, f"**整体指标命中率: {avg:.0%}**（命中=通用知识能推出的维度；未命中=需抄答案的艺术分层）")
out.insert(5, "")
( HW / "对账报告.md").write_text("\n".join(out), encoding="utf-8")
print(f"report written, avg hit rate {avg:.0%}")
for r in rows:
    print(f"P{r[0]:02d} {r[1]:<28} hit={r[5]:.0%}")
