import copy
import unittest

from work.pipeline2.concept_map import validate_concept_map
from work.pipeline2.study import (require_source_evidence_kept, validate_audit,
                                  validate_plan, validate_style, validate_unit)


class StudyContracts(unittest.TestCase):
    def setUp(self):
        self.lecture = {
            "segments": [{"id": "s1", "start": 0, "end": 30}, {"id": "s2", "start": 30, "end": 60}],
            "frames": [{"id": "f1", "actual_t": 15}, {"id": "f2", "actual_t": 45}]}
        self.plan = {
            "domain": "mathematics", "course_question": "为什么引入定义", "perspective": "从例子出发",
            "prerequisites": ["集合"], "writing_brief": "考察定义的条件",
            "goals": [{"level": "deep", "outcome": "构造反例", "check": "去掉条件如何"}],
            "units": [{"title": "定义", "segment_ids": ["s1", "s2"], "frame_id": "f1",
                       "focus": "条件的作用", "lens": "反例", "deep_question": "逆命题如何"}]}

    def test_plan_rejects_reordering_duplication_and_missing_evidence(self):
        validate_plan(self.plan, self.lecture)
        for ids in (["s1"], ["s2", "s1"], ["s1", "s1", "s2"], ["s1", "unknown"]):
            bad = copy.deepcopy(self.plan)
            bad["units"][0]["segment_ids"] = ids
            with self.assertRaises(ValueError):
                validate_plan(bad, self.lecture)

    def test_representative_frame_must_belong_to_unit(self):
        bad = copy.deepcopy(self.plan)
        bad["units"] = [
            {**bad["units"][0], "segment_ids": ["s1"], "frame_id": "f2"},
            {**bad["units"][0], "segment_ids": ["s2"], "frame_id": None}]
        with self.assertRaises(ValueError):
            validate_plan(bad, self.lecture)

    def test_supplements_and_source_claims_remain_distinct(self):
        value = {"audio_summary": "原话整理", "continuity": "已学定义",
                 "notes": [{"title": "定义", "text": "精确定义", "provenance": "source",
                            "evidence_ids": ["s1"],
                            "equations": [r"SO(3)=\{R\in\mathbb{R}^{3\times3}\mid R^TR=I\}"]}],
                 "annotations": [{"title": "直觉", "text": "补充说明"}],
                 "self_check": {"question": "为什么", "hint": "检查条件"}, "uncertainties": []}
        validate_unit(value, {"s1"})
        value["notes"][0]["evidence_ids"] = []
        with self.assertRaises(ValueError):
            validate_unit(value, {"s1"})
        value["notes"][0]["provenance"] = "supplement"
        validate_unit(value, {"s1"})
        value["notes"][0]["equations"] = [r"\input{private}"]
        with self.assertRaises(ValueError):
            validate_unit(value, {"s1"})

    def test_audit_cannot_introduce_unsupported_source_evidence(self):
        value = {"audio_summary": "原话整理", "continuity": "已学定义",
                 "notes": [{"title": "定义", "text": "精确定义", "provenance": "source",
                            "evidence_ids": ["s1"], "equations": ["x^2"]}],
                 "annotations": [{"title": "直觉", "text": "补充说明"}],
                 "self_check": {"question": "为什么", "hint": "检查条件"}, "uncertainties": []}
        self.assertEqual(validate_audit({"findings": [], "content": value}, {"s1"}), value)
        value["notes"][0]["evidence_ids"] = ["invented"]
        with self.assertRaises(ValueError):
            validate_audit({"findings": ["来源错误"], "content": value}, {"s1"})
        with self.assertRaises(ValueError):
            validate_audit({"findings": "已审校", "content": value}, {"s1"})

    def test_audit_repairs_double_escaped_tex_without_touching_row_breaks(self):
        value = {"audio_summary": r"速度 \\(\\omega\\) 已知", "continuity": "已知速度",
                 "notes": [{"title": "方程", "text": r"推出 \\(\\dot R\\)",
                            "provenance": "source", "evidence_ids": ["s1"],
                            "equations": [r"\begin{aligned}x &= \\frac{1}{2} \\alpha \\ "
                                          r"y &= \\beta\end{aligned}"]}],
                 "annotations": [{"title": "直觉", "text": r"见 \\(\\alpha\\)"}],
                 "self_check": {"question": "为何", "hint": "推导"}, "uncertainties": []}
        result = validate_audit({"findings": [], "content": value}, {"s1"})
        self.assertEqual(result["audio_summary"], r"速度 \(\omega\) 已知")
        self.assertEqual(result["notes"][0]["equations"][0],
                         r"\begin{aligned}x &= \frac{1}{2} \alpha \\ y &= \beta\end{aligned}")
        self.assertEqual(value["audio_summary"], r"速度 \\(\\omega\\) 已知")

    def test_symbol_summary_is_optional_but_validated(self):
        value = {"audio_summary": "原话整理", "continuity": "已学定义",
                 "notes": [{"title": "定义", "text": "精确定义", "provenance": "source",
                            "evidence_ids": ["s1"], "equations": []}],
                 "annotations": [{"title": "直觉", "text": "补充说明"}],
                 "self_check": {"question": "为什么", "hint": "检查条件"}, "uncertainties": []}
        validate_unit(value, {"s1"})
        value["symbol_summary"] = [{"symbol": r"\hat{\omega}", "meaning": "角速度"}]
        validate_unit(value, {"s1"})
        value["symbol_summary"] = [{"symbol": r"\input{private}", "meaning": "x"}]
        with self.assertRaises(ValueError):
            validate_unit(value, {"s1"})
        value["symbol_summary"] = [{"symbol": r"\hat{\omega}"}]
        with self.assertRaises(ValueError):
            validate_unit(value, {"s1"})

    def test_revision_cannot_drop_source_evidence(self):
        draft = {"audio_summary": "原话整理", "continuity": "已学定义",
                 "notes": [{"title": "定义", "text": "精确定义", "provenance": "source",
                            "evidence_ids": ["s1", "s2"], "equations": []},
                           {"title": "补充", "text": "推导", "provenance": "supplement",
                            "evidence_ids": [], "equations": []}],
                 "annotations": [{"title": "直觉", "text": "补充说明"}],
                 "self_check": {"question": "为什么", "hint": "检查条件"}, "uncertainties": []}
        kept = copy.deepcopy(draft)
        kept["notes"][0]["evidence_ids"] = ["s1"]
        with self.assertRaises(ValueError):
            require_source_evidence_kept(draft, kept)
        kept["notes"][0]["evidence_ids"] = ["s1", "s2"]
        require_source_evidence_kept(draft, kept)

    def test_style_pass_must_cover_every_unit_in_order(self):
        annotation = {"title": "批注", "text": "判断"}
        good = {"findings": ["统一术语"], "units": [{"index": 1, "annotations": [annotation]},
                                                   {"index": 2, "annotations": [annotation]}]}
        validate_style(good, 2)
        for bad in ({"findings": [], "units": [{"index": 2, "annotations": [annotation]}]},
                    {"findings": [], "units": [{"index": 1, "annotations": [annotation]}]},
                    {"findings": [], "units": [{"index": 1, "annotations": []},
                                               {"index": 2, "annotations": [annotation]}]},
                    {"units": good["units"]}):
            with self.assertRaises(ValueError):
                validate_style(copy.deepcopy(bad), 2)

    def test_concept_map_structure_is_bounded(self):
        nodes = [{"id": f"n{i}", "label": f"概念{i}", "kind": "definition",
                  "unit_index": 1 if i % 2 else 2} for i in range(1, 9)]
        edges = [{"from": f"n{i}", "to": f"n{i+1}", "relation": "依赖"} for i in range(1, 8)]
        edges += [{"from": "n1", "to": "n8", "relation": "推广"},
                  {"from": "n2", "to": "n4", "relation": "对比"},
                  {"from": "n3", "to": "n5", "relation": "应用"},
                  {"from": "n4", "to": "n6", "relation": "应用"},
                  {"from": "n5", "to": "n7", "relation": "等价"}]
        good = {"nodes": nodes, "edges": edges}
        validate_concept_map(good, 2)
        duplicate = dict(nodes[0], label="重复")
        cases = [
            {"nodes": nodes[:5], "edges": edges},
            {"nodes": nodes, "edges": edges[:5]},
            {"nodes": nodes, "edges": edges + [{"from": "n1", "to": "n1", "relation": "自环"}]},
            {"nodes": nodes, "edges": edges + [{"from": "n1", "to": "ghost", "relation": "依赖"}]},
            {"nodes": nodes + [duplicate], "edges": edges},
            {"nodes": [dict(nodes[0], kind="unknown")] + nodes[1:], "edges": edges},
            {"nodes": [dict(nodes[0], unit_index=9)] + nodes[1:], "edges": edges},
            {"nodes": nodes + [duplicate], "edges": edges[:11]},
        ]
        for bad in cases:
            with self.assertRaises(ValueError):
                validate_concept_map(copy.deepcopy(bad), 2)


if __name__ == "__main__":
    unittest.main()
