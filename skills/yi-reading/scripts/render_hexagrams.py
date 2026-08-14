#!/usr/bin/env python3
"""構建期工具：一次性渲染 64 張卦象圖。占卜時只查表發圖，運行時不畫任何東西。

SVG 是樣式的源，PNG 由它轉出（飛書圖片接口要位圖）。改風格就改這裏重跑一次。

用法：
    python3 render_hexagrams.py              # 全部 64 張
    python3 render_hexagrams.py --only 3     # 只出第 3 卦，調樣式時用
    python3 render_hexagrams.py --svg-only   # 不轉 PNG

PNG 轉換依賴 rsvg-convert（brew install librsvg）。沒有它就只出 SVG 並如實報告，
不靜默跳過——少一張圖，占到那一卦就發不出東西。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DATA = SKILL / "data"
OUT_PNG = SKILL / "assets" / "hexagrams"
OUT_SVG = OUT_PNG / "svg"

W, H = 1080, 1200

# 克制、留白、無紅金。深底細線，字壓得很小，畫面大半是空的。
BG = "#12100E"
INK = "#E9E3D7"
MID = "#B0A899"
MUTED = "#6F685C"
HAIRLINE = "#37312A"

SERIF = "Songti SC, STSong, Songti TC, Noto Serif CJK SC, serif"
SANS = "Hiragino Sans GB, PingFang SC, Noto Sans CJK SC, sans-serif"

MARGIN = 140  # 左欄基線
BAR_W = 300  # 爻長
BAR_T = 13  # 爻厚
PITCH = 46  # 行距（爻心到爻心）
GAP = 52  # 陰爻中斷
TOP = 300  # 上爻頂邊

CN_DIGITS = "〇一二三四五六七八九"


def cn_number(n: int) -> str:
    """1 → 一；11 → 十一；64 → 六十四。只需覆蓋 1..64。"""
    if n < 10:
        return CN_DIGITS[n]
    if n == 10:
        return "十"
    tens, ones = divmod(n, 10)
    return ("十" if tens == 1 else CN_DIGITS[tens] + "十") + (CN_DIGITS[ones] if ones else "")


def first_clause(gua_ci: str, name: str) -> str:
    """卦辭首句。去掉開頭的「屯：」，取到第一個句號；太短就再帶一句。"""
    body = re.sub(rf"^{re.escape(name)}[：:，,]?", "", gua_ci).strip()
    parts = [p for p in re.split(r"(?<=。)", body) if p.strip()]
    if not parts:
        return body
    out = parts[0]
    if len(out) < 6 and len(parts) > 1:
        out += parts[1]
    return out.strip()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def yao_shapes(lines: str) -> list[str]:
    """六爻，自下而上讀 lines，自上而下畫。"""
    out = []
    for row, pos in enumerate(range(6, 0, -1)):
        y = TOP + row * PITCH
        if lines[pos - 1] == "1":
            out.append(f'<rect x="{MARGIN}" y="{y}" width="{BAR_W}" height="{BAR_T}" fill="{INK}"/>')
        else:
            half = (BAR_W - GAP) / 2
            out.append(
                f'<rect x="{MARGIN}" y="{y}" width="{half:g}" height="{BAR_T}" fill="{INK}"/>'
                f'<rect x="{MARGIN + half + GAP:g}" y="{y}" width="{half:g}" '
                f'height="{BAR_T}" fill="{INK}"/>'
            )
    return out


def svg(h: dict) -> str:
    lines = h["lines"]
    name, no = h["name"], h["no"]
    upper, lower = h["upper"], h["lower"]
    images = {"乾": "天", "兌": "澤", "離": "火", "震": "雷",
              "巽": "風", "坎": "水", "艮": "山", "坤": "地"}
    full = f"{name}為{images[upper]}" if upper == lower else f"{images[upper]}{images[lower]}{name}"
    clause = first_clause(h["gua_ci"], name)

    # 上下卦標在爻畫右側，各自對準所屬的三爻
    label_x = MARGIN + BAR_W + 54
    upper_y = TOP + PITCH * 1 + BAR_T
    lower_y = TOP + PITCH * 4 + BAR_T

    name_y = TOP + PITCH * 5 + BAR_T + 250
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        # 卦序
        f'<text x="{MARGIN}" y="168" font-family="{SANS}" font-size="30" fill="{MUTED}" '
        f'letter-spacing="0.34em">第{cn_number(no)}卦</text>',
        f'<text x="{W - MARGIN}" y="168" font-family="{SERIF}" font-size="46" fill="{HAIRLINE}" '
        f'text-anchor="end">{esc(h["unicode"])}</text>',
        *yao_shapes(lines),
        # 上下卦
        f'<text x="{label_x}" y="{upper_y}" font-family="{SANS}" font-size="26" '
        f'fill="{MUTED}">{esc(upper)}　上</text>',
        f'<text x="{label_x}" y="{lower_y}" font-family="{SANS}" font-size="26" '
        f'fill="{MUTED}">{esc(lower)}　下</text>',
        # 卦名
        f'<text x="{MARGIN}" y="{name_y}" font-family="{SERIF}" font-size="150" '
        f'fill="{INK}">{esc(name)}</text>',
        f'<text x="{MARGIN}" y="{name_y + 76}" font-family="{SANS}" font-size="38" '
        f'fill="{MID}" letter-spacing="0.22em">{esc(full)}</text>',
        # 卦辭首句
        f'<rect x="{MARGIN}" y="{name_y + 156}" width="180" height="1" fill="{HAIRLINE}"/>',
        f'<text x="{MARGIN}" y="{name_y + 232}" font-family="{SERIF}" font-size="40" '
        f'fill="{MID}" letter-spacing="0.06em">{esc(clause)}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染 64 張卦象圖")
    ap.add_argument("--only", type=int, help="只渲染這一卦（調樣式用）")
    ap.add_argument("--svg-only", action="store_true", help="不轉 PNG")
    args = ap.parse_args()

    rows = json.loads((DATA / "hexagrams.json").read_text(encoding="utf-8"))
    if args.only:
        rows = [r for r in rows if r["no"] == args.only]
        if not rows:
            print(f"沒有第 {args.only} 卦", file=sys.stderr)
            return 2

    OUT_SVG.mkdir(parents=True, exist_ok=True)
    rsvg = shutil.which("rsvg-convert")
    if not rsvg and not args.svg_only:
        print("找不到 rsvg-convert（brew install librsvg）；只出 SVG。", file=sys.stderr)

    made = 0
    for h in rows:
        stem = f"{h['no']:02d}-{h['name']}"
        (OUT_SVG / f"{stem}.svg").write_text(svg(h), encoding="utf-8")
        if rsvg and not args.svg_only:
            subprocess.run(
                [rsvg, "-w", str(W), "-h", str(H),
                 str(OUT_SVG / f"{stem}.svg"), "-o", str(OUT_PNG / f"{stem}.png")],
                check=True,
            )
        made += 1

    print(f"寫出 {made} 張 SVG → {OUT_SVG}", file=sys.stderr)
    if rsvg and not args.svg_only:
        print(f"寫出 {made} 張 PNG → {OUT_PNG}", file=sys.stderr)
        return 0
    return 0 if args.svg_only else 1


if __name__ == "__main__":
    sys.exit(main())
