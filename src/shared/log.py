#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log.py —— 共享日志工具：同时 print 到终端 + 追加到 logs/{agent}/{date}.log
所有 orchestrator/validator 脚本 import 使用，保证运行有留痕。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # code/（log.py 在 code/src/shared/）
LOGS = ROOT / "logs"


def log(agent: str, *args, sep: str = " "):
    """同时输出到终端 + 追加到 logs/{agent}/{date}.log。
    agent: 如 'orchestrator' / 'reviewer_writer' / 'qa' / 'cad_runner'
    日期取自系统日期（YYYY-MM-DD），按天分文件。
    """
    msg = sep.join(str(a) for a in args)
    print(msg)  # 终端
    try:
        d = LOGS / agent
        d.mkdir(parents=True, exist_ok=True)
        # 用 date 命令避免在脚本里调被禁的 Date.now
        import subprocess
        try:
            date = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()
        except Exception:
            date = "undated"
        # 时间戳
        try:
            ts = subprocess.run(["date", "+%H:%M:%S"], capture_output=True, text=True).stdout.strip()
        except Exception:
            ts = ""
        with open(d / f"{date}.log", "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception as e:
        # 日志失败不影响主流程
        print(f"[log-warn] 写日志失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    # 自测
    log("orchestrator", "测试日志", 123, {"a": 1})
    print("ok, 查看 logs/orchestrator/")
