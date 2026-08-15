#!/usr/bin/env python3
"""核对一段「引文」是否真的出自库中原文。

存在的理由很直接：一个语言模型写出一段像苏轼的话，比引对一段真的苏轼容易得多，
而读者无从分辨。所以「不得以自撰文字冒充原文」这条不能靠自觉，要有机器判据。

用法：
    python3 verify_quote.py --dongpo 3 "困者坐而见制"
    python3 verify_quote.py --yichuan 47 "行吾义而已"
    python3 verify_quote.py --benyi 47 "当务晦黙"
    python3 verify_quote.py --any 47 "刚揜也"          # 三家＋经传一起找，并报出处
    echo "..." | python3 verify_quote.py --jing 3

比对前只做一件事：去掉空白。标点、繁简、引号样式一律不归一化——
归一化就等于允许改字，而这里要保的正是逐字。退出码 0 为通过，1 为不通过。

四库本无标点，所以引它时取短句（四到十来个字）最稳；长段落用自己的话转述，
但**转述就不要挂在注家名下**——要么真引，要么别署名。
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
        raise LookupError(f"第 {no} 卦没有《{WORKS[slug]}》的数据——请重跑 fetch_commentary.py")
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
    ap = argparse.ArgumentParser(description="核对引文是否为原文的逐字子串")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dongpo", type=int, metavar="卦序", help="对照苏轼《东坡易传》")
    g.add_argument("--yichuan", type=int, metavar="卦序", help="对照程颐《伊川易传》")
    g.add_argument("--benyi", type=int, metavar="卦序", help="对照朱熹《周易本义》")
    g.add_argument("--jing", type=int, metavar="卦序", help="对照经传（卦爻辞、彖、象）")
    g.add_argument("--any", type=int, metavar="卦序", help="三家＋经传一起找，命中则报出处")
    ap.add_argument("quote", nargs="?", help="待核引文；省略则从 stdin 读")
    args = ap.parse_args()

    quote = (args.quote if args.quote is not None else sys.stdin.read()).strip()
    if not quote:
        print("没有给出引文", file=sys.stderr)
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
        print(f"✗ 第 {args.any} 卦的三家注与经传里都没有这段字。不得作为原文引用。", file=sys.stderr)
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
    print("✗ 不是原文——库中找不到这段字。不得作为原文引用。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
