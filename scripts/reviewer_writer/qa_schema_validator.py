#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA JSON 格式校验器（qa_schema_validator.py）
检查一道/一批 QA 文件是否符合 TENGBench schema（通用字段 + 各题型特定字段）。
用法：
    python3 qa_schema_validator.py <qa.json | 目录>
对应规格：docs/implementation.md §5；被 TENGBench-reviewer-writer 出题后自检调用。
"""
import json
import sys
from pathlib import Path

TYPES = {"BK1", "BK2", "BK3", "BK4", "RP1", "RP2", "RP3", "RP4", "DG1", "DG2", "DG3"}
LAYERS = {"L1", "L2", "L3"}
# L1 subcategory 为 BK 子方向名；L2/L3 为传感应用场景（15 个，受控）
L1_SUBCATS = {
    "triboelectric_mechanism", "electrostatic_induction", "displacement_current",  # BK1
    "contact_separation", "sliding", "single_electrode", "freestanding",            # BK2
    "triboelectric_series", "surface_modification",                                  # BK3
    "output_coupling", "impedance_matching",                                         # BK4
}
L2L3_SUBCATS = {
    "aviation", "wearable", "tactile", "chemical", "hmi", "iot",
    "biomedical", "marine", "wind", "motion", "acoustic",
    "robotics", "smarttextile", "energyharv", "space",
}
SUBCATS = L1_SUBCATS | L2L3_SUBCATS

REQUIRED_COMMON = ["qa_id", "type", "layer", "subcategory", "source_paper_id",
                   "source_excerpt", "question", "scoring"]


def validate(qa: dict) -> list:
    """返回错误信息列表；空列表表示通过。"""
    e = []
    for k in REQUIRED_COMMON:
        if qa.get(k) in (None, "", []):
            e.append(f"缺失或为空：{k}")
    if qa.get("type") not in TYPES:
        e.append(f"type 非法：{qa.get('type')}")
    if qa.get("layer") not in LAYERS:
        e.append(f"layer 非法：{qa.get('layer')}")
    if qa.get("subcategory") not in SUBCATS:
        e.append(f"subcategory 非法：{qa.get('subcategory')}")
    # layer-subcategory 一致性：L1 必须是 BK 子方向；L2/L3 必须是传感场景
    layer = qa.get("layer")
    subcat = qa.get("subcategory")
    if layer == "L1" and subcat not in L1_SUBCATS:
        e.append(f"L1 题的 subcategory 必须是 BK 子方向名（如 triboelectric_mechanism），当前为 {subcat}")
    if layer in ("L2", "L3") and subcat not in L2L3_SUBCATS:
        e.append(f"{layer} 题的 subcategory 必须是传感场景名（如 aviation），当前为 {subcat}")
    if not qa.get("source_excerpt"):
        e.append("source_excerpt 必填（防污染与可追溯）")

    t = qa.get("type")
    sc = qa.get("scoring", {})
    mech = sc.get("mechanism")

    # 所有选择题（BK1-4/RP1-4）统一：options 是字母到文本的映射对象 + answer 是正确项字母
    if t in {"BK1", "BK2", "BK3", "BK4", "RP1", "RP2", "RP3", "RP4"}:
        opts = qa.get("options")
        if not isinstance(opts, dict) or not opts:
            e.append(t + " 需要 options（字母到选项文本的映射对象，如 {\"A\":\"...\",\"B\":\"...\",\"C\":\"...\",\"D\":\"...\",\"E\":\"...\"}）")
        else:
            if not all(k in opts for k in ("A", "B", "C", "D", "E")):
                e.append(f"{t} options 应包含 A/B/C/D/E 五项（随机猜对率 20%）")
        if "answer" not in qa:
            e.append(f"{t} 需要 answer（正确项字母，如 'B'，可选 A/B/C/D/E）")
        elif qa.get("answer") not in ("A", "B", "C", "D", "E"):
            e.append(f"{t} answer 必须是 A/B/C/D/E 之一，当前为：{qa.get('answer')}")
        if mech != "A":
            e.append(f"{t} scoring.mechanism 应为 'A'")
        # 旧字段冗余检查
        if "magnitude_options" in qa:
            e.append(f"{t} 不应含 magnitude_options（统一用 options）")
        if "answer_index" in qa:
            e.append(f"{t} 不应含 answer_index（与 answer 重复，删掉）")
        sc.pop("magnitude_check", None)  # 忽略遗留的 magnitude_check
        # 推理题规则：RP4 必填 multi_step_reasoning；RP1/2/3 不应有
        if t == "RP4":
            if not qa.get("multi_step_reasoning"):
                e.append("RP4 必填 multi_step_reasoning（分步推理答案）")
        elif qa.get("multi_step_reasoning"):
            e.append(f"{t} 不应含 multi_step_reasoning（L2 仅 RP4 推理）")
    elif t in {"DG1", "DG2", "DG3"}:
        if "rubric" not in qa or "reference_answer" not in qa:
            e.append(f"{t} 需要 rubric + reference_answer")
        if not qa.get("multi_step_reasoning"):
            e.append(f"{t} 必填 multi_step_reasoning（分步答案）")
        if mech != "A+B":
            e.append(f"{t} scoring.mechanism 应为 'A+B'")
    return e


def main():
    if len(sys.argv) < 2:
        print("用法: python3 qa_schema_validator.py <qa.json | 目录>")
        sys.exit(2)
    target = Path(sys.argv[1])
    if not target.exists():
        print(f"路径不存在: {target}")
        sys.exit(2)
    files = [target] if target.is_file() else sorted(target.rglob("*.json"))

    total, bad = 0, 0
    for f in files:
        total += 1
        try:
            qa = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:
            print(f"[ERR] {f.name}: JSON 解析失败：{ex}")
            bad += 1
            continue
        errs = validate(qa)
        if errs:
            bad += 1
            print(f"[FAIL] {f.name} ({qa.get('qa_id', '?')}):")
            for x in errs:
                print(f"    - {x}")
        else:
            print(f"[OK]   {f.name} ({qa.get('qa_id', '?')})")
    print(f"\n校验完成：{total - bad}/{total} 通过")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
