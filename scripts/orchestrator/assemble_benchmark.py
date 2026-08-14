#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble_benchmark.py —— 编排 Agent 第4步：组装正式 benchmark
条件：phase=calibration 且 papers/qualified/.validated 存在。
扫描 papers/qualified/*/*/qa/*.json，跳过同目录有同名 .rejected 的题，
把通过的题复制到 benchmark/questions/{layer}/，完成后 phase 切到 ready。
"""
import json
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

ROOT = Path(__file__).resolve().parents[2]
QUALIFIED = ROOT / "papers/qualified"
BENCHMARK_Q = ROOT / "benchmark/questions"
MASTER = ROOT / "state/master.json"


def main():
    validated_marker = QUALIFIED / ".validated"
    if not validated_marker.exists():
        log("orchestrator", "[ASSEMBLE] 跳过：papers/qualified/.validated 不存在（qa-validator 尚未完成）")
        return

    master = json.loads(MASTER.read_text(encoding="utf-8")) if MASTER.exists() else {}
    phase = master.get("phase")
    if phase != "calibration":
        log("orchestrator", f"[ASSEMBLE] 跳过：phase={phase}，需要 calibration")
        return

    log("orchestrator", "[ASSEMBLE] 开始组装 benchmark...")
    BENCHMARK_Q.mkdir(parents=True, exist_ok=True)

    all_qa = sorted(QUALIFIED.glob("*/*/qa/*.json"))
    log("orchestrator", f"[ASSEMBLE] 扫描到 {len(all_qa)} 道题")

    total, copied, skipped = 0, 0, 0
    skipped_list = []
    layer_counts = {}

    for qa_file in all_qa:
        total += 1
        rejected_marker = qa_file.with_suffix(".rejected")
        if rejected_marker.exists():
            skipped += 1
            skipped_list.append(qa_file.name)
            continue

        parts = qa_file.stem.split("_")
        layer = parts[0] if parts else "unknown"
        dest_dir = BENCHMARK_Q / layer
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / qa_file.name
        shutil.copy2(str(qa_file), str(dest))
        copied += 1
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    log("orchestrator", f"[ASSEMBLE] 复制完成：总计 {total} 题，复制 {copied} 题，跳过 {skipped} 题")
    for layer, cnt in sorted(layer_counts.items()):
        log("orchestrator", f"[ASSEMBLE]   {layer}: {cnt} 题")
    if skipped_list:
        log("orchestrator", f"[ASSEMBLE] 被跳过的题（.rejected）：")
        for name in skipped_list:
            log("orchestrator", f"[ASSEMBLE]   - {name}")

    master["phase"] = "ready"
    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    log("orchestrator", "[ASSEMBLE] phase -> ready，benchmark 已就绪")


if __name__ == "__main__":
    main()
