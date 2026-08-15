#!/usr/bin/env python3
"""数一数简读有没有超过 200 字。

为什么要有这个脚本：**「简明扼要」是一句没有判据的话**。
写的人每一句都觉得删不得，于是二百字的东西写成六百字，而且自己看不出来——
和这个仓库里其他几条规矩一样，靠自觉守不住的规矩就得有机器来数。

计数规则：**去掉空白与 Markdown 标记后的字符数**。
标点算在内（中文标点本来就占位），连续的拉丁字母数字算一个词、记一个字符
（否则一个 `verify_quote.py` 就吃掉十五个额度，不合理）。

用法：
    python3 brief_check.py "……简读正文……"
    cat draft.md | python3 brief_check.py
    python3 brief_check.py --limit 200 draft.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_LIMIT = 200

# Markdown 的装饰字符不是内容，不占额度
MARKUP = re.compile(r"[*_`#>|\-\[\]()\\]")
WHITESPACE = re.compile(r"\s+")
# 连续的拉丁字母／数字／点记为一个字符
LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:%+-]*")

# 一段连续的拉丁串（GPT-5.6、verify_quote.py）压成这个占位符，只记一个字。
# 用一个显式常量而不是把控制字符直接写进 sub()——写进去在编辑器里是看不见的，
# 读代码的人会以为那里是空字符串，然后照着错的理解去改。
PLACEHOLDER = "\u0001"


def count(text: str) -> int:
    t = MARKUP.sub("", text)
    t = LATIN_RUN.sub(PLACEHOLDER, t)  # 每段拉丁串记一个字
    t = WHITESPACE.sub("", t)
    return len(t)


def main() -> int:
    ap = argparse.ArgumentParser(description="简读字数检查")
    ap.add_argument("text", nargs="?", help="简读正文，或一个文件路径；省略则读 stdin")
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
        print(f"✓ {n} 字，在 {args.limit} 字以内")
        return 0
    print(
        f"✗ {n} 字，超出 {n - args.limit} 字。简读就该是简读——"
        f"砍掉的通常是第二個比喻和那句「也就是說」。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
