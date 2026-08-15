#!/usr/bin/env python3
"""断卦：按朱熹《易学启蒙·考变占》定「该读哪一句」，并取出经文与注家原文。

这是整条链路上最容易做错、而且错了也看不出来的一环——读错一句，
后面所有话都跟著错，且没有任何外部信号提示。故七个分支逐条有测试。

规则原文取自《易学启蒙通释》（四库全书本）卷下，见 REFERENCE.md。
只依赖标准库。
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from cast import (
    DATA_DIR,
    by_lines,
    cast,
    full_name,
    load_hexagrams,
    render_lines,
)

# 《易学启蒙·考变占》七条。彖辞在此指卦下之辞（卦辞），非《彖传》——
# 通释原注：「彖辞为卦下之辞」。这两个东西同名不同物，是这一段最常见的误读。
RULES = {
    0: "凡卦六爻皆不變，則占本卦彖辭，而以內卦為貞、外卦為悔。",
    1: "一爻變，則以本卦變爻辭占。",
    2: "二爻變，則以本卦二變爻辭占，仍以上爻為主。",
    3: "三爻變，則占本卦及之卦之彖辭，即以本卦為貞、之卦為悔，前十卦主貞，後十卦主悔。",
    4: "四爻變，則以之卦二不變爻占，仍以下爻為主。",
    5: "五爻變，則以之卦不變爻占。",
    6: "六爻變，則乾坤占二用，餘卦占之卦彖辭。",
}

RULE_NAMES = {
    0: "六爻不變",
    1: "一爻變",
    2: "二爻變",
    3: "三爻變",
    4: "四爻變",
    5: "五爻變",
    6: "六爻變",
}

# 三爻变时 20 种变爻组合的次序。朱熹的变卦图按「所變之爻」由小到大排列，
# 前十主贞（本卦）、后十主悔（之卦）。此序可由原文反推并验证：
#   乾三爻变「自否至恒为前十卦，自益至泰为后十卦」——
#   字典序第 10 位 (1,5,6) 正是恒，第 11 位 (2,3,4) 正是益；
#   坤三爻变「自泰至益为前十卦，自恒至否为后十卦」——同样吻合。
# 两个独立的锚点都对上，这个排序就不是猜的。测试里把这四个点钉死。
TRIPLES = list(itertools.combinations(range(1, 7), 3))
assert len(TRIPLES) == 20


def triple_rank(moving: list[int]) -> int:
    """三条动爻在朱熹变卦图中的次第，1..20。"""
    return TRIPLES.index(tuple(moving)) + 1


def _coverage() -> dict:
    with open(DATA_DIR / "commentary" / "coverage.json", encoding="utf-8") as f:
        return json.load(f)


def _hexagram(no: int) -> dict:
    for h in load_hexagrams():
        if h["no"] == no:
            return h
    raise KeyError(no)


def _gua_ci(h: dict, role: str, note: str = "") -> dict:
    return {
        "role": role,
        "kind": "卦辭",
        "hexagram_no": h["no"],
        "hexagram": full_name(h),
        "title": h["name"],
        "text": h["gua_ci"],
        "note": note,
    }


def _yao(h: dict, pos: int, role: str, note: str = "") -> dict:
    y = h["yao"][pos - 1]
    return {
        "role": role,
        "kind": "爻辭",
        "hexagram_no": h["no"],
        "hexagram": full_name(h),
        "pos": pos,
        "title": y["title"],
        "text": y["text"],
        "xiao_xiang": y["xiao_xiang"],
        "note": note,
    }


def select(primary: dict, moving: list[int], relating: dict | None) -> dict:
    """按考变占定该读哪一句。primary/relating 为 hexagrams.json 的整条记录。"""
    k = len(moving)
    readings: list[dict] = []
    why = ""

    if k == 0:
        readings.append(_gua_ci(primary, "主"))
        why = (
            "六爻皆不動，沒有哪一爻在說話，讀的就是整卦的卦辭。"
            f"此時以內卦（下 {primary['lower']}）為貞、外卦（上 {primary['upper']}）為悔——"
            "貞是此事在我的一面，悔是應人的一面。"
        )

    elif k == 1:
        pos = moving[0]
        readings.append(_yao(primary, pos, "主"))
        why = f"只有第 {pos} 爻在動，讀本卦這一爻的爻辭。動的那一爻就是此刻說話的位置。"

    elif k == 2:
        hi, lo = moving[1], moving[0]
        readings.append(_yao(primary, hi, "主", "以上爻為主"))
        readings.append(_yao(primary, lo, "輔"))
        why = (
            f"兩爻俱動，讀本卦這兩條爻辭，以在上的第 {hi} 爻為主。"
            "朱子的理由是：變要看它變到極處，故取上爻。"
        )

    elif k == 3:
        assert relating is not None
        rank = triple_rank(moving)
        if rank <= 10:
            readings.append(_gua_ci(primary, "主", f"變卦圖第 {rank} 位，在前十卦，主貞"))
            readings.append(_gua_ci(relating, "輔"))
        else:
            readings.append(_gua_ci(relating, "主", f"變卦圖第 {rank} 位，在後十卦，主悔"))
            readings.append(_gua_ci(primary, "輔"))
        why = (
            "三爻動、三爻不動，六爻正好對半分，於是不落在任何一爻上，"
            "改讀本卦與之卦兩條卦辭。本卦為貞、之卦為悔；"
            f"這一組動爻在朱熹變卦圖中列第 {rank} 位，"
            + ("在前十卦，故以本卦為主。" if rank <= 10 else "在後十卦，故以之卦為主。")
        )

    elif k == 4:
        assert relating is not None
        static = [p for p in range(1, 7) if p not in moving]
        readings.append(_yao(relating, static[0], "主", "以下爻為主"))
        readings.append(_yao(relating, static[1], "輔"))
        why = (
            "動的多、不動的少，重心已經移到之卦，讀之卦裏那兩條沒有動的爻，"
            f"以在下的第 {static[0]} 爻為主。不變者順其先後，故取下爻——"
            "與二爻變取上爻恰好相反，這一正一反是朱子講的老少之義。"
        )

    elif k == 5:
        assert relating is not None
        static = [p for p in range(1, 7) if p not in moving][0]
        readings.append(_yao(relating, static, "主"))
        why = f"五爻皆動，只剩第 {static} 爻不動，讀之卦這一條不變之爻。滿盤皆變，不變處才是落腳點。"

    elif k == 6:
        if primary["no"] == 1:
            readings.append(
                {
                    "role": "主",
                    "kind": "用九",
                    "hexagram_no": 1,
                    "hexagram": "乾為天",
                    "title": "用九",
                    "text": primary["extra"]["用九"],
                    "note": "乾六爻皆變，占二用",
                }
            )
            why = "乾之六爻全變，這是乾坤獨有的一種局面，讀「用九」。"
        elif primary["no"] == 2:
            readings.append(
                {
                    "role": "主",
                    "kind": "用六",
                    "hexagram_no": 2,
                    "hexagram": "坤為地",
                    "title": "用六",
                    "text": primary["extra"]["用六"],
                    "note": "坤六爻皆變，占二用",
                }
            )
            why = "坤之六爻全變，這是乾坤獨有的一種局面，讀「用六」。"
        else:
            assert relating is not None
            readings.append(_gua_ci(relating, "主"))
            why = "六爻全變，本卦已整個翻成之卦，讀之卦卦辭。乾坤之外的卦沒有二用可占。"

    return {
        "moving_count": k,
        "rule_name": RULE_NAMES[k],
        "rule_text": RULES[k],
        "rule_source": "朱熹《易學啟蒙·考變占》",
        "why": why,
        "readings": readings,
    }


WORKS = ("dongpo", "yichuan", "benyi")


def commentary(nos: list[int]) -> list[dict]:
    """取三家注原文。六十四卦皆全，引用时按 citation 注出处。"""
    out = []
    for no in nos:
        h = _hexagram(no)
        entry = {"hexagram_no": no, "hexagram": full_name(h), "commentators": []}
        for slug in WORKS:
            path = DATA_DIR / "commentary" / slug / f"{no:02d}.json"
            if not path.exists():  # 只该在数据没抓全时出现
                entry["commentators"].append({"slug": slug, "available": False})
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
            entry["commentators"].append(
                {
                    "slug": slug,
                    "available": True,
                    "author": d["author"],
                    "work": d["work"],
                    "citation": d["citation"],
                    "edition": d["edition"],
                    "source_url": d["source_url"],
                    "text": d["text"],
                }
            )
        out.append(entry)
    return out


def images(c: dict) -> dict:
    """本卦与之卦该发哪张图。本卦有动爻就临时渲一张带记号的，之卦一律用内置的。

    路径相对 skill 目录——飞书发图只收当前目录下的相对路径，给绝对路径会被拒。
    """
    from render_hexagrams import render_cast  # 构建期脚本，用到才导入

    skill = DATA_DIR.parent

    def rel(p: Path) -> str:
        try:
            return "./" + str(p.relative_to(skill))
        except ValueError:
            return str(p)

    out = {"primary": rel(render_cast(c["primary"]["no"], c["moving"]))}
    if c["relating"]:
        out["relating"] = rel(render_cast(c["relating"]["no"], []))
    return out


def reading(values: list[int] | None = None, cast_result: dict | None = None) -> dict:
    """起一卦并断之。values 为重放用（六个 6/7/8/9，自下而上）。"""
    c = cast_result or cast(values)
    primary = by_lines(c["primary"]["lines"])
    relating = by_lines(c["relating"]["lines"]) if c["relating"] else None

    sel = select(primary, c["moving"], relating)
    involved = sorted({r["hexagram_no"] for r in sel["readings"]})

    context = {
        "本卦": {
            "彖傳": primary["tuan"],
            "大象傳": primary["da_xiang"],
            "卦辭": primary["gua_ci"],
        }
    }
    if relating:
        context["之卦"] = {
            "彖傳": relating["tuan"],
            "大象傳": relating["da_xiang"],
            "卦辭": relating["gua_ci"],
        }

    return {
        "cast": c,
        "images": images(c),
        "judgement": sel,
        "context": context,
        "commentary": commentary(involved),
        "constraints": [
            "引某家之言，必須是其原文的逐字片段，並在句末括注出處（如「蘇軾說……（《東坡易傳·卷五》）」）。"
            "引之前用 verify_quote.py 過一遍。",
            "自己的話就用自己的口氣說，不要掛在某位注家名下。要麼真引，要麼別署名。",
            "不出吉凶斷語，不作預測。目的是看清此刻的位置，不是預告結果。",
        ],
    }


def _print_human(r: dict) -> None:
    c = r["cast"]
    for t in c["tosses"]:
        coins = "、".join(("背" if x == 3 else "字") for x in t["coins"]) if t["coins"] else "（重放）"
        flag = "　（動爻）" if t["moving"] else ""
        print(f"第{t['pos']}擲　{coins}　＝ {t['value']}　{t['symbol']}{flag}")

    p = c["primary"]
    print(f"\n本卦　{p['unicode']} {p['full_name']}（第 {p['no']} 卦）")
    print(render_lines(p["lines"], c["moving"]))
    if c["relating"]:
        q = c["relating"]
        print(f"\n動爻　{'、'.join(c['moving_titles'])}")
        print(f"之卦　{q['unicode']} {q['full_name']}（第 {q['no']} 卦）")
        print(render_lines(q["lines"]))
    else:
        print("\n六爻不动，无之卦。")

    j = r["judgement"]
    print(f"\n── 斷卦：{j['rule_name']} ──")
    print(f"{j['rule_source']}：{j['rule_text']}")
    print(j["why"])
    for x in j["readings"]:
        head = f"[{x['role']}] {x['hexagram']} {x['title']}"
        print(f"\n{head}　{x['text']}")
        if x.get("xiao_xiang"):
            print(f"　　《象》曰：{x['xiao_xiang']}")
        if x.get("note"):
            print(f"　　（{x['note']}）")

    print("\n── 卦象图 ──")
    for k, v in r["images"].items():
        print(f"{'本卦' if k == 'primary' else '之卦'}　{v}")

    print("\n── 大象传 ──")
    print(r["context"]["本卦"]["大象傳"])

    print("\n── 注家原文 ──")
    for e in r["commentary"]:
        for c in e["commentators"]:
            if c["available"]:
                print(
                    f"{e['hexagram']}　{c['author']}{c['citation']}"
                    f"（{c['edition']}，{len(c['text'])} 字）"
                )
            else:
                print(f"{e['hexagram']}　{c['slug']}：數據缺失，請重跑 fetch_commentary.py")
    print("全文用 --json 取；引用前过 verify_quote.py。")


def main() -> None:
    ap = argparse.ArgumentParser(description="起卦并按考变占断之")
    ap.add_argument("--values", help="重放：六个 6/7/8/9，自下而上，逗号分隔")
    ap.add_argument("--json", action="store_true", help="输出完整 JSON（含注家原文全文）")
    args = ap.parse_args()

    values = [int(v) for v in args.values.split(",")] if args.values else None
    r = reading(values)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        _print_human(r)


if __name__ == "__main__":
    main()
