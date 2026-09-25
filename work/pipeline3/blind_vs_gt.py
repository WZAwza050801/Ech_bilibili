"""Blind version vs ground truth: how close did understanding-only get?"""
import re
from pathlib import Path

BLIND = Path(r"D:\课程视频变操作agent\EchoNotes\work\pipeline3\demo_homework\muzzle_flash.tscn")
GT = Path(r"D:\课程视频变操作agent\course-files\02_Results\VFX_GodotCourse_02_Results"
          r"\Prefabs\vfx_Projectile01_Muzzle.tscn")

blind = BLIND.read_text(encoding="utf-8")
gt = GT.read_text(encoding="utf-8")

print("=== 盲写版（仅凭分析理解，未看答案）===")
print(f"粒子系统数: {len(re.findall(r'type=.GPUParticles3D', blind))}")
print(f"子资源数(材质/曲线/网格): {len(re.findall(r'^..sub_resource', blind, re.M))}")
print(f"one_shot 爆发式: {'one_shot = true' in blind}")
print(f"explosiveness 瞬发: {'explosiveness' in blind}")
print(f"橙色系闪光: {'Color(1, 0.78, 0.3' in blind or '0.78' in blind}")
print(f"带灯光: {'OmniLight3D' in blind}")
print(f"使用贴图: {bool(re.findall(r'Texture2D', blind))}")

print()
print("=== 标准答案 ===")
print(f"粒子系统数: {len(re.findall(r'type=.GPUParticles3D', gt))}")
print(f"子资源数(材质/曲线/网格): {len(re.findall(r'^..sub_resource', gt, re.M))}")
print(f"one_shot 爆发式: {'one_shot = true' in gt}")
print(f"explosiveness 瞬发: {'explosiveness' in gt}")
print(f"橙色系闪光: {'Color(0.95, 0.75, 0' in gt or 'Color(1, 0.78' in gt or '1.5, 1, 1' in gt}")
print(f"带灯光: {'OmniLight3D' in gt}")
print(f"使用贴图: {len(re.findall(r'Texture2D', gt))} 处引用")
gt_nodes = re.findall(r'\[node name="([^"]+)" type="GPUParticles3D"', gt)
print(f"分层构成: {gt_nodes}")
print(f"湍流(turbulence): {'turbulence_enabled = true' in gt}")
print(f"lifetime 档位: {sorted(set(re.findall(r'lifetime = ([\d.]+)', gt)))}")
