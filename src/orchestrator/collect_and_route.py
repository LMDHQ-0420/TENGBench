#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_and_route.py —— 编排 Agent 第2步：按分数收取并分拣
扫描 cache/{stem}/（每篇论文一个文件夹，含 PDF + index/score/qa），读 score.json.total，按阈值移动：
  ≥3.5  -> papers/qualified/{subcategory}/{paper_id}/   (status=qualified)
  <3.0  -> papers/rejected/{subcategory}/{paper_id}/    (status=rejected)
  3.0–3.5 -> papers/qualified/{subcategory}/{paper_id}/ (status=needs_human_review，不自动决定)
整个 cache/{stem}/ 目录搬到 qualified/rejected，原 PDF 重命名为 paper.pdf。
同时把 state/papers 记录从 original_stem 迁移到最终 paper_id，填 score / qa_count。
"""
import json
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from log import log

ROOT = Path(__file__).resolve().parents[2]            # code/
CACHE = ROOT / "cache"
QUALIFIED = ROOT / "papers/qualified"
REJECTED = ROOT / "papers/rejected"
STATE_PAPERS = ROOT / "state/papers"
INDEX_ALL = ROOT / "papers/index/all_papers.json"     # 全局论文索引（每收一篇即 upsert）


def count_qa(dest: Path) -> dict:
    qa_dir = dest / "qa"
    if not qa_dir.exists():
        return {}
    counts = {}
    for f in qa_dir.glob("*.json"):
        # 文件名 {layer}_{type}_{subcategory}_{seq}，type 在第 2 段
        parts = f.stem.split("_")
        t = parts[1] if len(parts) >= 2 else parts[0]
        counts[t] = counts.get(t, 0) + 1
    return counts


def update_all_papers_index(paper_id, status, subcat, idx, score, dest):
    """每收一篇论文即 upsert 到 papers/index/all_papers.json（全局索引）"""
    INDEX_ALL.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if INDEX_ALL.exists():
        try:
            data = json.loads(INDEX_ALL.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    papers = data.get("papers", {})
    papers[paper_id] = {
        "paper_id": paper_id,
        "status": status,
        "subcategory": subcat,
        "title": idx.get("title", ""),
        "authors": idx.get("authors", []),
        "first_affil": idx.get("first_affil", ""),
        "venue": idx.get("venue", ""),
        "doi": idx.get("doi", ""),
        "date": idx.get("date", ""),
        "score_total": score.get("total", 0),
        "location": str(dest),
    }
    data["papers"] = papers
    data["count"] = len(papers)
    INDEX_ALL.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if not CACHE.exists():
        log("orchestrator", "cache 为空，无待收取论文")
        return
    QUALIFIED.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)

    routed = {"qualified": 0, "rejected": 0, "needs_human_review": 0}
    for d in sorted(CACHE.iterdir()):
        if not d.is_dir():
            continue
        # 完整性检查：必须 index + score + .complete 标记都齐全才算处理完成，否则跳过（writer 可能还在写）
        score_f, index_f = d / "score.json", d / "index.json"
        complete_f = d / ".complete"
        if not score_f.exists() or not index_f.exists():
            log("orchestrator", f"[WARN] {d.name} 缺 score.json/index.json，跳过（留待 reviewer 补全）")
            continue
        if not complete_f.exists():
            log("orchestrator", f"[WARN] {d.name} 无 .complete 标记（writer 还在出题），跳过待完成")
            continue

        score = json.loads(score_f.read_text(encoding="utf-8"))
        idx = json.loads(index_f.read_text(encoding="utf-8"))
        total = score.get("total", 0)
        paper_id = idx.get("paper_id") or d.name
        subcat = idx.get("subcategory", "uncategorized")  # 二级目录按 subcategory 分

        if total >= 3.5:
            dest, status = QUALIFIED / subcat / paper_id, "qualified"
        elif total < 3.0:
            dest, status = REJECTED / subcat / paper_id, "rejected"
        else:
            dest, status = QUALIFIED / subcat / paper_id, "needs_human_review"

        # 整个 cache/{stem}/ 目录搬到 dest/，PDF 重命名为 paper.pdf
        dest.mkdir(parents=True, exist_ok=True)
        for f in list(d.iterdir()):
            shutil.move(str(f), str(dest / f.name))
        d.rmdir()
        orig = idx.get("original_filename", "")
        if orig and (dest / orig).exists():
            shutil.move(str(dest / orig), str(dest / "paper.pdf"))

        # 迁移 state 记录：original_stem -> paper_id
        orig_stem = idx.get("original_filename", "").rsplit(".", 1)[0] or paper_id
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
            "qa_count": count_qa(dest),
        })
        (STATE_PAPERS / f"{paper_id}.json").write_text(
            json.dumps(rec_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # upsert 全局论文索引 all_papers.json（每收一篇即更新）
        update_all_papers_index(paper_id, status, subcat, idx, score, dest)

        routed[status] += 1
        log("orchestrator", f"[{status}] {paper_id} (total={total}) -> {dest.parent.name}/{dest.name}/")

    log("orchestrator", f"分拣汇总：{routed}")


if __name__ == "__main__":
    main()
