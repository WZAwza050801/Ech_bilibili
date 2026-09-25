"""Diff the generated homework scene against the ground-truth scene."""
import json
import re
from pathlib import Path

GT = Path(r"D:\课程视频变操作agent\course-files\02_Results\VFX_GodotCourse_02_Results"
          r"\Prefabs\vfx_Projectile01_Muzzle.tscn")
HW = Path(r"D:\课程视频变操作agent\homework\P08\VFX_GodotCourseEmpty"
          r"\Prefabs\vfx_Projectile01_Muzzle.tscn")
OUT = Path(r"D:\课程视频变操作agent\homework\P08\diff_report.json")

NODES = ["QuickImpact", "Shockwave", "Flash", "BeamDark",
         "ParticlesBurstBright", "ParticlesBurstDark"]


def parse(text):
    """Extract per-node dict of properties and the set of sub_resource types."""
    nodes = {}
    cur = None
    subs = []
    for line in text.splitlines():
        m = re.match(r'\[node name="([^"]+)" type="([^"]+)"', line)
        if m:
            cur = m.group(1)
            nodes[cur] = {"_type": m.group(2)}
            continue
        m = re.match(r'\[sub_resource type="([^"]+)"', line)
        if m:
            subs.append(m.group(1))
            continue
        if cur and "=" in line and not line.startswith(("delays", "\t")):
            key = line.split("=", 1)[0].strip()
            nodes[cur][key] = line.split("=", 1)[1].strip()[:80]
        if cur and line.startswith("delays"):
            nodes[cur]["delays"] = "present"
    return nodes, sorted(set(subs))


gt_nodes, gt_subs = parse(GT.read_text(encoding="utf-8"))
hw_nodes, hw_subs = parse(HW.read_text(encoding="utf-8"))

node_report = {}
for n in NODES:
    g, h = gt_nodes.get(n), hw_nodes.get(n)
    if g is None or h is None:
        node_report[n] = {"gt": bool(g), "hw": bool(h), "match": False}
        continue
    keys = set(g) | set(h)
    diffs = [k for k in keys if g.get(k) != h.get(k)]
    # value strings may differ in float formatting; compare loosely
    real_diffs = [k for k in diffs if str(g.get(k)).replace(" ", "") != str(h.get(k)).replace(" ", "")]
    node_report[n] = {"present": True, "prop_keys_gt": len(g), "prop_keys_hw": len(h),
                      "differing_props": real_diffs, "match": not real_diffs}

report = {
    "gt_scene": str(GT),
    "hw_scene": str(HW),
    "nodes_in_gt": len(gt_nodes),
    "nodes_in_hw": len(hw_nodes),
    "sub_resource_types_equal": gt_subs == hw_subs,
    "sub_resource_types_gt": gt_subs,
    "node_report": node_report,
    "all_nodes_match": all(v.get("match") for v in node_report.values()),
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "sub_resource_types_gt"},
                 ensure_ascii=False, indent=1))
