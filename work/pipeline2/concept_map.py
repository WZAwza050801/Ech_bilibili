"""Course concept map: planner-generated graph, Python-laid-out TikZ page.

The model only decides concepts and relations; layout is deterministic so the
picture can never drift outside the page or invent structure.
"""
import math
import re

from .render import prose_tex

KIND_STYLE = {
    "definition": ("cmS1", "cmF1", "cmT1"),
    "theorem": ("cmS2", "cmF2", "cmT2"),
    "method": ("cmS3", "cmF3", "cmT3"),
    "application": ("cmS4", "cmF4", "cmT4"),
}

COLOR_DEFS = r"""\definecolor{cmS1}{HTML}{185FA5}\definecolor{cmF1}{HTML}{E6F1FB}\definecolor{cmT1}{HTML}{0C447C}
\definecolor{cmS2}{HTML}{534AB7}\definecolor{cmF2}{HTML}{EEEDFE}\definecolor{cmT2}{HTML}{26215C}
\definecolor{cmS3}{HTML}{0F6E56}\definecolor{cmF3}{HTML}{E1F5EE}\definecolor{cmT3}{HTML}{085041}
\definecolor{cmS4}{HTML}{854F0B}\definecolor{cmF4}{HTML}{FAEEDA}\definecolor{cmT4}{HTML}{412402}
\definecolor{cmLbl}{HTML}{444441}"""

DASHED_WORDS = ("对比", "类比", "区别", "对偶")


def validate_concept_map(data, unit_count):
    if not isinstance(data, dict):
        raise ValueError("Concept map must be an object")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not 8 <= len(nodes) <= 20:
        raise ValueError("Concept map needs 8-20 nodes")
    ids = set()
    per_unit = {}
    for node in nodes:
        if (not isinstance(node, dict) or not isinstance(node.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9]+", node["id"])):
            raise ValueError("Concept node id must be alphanumeric")
        if node["id"] in ids:
            raise ValueError("Duplicate concept id")
        ids.add(node["id"])
        if (not isinstance(node.get("label"), str) or not node["label"].strip()
                or len(node["label"]) > 40):
            raise ValueError("Concept label must be 1-40 characters")
        if node.get("kind") not in KIND_STYLE:
            raise ValueError("Unknown concept kind")
        if not isinstance(node.get("unit_index"), int) or not 1 <= node["unit_index"] <= unit_count:
            raise ValueError("Concept unit_index out of range")
        per_unit.setdefault(node["unit_index"], 0)
        per_unit[node["unit_index"]] += 1
    if any(count > 6 for count in per_unit.values()):
        raise ValueError("Any unit column holds at most 6 concept nodes")
    if not isinstance(edges, list) or not 12 <= len(edges) <= 3 * len(nodes):
        raise ValueError("Concept map needs 12-3n edges")
    seen = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Edge must be an object")
        start, end = edge.get("from"), edge.get("to")
        if start not in ids or end not in ids or start == end:
            raise ValueError("Edge endpoints invalid")
        if (start, end) in seen:
            raise ValueError("Duplicate edge")
        seen.add((start, end))
        relation = edge.get("relation", "关联")
        if not isinstance(relation, str) or not relation.strip() or len(relation) > 16:
            raise ValueError("Relation label must be 1-16 characters")
    return data


def _column(nodes, unit):
    return [n for n in nodes if n["unit_index"] == unit]


def _layout(nodes, unit_count):
    """Snake layout: one column per unit; two rows when more than four columns."""
    columns = [u for u in range(1, unit_count + 1) if _column(nodes, u)]
    if len(columns) <= 4:
        rows = [columns]
    else:
        half = math.ceil(len(columns) / 2)
        rows = [columns[:half], columns[half:]]
    row_half = [max(len(_column(nodes, c)) for c in row) * 2.1 / 2 for row in rows]
    gap = 1.5
    centers = [0.0] if len(rows) == 1 else [row_half[1] + gap / 2, -(row_half[0] + gap / 2)]
    position, unit_pos = {}, {}
    for r, row in enumerate(rows):
        for i, c in enumerate(row):
            x = (i if r == 0 else len(row) - 1 - i) * 4.15
            members = _column(nodes, c)
            for j, node in enumerate(members):
                y = centers[r] + ((len(members) - 1) / 2 - j) * 2.1
                position[node["id"]] = (x, y)
            unit_pos[c] = (x, centers[r] + row_half[r] + 0.5)
    width = (max(len(row) for row in rows) - 1) * 4.15
    return position, unit_pos, width, sum(row_half) * 2 + gap


def render_concept_map(map_data, unit_count):
    """Return a self-contained LaTeX block: the concept-map TikZ picture."""
    nodes, edges = map_data["nodes"], map_data["edges"]
    position, unit_pos, width, height = _layout(nodes, unit_count)
    lines = ["{" + COLOR_DEFS,
             r"\centering\resizebox{\textwidth}{!}{%",
             r"\begin{tikzpicture}[x=1cm,y=1cm,",
             r">={Stealth}]"]
    for unit, (x, y) in sorted(unit_pos.items()):
        lines.append(r"\node[font=\scriptsize, text=cmLbl] at (" +
                     f"{x:.2f},{y:.2f})" + r"{第 " + str(unit) + r" 单元};")
    for node in nodes:
        stroke, fill, text_color = KIND_STYLE[node["kind"]]
        x, y = position[node["id"]]
        lines.append(r"\node[draw=" + stroke + r", fill=" + fill + r", text=" + text_color +
                     r", rounded corners=2pt, align=center, font=\footnotesize, "
                     r"text width=2.35cm, inner sep=2.5pt] (" + node["id"] + ") at (" +
                     f"{x:.2f},{y:.2f})" + "{" + prose_tex(node["label"]) + "};")
    for edge in edges:
        start, end = edge["from"], edge["to"]
        relation = edge.get("relation", "关联")
        style = r", dashed" if any(word in relation for word in DASHED_WORDS) else ""
        same_column = (position[start][0] == position[end][0])
        bend = r"bend right=32" if same_column else r"bend left=14"
        lines.append(r"\draw[->, cmLbl, line width=0.5pt" + style + "] (" + start + ") to[" +
                     bend + "] node[midway, font=\\tiny, text=cmLbl, fill=white, inner sep=1pt]{" +
                     prose_tex(relation) + "} (" + end + ");")
    lines += [r"\end{tikzpicture}}", r"\par"]
    return "\n".join(lines)


MAP_CAPTION = ("概念节点按学习单元分列；实线为依赖/应用，虚线为对比/对偶；"
               "蓝=定义对象，紫=定理结论，绿=方法技巧，金=应用场景。"
               "地图是阅读导航，帮助先看到全局结构，不是完备知识图谱。")
