#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_and_route.py —— 编排 Agent 第2步：按分数收取并分拣
扫描 cache/{stem}/（每篇论文一个文件夹，含 PDF + index/score/qa），读 score.json.total，按阈值移动：
  >=3.5 -> papers/qualified/{subcategory}/{paper_id}/   (status=qualified)
  <3.5  -> papers/rejected/{subcategory}/{paper_id}/    (status=rejected)
整个 cache/{stem}/ 目录搬到 qualified/rejected，原 PDF 重命名为 paper.pdf。
同时把 state/papers 记录从 original_stem 迁移到最终 paper_id，填 score / qa_count。
"""
import json
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache"
QUALIFIED = ROOT / "papers/qualified"
REJECTED = ROOT / "papers/rejected"
STATE_PAPERS = ROOT / "state/papers"


def count_qa(dest: Path) -> dict:
    qa_dir = dest / "qa"
    if not qa_dir.exists():
        return {}
    counts = {}
    for f in qa_dir.glob("*.json"):
        # 文件名 {layer}_{type}_{subcategory}_{paper_id}_{题号}，type 固定第 2 段
        parts = f.stem.split("_")
        t = parts[1] if len(parts) >= 2 else parts[0]
        counts[t] = counts.get(t, 0) + 1
    return counts


def main():
    if not CACHE.exists():
        log("orchestrator", "[COLLECT] cache 目录不存在，无待收取论文")
        return

    QUALIFIED.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)

    dirs = [d for d in sorted(CACHE.iterdir()) if d.is_dir()]
    log("orchestrator", f"[COLLECT] 扫描 cache，发现 {len(dirs)} 个目录")

    routed = {"qualified": 0, "rejected": 0, "skipped": 0}
    for d in dirs:
        score_f = d / "score.json"
        index_f = d / "index.json"
        complete_f = d / ".complete"

        if not score_f.exists() or not index_f.exists():
            routed["skipped"] += 1
            log("orchestrator", f"[COLLECT] 跳过 {d.name}：缺少 score.json 或 index.json（reviewer 尚未完成）")
            continue
        if not complete_f.exists():
            routed["skipped"] += 1
            log("orchestrator", f"[COLLECT] 跳过 {d.name}：无 .complete 标记（reviewer 仍在出题）")
            continue

        score = json.loads(score_f.read_text(encoding="utf-8"))
        idx = json.loads(index_f.read_text(encoding="utf-8"))
        total = score.get("total", 0)
        paper_id = idx.get("paper_id") or d.name
        subcat = idx.get("subcategory", "uncategorized")
        qa_counts = count_qa(d)
        qa_total = sum(qa_counts.values())

        if total >= 3.5:
            dest, status = QUALIFIED / subcat / paper_id, "qualified"
        else:
            dest, status = REJECTED / subcat / paper_id, "rejected"

        dest.mkdir(parents=True, exist_ok=True)
        for f in list(d.iterdir()):
            shutil.move(str(f), str(dest / f.name))
        d.rmdir()

        # 迁移 state 记录：original_stem -> paper_id
        orig_stem = d.name  # distribute 时用原始目录名（stem）登记
        old_rec = STATE_PAPERS / f"{orig_stem}.json"
        rec_data = {}
        if old_rec.exists():
            rec_data = json.loads(old_rec.read_text(encoding="utf-8"))
            old_rec.unlink()
        rec_data.update({
            "paper_id": paper_id,
            "status": status,
            "location": str(dest),
            "index": idx,
            "score": score,
            "qa_count": qa_counts,
        })
        (STATE_PAPERS / f"{paper_id}.json").write_text(
            json.dumps(rec_data, ensure_ascii=False, indent=2), encoding="utf-8")

        routed[status] += 1
        qa_detail = " | ".join(f"{k}={v}" for k, v in sorted(qa_counts.items()))
        log("orchestrator", f"[COLLECT] [{status.upper()}] {paper_id} | score={total:.2f} | subcat={subcat} | qa={qa_total}题 ({qa_detail}) -> {dest.relative_to(ROOT)}")

    log("orchestrator", f"[COLLECT] 完成：qualified={routed['qualified']} rejected={routed['rejected']} skipped={routed['skipped']}")


if __name__ == "__main__":
    main()
