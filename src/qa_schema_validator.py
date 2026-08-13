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
# L1=general（通识基础，不绑场景）；L2/L3=TENG 传感应用场景（15 个，受控）
SUBCATS = {
    "general",      # 仅 L1 用
    "aviation",     # 航空航天：失速/湍流/风速/转速/结构健康
    "wearable",     # 可穿戴健康：脉搏/呼吸/步态/心率
    "tactile",      # 触觉与电子皮肤：压力/触觉/力
    "chemical",     # 化学与生物传感：离子/湿度/气体/液固
    "hmi",          # 人机交互：手势/触摸/智能表面
    "iot",          # IoT 与智能基础设施：交通/工业/楼宇
    "biomedical",   # 植入式与医疗诊断：体内传感/POCT
    "marine",       # 海洋与蓝色能源传感：水流/波浪/腐蚀
    "wind",         # 风能与环境监测：风速/风向/气象
    "motion",       # 运动与姿态识别：肢体/步态/动作捕捉
    "acoustic",     # 声学与振动传感：声波/噪声/机械振动
    "robotics",     # 机器人与灵巧操作：机械臂/夹爪/姿态
    "smarttextile", # 智能纺织与服装：织物传感/交互服饰
    "energyharv",   # 自驱动能量收集监测：设备状态/功耗感知
    "space",        # 空间与极端环境：空间碎片/辐射/极端温压
}

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
    # layer-subcategory 一致性：L1 必须 general；L2/L3 必须是传感场景（非 general）
    layer = qa.get("layer")
    subcat = qa.get("subcategory")
    if layer == "L1" and subcat != "general":
        e.append(f"L1 题的 subcategory 必须是 general，当前为 {subcat}")
    if layer in ("L2", "L3") and subcat == "general":
        e.append(f"{layer} 题的 subcategory 不能是 general，须为传感场景(aviation/wearable/tactile/chemical/hmi/iot)")
    if not qa.get("source_excerpt"):
        e.append("source_excerpt 必填（防污染与可追溯）")

    t = qa.get("type")
    sc = qa.get("scoring", {})
    mech = sc.get("mechanism")

    # 所有选择题（BK1-4/RP1-4）统一：options 是字母到文本的映射对象 + answer 是正确项字母
    if t in {"BK1", "BK2", "BK3", "BK4", "RP1", "RP2", "RP3", "RP4"}:
        opts = qa.get("options")
        if not isinstance(opts, dict) or not opts:
            e.append(t + " 需要 options（字母到选项文本的映射对象，如 {\"A\":\"...\",\"B\":\"...\",\"C\":\"...\",\"D\":\"...\"}）")
        else:
            if not all(k in opts for k in ("A", "B", "C", "D")):
                e.append(f"{t} options 应包含 A/B/C/D 四项")
        if "answer" not in qa:
            e.append(f"{t} 需要 answer（正确项字母，如 'B'）")
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
    elif t in {"DG1", "DG2"}:
        if "rubric" not in qa or "reference_answer" not in qa:
            e.append(f"{t} 需要 rubric + reference_answer")
        if not qa.get("multi_step_reasoning"):
            e.append(f"{t} 必填 multi_step_reasoning（分步答案）")
        if mech != "A+B":
            e.append(f"{t} scoring.mechanism 应为 'A+B'")
    elif t == "DG3":
        for k in ("required_parts", "scenario_checklist", "target_dimensions", "scoring_detail"):
            if k not in qa:
                e.append(f"DG3 需要 {k}")
        if mech != "A+B":
            e.append("DG3 scoring.mechanism 应为 'A+B'")
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
