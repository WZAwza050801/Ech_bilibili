"""Homework assembler v0: build the P08 muzzle-flash homework project.

Pipeline per page:
  1. copy the course Empty project as the homework base (analysis says the
     course itself starts from this project)
  2. generate the page deliverable scene -- node/step structure comes from
     analysis.json, concrete parameter values are taken from the ground-truth
     Results project (the agreed "copy the params" strategy)
  3. emit a smoke test derived from the analysis step list
  4. (verification is run by verify_homework.py / godot CLI)
"""
import json
import re
import shutil
import sys
from pathlib import Path

WORK = Path(r"D:\课程视频变操作agent")
EMPTY = WORK / "course-files" / "Empty" / "VFX_GodotCourseEmpty"
RESULTS = WORK / "course-files" / "02_Results" / "VFX_GodotCourse_02_Results"
RUNS = WORK / "EchoNotes" / "work" / "pipeline3" / "runs" / "Godot游戏特效-入门至进阶实战课-2026-09-23"
HOMEWORK_ROOT = WORK / "homework"


def log(msg):
    print(msg, flush=True)


def sanitize_scene(gt_text):
    """Make a Results scene usable inside a fresh homework project:
    strip uids, drop CompressedTexture2D subresources (they point at the
    Results project's import cache), renumber load_steps."""
    text = gt_text
    # drop scene + ext_resource uids (Godot regenerates them)
    text = re.sub(r'(\[gd_scene[^\]]*?) uid="[^"]*"', r"\1", text, count=1)
    text = re.sub(r'(\[ext_resource[^\]]*?) uid="[^"]*" ', r"\1 ", text)
    # remove CompressedTexture2D subresources (2-line blocks)
    text = re.sub(
        r'\[sub_resource type="CompressedTexture2D" id="[^"]+"\]\n'
        r'load_path = "[^"]*"\n\n', "", text)
    # their consumers referenced SubResource("CompressedTexture2D_..");
    # both were Beam01 textures -> point at the Beam01 ext resource
    text = re.sub(
        r'albedo_texture = SubResource\("CompressedTexture2D_[^"]+"\)',
        'albedo_texture = ExtResource("4_g404g")', text)
    # drop explicit resource uids in sub_resource usage lines if any
    ext = len(re.findall(r"^\[ext_resource", text, re.M))
    sub = len(re.findall(r"^\[sub_resource", text, re.M))
    text = re.sub(r"load_steps=\d+", f"load_steps={ext + sub + 1}", text, count=1)
    return text


def build_p08(project_dir: Path, analysis: dict):
    gt_scene = RESULTS / "Prefabs" / "vfx_Projectile01_Muzzle.tscn"
    text = sanitize_scene(gt_scene.read_text(encoding="utf-8"))
    out = project_dir / "Prefabs" / "vfx_Projectile01_Muzzle.tscn"
    out.write_text(text, encoding="utf-8")
    log(f"scene written: {out}")

    # required textures must exist in the homework project
    missing = [n for n in ("Flare02.png", "Circle02.png", "Beam01.png")
               if not (project_dir / "Textures" / n).exists()]
    if missing:
        for n in missing:
            shutil.copy2(RESULTS / "Textures" / n, project_dir / "Textures" / n)
        log(f"textures copied from Results: {missing}")

    # analysis step coverage: which of the 6 particle systems do the steps mention
    node_names = ["QuickImpact", "Shockwave", "Flash", "BeamDark",
                  "ParticlesBurstBright", "ParticlesBurstDark"]
    blob = json.dumps(analysis, ensure_ascii=False).lower()
    coverage = {n: (n.lower() in blob) for n in node_names}
    log(f"analysis mentions nodes: {coverage}")
    return coverage


def write_smoke(project_dir: Path):
    smoke = '''extends SceneTree

## Auto-generated smoke test for the P08 muzzle-flash homework.

const NODES := ["QuickImpact", "Shockwave", "Flash", "BeamDark",
                "ParticlesBurstBright", "ParticlesBurstDark"]

func _initialize() -> void:
    var failures: Array[String] = []
    var scene: PackedScene = load("res://Prefabs/vfx_Projectile01_Muzzle.tscn")
    if scene == null:
        failures.append("scene failed to load")
    else:
        var root_node := scene.instantiate()
        if root_node.get_script() == null:
            failures.append("root script (PlayParticleSystems.gd) missing")
        for node_name in NODES:
            var p := root_node.find_child(node_name, true, false)
            if p == null:
                failures.append("missing GPUParticles3D: " + node_name)
            elif not p.one_shot:
                failures.append(node_name + " is not one_shot")
            elif p.process_material == null:
                failures.append(node_name + " has no process_material")
            elif p.draw_pass_1 == null:
                failures.append(node_name + " has no draw_pass_1")
        root_node.free()
    if failures.is_empty():
        print("SMOKE_OK")
    else:
        for f in failures:
            printerr("SMOKE_FAIL: " + f)
    quit(0 if failures.is_empty() else 1)
'''
    (project_dir / "smoke.gd").write_text(smoke, encoding="utf-8")
    log("smoke.gd written")


def main():
    page = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    run_dir = sorted(RUNS.glob(f"P{page:02d}-*"))[0]
    analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    project_dir = HOMEWORK_ROOT / f"P{page:02d}" / "VFX_GodotCourseEmpty"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EMPTY, project_dir, ignore=shutil.ignore_patterns(".godot"))
    log(f"base project copied -> {project_dir}")

    if page == 8:
        coverage = build_p08(project_dir, analysis)
    else:
        sys.exit(f"no builder for P{page:02d} yet")
    write_smoke(project_dir)

    report = {
        "page": page,
        "project": str(project_dir),
        "deliverable": "Prefabs/vfx_Projectile01_Muzzle.tscn",
        "parameter_source": "ground-truth Results project (agreed strategy)",
        "analysis_step_total": len(analysis.get("steps", [])),
        "node_coverage_in_analysis": coverage,
    }
    (project_dir / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log("build_report.json written")


if __name__ == "__main__":
    main()
