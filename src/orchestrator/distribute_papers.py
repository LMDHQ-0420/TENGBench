#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distribute_papers.py —— 编排 Agent 第1步：论文入库分发
扫描 papers/inbox/ 的新 PDF，登记到 state/papers/{stem}.json（status=inbox），
为每篇论文创建 cache/{stem}/ 文件夹并把 PDF 放进去，等待审核出题 Agent 处理。
注意：此处 paper_id 尚未最终确定（用 PDF 文件名 stem 作临时标识），
最终 paper_id 由审核出题 Agent 读完论文后重命名（见 collect_and_route 的迁移逻辑）。
"""
import json
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from log import log

ROOT = Path(__file__).resolve().parents[2]            # code/
INBOX = ROOT / "papers/inbox"
CACHE = ROOT / "cache"
STATE_PAPERS = ROOT / "state/papers"


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE_PAPERS.mkdir(parents=True, exist_ok=True)

    distributed = 0
    # 用户下载时随手丢 PDF 到 inbox/ 顶层（不分类）；subcategory 由 reviewer-writer
    # 读完论文后在 index.json 判定，collect 再按 subcategory 归到 qualified/{subcategory}/。
    # 兼容：也扫 inbox/{subcategory}/*.pdf（若用户已分类则保留，subcategory 仍由 reviewer 复核）
    inbox_pdfs = sorted(set(list(INBOX.glob("*.pdf")) + list(INBOX.glob("*/*.pdf"))))
    for pdf in inbox_pdfs:
        stem = pdf.stem
        rec = STATE_PAPERS / f"{stem}.json"
        if not rec.exists():
            rec.write_text(json.dumps({
                "paper_id": None,                  # 待 reviewer-writer 最终命名
                "status": "inbox",
                "source_file": pdf.name,
                "original_stem": stem,
                "location": str(CACHE / stem),
                "timestamps": {"inbox": None}
            }, ensure_ascii=False, indent=2), encoding="utf-8")

        # 为每篇论文创建 cache/{stem}/ 文件夹，PDF 放进去（此后 reviewer 不移动 PDF）
        paper_dir = CACHE / stem
        paper_dir.mkdir(parents=True, exist_ok=True)
        dest = paper_dir / pdf.name
        if not dest.exists():
            shutil.move(str(pdf), str(dest))
            distributed += 1
            log("orchestrator", f"[DISTRIBUTE] {pdf.name} -> cache/{stem}/")
        else:
            log("orchestrator", f"[SKIP] {pdf.name} 已在 cache/{stem}/")

    n_rev = len([x for x in CACHE.iterdir() if x.is_dir()])
    log("orchestrator", f"本轮分发 {distributed} 篇；cache 现有 {n_rev} 篇待处理")


if __name__ == "__main__":
    main()
