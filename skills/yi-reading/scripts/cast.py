#!/usr/bin/env python3
"""金錢卦起卦：三枚硬幣擲六次，自下而上得本卦、動爻與之卦。

隨機源固定為 `secrets`。這不是潔癖：`random` 是可復現的偽隨機，
而整件事的意義建立在「這一次的落點不可預先知道」之上。
用一個可復現的偽隨機數做共時性占卜是自我拆台。

只依賴標準庫，可直接 `python3 cast.py` 運行。
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 三枚硬幣同擲：背面為陽記 3，字面為陰記 2。
# 寫死在代碼裏，不提供配置項——換一種記法會讓老陰與老陽整體對調，
# 而動爻的方向就是解卦的全部。一個可配置的開關只會製造沉默的錯卦。
BEI = 3  # 背，陽
ZI = 2  # 字，陰

# 三枚之和 -> (四象名, 本卦爻位, 是否動爻)
FOUR_SYMBOLS: dict[int, tuple[str, str, bool]] = {
    6: ("老陰", "0", True),
    7: ("少陽", "1", False),
    8: ("少陰", "0", False),
    9: ("老陽", "1", True),
}

# 八卦取象，用於拼「水雷屯」這類全名
TRIGRAM_IMAGE = {
    "乾": "天",
    "兌": "澤",
    "離": "火",
    "震": "雷",
    "巽": "風",
    "坎": "水",
    "艮": "山",
    "坤": "地",
}

_TABLE: list[dict] | None = None
_BY_LINES: dict[str, dict] | None = None


def load_hexagrams() -> list[dict]:
    """讀入 64 卦經文表（自下而上的六位二進制為索引鍵）。"""
    global _TABLE, _BY_LINES
    if _TABLE is None:
        with open(DATA_DIR / "hexagrams.json", encoding="utf-8") as f:
            _TABLE = json.load(f)
        _BY_LINES = {h["lines"]: h for h in _TABLE}
        if len(_BY_LINES) != 64:
            raise RuntimeError("hexagrams.json 的卦畫不是 64 個互異值")
    return _TABLE


def by_lines(lines: str) -> dict:
    """按六位卦畫（自下而上，1 陽 0 陰）取卦。"""
    load_hexagrams()
    assert _BY_LINES is not None
    try:
        return _BY_LINES[lines]
    except KeyError:
        raise ValueError(f"不是合法卦畫：{lines!r}") from None


def full_name(hexagram: dict) -> str:
    """「水雷屯」；八純卦作「乾為天」。"""
    upper = TRIGRAM_IMAGE[hexagram["upper"]]
    lower = TRIGRAM_IMAGE[hexagram["lower"]]
    if hexagram["upper"] == hexagram["lower"]:
        return f"{hexagram['name']}為{upper}"
    return f"{upper}{lower}{hexagram['name']}"


def yao_title(pos: int, yang: bool) -> str:
    """爻題：初九、六二、上六……pos 自下而上為 1..6。"""
    if not 1 <= pos <= 6:
        raise ValueError(f"爻位須在 1..6：{pos}")
    num = "九" if yang else "六"
    if pos == 1:
        return "初" + num
    if pos == 6:
        return "上" + num
    return num + "二三四五"[pos - 2]


def toss_coin() -> int:
    """擲一枚：背 3 或字 2。"""
    return BEI if secrets.randbits(1) else ZI


def toss_line() -> tuple[list[int], int]:
    """擲一爻：三枚同擲，返回 (三枚點數, 和)。"""
    coins = [toss_coin() for _ in range(3)]
    return coins, sum(coins)


def cast(values: list[int] | None = None) -> dict:
    """起一卦。

    values 只為測試與復盤而設：傳入六個 6/7/8/9（自下而上）以重放一次占問。
    正常占問不傳，六爻現擲。
    """
    if values is not None:
        if len(values) != 6 or any(v not in FOUR_SYMBOLS for v in values):
            raise ValueError("values 須為六個 6/7/8/9，自下而上")

    tosses: list[dict] = []
    primary_bits: list[str] = []
    relating_bits: list[str] = []
    moving: list[int] = []

    for pos in range(1, 7):
        if values is not None:
            coins, value = None, values[pos - 1]
        else:
            coins, value = toss_line()
        name, bit, is_moving = FOUR_SYMBOLS[value]
        primary_bits.append(bit)
        relating_bits.append(("1" if bit == "0" else "0") if is_moving else bit)
        if is_moving:
            moving.append(pos)
        tosses.append(
            {
                "pos": pos,
                "coins": coins,
                "value": value,
                "symbol": name,
                "yao": bit,
                "moving": is_moving,
                "title": yao_title(pos, bit == "1"),
            }
        )

    primary = by_lines("".join(primary_bits))
    relating = by_lines("".join(relating_bits)) if moving else None

    return {
        "method": "金錢卦",
        "convention": "背為陽記 3、字為陰記 2；三枚之和：6 老陰、7 少陽、8 少陰、9 老陽",
        "tosses": tosses,
        "primary": _brief(primary),
        "moving": moving,
        "moving_titles": [tosses[p - 1]["title"] for p in moving],
        "relating": _brief(relating) if relating else None,
    }


def _brief(h: dict) -> dict:
    return {
        "no": h["no"],
        "name": h["name"],
        "full_name": full_name(h),
        "unicode": h["unicode"],
        "lines": h["lines"],
        "lower": h["lower"],
        "upper": h["upper"],
    }


def render_lines(lines: str, moving: list[int] | None = None) -> str:
    """把卦畫畫成六行文本，自上而下（上爻在最上，合乎閱讀習慣）。"""
    moving = moving or []
    rows = []
    for pos in range(6, 0, -1):
        bar = "▬▬▬▬▬▬▬" if lines[pos - 1] == "1" else "▬▬▬　▬▬▬"
        mark = " ←動" if pos in moving else ""
        rows.append(f"{bar}{mark}")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="金錢卦起卦")
    ap.add_argument(
        "--values",
        help="重放一次占問：六個 6/7/8/9，自下而上，逗號分隔（測試與復盤用）",
    )
    ap.add_argument("--json", action="store_true", help="只輸出 JSON")
    args = ap.parse_args()

    values = [int(v) for v in args.values.split(",")] if args.values else None
    result = cast(values)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    for t in result["tosses"]:
        coins = "、".join(("背" if c == BEI else "字") for c in t["coins"]) if t["coins"] else "（重放）"
        flag = "　（動爻）" if t["moving"] else ""
        print(f"第{t['pos']}擲　{coins}　＝ {t['value']}　{t['symbol']}{flag}")
    print()
    p = result["primary"]
    print(f"本卦　{p['unicode']} {p['full_name']}（第 {p['no']} 卦）")
    print(render_lines(p["lines"], result["moving"]))
    if result["relating"]:
        r = result["relating"]
        print(f"\n動爻　{'、'.join(result['moving_titles'])}")
        print(f"之卦　{r['unicode']} {r['full_name']}（第 {r['no']} 卦）")
        print(render_lines(r["lines"]))
    else:
        print("\n六爻不動，無之卦。")


if __name__ == "__main__":
    main()
