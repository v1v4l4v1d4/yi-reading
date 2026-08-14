#!/usr/bin/env python3
"""核對一段「引文」是否真的出自庫中原文。

存在的理由很直接：一個語言模型寫出一段像蘇軾的話，比引對一段真的蘇軾容易得多，
而讀者無從分辨。所以「不得以自撰文字冒充原文」這條不能靠自覺，要有機器判據。

用法：
    python3 verify_quote.py --dongpo 3 "困者坐而見制"
    python3 verify_quote.py --yichuan 47 "行吾義而已"
    python3 verify_quote.py --benyi 47 "當務晦黙"
    python3 verify_quote.py --any 47 "剛揜也"          # 三家＋經傳一起找，並報出處
    echo "..." | python3 verify_quote.py --jing 3

比對前只做一件事：去掉空白。標點、繁簡、引號樣式一律不歸一化——
歸一化就等於允許改字，而這裏要保的正是逐字。退出碼 0 為通過，1 為不通過。

四庫本無標點，所以引它時取短句（四到十來個字）最穩；長段落用自己的話轉述，
但**轉述就不要掛在注家名下**——要麼真引，要麼別署名。
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


WORKS = {"dongpo": "東坡易傳", "yichuan": "伊川易傳", "benyi": "周易本義"}


def work_entry(slug: str, no: int) -> dict:
    path = DATA_DIR / "commentary" / slug / f"{no:02d}.json"
    if not path.exists():
        raise LookupError(f"第 {no} 卦沒有《{WORKS[slug]}》的數據——請重跑 fetch_commentary.py")
    return json.loads(path.read_text(encoding="utf-8"))


def dongpo_text(no: int) -> str:
    return work_entry("dongpo", no)["text"]


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
    g.add_argument("--dongpo", type=int, metavar="卦序", help="對照蘇軾《東坡易傳》")
    g.add_argument("--yichuan", type=int, metavar="卦序", help="對照程頤《伊川易傳》")
    g.add_argument("--benyi", type=int, metavar="卦序", help="對照朱熹《周易本義》")
    g.add_argument("--jing", type=int, metavar="卦序", help="對照經傳（卦爻辭、彖、象）")
    g.add_argument("--any", type=int, metavar="卦序", help="三家＋經傳一起找，命中則報出處")
    ap.add_argument("quote", nargs="?", help="待核引文；省略則從 stdin 讀")
    args = ap.parse_args()

    quote = (args.quote if args.quote is not None else sys.stdin.read()).strip()
    if not quote:
        print("沒有給出引文", file=sys.stderr)
        return 2

    if args.any:
        hits = []
        for slug in WORKS:
            try:
                e = work_entry(slug, args.any)
            except LookupError:
                continue
            if verify(quote, e["text"]):
                hits.append(f"{e['author']}{e['citation']}")
        if verify(quote, jing_text(args.any)):
            hits.append("經傳（卦爻辭／彖／象）")
        if hits:
            print("✓ 是原文，出自：" + "、".join(hits))
            return 0
        print(f"✗ 第 {args.any} 卦的三家注與經傳裏都沒有這段字。不得作為原文引用。", file=sys.stderr)
        return 1

    slug = next((s for s in WORKS if getattr(args, s)), None)
    no = getattr(args, slug) if slug else args.jing
    try:
        source = work_entry(slug, no)["text"] if slug else jing_text(no)
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
