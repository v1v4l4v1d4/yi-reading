#!/usr/bin/env python3
"""核對一段「引文」是否真的出自庫中原文。

存在的理由很直接：一個語言模型寫出一段像蘇軾的話，比引對一段真的蘇軾容易得多，
而讀者無從分辨。所以「不得以自撰文字冒充原文」這條不能靠自覺，要有機器判據。

用法：
    python3 verify_quote.py --dongpo 3 "因世之“屯”，而務往以求功"
    echo "..." | python3 verify_quote.py --jing 3

比對前只做一件事：去掉空白。標點、繁簡、引號樣式一律不歸一化——
歸一化就等於允許改字，而這裏要保的正是逐字。退出碼 0 為通過，1 為不通過。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

WS = str.maketrans("", "", " \t\r\n　")


def normalise(s: str) -> str:
    return s.translate(WS)


def dongpo_text(no: int) -> str:
    path = DATA_DIR / "commentary" / "dongpo" / f"{no:02d}.json"
    if not path.exists():
        raise LookupError(f"第 {no} 卦無《東坡易傳》原文（維基文庫只轉錄到第 35 卦）")
    return json.loads(path.read_text(encoding="utf-8"))["text"]


def jing_text(no: int) -> str:
    with open(DATA_DIR / "hexagrams.json", encoding="utf-8") as f:
        h = next(x for x in json.load(f) if x["no"] == no)
    parts = [h["gua_ci"], h["tuan"], h["da_xiang"]]
    for y in h["yao"]:
        parts += [y["text"], y["xiao_xiang"]]
    parts += list((h.get("extra") or {}).values())
    return "\n".join(parts)


def verify(quote: str, source: str) -> bool:
    return normalise(quote) in normalise(source)


def main() -> int:
    ap = argparse.ArgumentParser(description="核對引文是否為原文的逐字子串")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dongpo", type=int, metavar="卦序", help="對照《東坡易傳》")
    g.add_argument("--jing", type=int, metavar="卦序", help="對照經傳（卦爻辭、彖、象）")
    ap.add_argument("quote", nargs="?", help="待核引文；省略則從 stdin 讀")
    args = ap.parse_args()

    quote = args.quote if args.quote is not None else sys.stdin.read()
    quote = quote.strip()
    if not quote:
        print("沒有給出引文", file=sys.stderr)
        return 2

    no = args.dongpo if args.dongpo else args.jing
    try:
        source = dongpo_text(no) if args.dongpo else jing_text(no)
    except LookupError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if verify(quote, source):
        print("✓ 是原文")
        return 0
    print("✗ 不是原文——庫中找不到這段字。不得作為原文引用。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
