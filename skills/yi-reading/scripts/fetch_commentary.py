#!/usr/bin/env python3
"""构建期工具：抓三家易注，按卦切分入库。

三家都有完整的四库全书本在维基文库，六十四卦一卦不缺：

    苏轼《东坡易传》   卷 1–6（卷 7–9 为系辞、说卦等，不在此列）
    程颐《伊川易传》   卷 1–4
    朱熹《周易本义》   卷 1–2（卷 3–4 为系辞以下）

第一版只抓到带标点的《东坡易传》子页（仅 1–35 卦），据此判定「只能引一半」——
那是**找得不够**，不是来源不全。四库本就在隔壁，一直都在。

四库本的代价是**无标点**。所以《东坡易传》1–35 卦仍优先用带标点的维基文库本，
其余一律四库本；每个文件记下自己是哪个本子、在第几卷，引用时好注出处。

切分依据是每卦开头的 `{{SKchar|NNNN}}{{SK notes|震下坎上}}` 标记——
由上下卦反查卦序，再断言全书恰好覆盖 1..64 且次序单调。
不靠卦名匹配：四库本用了大量异体字（兑写作兑、兊，无咎写作元咎），
按名字对必然漏，按卦画对不会。

用法：python3 fetch_commentary.py [--work dongpo|yichuan|benyi]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
API = "https://zh.wikisource.org/w/api.php"
UA = "yi-reading/0.1 (build script; https://github.com/v1v4l4v1d4/yi-reading)"

WORKS = {
    "dongpo": {
        "title": "東坡易傳",
        "author": "蘇軾",
        "juan": range(1, 7),
        # 带标点的维基文库子页只到第 35 卦；有则优先，其余用四库本
        "punctuated_subpages": range(1, 36),
    },
    "yichuan": {"title": "伊川易傳", "author": "程頤", "juan": range(1, 5)},
    "benyi": {"title": "周易本義", "author": "朱熹", "juan": range(1, 3)},
}

BITS = {"乾": "111", "兌": "110", "離": "101", "震": "100",
        "巽": "011", "坎": "010", "艮": "001", "坤": "000"}
# 四库本的异体写法。兑一个字就有三种写法，这正是不能按卦名切分的理由。
VARIANTS = {"兑": "兌", "兊": "兌", "离": "離", "㢲": "巽", "刋": "巽"}
TRIGRAM_CLASS = "[" + "".join(sorted(set(BITS) | set(VARIANTS))) + "]"
HEX_MARK = re.compile(
    r"\{\{SKchar\|\d+\}\}\s*\{\{SK ?notes\|(%s)下(%s)上\}\}" % (TRIGRAM_CLASS, TRIGRAM_CLASS)
)


def wikitext(title: str) -> str:
    url = f"{API}?" + urllib.parse.urlencode(
        {"action": "query", "prop": "revisions", "rvprop": "content",
         "rvslots": "main", "format": "json", "titles": title}
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                page = list(json.load(r)["query"]["pages"].values())[0]
            break
        except urllib.error.HTTPError as exc:  # 维基对连续请求会 429，退避重试
            if exc.code != 429 or attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    if "revisions" not in page:
        raise LookupError(f"missing page: {title}")
    return page["revisions"][0]["slots"]["main"]["*"]


def clean_skqs(s: str) -> tuple[str, int]:
    """把四库本页面清成正文。返回 (正文, 缺字数)。

    `{{SK anchor|…}}` 是扫描页的导航锚点，内容与正文重复，去掉。
    `{{SK notes|…}}` 是双行小注——在《周易本义》里它就是朱熹的注本身，
    内容必须留下。`{{SKchar|N}}` 是字库外的字，留一个 □ 占位，如实计数。
    """
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{SKQS header[^}]*\}\}", "", s)
    s = re.sub(r"</?(?:onlyinclude|poem|div|span)[^>]*>", "", s)
    s = re.sub(r"\{\{SK ?anchor\|[^}]*\}\}", "", s)
    s = re.sub(r"\{\{SK ?notes\|([^}]*)\}\}", r"\1", s)
    lacunae = len(re.findall(r"\{\{SKchar\|\d+\}\}", s))
    s = re.sub(r"\{\{SKchar\|\d+\}\}", "□", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    lines = [ln.strip("　 \t") for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln), lacunae


def trigram(ch: str) -> str:
    return BITS[VARIANTS.get(ch, ch)]


def split_juan(raw: str, by_lines: dict) -> list[tuple[int, str]]:
    """把一卷切成 [(卦序, 该卦全文), …]，次序即原书次序。"""
    marks = list(HEX_MARK.finditer(raw))
    out = []
    for i, m in enumerate(marks):
        no = by_lines[trigram(m.group(1)) + trigram(m.group(2))]["no"]
        end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
        out.append((no, raw[m.end():end]))
    return out


def fetch_work(slug: str, by_lines: dict, names: dict) -> dict:
    spec = WORKS[slug]
    outdir = DATA / "commentary" / slug
    outdir.mkdir(parents=True, exist_ok=True)

    juan_of: dict[int, int] = {}
    blocks: dict[int, str] = {}
    lacunae: dict[int, int] = {}
    order: list[int] = []

    for j in spec["juan"]:
        title = f"{spec['title']} (四庫全書本)/卷{j}"
        raw = wikitext(title)
        for no, body in split_juan(raw, by_lines):
            text, gaps = clean_skqs(body)
            juan_of[no] = j
            blocks[no] = text
            lacunae[no] = gaps
            order.append(no)
        print(f"  {title} → {len([n for n in order if juan_of[n] == j])} 卦", file=sys.stderr)

    # 全书恰好覆盖 1..64，且次序单调。任一条不成立，说明切分规则漏了某种写法，
    # 这时宁可失败也不要静默少一卦——少的那一卦占到了就没注可引。
    assert order == sorted(order), f"{slug}: 卦序非單調，切分有誤"
    assert sorted(order) == list(range(1, 65)), (
        f"{slug}: 覆蓋不全，缺 {sorted(set(range(1, 65)) - set(order))}"
    )

    editions = {}
    for no in range(1, 65):
        text, edition = blocks[no], "四庫全書本"
        source_url = (
            f"https://zh.wikisource.org/wiki/{spec['title']} (四庫全書本)/卷{juan_of[no]}"
        )
        if no in spec.get("punctuated_subpages", ()):
            # 带标点的本子好读好引，有就优先
            punct = clean_punctuated(wikitext(f"{spec['title']}/{no:02d}"))
            if len(punct) > 200:
                text, edition = punct, "維基文庫標點本"
                source_url = f"https://zh.wikisource.org/wiki/{spec['title']}/{no:02d}"
        editions[no] = edition
        (outdir / f"{no:02d}.json").write_text(
            json.dumps(
                {
                    "no": no,
                    "name": names[no],
                    "work": spec["title"],
                    "author": spec["author"],
                    "juan": juan_of[no],
                    "citation": f"《{spec['title']}·卷{cn_num(juan_of[no])}》",
                    "edition": edition,
                    "source_url": urllib.parse.quote(source_url, safe=":/#"),
                    "lacunae": lacunae[no] if edition == "四庫全書本" else 0,
                    "text": text,
                },
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    return {
        "work": spec["title"],
        "author": spec["author"],
        "covered": list(range(1, 65)),
        "juan_of": {str(k): v for k, v in sorted(juan_of.items())},
        "editions": {str(k): v for k, v in sorted(editions.items())},
        "lacunae_total": sum(v for k, v in lacunae.items() if editions[k] == "四庫全書本"),
    }


FURNITURE = re.compile(r"^(?:\||\}\}|\{\{|[乾兌離震巽坎艮坤幹][上下]|經|傳|$)")


def clean_punctuated(wt: str) -> str:
    """带标点的《东坡易传》子页：清掉模板与版面字，只留正文。"""
    def one(s: str) -> str:
        s = re.sub(r"-\{(?:[a-zA-Z-]+:)?([^}|]*)\}-", r"\1", s)
        s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", s, flags=re.S)
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"'''?|\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", s)
        s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
        return s.strip()

    lines = [ln for ln in (one(l) for l in wt.splitlines()) if ln]
    while lines and FURNITURE.match(lines[0]):
        lines.pop(0)
    return "\n".join(ln for ln in lines if not ln.startswith("{{"))


CN = "〇一二三四五六七八九"


def cn_num(n: int) -> str:
    if n < 10:
        return CN[n]
    tens, ones = divmod(n, 10)
    return ("十" if tens == 1 else CN[tens] + "十") + (CN[ones] if ones else "")


def main() -> None:
    ap = argparse.ArgumentParser(description="抓三家易注")
    ap.add_argument("--work", choices=sorted(WORKS), help="只抓一家")
    args = ap.parse_args()

    hexagrams = json.loads((DATA / "hexagrams.json").read_text(encoding="utf-8"))
    by_lines = {h["lines"]: h for h in hexagrams}
    names = {h["no"]: h["name"] for h in hexagrams}

    cov_path = DATA / "commentary" / "coverage.json"
    coverage = json.loads(cov_path.read_text(encoding="utf-8")) if cov_path.exists() else {}

    for slug in ([args.work] if args.work else list(WORKS)):
        print(f"\n{slug} — {WORKS[slug]['author']}《{WORKS[slug]['title']}》", file=sys.stderr)
        coverage[slug] = fetch_work(slug, by_lines, names)

    coverage["note"] = (
        "三家均為完整六十四卦。四庫全書本無標點，引用時宜取短句；"
        "□ 為原掃描本字庫外的缺字，如實保留，不猜補。"
    )
    cov_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {cov_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
