#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble_benchmark.py —— 编排 Agent 第4步：组装正式 benchmark
条件：phase=calibration 且所有 papers/qualified/*/*/ 论文目录均有完成标记
（.complete，兼容 .completed）。.validated 仅表示抽样校验完成，不阻塞组装。
扫描 papers/qualified/*/*/qa/*.json，跳过同目录有同名 .rejected 的题，
把通过的题复制到 benchmark/question/{layer}/{question_id}/{category}/，完成后
phase 切到 ready。其中 L1 的 category 是知识点（qa JSON 的 subcategory）；其他
层级的 category 是题目分类（同样来自 subcategory）。
"""
import json
import re
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

ROOT = Path(__file__).resolve().parents[3]
QUALIFIED = ROOT / "papers/qualified"
BENCHMARK_Q = ROOT / "benchmark/question"
MASTER = ROOT / "state/master.json"
COMPLETION_MARKERS = (".complete", ".completed")


def path_component(value, fallback):
    """Return a stable, path-safe directory component from QA metadata."""
    text = str(value or "").strip()
    if not text:
        return fallback
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._") or fallback


def destination_directory(qa_file: Path) -> Path:
    """Build benchmark/question/L{n}/{question_id}/{category_or_knowledge_point}."""
    data = json.loads(qa_file.read_text(encoding="utf-8"))
    filename_parts = qa_file.stem.split("_")
    layer_value = data.get("layer") or (filename_parts[0] if filename_parts else None)
    layer = path_component(layer_value, "unknown")
    question_id = path_component(data.get("type") or (filename_parts[1] if len(filename_parts) > 1 else None), "unknown")

    # L1 subcategory is the knowledge point.  Other layers use subcategory as
    # their classification.  Accept knowledge_point as a future-compatible
    # fallback for L1 files that do not carry subcategory.
    category_value = data.get("subcategory")
    if layer == "L1" and not category_value:
        category_value = data.get("knowledge_point")
    category = path_component(category_value, "uncategorized")
    return BENCHMARK_Q / layer / question_id / category


def incomplete_paper_directories():
    """Return qualified paper directories without a reviewer completion marker."""
    paper_dirs = sorted(path for path in QUALIFIED.glob("*/*") if path.is_dir())
    return [
        paper_dir
        for paper_dir in paper_dirs
        if not any((paper_dir / marker).exists() for marker in COMPLETION_MARKERS)
    ]


def main():
    master = json.loads(MASTER.read_text(encoding="utf-8")) if MASTER.exists() else {}
    phase = master.get("phase")
    if phase != "calibration":
        log("orchestrator", f"[ASSEMBLE] 跳过：phase={phase}，需要 calibration")
        return

    incomplete_dirs = incomplete_paper_directories()
    if incomplete_dirs:
        log("orchestrator", f"[ASSEMBLE] 跳过：{len(incomplete_dirs)} 篇合格论文缺少 .complete/.completed 标记")
        for paper_dir in incomplete_dirs:
            log("orchestrator", f"[ASSEMBLE]   - {paper_dir.relative_to(QUALIFIED)}")
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

        dest_dir = destination_directory(qa_file)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / qa_file.name
        shutil.copy2(str(qa_file), str(dest))
        copied += 1
        layer = dest_dir.relative_to(BENCHMARK_Q).parts[0]
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
