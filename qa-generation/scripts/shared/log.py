#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log.py —— 共享日志工具：同时 print 到终端 + 追加到 logs/{YYYY-MM-DD-AM|PM}.log
所有脚本 import 使用。每 12 小时一个文件（AM=00-11, PM=12-23）。
格式：[YYYY-MM-DD HH:MM:SS] [agent] message
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "logs"


def log(agent: str, *args, sep: str = " "):
    """同时输出到终端 + 追加到 logs/{date}-{AM|PM}.log。
    agent: 脚本所属模块名，如 'orchestrator' / 'validator' / 'reviewer'
    """
    msg = sep.join(str(a) for a in args)
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    period = "AM" if now.hour < 12 else "PM"
    date_str = now.strftime("%Y-%m-%d")
    filename = f"{date_str}-{period}.log"
    line = f"[{ts}] [{agent}] {msg}"

    print(line)
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        with open(LOGS / filename, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[log-warn] 写日志失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    log("orchestrator", "测试日志 AM/PM 分割")
    print(f"查看 logs/ 目录")
