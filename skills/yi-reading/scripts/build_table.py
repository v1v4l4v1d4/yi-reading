"""Derive the 64-hexagram King Wen table programmatically, then prove it correct.

Nothing here is hand-typed except the validation anchors. The line patterns are
computed from the Unicode trigram symbols that English Wikipedia states for each
hexagram's inner/outer trigram, so a transcription slip is not possible; the
checks at the bottom then have to pass before anything is written out.

Source: en.wikipedia.org "List of hexagrams of the I Ching" (fetched via the
MediaWiki API). Run with no arguments to fetch and write data/_table.json.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Unicode trigrams U+2630..U+2637 = 乾 兑 离 震 巽 坎 艮 坤.
# For offset n, the bottom-to-top bits are the complement of n's bits, LSB at top.
TRIGRAM_NAMES = ["乾", "兌", "離", "震", "巽", "坎", "艮", "坤"]


def trigram_bits(sym: str) -> str:
    """Bottom-to-top bits of a Unicode trigram symbol, e.g. '☳' -> '100'."""
    n = ord(sym) - 0x2630
    if not 0 <= n <= 7:
        raise ValueError(f"not a trigram: {sym!r}")
    b0 = 1 - ((n >> 2) & 1)
    b1 = 1 - ((n >> 1) & 1)
    b2 = 1 - (n & 1)
    return f"{b0}{b1}{b2}"


def parse(wikitext: str) -> list[dict]:
    out = []
    sections = re.split(r"==+\s*Hexagram (\d+)\s*==+", wikitext)
    # sections = [preamble, "1", body1, "2", body2, ...]
    for i in range(1, len(sections) - 1, 2):
        no = int(sections[i])
        body = sections[i + 1]
        # The article is not uniform: some entries use {{linktext|lang=zh|X}} rather
        # than {{lang|zh|X}}, and some link [[bagua|…]] rather than [[Ba gua|…]].
        name = re.search(r"is named \{\{(?:lang\|zh|linktext\|lang=zh)\|([^}]+)\}\}", body)
        inner = re.search(r"inner \(lower\) \[\[[Bb]a ?gua\|trigram\]\] is (.)", body)
        outer = re.search(r"outer \(upper\) \[\[[Bb]a ?gua\|trigram\]\] is (.)", body)
        if not (name and inner and outer):
            print(f"  !! hexagram {no}: could not parse", file=sys.stderr)
            continue
        # The eight doubled hexagrams say "identical" instead of repeating the symbol.
        outer_sym = inner.group(1) if outer.group(1) == "i" else outer.group(1)
        lower, upper = trigram_bits(inner.group(1)), trigram_bits(outer_sym)
        out.append(
            {
                "no": no,
                "name": name.group(1).strip(),
                "lower": TRIGRAM_NAMES[ord(inner.group(1)) - 0x2630],
                "upper": TRIGRAM_NAMES[ord(outer_sym) - 0x2630],
                "lines": lower + upper,  # bottom-to-top, 6 chars
                "unicode": chr(0x4DC0 + no - 1),
            }
        )
    return out


def check(rows: list[dict]) -> None:
    """Every one of these must pass. A failure means the table is not usable."""
    assert len(rows) == 64, f"expected 64 hexagrams, got {len(rows)}"
    assert [r["no"] for r in rows] == list(range(1, 65)), "numbering is not 1..64"

    pats = [r["lines"] for r in rows]
    assert len(set(pats)) == 64, "duplicate line patterns"
    assert all(len(p) == 6 and set(p) <= {"0", "1"} for p in pats), "malformed pattern"
    assert set(pats) == {f"{i:06b}" for i in range(64)}, "does not cover all 2^6"

    # Anchors: independently known hexagrams (bottom-to-top).
    anchors = {
        1: "111111", 2: "000000", 3: "100010", 4: "010001",
        11: "111000", 12: "000111", 29: "010010", 30: "101101",
        63: "101010", 64: "010101",
    }
    by_no = {r["no"]: r for r in rows}
    for no, want in anchors.items():
        got = by_no[no]["lines"]
        assert got == want, f"hexagram {no} ({by_no[no]['name']}): {got} != {want}"

    # Structural invariant of the King Wen sequence: within each pair (2k-1, 2k)
    # the second is the vertical reversal of the first, or — when the reversal
    # would be identical to itself — its complement. This checks all 32 pairs at
    # once and catches essentially any transcription error.
    for k in range(1, 33):
        a, b = by_no[2 * k - 1]["lines"], by_no[2 * k]["lines"]
        reversed_a = a[::-1]
        complement_a = "".join("1" if c == "0" else "0" for c in a)
        expect = complement_a if reversed_a == a else reversed_a
        assert b == expect, (
            f"pair {2*k-1}/{2*k} ({by_no[2*k-1]['name']}/{by_no[2*k]['name']}): "
            f"{b} != {expect}"
        )

    print(f"✓ all checks passed on {len(rows)} hexagrams", file=sys.stderr)


SOURCE = "List of hexagrams of the I Ching"
API = "https://en.wikipedia.org/w/api.php"
UA = "yi-reading/0.1 (build script; https://github.com/v1v4l4v1d4/yi-reading)"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "_table.json"


def fetch_wikitext() -> str:
    url = f"{API}?" + urllib.parse.urlencode(
        {
            "action": "query", "prop": "revisions", "rvprop": "content",
            "rvslots": "main", "format": "json", "titles": SOURCE,
        }
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        page = list(json.load(r)["query"]["pages"].values())[0]
    return page["revisions"][0]["slots"]["main"]["*"]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and Path(args[0]).exists():
        data = json.load(open(args[0]))
        wt = list(data["query"]["pages"].values())[0]["revisions"][0]["slots"]["main"]["*"]
        out = Path(args[1]) if len(args) > 1 else DEFAULT_OUT
    else:
        wt = fetch_wikitext()
        out = Path(args[0]) if args else DEFAULT_OUT

    rows = parse(wt)
    check(rows)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
