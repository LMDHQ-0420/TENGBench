#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_master.py —— 编排 Agent 第3步：更新全局看板 state/master.json
判断并更新流水线阶段（phase）。
所有 Agent 只读 master.json，仅编排 Agent 通过本脚本写入。
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

ROOT = Path(__file__).resolve().parents[3]
INBOX = ROOT / "papers/inbox"
CACHE = ROOT / "cache"
STATE = ROOT / "state"
MASTER = STATE / "master.json"


def n_dirs(p: Path) -> int:
    return len([x for x in p.iterdir() if x.is_dir()]) if p.exists() else 0


def main():
    STATE.mkdir(exist_ok=True)

    inbox_n = len(list(INBOX.glob("*.pdf"))) if INBOX.exists() else 0
    inbox_n += sum(len(list(d.glob("*.pdf"))) for d in INBOX.iterdir() if d.is_dir()) if INBOX.exists() else 0
    screening = n_dirs(CACHE)

    prev = json.loads(MASTER.read_text(encoding="utf-8")) if MASTER.exists() else {}
    phase_before = prev.get("phase", "screening")
    phase = phase_before

    if inbox_n == 0 and screening == 0 and phase == "screening":
        phase = "calibration"
        log("orchestrator", f"[UPDATE] phase 切换：screening -> calibration（inbox={inbox_n} cache={screening}）")
    else:
        log("orchestrator", f"[UPDATE] phase 保持：{phase}（inbox={inbox_n} cache={screening}）")

    master = {"phase": phase}
    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    log("orchestrator", f"[UPDATE] master.json 已写入：phase={phase}")


if __name__ == "__main__":
    main()
