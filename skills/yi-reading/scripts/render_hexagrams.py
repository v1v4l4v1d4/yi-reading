#!/usr/bin/env python3
"""构建期工具：一次性渲染 64 张卦象图。占卜时只查表发图，运行时不画任何东西。

SVG 是样式的源，PNG 由它转出（飞书图片接口要位图）。改风格就改这里重跑一次。

用法：
    python3 render_hexagrams.py                       # 全部 64 张（无动爻记号）
    python3 render_hexagrams.py --only 3              # 只出第 3 卦，调样式时用
    python3 render_hexagrams.py --svg-only            # 不转 PNG
    python3 render_hexagrams.py --cast 3 --moving 1,4 # 临时出一张带动爻记号的，印出路径

内置的 64 张是无动爻的本相；动爻是 2⁶ 种组合，不可能预先穷举，
所以有动爻时临时渲染一张——不过是画六条线加两个记号，成本可以忽略。

PNG 转换依赖 rsvg-convert（brew install librsvg）。没有它就只出 SVG 并如实报告，
不静默跳过——少一张图，占到那一卦就发不出东西。
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
CAST_DIR = OUT_PNG / "cast"  # 临时渲染的带动爻图，不入库

W, H = 1080, 1200

# 克制、留白、无红金。深底细线，字压得很小，画面大半是空的。
BG = "#12100E"
INK = "#E9E3D7"
MID = "#B0A899"
MUTED = "#6F685C"
HAIRLINE = "#37312A"

SERIF = "Songti SC, STSong, Songti TC, Noto Serif CJK SC, serif"
SANS = "Hiragino Sans GB, PingFang SC, Noto Sans CJK SC, sans-serif"

MARGIN = 140  # 左栏基线
BAR_W = 300  # 爻长
BAR_T = 13  # 爻厚
PITCH = 46  # 行距（爻心到爻心）
GAP = 52  # 阴爻中断
TOP = 300  # 上爻顶边

CN_DIGITS = "〇一二三四五六七八九"


def cn_number(n: int) -> str:
    """1 → 一；11 → 十一；64 → 六十四。只需覆盖 1..64。"""
    if n < 10:
        return CN_DIGITS[n]
    if n == 10:
        return "十"
    tens, ones = divmod(n, 10)
    return ("十" if tens == 1 else CN_DIGITS[tens] + "十") + (CN_DIGITS[ones] if ones else "")


def first_clause(gua_ci: str, name: str) -> str:
    """卦辞首句。去掉开头的「屯：」，取到第一个句号；太短就再带一句。"""
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
    """六爻，自下而上读 lines，自上而下画。"""
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


def moving_marks(lines: str, moving: list[int]) -> list[str]:
    """动爻记号，画在左栏外侧。

    用传统那套：老阳（阳极而变）记 ○，老阴记 ×。不是自创符号，
    六爻的卦录本来就这么写，看得懂的人一眼认得，看不懂的人也不会被误导。
    """
    out = []
    cx = MARGIN - 46
    r = 9
    for pos in moving:
        row = 6 - pos  # 自下而上的爻位 → 自上而下的行号
        cy = TOP + row * PITCH + BAR_T / 2
        if lines[pos - 1] == "1":  # 老阳
            out.append(
                f'<circle cx="{cx}" cy="{cy:g}" r="{r}" fill="none" '
                f'stroke="{INK}" stroke-width="2.5"/>'
            )
        else:  # 老阴
            d = r * 0.78
            out.append(
                f'<path d="M{cx - d:g} {cy - d:g} L{cx + d:g} {cy + d:g} '
                f'M{cx + d:g} {cy - d:g} L{cx - d:g} {cy + d:g}" '
                f'stroke="{INK}" stroke-width="2.5" fill="none"/>'
            )
    return out


def yao_title(pos: int, yang: bool) -> str:
    """爻题：初九、六二、上六……pos 自下而上为 1..6。与 cast.py 同一套规则。"""
    num = "九" if yang else "六"
    if pos == 1:
        return "初" + num
    if pos == 6:
        return "上" + num
    return num + "二三四五"[pos - 2]


def svg(h: dict, moving: list[int] | None = None) -> str:
    moving = sorted(moving or [])
    lines = h["lines"]
    name, no = h["name"], h["no"]
    upper, lower = h["upper"], h["lower"]
    images = {"乾": "天", "兌": "澤", "離": "火", "震": "雷",
              "巽": "風", "坎": "水", "艮": "山", "坤": "地"}
    full = f"{name}為{images[upper]}" if upper == lower else f"{images[upper]}{images[lower]}{name}"
    clause = first_clause(h["gua_ci"], name)

    # 上下卦标在爻画右侧，各自对准所属的三爻
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
        *moving_marks(lines, moving),
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
    ]
    # 动爻另起一行写出爻题——记号说「哪几条在动」，这一行说「它们叫什么」，
    # 解卦时要用的是后者。位置固定预留，无动爻时留白。
    if moving:
        titles = "、".join(yao_title(p, lines[p - 1] == "1") for p in moving)
        parts.append(
            f'<text x="{MARGIN}" y="{name_y + 134}" font-family="{SANS}" font-size="28" '
            f'fill="{MUTED}" letter-spacing="0.14em">動爻　{esc(titles)}</text>'
        )
    parts += [
        # 卦辞首句
        f'<rect x="{MARGIN}" y="{name_y + 186}" width="180" height="1" fill="{HAIRLINE}"/>',
        f'<text x="{MARGIN}" y="{name_y + 262}" font-family="{SERIF}" font-size="40" '
        f'fill="{MID}" letter-spacing="0.06em">{esc(clause)}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def hexagram(no: int) -> dict:
    rows = json.loads((DATA / "hexagrams.json").read_text(encoding="utf-8"))
    try:
        return next(r for r in rows if r["no"] == no)
    except StopIteration:
        raise ValueError(f"没有第 {no} 卦") from None


def render_cast(no: int, moving: list[int], out: Path | None = None) -> Path:
    """临时渲染一张带动爻记号的图，返回图片路径。

    无动爻时直接返回内置的那张，不做多余的事。
    有动爻而环境里没有 rsvg-convert 时，也退回内置图——
    少了记号总比发不出图强，但这件事要说出来，不静默降级。
    """
    h = hexagram(no)
    static = OUT_PNG / f"{no:02d}-{h['name']}.png"
    if not moving:
        return static

    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        print(
            "找不到 rsvg-convert，动爻记号画不出来，退回无记号的内置图"
            "（記得在文字裏說清哪幾爻在動）。",
            file=sys.stderr,
        )
        return static

    # 默认落在 skill 目录内部而不是 /tmp：飞书的发图接口只收当前目录下的相对路径，
    # 给绝对路径会被拒。放这里，`cd` 到 skill 目录后就是 ./assets/hexagrams/cast/…
    out = out or CAST_DIR / f"{no:02d}-{h['name']}-{''.join(map(str, moving))}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    svg_path = out.with_suffix(".svg")
    svg_path.write_text(svg(h, moving), encoding="utf-8")
    subprocess.run([rsvg, "-w", str(W), "-h", str(H), str(svg_path), "-o", str(out)], check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染卦象图")
    ap.add_argument("--only", type=int, help="只渲染这一卦（调样式用）")
    ap.add_argument("--svg-only", action="store_true", help="不转 PNG")
    ap.add_argument("--cast", type=int, metavar="卦序", help="临时出一张带动爻记号的图")
    ap.add_argument("--moving", default="", help="动爻位置，自下而上 1..6，逗号分隔")
    ap.add_argument("-o", "--out", type=Path, help="--cast 的输出路径")
    args = ap.parse_args()

    if args.cast:
        moving = [int(p) for p in args.moving.split(",") if p.strip()]
        if any(not 1 <= p <= 6 for p in moving):
            print("动爻位置须在 1..6", file=sys.stderr)
            return 2
        path = render_cast(args.cast, moving, args.out)
        # 印相对路径：发图那一步要的就是它
        try:
            print("./" + str(path.relative_to(SKILL)))
        except ValueError:
            print(path)
        return 0

    rows = json.loads((DATA / "hexagrams.json").read_text(encoding="utf-8"))
    if args.only:
        rows = [r for r in rows if r["no"] == args.only]
        if not rows:
            print(f"没有第 {args.only} 卦", file=sys.stderr)
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

    print(f"写出 {made} 张 SVG → {OUT_SVG}", file=sys.stderr)
    if rsvg and not args.svg_only:
        print(f"写出 {made} 张 PNG → {OUT_PNG}", file=sys.stderr)
        return 0
    return 0 if args.svg_only else 1


if __name__ == "__main__":
    sys.exit(main())
