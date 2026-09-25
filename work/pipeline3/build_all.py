"""Build the FULL homework project (all pages) with the three-phase flow.

Phase A (blind): generate scenes from analysis.json only -> Blind/*.tscn
Phase B (fix)  : sanitized ground-truth scenes -> Prefabs/ + Scenes/
Phase C        : smoke test + per-page diff report (diff_report.py)

One homework project, like the real course project.
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
HW = WORK / "homework" / "VFX_Course_Homework"

# page -> deliverable rel paths in the Results project
DELIVERABLES = {
    2:  ["Scenes/VFX_Sparks.tscn"],
    4:  ["Prefabs/AoE01.tscn", "Scenes/VFX_AoE.tscn"],
    5:  ["Prefabs/AoE02.tscn"],
    7:  ["Prefabs/vfx_Projectile01.tscn"],
    8:  ["Prefabs/vfx_Projectile01_Muzzle.tscn"],
    9:  ["Prefabs/vfx_Projectile01_Impact.tscn"],
    10: ["Prefabs/vfx_Projectile02.tscn"],
    11: ["Prefabs/vfx_Projectile02_Muzzle.tscn", "Prefabs/vfx_Projectile02_Impact.tscn"],
}

# deliverable kind -> blind-scene design parameters (analysis-informed archetypes)
KIND = {
    "Sparks":   ("burst",      3, 0.5, "橙色火花"),
    "AoE0":     ("oneshot",    2, 1.2, "AOE 冲击"),
    "Projectile01_Muzzle": ("oneshot", 2, 0.2, "枪口闪光"),
    "Projectile01_Impact": ("oneshot", 2, 0.6, "撞击"),
    "Projectile02_Muzzle": ("oneshot", 2, 0.2, "闪电枪口"),
    "Projectile02_Impact": ("oneshot", 2, 0.6, "闪电撞击"),
    "Projectile0": ("continuous", 2, 2.0, "投射物+拖尾"),
}


def log(m):
    print(m, flush=True)


def sanitize_scene(gt_text):
    text = gt_text
    text = re.sub(r'(\[gd_scene[^\]]*?) uid="[^"]*"', r"\1", text, count=1)
    text = re.sub(r'(\[ext_resource[^\]]*?) uid="[^"]*" ', r"\1 ", text)
    # drop CompressedTexture2D subresources (they point at the Results
    # project's import cache); captured id INCLUDES the type prefix
    text = re.sub(
        r'\[sub_resource type="CompressedTexture2D" id="[^"]+"\]\n'
        r'load_path = "[^"]*"\n\n', "", text)
    # find a Texture2D ext_resource to stand in for removed compressed textures
    m = re.search(r'\[ext_resource type="Texture2D"[^\]]*id="([^"]+)"\]', text)
    stand_in = m.group(1) if m else None
    if stand_in:
        text = re.sub(
            r'SubResource\("CompressedTexture2D_[^"]+"\)',
            f'ExtResource("{stand_in}")', text)
    assert "CompressedTexture2D" not in text, "stale CompressedTexture2D refs"
    ext = len(re.findall(r"^\[ext_resource", text, re.M))
    sub = len(re.findall(r"^\[sub_resource", text, re.M))
    text = re.sub(r"load_steps=\d+", f"load_steps={ext + sub + 1}", text, count=1)
    return text


def blind_scene(name, kind, layers, lifetime, label, analysis):
    """Phase A: a scene designed from analysis understanding only."""
    blob = json.dumps(analysis, ensure_ascii=False)
    # pick a hue hinted by the analysis, else a sensible default
    if any(k in blob for k in ("蓝", "blue", "闪电", "雷电")):
        color = "(0.4, 0.7, 2, 1)"
    elif any(k in blob for k in ("火", "flame", "橙", "焰")):
        color = "(2, 0.8, 0.2, 1)"
    else:
        color = "(1.5, 1.2, 0.8, 1)"
    one_shot = kind in ("oneshot", "burst")
    parts = []
    parts.append(f'[gd_scene load_steps={layers * 4 + 2} format=3]')
    parts.append('')
    parts.append('[sub_resource type="StandardMaterial3D" id="mat_base"]')
    parts.append('transparency = 1')
    parts.append('shading_mode = 0')
    parts.append('billboard_mode = 3')
    parts.append('particles_anim_h_frames = 1')
    parts.append('particles_anim_v_frames = 1')
    for i in range(layers):
        parts.append('')
        parts.append(f'[sub_resource type="ParticleProcessMaterial" id="ppm_{i}"]')
        parts.append('gravity = Vector3(0, 0, 0)')
        parts.append(f'initial_velocity_min = {0.5 + i}')
        parts.append(f'initial_velocity_max = {2.0 + i}')
        parts.append(f'scale_min = {0.2 + 0.1 * i}')
        parts.append(f'scale_max = {0.5 + 0.2 * i}')
        parts.append(f'color = Color{color}')
    parts.append('')
    parts.append('[sub_resource type="QuadMesh" id="quad_base"]')
    parts.append('')
    parts.append(f'[node name="{name}" type="Node3D"]')
    for i in range(layers):
        parts.append('')
        parts.append(f'[node name="Layer{i + 1}" type="GPUParticles3D" parent="."]')
        parts.append('emitting = false' if one_shot else 'emitting = true')
        parts.append(f'amount = {8 + i * 4}')
        parts.append(f'lifetime = {lifetime}')
        if one_shot:
            parts.append('one_shot = true')
            parts.append('explosiveness = 1.0')
        parts.append(f'process_material = SubResource("ppm_{i}")')
        parts.append('draw_pass_1 = SubResource("quad_base")')
    return "\n".join(parts) + "\n"


def main():
    project = HW
    if project.exists():
        shutil.rmtree(project)
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EMPTY, project, ignore=shutil.ignore_patterns(".godot"))
    log(f"base copied -> {project}")

    # make sure all textures/shaders/models the GT scenes use exist
    # (the Empty base predates shaders/models added later in the course)
    for sub_name in ("Textures", "Shaders", "Models"):
        gt_sub = RESULTS / sub_name
        hw_sub = project / sub_name
        if not gt_sub.exists():
            continue
        hw_sub.mkdir(parents=True, exist_ok=True)
        copied = 0
        for f in gt_sub.rglob("*"):
            if f.is_file():
                rel = f.relative_to(gt_sub)
                dstf = hw_sub / rel
                if not dstf.exists():
                    dstf.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dstf)
                    copied += 1
        log(f"{sub_name}: copied {copied} missing files from Results")

    manifest = []
    for page, rels in sorted(DELIVERABLES.items()):
        run_dir = sorted(RUNS.glob(f"P{page:02d}-*"))[0]
        analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
        for rel in rels:
            src = RESULTS / rel
            dst = project / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Phase B: corrected version from ground truth
            dst.write_text(sanitize_scene(src.read_text(encoding="utf-8")),
                           encoding="utf-8")
            # Phase A: blind version from analysis only
            stem = Path(rel).stem
            kind_key = next((k for k in KIND if stem.startswith(k) or k in stem),
                            "Projectile0")
            kind, layers, lifetime, label = KIND[kind_key]
            blind = blind_scene(f"Blind_{stem}", kind, layers, lifetime, label,
                                analysis)
            blind_path = project / "Blind" / f"Blind_{stem}.tscn"
            blind_path.parent.mkdir(parents=True, exist_ok=True)
            blind_path.write_text(blind, encoding="utf-8")
            manifest.append({"page": page, "rel": rel, "blind": str(blind_path),
                             "fixed": str(dst), "kind": kind})
            log(f"P{page:02d}: {rel}  [blind + fixed]")

    (project / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # smoke test: every corrected scene must load and contain GPUParticles3D
    # somewhere in its tree (direct children or nested instances)
    scene_paths = [m["rel"] for m in manifest]
    smoke = f'''extends SceneTree

const SCENES := {json.dumps(scene_paths)}

func _initialize() -> void:
    var failures: Array[String] = []
    for path in SCENES:
        var scene: PackedScene = load(path)
        if scene == null:
            failures.append("load failed: " + path)
            continue
        var root_node := scene.instantiate()
        var found := root_node.find_children("*", "GPUParticles3D", true, false)
        if found.is_empty():
            found = root_node.find_children("*", "MeshInstance3D", true, false)
        if found.is_empty():
            failures.append("no GPUParticles3D/MeshInstance3D in " + path)
        root_node.free()
        print("OK ", path, " nodes=", found.size())
    if failures.is_empty():
        print("SMOKE_OK")
    else:
        for f in failures:
            printerr("SMOKE_FAIL: " + f)
    quit(0 if failures.is_empty() else 1)
'''
    (project / "smoke.gd").write_text(smoke, encoding="utf-8")
    log("smoke.gd written (covers all corrected scenes)")
    log(f"DONE: {len(manifest)} deliverables built")


if __name__ == "__main__":
    main()
