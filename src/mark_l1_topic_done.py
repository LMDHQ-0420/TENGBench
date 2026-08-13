#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mark_l1_topic_done.py —— L1 考点 done 计数标记
reviewer-writer 出完一道 L1 题后调用：把指定考点的 done+1。
用法：
    python3 mark_l1_topic_done.py BK1-03            # 考点 BK1-03 的 done+1
    python3 mark_l1_topic_done.py BK1-03 2          # 考点 BK1-03 的 done+2（一次出多道）
    python3 mark_l1_topic_done.py --list            # 列出所有考点及 done/target
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]            # code/
L1_TOPICS = ROOT / "state" / "l1_topics.json"


def load():
    return json.loads(L1_TOPICS.read_text(encoding="utf-8"))


def save(d):
    L1_TOPICS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def list_topics():
    d = load()
    t = d.get("target_per_topic", 30)
    print(f"target/考点 = {t}；各考点 done：")
    total = 0
    for bk, topics in d["topics"].items():
        for tp in topics:
            print(f"  {tp['id']:8s} {tp['name']:40s} {tp['done']}/{t}")
            total += tp["done"]
    print(f"\nL1 总进度：{total} / {sum(len(v) for v in d['topics'].values()) * t}")


def mark(topic_id, n=1):
    d = load()
    for bk, topics in d["topics"].items():
        for tp in topics:
            if tp["id"] == topic_id:
                tp["done"] = min(tp["done"] + n, d.get("target_per_topic", 30))
                save(d)
                print(f"[OK] {topic_id} ({tp['name']}) done={tp['done']}")
                return
    print(f"[ERR] 找不到考点 {topic_id}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        list_topics()
        return
    tid = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    mark(tid, n)


if __name__ == "__main__":
    main()
