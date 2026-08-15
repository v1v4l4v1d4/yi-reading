"""Build-time: fetch the classical texts and assemble data/hexagrams.json.

Source, via the MediaWiki API (never by scraping rendered HTML):
  - 经文  https://zh.wikisource.org/wiki/周易/<卦名>   卦辞、六爻辞、彖传、大象、六小象

The three commentaries live in fetch_commentary.py — this file is 经传 only.

The hexagram table itself comes from build_table.py, which derives the six-line
patterns from Unicode trigram symbols rather than transcribing them. This script
then re-derives the trigrams a second time from the 「震下坎上」 line that the
Wikisource 经文 pages carry, and asserts the two agree. Two independent sources
have to say the same thing before anything is written.

Usage:
    python3 scripts/build_table.py       # → data/_table.json
    python3 scripts/fetch_texts.py       # → data/hexagrams.json
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "yi-reading/0.1 (https://github.com/v1v4l4v1d4/yi-reading)"
API = "https://zh.wikisource.org/w/api.php"
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

YAO_TITLES_YANG = ["初九", "九二", "九三", "九四", "九五", "上九"]
YAO_TITLES_YIN = ["初六", "六二", "六三", "六四", "六五", "上六"]
TRIGRAM_BITS = {
    "乾": "111", "兌": "110", "離": "101", "震": "100",
    "巽": "011", "坎": "010", "艮": "001", "坤": "000",
}


def wikitext(title: str) -> str:
    url = f"{API}?" + urllib.parse.urlencode(
        {
            "action": "query", "prop": "revisions", "rvprop": "content",
            "rvslots": "main", "format": "json", "titles": title,
        }
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        page = list(json.load(r)["query"]["pages"].values())[0]
    if "revisions" not in page:
        raise LookupError(f"missing page: {title}")
    return page["revisions"][0]["slots"]["main"]["*"]


def clean(s: str) -> str:
    """Strip wiki markup, Chinese-variant conversion marks, and refs."""
    s = re.sub(r"-\{(?:[a-zA-Z-]+:)?([^}|]*)\}-", r"\1", s)  # -{无}- and -{zh-cn:X}-
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"'''?|\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    return s.strip()


CN_NUM = {c: i for i, c in enumerate("〇一二三四五六七八九")}


def hexagram_number(wt: str) -> int | None:
    """Read 「第三十二卦」 off a 周易 subpage. Numbering is the join key: hexagram
    names vary between orthographies (恒/恒), the ordinal never does."""
    m = re.search(r"第([一二三四五六七八九十]+)卦", clean(wt))
    if not m:
        return None
    s, total, section = m.group(1), 0, 0
    for ch in s:
        if ch == "十":
            section = (section or 1) * 10
            total += section
            section = 0
        else:
            section = CN_NUM[ch]
    return total + section


def subpage_titles() -> list[str]:
    """Every 周易/<x> subpage, so we never have to guess a title."""
    url = f"{API}?" + urllib.parse.urlencode(
        {"action": "query", "list": "allpages", "apprefix": "周易/",
         "aplimit": "500", "format": "json"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return [p["title"] for p in json.load(r)["query"]["allpages"]]


def parse_jing(wt: str, name: str) -> dict:
    """Pull 卦辞 / 六爻辞 / 彖 / 大象 / 六小象 out of a 周易/<卦名> page."""
    # 乾/坤 write the trigram line with variant marks: -{乾}-下-{乾}-上
    trigram_line = re.search(r"([乾兌離震巽坎艮坤])下([乾兌離震巽坎艮坤])上", clean(wt))
    if not trigram_line:
        raise ValueError(f"{name}: no 「X下Y上」 line")

    # 乾 and 坤 continue into 文言传, whose *# items would otherwise be swallowed
    # as 小象. Cut the page there.
    cut = wt.find("文言曰")
    body = wt[:cut] if cut > 0 else wt
    # 坤 breaks a line in the middle of an HTML tag ("*<span\nstyle=..."), which
    # would hide the 「易经：」 marker from a line-by-line scan. Rejoin such tags.
    body = re.sub(r"<[^<>]*>", lambda m: m.group(0).replace("\n", " "), body)
    lines = [clean(ln) for ln in body.splitlines()]
    gua_ci, yao, tuan, da_xiang, xiao_xiang = "", [], "", "", []
    extra = {}  # 用九 / 用六, present only in 乾 and 坤
    section = None
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("*") and "彖曰" in ln:
            section = "tuan"; continue
        if ln.startswith("*") and "象曰" in ln:
            section = "xiang"; continue
        if ln.startswith("*") and "易經" in ln:
            section = "jing"; continue
        if ln.startswith("*#"):
            body = ln.lstrip("*#").strip()
            if body.startswith(("用九", "用六")):
                extra.setdefault(body[:2], body)
                continue
            (yao if section == "jing" else xiao_xiang).append(body)
        elif ln.startswith("***"):
            # Continuation of the preceding ** line — 坤's 卦辞 and 乾/坤's 彖 run on.
            body = ln.lstrip("*").strip()
            if section == "jing" and gua_ci:
                gua_ci += body
            elif section == "tuan" and tuan:
                tuan += body
            elif section == "xiang" and da_xiang:
                da_xiang += body
        elif ln.startswith("**"):
            body = ln.lstrip("*").strip()
            if section == "jing" and not gua_ci:
                gua_ci = body
            elif section == "tuan" and not tuan:
                tuan = body
            elif section == "xiang" and not da_xiang:
                da_xiang = body
    if not (gua_ci and len(yao) == 6 and tuan and da_xiang and len(xiao_xiang) == 6):
        raise ValueError(
            f"{name}: incomplete — 卦辞{bool(gua_ci)} 爻{len(yao)} 彖{bool(tuan)} "
            f"大象{bool(da_xiang)} 小象{len(xiao_xiang)}"
        )
    return {
        "lower_src": trigram_line.group(1), "upper_src": trigram_line.group(2),
        "gua_ci": gua_ci, "yao": yao, "tuan": tuan,
        "da_xiang": da_xiang, "xiao_xiang": xiao_xiang, "extra": extra,
    }


def yao_titles(lines: str) -> list[str]:
    """初九/初六 … 上九/上六, from the six-line pattern (bottom to top)."""
    return [
        (YAO_TITLES_YANG if bit == "1" else YAO_TITLES_YIN)[i]
        for i, bit in enumerate(lines)
    ]


def main() -> None:
    table = json.load(open(DATA / "_table.json"))
    out, failures = [], []

    # Index every 周易 subpage by its stated hexagram number, so titles never
    # have to be guessed and orthographic variants (恒/恒) cannot break the join.
    print("indexing 周易 subpages…", file=sys.stderr)
    by_number: dict[int, tuple[str, str]] = {}
    for title in subpage_titles():
        try:
            wt = wikitext(title)
        except LookupError:
            continue
        n = hexagram_number(wt)
        if n and n not in by_number and re.search(r"[乾兌離震巽坎艮坤]下[乾兌離震巽坎艮坤]上", clean(wt)):
            by_number[n] = (title, wt)
        time.sleep(0.3)
    print(f"  indexed {len(by_number)} hexagram pages", file=sys.stderr)

    for row in table:
        name = row["name"]
        if row["no"] not in by_number:
            failures.append(f"{row['no']:2d} {name}: no 周易 subpage found")
            continue
        title, wt = by_number[row["no"]]
        try:
            jing = parse_jing(wt, name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{row['no']:2d} {name} ({title}): {exc}")
            continue

        # Cross-check: the trigrams stated by Wikisource must match the ones
        # derived from Unicode symbols in build_table.py. Disagreement means one
        # source is wrong and the data is not safe to ship.
        derived = row["lower"] + row["upper"]
        stated = jing["lower_src"] + jing["upper_src"]
        assert derived == stated, f"{name}: trigram mismatch {derived} vs {stated}"
        assert TRIGRAM_BITS[row["lower"]] + TRIGRAM_BITS[row["upper"]] == row["lines"], (
            f"{name}: trigram bits do not rebuild {row['lines']}"
        )

        titles = yao_titles(row["lines"])
        out.append(
            {
                "no": row["no"], "name": name, "unicode": row["unicode"],
                "lines": row["lines"], "lower": row["lower"], "upper": row["upper"],
                "gua_ci": jing["gua_ci"], "tuan": jing["tuan"],
                "da_xiang": jing["da_xiang"],
                "yao": [
                    {"pos": i + 1, "title": titles[i], "text": jing["yao"][i],
                     "xiao_xiang": jing["xiao_xiang"][i]}
                    for i in range(6)
                ],
                **({"extra": jing["extra"]} if jing["extra"] else {}),
            }
        )
        print(f"  {row['no']:2d} {name} ✓", file=sys.stderr)

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print("  " + f, file=sys.stderr)
    assert not failures, f"{len(failures)} hexagrams failed; refusing to write partial data"
    assert len(out) == 64

    (DATA / "hexagrams.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {DATA / 'hexagrams.json'} ({len(out)} hexagrams)", file=sys.stderr)


if __name__ == "__main__":
    if "--dongpo" in sys.argv:
        sys.exit(
            "注解已改由 fetch_commentary.py 抓取——三家、六十四卦全。\n"
            "這裏的 --dongpo 只會抓到 1–35 卦並覆蓋掉完整數據，故已移除。"
        )
    main()
