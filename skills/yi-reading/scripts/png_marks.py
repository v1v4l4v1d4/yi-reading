#!/usr/bin/env python3
"""在现成的 PNG 上画动爻记号，只用标准库。

**为什么不复用那条 SVG → PNG 的路**：那条路要 `rsvg-convert`，而六爻全不动的
概率只有 (3/4)⁶ ≈ 18%——也就是说五次占问里约四次要画记号，
于是一个「构建期工具」实际上变成了运行时依赖，使用方不装 librsvg 就少一半信息。

记号是纯几何（一个圈、一个叉），不需要字体，那就没必要为它拖进一个渲染引擎。
底图是构建期就渲染好的 PNG，运行时只要往上叠两个形状——`zlib` 够用。

只处理这个仓库里 64 张底图的格式：8 位、真彩色（colortype 2）、非隔行。
遇到别的格式直接报错，不猜——猜错了会画出一张看起来正常但颜色错乱的图。
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
BPP = 3  # colortype 2, 8-bit：每像素 3 字节


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_rgb(path: Path) -> tuple[int, int, bytearray]:
    """读成 (宽, 高, RGB 字节)。逐行反滤波。"""
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError(f"不是 PNG：{path}")
    idat = bytearray()
    width = height = None
    off = 8
    while off < len(data):
        (length,) = struct.unpack(">I", data[off:off + 4])
        ctype = data[off + 4:off + 8]
        body = data[off + 8:off + 8 + length]
        if ctype == b"IHDR":
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, color, interlace) != (8, 2, 0):
                raise ValueError(
                    f"只支持 8 位真彩非隔行 PNG，这张是 depth={depth} color={color} "
                    f"interlace={interlace}：{path}"
                )
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        off += 12 + length
    if width is None:
        raise ValueError(f"没有 IHDR：{path}")

    raw = zlib.decompress(bytes(idat))
    stride = width * BPP
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for i in range(BPP, stride):
                line[i] = (line[i] + line[i - BPP]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - BPP] if i >= BPP else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                left = line[i - BPP] if i >= BPP else 0
                ul = prev[i - BPP] if i >= BPP else 0
                line[i] = (line[i] + _paeth(left, prev[i], ul)) & 0xFF
        elif ft != 0:
            raise ValueError(f"未知滤波类型 {ft}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return width, height, out


def write_rgb(path: Path, width: int, height: int, pixels: bytearray) -> None:
    """写回去。所有行用滤波类型 0（None）——文件略大，但没有出错的余地。"""
    stride = width * BPP
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    Path(path).write_bytes(
        PNG_SIG
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _blend(pixels: bytearray, width: int, x: int, y: int, rgb: tuple[int, int, int],
           coverage: float) -> None:
    if coverage <= 0:
        return
    i = (y * width + x) * BPP
    for k in range(3):
        old = pixels[i + k]
        pixels[i + k] = int(round(old + (rgb[k] - old) * min(coverage, 1.0)))


def _coverage(px: int, py: int, inside, samples: int = 4) -> float:
    """4×4 超采样求覆盖率——底图是矢量渲染的，硬边记号贴上去会显得毛糙。"""
    hit = 0
    step = 1.0 / samples
    for sy in range(samples):
        for sx in range(samples):
            if inside(px + (sx + 0.5) * step, py + (sy + 0.5) * step):
                hit += 1
    return hit / (samples * samples)


def draw_ring(pixels: bytearray, width: int, height: int, cx: float, cy: float,
              r: float, stroke: float, rgb: tuple[int, int, int]) -> None:
    half = stroke / 2.0
    lo, hi = (r - half) ** 2, (r + half) ** 2

    def inside(x: float, y: float) -> bool:
        d = (x - cx) ** 2 + (y - cy) ** 2
        return lo <= d <= hi

    _paint(pixels, width, height, cx, cy, r + half + 1, inside, rgb)


def draw_cross(pixels: bytearray, width: int, height: int, cx: float, cy: float,
               d: float, stroke: float, rgb: tuple[int, int, int]) -> None:
    half = stroke / 2.0
    segs = [((cx - d, cy - d), (cx + d, cy + d)), ((cx + d, cy - d), (cx - d, cy + d))]

    def inside(x: float, y: float) -> bool:
        for (x1, y1), (x2, y2) in segs:
            dx, dy = x2 - x1, y2 - y1
            t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            px, py = x1 + t * dx, y1 + t * dy
            if (x - px) ** 2 + (y - py) ** 2 <= half * half:
                return True
        return False

    _paint(pixels, width, height, cx, cy, d + half + 1, inside, rgb)


def _paint(pixels, width, height, cx, cy, reach, inside, rgb) -> None:
    x0, x1 = max(0, int(cx - reach)), min(width - 1, int(cx + reach) + 1)
    y0, y1 = max(0, int(cy - reach)), min(height - 1, int(cy + reach) + 1)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _blend(pixels, width, x, y, rgb, _coverage(x, y, inside))
