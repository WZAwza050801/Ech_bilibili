"""Generate showcase scenes (camera + light + autoplay driver + prefab instance)
for every course deliverable, so they can be rendered to video."""
import json
from pathlib import Path

HW = Path(r"D:\课程视频变操作agent\homework\VFX_Course_Homework")
manifest = json.loads((HW / "manifest.json").read_text(encoding="utf-8"))

DRIVER = '''extends Node3D

func _ready() -> void:
    await get_tree().create_timer(0.15).timeout
    for p in find_children("*", "GPUParticles3D", true, false):
        p.restart()
        p.emitting = true
    for p in find_children("*", "GPUParticles3D", true, false):
        pass
'''

showcase_dir = HW / "Scenes" / "Showcase"
showcase_dir.mkdir(parents=True, exist_ok=True)
(HW / "Scripts" / "showcase_driver.gd").write_text(DRIVER, encoding="utf-8")

entries = []
FULL_STAGE = {"VFX_Sparks", "VFX_AoE"}  # GT scenes with own camera/env/stage
for m in manifest:
    stem = Path(m["rel"]).stem
    ext_id = f'ext_{stem.replace("-", "_")}'
    if stem in FULL_STAGE:
        scene = f'''[gd_scene load_steps=3 format=3]

[ext_resource type="PackedScene" path="res://{m['rel']}" id="{ext_id}"]
[ext_resource type="Script" path="res://Scripts/showcase_driver.gd" id="driver"]

[node name="Showcase_{stem}" type="Node3D"]
script = ExtResource("driver")

[node name="Effect" parent="." instance=ExtResource("{ext_id}")]
'''
    else:
        scene = f'''[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="res://{m['rel']}" id="{ext_id}"]
[ext_resource type="Script" path="res://Scripts/showcase_driver.gd" id="driver"]

[sub_resource type="Environment" id="env"]
background_mode = 1
background_color = Color(0.08, 0.09, 0.12, 1)
ambient_light_source = 2
ambient_light_color = Color(1, 1, 1, 1)
ambient_light_energy = 0.6

[node name="Showcase_{stem}" type="Node3D"]
script = ExtResource("driver")

[node name="Env" type="WorldEnvironment" parent="."]
environment = SubResource("env")

[node name="Cam" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0.984808, 0.173648, 0, -0.173648, 0.984808, 0, 0.45, 2.6)

[node name="KeyLight" type="DirectionalLight3D" parent="."]
light_energy = 0.4
transform = Transform3D(0.813798, 0.342020, -0.469846, 0, 0.808290, 0.588490, 0.581289, -0.478908, 0.657823, 1.5, 2.5, 1.5)

[node name="Effect" parent="." instance=ExtResource("{ext_id}")]
'''
    path = showcase_dir / f"Showcase_{stem}.tscn"
    path.write_text(scene, encoding="utf-8")
    entries.append(path.name)

(HW / "Scenes" / "Showcase" / "showcase_list.json").write_text(
    json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(entries)} showcase scenes written")
