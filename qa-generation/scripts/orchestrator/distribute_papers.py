#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distribute_papers.py —— 编排 Agent 第1步：论文入库分发
扫描 papers/inbox/ 的新 PDF，登记到 state/papers/{stem}.json（status=inbox），
为每篇论文创建 cache/{stem}/ 文件夹并把 PDF 放进去，等待审核出题 Agent 处理。
"""
import json
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

ROOT = Path(__file__).resolve().parents[3]
INBOX = ROOT / "papers/inbox"
CACHE = ROOT / "cache"
STATE_PAPERS = ROOT / "state/papers"


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE_PAPERS.mkdir(parents=True, exist_ok=True)

    inbox_pdfs = sorted(set(list(INBOX.glob("*.pdf")) + list(INBOX.glob("*/*.pdf"))))
    log("orchestrator", f"[DISTRIBUTE] 扫描 inbox，发现 {len(inbox_pdfs)} 个 PDF")

    distributed, skipped, already = 0, 0, 0
    for pdf in inbox_pdfs:
        stem = pdf.stem
        rec = STATE_PAPERS / f"{stem}.json"
        if not rec.exists():
            rec.write_text(json.dumps({
                "paper_id": None,
                "status": "inbox",
                "source_file": pdf.name,
                "original_stem": stem,
                "location": str(CACHE / stem),
                "timestamps": {"inbox": None}
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            log("orchestrator", f"[DISTRIBUTE] 新建状态记录：state/papers/{stem}.json")

        paper_dir = CACHE / stem
        paper_dir.mkdir(parents=True, exist_ok=True)
        dest = paper_dir / pdf.name
        if not dest.exists():
            shutil.move(str(pdf), str(dest))
            distributed += 1
            log("orchestrator", f"[DISTRIBUTE] 移动：{pdf.name} -> cache/{stem}/")
        else:
            already += 1
            log("orchestrator", f"[DISTRIBUTE] 已存在，跳过：cache/{stem}/{pdf.name}")

    log("orchestrator", f"[DISTRIBUTE] 完成：新分发 {distributed} 篇，已存在跳过 {already} 篇，inbox 当前 {len(inbox_pdfs) - distributed} 篇残留")
    log("orchestrator", f"[DISTRIBUTE] cache 当前目录数：{len(list(CACHE.iterdir()))}")


if __name__ == "__main__":
    main()
