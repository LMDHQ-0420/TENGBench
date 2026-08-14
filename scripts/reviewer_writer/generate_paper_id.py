#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_paper_id.py —— reviewer-writer 第1步后调用：从 index.json 生成规范 paper_id
格式：{subcategory}_{venue_short}{year}_{first_author_lastname}_{word1}_{word2}_{word3}
示例：aviation_NatComm2023_Xu_Triboelectric_Nanogenerator_Stall

用法：
    python3 scripts/reviewer_writer/generate_paper_id.py <cache_paper_dir>
    e.g.  python3 scripts/reviewer_writer/generate_paper_id.py cache/some_stem/

逻辑：
1. 读取 <cache_paper_dir>/index.json
2. 从 title/venue/date/authors/subcategory 字段拼接 paper_id
3. 把 paper_id 写回 index.json
4. 把该目录下唯一的 PDF 重命名为 {paper_id}.pdf
5. 更新 index.json 里的 original_filename 字段
所有操作写日志到 logs/{date}-{AM|PM}.log
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
from log import log

STOPWORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for",
             "and", "or", "but", "with", "by", "from", "is", "are",
             "using", "via", "based", "toward", "towards"}

VENUE_ABBREV = {
    "nature communications": "NatComm",
    "nature nanotechnology": "NatNano",
    "nature energy": "NatEnergy",
    "nature materials": "NatMater",
    "acs nano": "ACSNano",
    "acs energy letters": "ACSEnergyLett",
    "advanced materials": "AdvMater",
    "advanced functional materials": "AdvFunctMater",
    "advanced energy materials": "AdvEnergyMater",
    "nano energy": "NanoEnergy",
    "nano letters": "NanoLett",
    "small": "Small",
    "applied physics letters": "APL",
    "journal of materials chemistry a": "JMaterChemA",
    "energy & environmental science": "EES",
    "angewandte chemie": "AngChem",
    "science advances": "SciAdv",
    "npj flexible electronics": "NPJFlex",
}


def clean_word(w: str) -> str:
    """去除非字母数字字符，首字母大写。"""
    w = re.sub(r"[^a-zA-Z0-9]", "", w)
    return w.capitalize() if w else ""


def tokenize(title: str) -> list:
    """把标题拆成 token 列表，连字符单词拆开（Self-Powered -> [Self, Powered]）。"""
    tokens = []
    for w in title.split():
        parts = w.split("-")
        for p in parts:
            cleaned = clean_word(p)
            if cleaned:
                tokens.append(cleaned)
    return tokens


def extract_title_words(title: str, n: int = 3) -> list:
    """从标题提取前 n 个有意义的单词（跳过冠词/介词，连字符单词拆开）。"""
    tokens = tokenize(title)
    result = []
    for t in tokens:
        if t.lower() in STOPWORDS:
            continue
        result.append(t)
        if len(result) == n:
            break
    # 如果跳过停用词后不足 n 个，从头直接取（不跳过）
    if len(result) < n:
        result = tokenize(title)[:n]
    return result


def get_venue_short(venue: str) -> str:
    """期刊全称映射到缩写，未知期刊取前两个有意义单词拼接。"""
    key = venue.strip().lower()
    if key in VENUE_ABBREV:
        return VENUE_ABBREV[key]
    # 未收录：取期刊名前两个单词首字母大写拼接
    parts = [clean_word(w) for w in venue.split() if clean_word(w)][:2]
    return "".join(parts) if parts else "Unknown"


def get_first_author_lastname(authors: list) -> str:
    """取第一作者姓氏（last name = 最后一个空格分隔的词）。"""
    if not authors:
        return "Unknown"
    first = authors[0].strip()
    parts = first.split()
    lastname = clean_word(parts[-1]) if parts else "Unknown"
    return lastname if lastname else "Unknown"


def get_year(date: str) -> str:
    """从 YYYY-MM 或 YYYY 格式提取年份。"""
    m = re.search(r"\d{4}", date or "")
    return m.group(0) if m else "0000"


def build_paper_id(idx: dict) -> str:
    subcategory = idx.get("subcategory", "unknown").strip().lower()
    venue_short = get_venue_short(idx.get("venue", ""))
    year = get_year(idx.get("date", ""))
    lastname = get_first_author_lastname(idx.get("authors", []))
    title_words = extract_title_words(idx.get("title", ""), n=3)

    parts = [subcategory, f"{venue_short}{year}", lastname] + title_words
    paper_id = "_".join(p for p in parts if p)
    # 替换空格为下划线，去除非法字符
    paper_id = re.sub(r"[^\w]", "_", paper_id)
    paper_id = re.sub(r"_+", "_", paper_id).strip("_")
    return paper_id


def main():
    if len(sys.argv) < 2:
        print("用法: python3 generate_paper_id.py <cache_paper_dir>")
        sys.exit(2)

    paper_dir = Path(sys.argv[1]).resolve()
    if not paper_dir.exists():
        log("reviewer", f"[PAPER_ID] 错误：目录不存在 {paper_dir}")
        sys.exit(1)

    index_f = paper_dir / "index.json"
    if not index_f.exists():
        log("reviewer", f"[PAPER_ID] 错误：index.json 不存在于 {paper_dir}")
        sys.exit(1)

    idx = json.loads(index_f.read_text(encoding="utf-8"))

    # 校验必要字段
    missing = [k for k in ("title", "venue", "date", "authors", "subcategory") if not idx.get(k)]
    if missing:
        log("reviewer", f"[PAPER_ID] 错误：index.json 缺少字段 {missing}，无法生成 paper_id")
        sys.exit(1)

    paper_id = build_paper_id(idx)
    log("reviewer", f"[PAPER_ID] 生成 paper_id：{paper_id}")
    log("reviewer", f"[PAPER_ID]   subcategory={idx.get('subcategory')} venue={idx.get('venue')} "
                    f"date={idx.get('date')} authors={idx.get('authors', [])[:1]} title={idx.get('title', '')[:60]}")

    # 写回 index.json
    old_id = idx.get("paper_id")
    idx["paper_id"] = paper_id
    index_f.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    if old_id and old_id != paper_id:
        log("reviewer", f"[PAPER_ID] paper_id 更新：{old_id} -> {paper_id}")

    # 重命名 PDF
    pdfs = list(paper_dir.glob("*.pdf"))
    if not pdfs:
        log("reviewer", f"[PAPER_ID] 警告：{paper_dir} 下无 PDF 文件，跳过重命名")
    else:
        for pdf in pdfs:
            new_name = f"{paper_id}.pdf"
            new_path = paper_dir / new_name
            if pdf.name == new_name:
                log("reviewer", f"[PAPER_ID] PDF 已是正确文件名，跳过：{pdf.name}")
            else:
                pdf.rename(new_path)
                log("reviewer", f"[PAPER_ID] PDF 重命名：{pdf.name} -> {new_name}")
            # 更新 index.json 的 original_filename
            idx["original_filename"] = new_name
            index_f.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    log("reviewer", f"[PAPER_ID] 完成：{paper_dir.name} -> {paper_id}")
    print(paper_id)  # 供调用方捕获


if __name__ == "__main__":
    main()
