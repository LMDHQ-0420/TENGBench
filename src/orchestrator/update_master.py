#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_master.py —— 编排 Agent 第3步：更新全局看板 state/master.json
统计各目录论文数（counts）、各题型 QA 已生成数 vs 配额（quota）、判断阶段（phase）。
所有 Agent 只读 master.json，仅编排 Agent 通过本脚本写入。
"""
import json
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from log import log

ROOT = Path(__file__).resolve().parents[2]            # code/
INBOX = ROOT / "papers/inbox"
QUALIFIED = ROOT / "papers/qualified"
REJECTED = ROOT / "papers/rejected"
CACHE = ROOT / "cache"
STATE = ROOT / "state"
MASTER = STATE / "master.json"

TARGETS = {"BK1": 225, "BK2": 225, "BK3": 225, "BK4": 225,   # L1 共 900
           "RP1": 1375, "RP2": 1375, "RP3": 1375, "RP4": 1375,  # L2 共 5500，4 个均分
           "DG1": 1200, "DG2": 1800, "DG3": 100}               # L3 共 3100


def n_dirs(p: Path) -> int:
    return len([x for x in p.iterdir() if x.is_dir()]) if p.exists() else 0


def count_papers_under_subcat(root: Path) -> int:
    """统计 qualified/rejected 下的论文数（二级 subcategory/*/{paper_id}）"""
    if not root.exists():
        return 0
    return sum(n_dirs(sub) for sub in root.iterdir() if sub.is_dir())


def main():
    STATE.mkdir(exist_ok=True)

    # inbox 顶层 PDF（用户随手丢，不分类）+ 兼容 inbox/{subcategory}/*.pdf
    inbox_n = len(list(INBOX.glob("*.pdf"))) if INBOX.exists() else 0
    inbox_n += sum(len(list(d.glob("*.pdf"))) for d in INBOX.iterdir() if d.is_dir()) if INBOX.exists() else 0
    # screening = cache/*/ 目录数（每篇论文一个文件夹：待办 PDF 或待收产物都在这里）
    screening = n_dirs(CACHE)

    counts = {
        "inbox": inbox_n,
        "screening": screening,
        "qualified": count_papers_under_subcat(QUALIFIED),
        "rejected": count_papers_under_subcat(REJECTED),
    }

    quota = {t: {"target": TARGETS[t], "done": 0} for t in TARGETS}
    if QUALIFIED.exists():
        cn = Counter()
        # 路径：qualified/{subcategory}/{paper_id}/qa/{layer}_{type}_{subcategory}_{seq}.json
        for qa in QUALIFIED.glob("*/*/qa/*.json"):
            parts = qa.stem.split("_")        # [layer, type, subcat, seq]
            t = parts[1] if len(parts) >= 2 else parts[0]   # type 固定第 2 段
            cn[t] += 1
        for t in quota:
            quota[t]["done"] = cn.get(t, 0)

    prev = json.loads(MASTER.read_text(encoding="utf-8")) if MASTER.exists() else {}
    phase = prev.get("phase", "screening")
    # 阶段切换：inbox 与 screening 都清空 -> calibration
    if counts["inbox"] == 0 and counts["screening"] == 0 and phase == "screening":
        phase = "calibration"

    master = {
        "phase": phase,
        "counts": counts,
        "quota": quota,
        "dg3_full": quota["DG3"]["done"] >= quota["DG3"]["target"],
        "agents": prev.get("agents", {}),
        "updated_at": None,                       # 由编排 Agent 调用时填时间戳（脚本保持确定性）
    }
    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    log("orchestrator", f"master.json 已更新：phase={phase}")
    log("orchestrator", f"  counts: {counts}")
    log("orchestrator", "  quota(done/target): " + ", ".join(
        f"{t}={quota[t]['done']}/{quota[t]['target']}" for t in TARGETS))


if __name__ == "__main__":
    main()
