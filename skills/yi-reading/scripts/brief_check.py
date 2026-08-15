#!/usr/bin/env python3
"""數一數簡讀有沒有超過 200 字。

為什麼要有這個腳本：**「簡明扼要」是一句沒有判據的話**。
寫的人每一句都覺得刪不得，於是二百字的東西寫成六百字，而且自己看不出來——
和這個倉庫裏其他幾條規矩一樣，靠自覺守不住的規矩就得有機器來數。

計數規則：**去掉空白與 Markdown 標記後的字符數**。
標點算在內（中文標點本來就佔位），連續的拉丁字母數字算一個詞、記一個字符
（否則一個 `verify_quote.py` 就吃掉十五個額度，不合理）。

用法：
    python3 brief_check.py "……簡讀正文……"
    cat draft.md | python3 brief_check.py
    python3 brief_check.py --limit 200 draft.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_LIMIT = 200

# Markdown 的裝飾字符不是內容，不佔額度
MARKUP = re.compile(r"[*_`#>|\-\[\]()\\]")
WHITESPACE = re.compile(r"\s+")
# 連續的拉丁字母／數字／點記為一個字符
LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:%+-]*")

# 一段連續的拉丁串（GPT-5.6、verify_quote.py）壓成這個佔位符，只記一個字。
# 用一個顯式常量而不是把控制字符直接寫進 sub()——寫進去在編輯器裏是看不見的，
# 讀代碼的人會以為那裏是空字符串，然後照着錯的理解去改。
PLACEHOLDER = "\u0001"


def count(text: str) -> int:
    t = MARKUP.sub("", text)
    t = LATIN_RUN.sub(PLACEHOLDER, t)  # 每段拉丁串記一個字
    t = WHITESPACE.sub("", t)
    return len(t)


def main() -> int:
    ap = argparse.ArgumentParser(description="簡讀字數檢查")
    ap.add_argument("text", nargs="?", help="簡讀正文，或一個文件路徑；省略則讀 stdin")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"上限，默認 {DEFAULT_LIMIT}")
    args = ap.parse_args()

    if args.text is None:
        text = sys.stdin.read()
    elif Path(args.text).is_file():
        text = Path(args.text).read_text(encoding="utf-8")
    else:
        text = args.text

    n = count(text)
    if n <= args.limit:
        print(f"✓ {n} 字，在 {args.limit} 字以內")
        return 0
    print(
        f"✗ {n} 字，超出 {n - args.limit} 字。簡讀就該是簡讀——"
        f"砍掉的通常是第二個比喻和那句「也就是說」。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
