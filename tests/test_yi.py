#!/usr/bin/env python3
"""yi-reading 的回歸測試。只用標準庫：`python3 -m unittest discover tests`。

這些測試守的是同一件事：**錯了也看不出來的錯**。
卦畫錯一位、斷卦選錯一句、隨機源被換成 random——輸出照樣通順、照樣像那麼回事，
沒有任何外部信號提示。所以判據必須是機器可執行的，不能靠讀一遍覺得對。
"""

from __future__ import annotations

import collections
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "yi-reading"
sys.path.insert(0, str(SKILL / "scripts"))

import cast as cast_mod  # noqa: E402
import reading as reading_mod  # noqa: E402
import verify_quote  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestHexagramTable(unittest.TestCase):
    """六爻 → 卦序的映射。手抄這張表必錯，所以全覆蓋校驗。"""

    @classmethod
    def setUpClass(cls):
        cls.rows = load(SKILL / "data" / "hexagrams.json")

    def test_sixty_four_distinct(self):
        self.assertEqual(len(self.rows), 64)
        self.assertEqual([r["no"] for r in self.rows], list(range(1, 65)))
        self.assertEqual(len({r["name"] for r in self.rows}), 64)

    def test_covers_every_pattern(self):
        pats = {r["lines"] for r in self.rows}
        self.assertEqual(pats, {f"{i:06b}" for i in range(64)})

    def test_anchors(self):
        """獨立已知的錨點。寫 SPEC 時我在屯和未濟上各錯過一次，就是靠這一條發現的。"""
        want = {
            1: "111111", 2: "000000", 3: "100010", 4: "010001",
            11: "111000", 12: "000111", 29: "010010", 30: "101101",
            63: "101010", 64: "010101",
        }
        by_no = {r["no"]: r for r in self.rows}
        for no, lines in want.items():
            self.assertEqual(by_no[no]["lines"], lines, f"第 {no} 卦 {by_no[no]['name']}")

    def test_king_wen_pair_invariant(self):
        """序卦兩兩成對：後者是前者的反覆；反覆與自身相同時取其錯（旁通）。"""
        by_no = {r["no"]: r for r in self.rows}
        for k in range(1, 33):
            a, b = by_no[2 * k - 1]["lines"], by_no[2 * k]["lines"]
            expect = a[::-1] if a[::-1] != a else "".join("1" if c == "0" else "0" for c in a)
            self.assertEqual(b, expect, f"第 {2*k-1}/{2*k} 卦")

    def test_trigrams_match_lines(self):
        bits = {"乾": "111", "兌": "110", "離": "101", "震": "100",
                "巽": "011", "坎": "010", "艮": "001", "坤": "000"}
        for r in self.rows:
            self.assertEqual(bits[r["lower"]] + bits[r["upper"]], r["lines"], r["name"])

    def test_每卦六爻齊全(self):
        for r in self.rows:
            self.assertEqual([y["pos"] for y in r["yao"]], [1, 2, 3, 4, 5, 6], r["name"])
            for y in r["yao"]:
                self.assertTrue(y["text"].strip(), f"{r['name']} {y['title']} 爻辭為空")
            self.assertTrue(r["gua_ci"].strip() and r["da_xiang"].strip(), r["name"])

    def test_爻題與陰陽相符(self):
        for r in self.rows:
            for y in r["yao"]:
                yang = r["lines"][y["pos"] - 1] == "1"
                self.assertEqual(y["title"], cast_mod.yao_title(y["pos"], yang), r["name"])

    def test_乾坤有二用(self):
        by_no = {r["no"]: r for r in self.rows}
        self.assertIn("用九", by_no[1]["extra"])
        self.assertIn("用六", by_no[2]["extra"])


class TestCast(unittest.TestCase):
    def test_四象映射(self):
        self.assertEqual(cast_mod.FOUR_SYMBOLS[6], ("老陰", "0", True))
        self.assertEqual(cast_mod.FOUR_SYMBOLS[7], ("少陽", "1", False))
        self.assertEqual(cast_mod.FOUR_SYMBOLS[8], ("少陰", "0", False))
        self.assertEqual(cast_mod.FOUR_SYMBOLS[9], ("老陽", "1", True))

    def test_硬幣約定寫死(self):
        """背 3 陽、字 2 陰。這個約定一翻，老陰老陽整體對調，卦全錯而不報錯。"""
        self.assertEqual((cast_mod.BEI, cast_mod.ZI), (3, 2))
        self.assertEqual({cast_mod.toss_coin() for _ in range(200)}, {2, 3})

    def test_自下而上(self):
        """第一擲是初爻。屯 100010：初九動、六四動 → 之卦萃。"""
        r = cast_mod.cast([9, 8, 8, 6, 7, 8])
        self.assertEqual(r["primary"]["lines"], "100010")
        self.assertEqual(r["primary"]["no"], 3)
        self.assertEqual(r["moving"], [1, 4])
        self.assertEqual(r["moving_titles"], ["初九", "六四"])
        self.assertEqual(r["relating"]["no"], 45)

    def test_無動爻則無之卦(self):
        self.assertIsNone(cast_mod.cast([7, 7, 7, 7, 7, 7])["relating"])
        self.assertEqual(cast_mod.cast([7, 7, 7, 7, 7, 7])["primary"]["no"], 1)

    def test_老陽老陰各自翻面(self):
        r = cast_mod.cast([9, 9, 9, 6, 6, 6])
        self.assertEqual(r["primary"]["lines"], "111000")  # 泰
        self.assertEqual(r["relating"]["lines"], "000111")  # 否
        self.assertEqual((r["primary"]["no"], r["relating"]["no"]), (11, 12))

    def test_純卦全名(self):
        self.assertEqual(cast_mod.cast([7] * 6)["primary"]["full_name"], "乾為天")
        self.assertEqual(cast_mod.cast([8] * 6)["primary"]["full_name"], "坤為地")
        self.assertEqual(cast_mod.cast([9, 8, 8, 8, 7, 8])["primary"]["full_name"], "水雷屯")

    def test_拒絕非法輸入(self):
        for bad in ([7, 7, 7], [7, 7, 7, 7, 7, 5], [10] * 6):
            with self.assertRaises(ValueError):
                cast_mod.cast(bad)


class TestRandomSource(unittest.TestCase):
    """隨機源必須是 secrets。random 可復現，用它做共時性占卜是自我拆台。"""

    def test_cast_不引入_random(self):
        src = (SKILL / "scripts" / "cast.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*import\s+random\b", src, re.M))
        self.assertIsNone(re.search(r"^\s*from\s+random\s+import\b", src, re.M))
        self.assertIsNotNone(re.search(r"^\s*import\s+secrets\b", src, re.M))

    def test_分布(self):
        """蒙特卡洛：老陽 1/8、少陰 3/8、少陽 3/8、老陰 1/8，各差 ≤1 個百分點。"""
        n = 100_000
        counts = collections.Counter(sum(cast_mod.toss_coin() for _ in range(3)) for _ in range(n))
        for value, expect in ((6, 0.125), (7, 0.375), (8, 0.375), (9, 0.125)):
            self.assertAlmostEqual(counts[value] / n, expect, delta=0.01, msg=f"和為 {value}")

    def test_動爻概率四分之一(self):
        n = 60_000
        moving = sum(1 for _ in range(n) if sum(cast_mod.toss_coin() for _ in range(3)) in (6, 9))
        self.assertAlmostEqual(moving / n, 0.25, delta=0.01)


class TestKaobianzhan(unittest.TestCase):
    """考變占七條。這一步錯了，後面所有話都跟著錯，且沒有任何外部信號。"""

    def read(self, values):
        """只走起卦與斷卦，繞開發圖——這裏測的是選句子，不是渲染。
        （繞開也順帶讓這批用例不依賴 rsvg-convert，且快兩個數量級。）"""
        c = cast_mod.cast(values)
        primary = cast_mod.by_lines(c["primary"]["lines"])
        relating = cast_mod.by_lines(c["relating"]["lines"]) if c["relating"] else None
        return reading_mod.select(primary, c["moving"], relating)

    def test_零爻變讀本卦卦辭(self):
        j = self.read([8, 7, 8, 7, 8, 7])  # 未濟，六爻不動
        self.assertEqual(j["moving_count"], 0)
        self.assertEqual([r["kind"] for r in j["readings"]], ["卦辭"])
        self.assertEqual(j["readings"][0]["hexagram_no"], 64)
        self.assertIn("貞", j["why"])  # 內卦為貞、外卦為悔

    def test_一爻變讀本卦該爻(self):
        j = self.read([9, 8, 8, 7, 8, 8])  # 震，初九動
        self.assertEqual(j["moving_count"], 1)
        self.assertEqual(len(j["readings"]), 1)
        r = j["readings"][0]
        self.assertEqual((r["kind"], r["hexagram_no"], r["pos"], r["title"]), ("爻辭", 51, 1, "初九"))

    def test_二爻變以上爻為主(self):
        j = self.read([9, 8, 8, 6, 7, 8])  # 屯，初九、六四動
        self.assertEqual(j["moving_count"], 2)
        主, 輔 = j["readings"]
        self.assertEqual((主["role"], 主["pos"], 主["hexagram_no"]), ("主", 4, 3))
        self.assertEqual((輔["role"], 輔["pos"], 輔["hexagram_no"]), ("輔", 1, 3))

    def test_三爻變前十卦主貞(self):
        j = self.read([9, 9, 9, 8, 8, 8])  # 泰 → 坤，動爻 (1,2,3) 列第 1 位
        self.assertEqual(j["moving_count"], 3)
        主, 輔 = j["readings"]
        self.assertEqual([r["kind"] for r in j["readings"]], ["卦辭", "卦辭"])
        self.assertEqual((主["role"], 主["hexagram_no"]), ("主", 11))  # 本卦
        self.assertEqual((輔["role"], 輔["hexagram_no"]), ("輔", 2))  # 之卦

    def test_三爻變後十卦主悔(self):
        j = self.read([8, 9, 9, 9, 8, 8])  # 動爻 (2,3,4) 列第 11 位
        主, 輔 = j["readings"]
        self.assertEqual(主["role"], "主")
        self.assertGreater(reading_mod.triple_rank([2, 3, 4]), 10)
        c = cast_mod.cast([8, 9, 9, 9, 8, 8])
        本, 之 = c["primary"]["no"], c["relating"]["no"]
        self.assertEqual(主["hexagram_no"], 之)
        self.assertEqual(輔["hexagram_no"], 本)

    def test_變卦圖次序的四個錨點(self):
        """《易學啟蒙通釋》：乾三爻變「自否至恒為前十卦，自益至泰為後十卦」；
        坤三爻變「自泰至益為前十卦，自恒至否為後十卦」。四個錨點釘死這個排序。"""
        def 之卦(本: str, moving) -> int:
            bits = list(本)
            for p in moving:
                bits[p - 1] = "1" if bits[p - 1] == "0" else "0"
            return cast_mod.by_lines("".join(bits))["no"]

        乾, 坤 = "111111", "000000"
        self.assertEqual(之卦(乾, reading_mod.TRIPLES[0]), 12)   # 否
        self.assertEqual(之卦(乾, reading_mod.TRIPLES[9]), 32)   # 恒 ← 前十之末
        self.assertEqual(之卦(乾, reading_mod.TRIPLES[10]), 42)  # 益 ← 後十之首
        self.assertEqual(之卦(乾, reading_mod.TRIPLES[19]), 11)  # 泰
        self.assertEqual(之卦(坤, reading_mod.TRIPLES[0]), 11)   # 泰
        self.assertEqual(之卦(坤, reading_mod.TRIPLES[9]), 42)   # 益
        self.assertEqual(之卦(坤, reading_mod.TRIPLES[10]), 32)  # 恒
        self.assertEqual(之卦(坤, reading_mod.TRIPLES[19]), 12)  # 否

    def test_三爻變二十種組合都有歸屬(self):
        seen = {reading_mod.triple_rank(list(t)) for t in itertools.combinations(range(1, 7), 3)}
        self.assertEqual(seen, set(range(1, 21)))

    def test_四爻變讀之卦二不變爻以下爻為主(self):
        j = self.read([9, 9, 9, 9, 7, 8])  # 夬 → 比，不變爻為五、上
        self.assertEqual(j["moving_count"], 4)
        主, 輔 = j["readings"]
        self.assertEqual((主["role"], 主["pos"], 主["hexagram_no"]), ("主", 5, 8))
        self.assertEqual((輔["role"], 輔["pos"], 輔["hexagram_no"]), ("輔", 6, 8))
        self.assertTrue(all(r["hexagram_no"] == 8 for r in j["readings"]), "須讀之卦")

    def test_五爻變讀之卦唯一不變爻(self):
        j = self.read([9, 8, 9, 9, 9, 9])  # 只有第 2 爻不動
        self.assertEqual(j["moving_count"], 5)
        self.assertEqual(len(j["readings"]), 1)
        r = j["readings"][0]
        之 = cast_mod.cast([9, 8, 9, 9, 9, 9])["relating"]["no"]
        self.assertEqual((r["pos"], r["hexagram_no"], r["kind"]), (2, 之, "爻辭"))

    def test_六爻變乾占用九(self):
        j = self.read([9] * 6)
        self.assertEqual(j["readings"][0]["kind"], "用九")
        self.assertEqual(j["readings"][0]["text"], "用九：見羣龍无首，吉。")

    def test_六爻變坤占用六(self):
        j = self.read([6] * 6)
        self.assertEqual(j["readings"][0]["kind"], "用六")
        self.assertEqual(j["readings"][0]["text"], "用六：利永貞。")

    def test_六爻變餘卦讀之卦卦辭(self):
        j = self.read([6, 9, 9, 9, 9, 9])  # 姤 → 復
        self.assertEqual(j["moving_count"], 6)
        self.assertEqual(j["readings"][0]["kind"], "卦辭")
        self.assertEqual(j["readings"][0]["hexagram_no"], 24)

    def test_每個分支都給出理由(self):
        """第五步要把「為什麼讀這一句」講給用戶聽，所以 why 不能為空。"""
        for values in ([7] * 6, [9] + [7] * 5, [9, 9] + [7] * 4, [9] * 3 + [7] * 3,
                       [9] * 4 + [7] * 2, [9] * 5 + [7], [9] * 6):
            j = self.read(values)
            self.assertTrue(j["why"].strip(), f"{values} 沒有給理由")
            self.assertTrue(j["rule_text"].strip())
            self.assertEqual(j["rule_source"], "朱熹《易學啟蒙·考變占》")

    def test_窮舉所有動爻組合不崩(self):
        """2^6 = 64 種動爻組合全跑一遍：任何一種都必須選得出句子。"""
        for mask in range(64):
            values = [9 if mask >> i & 1 else 7 for i in range(6)]
            j = self.read(values)
            self.assertTrue(j["readings"], f"mask={mask:06b} 選不出經文")
            for r in j["readings"]:
                self.assertTrue(r["text"].strip())
            self.assertEqual(sum(1 for r in j["readings"] if r["role"] == "主"), 1)


class TestCommentary(unittest.TestCase):
    """三家注：六十四卦一卦不缺，每卦都能報出處。占到哪一卦都得有東西可引。"""

    WORKS = ("dongpo", "yichuan", "benyi")

    @classmethod
    def setUpClass(cls):
        cls.cov = load(SKILL / "data" / "commentary" / "coverage.json")
        cls.rows = {r["no"]: r for r in load(SKILL / "data" / "hexagrams.json")}

    def test_三家皆覆蓋六十四卦(self):
        for slug in self.WORKS:
            self.assertEqual(self.cov[slug]["covered"], list(range(1, 65)), slug)

    def test_每卦每家都有文件且不算短(self):
        for slug in self.WORKS:
            for no in range(1, 65):
                path = SKILL / "data" / "commentary" / slug / f"{no:02d}.json"
                self.assertTrue(path.exists(), f"{slug} 缺第 {no} 卦")
                self.assertGreater(len(load(path)["text"]), 200, f"{slug} 第 {no} 卦過短")

    def test_每一則注都落在對應的卦(self):
        for slug in self.WORKS:
            for no in range(1, 65):
                d = load(SKILL / "data" / "commentary" / slug / f"{no:02d}.json")
                self.assertEqual(d["no"], no)
                self.assertEqual(d["name"], self.rows[no]["name"], f"{slug} 第 {no} 卦")

    def test_出處齊備且卷次合理(self):
        """引用要括注到卷，所以 citation 與 juan 必須齊、必須對得上。"""
        limits = {"dongpo": 6, "yichuan": 4, "benyi": 2}
        for slug in self.WORKS:
            for no in range(1, 65):
                d = load(SKILL / "data" / "commentary" / slug / f"{no:02d}.json")
                self.assertTrue(1 <= d["juan"] <= limits[slug], f"{slug} 第 {no} 卦 卷{d['juan']}")
                self.assertTrue(d["citation"].startswith(f"《{d['work']}·卷"), d["citation"])
                self.assertTrue(d["citation"].endswith("》"), d["citation"])
                self.assertIn("zh.wikisource.org", d["source_url"])

    def test_卷次隨卦序單調(self):
        """卦序往後走，卷次只能不減。一旦回頭，說明切分把某卦歸錯了卷。"""
        for slug in self.WORKS:
            juan = [load(SKILL / "data" / "commentary" / slug / f"{n:02d}.json")["juan"]
                    for n in range(1, 65)]
            self.assertEqual(juan, sorted(juan), slug)

    def test_沒有模板殘留(self):
        """曾經有 14 個頁面把 {{header}} 的參數行當正文抓了進來。"""
        for slug in self.WORKS:
            for no in range(1, 65):
                text = load(SKILL / "data" / "commentary" / slug / f"{no:02d}.json")["text"]
                self.assertFalse(text.splitlines()[0].startswith(("|", "{{", "}}")),
                                 f"{slug} 第 {no} 卦有模板殘留")
                for junk in ("{{SK", "| title", "SKQS header", "onlyinclude"):
                    self.assertNotIn(junk, text, f"{slug} 第 {no} 卦殘留 {junk}")

    def test_reading_帶回三家並各有出處(self):
        entry = reading_mod.commentary([47])[0]
        self.assertEqual(len(entry["commentators"]), 3)
        for c in entry["commentators"]:
            self.assertTrue(c["available"])
            self.assertTrue(c["citation"] and c["author"] and c["text"])

    def test_後半段的卦也有蘇注(self):
        """第一版只有 1–35 卦，占到後面就沒得引。這一條盯住那個缺口不再出現。"""
        for no in (36, 47, 54, 64):
            c = next(x for x in reading_mod.commentary([no])[0]["commentators"]
                     if x["slug"] == "dongpo")
            self.assertTrue(c["available"] and len(c["text"]) > 200, f"第 {no} 卦無蘇注")


class TestVerifyQuote(unittest.TestCase):
    """語言模型寫一段像蘇軾的話，比引對一段真的蘇軾容易得多，而讀者分不出來。
    所以「引誰的話必須真是誰的話」不能靠自覺，要有judge得了的判據。"""

    def test_原文通過(self):
        self.assertTrue(verify_quote.verify("因世之“屯”，而務往以求功", verify_quote.dongpo_text(3)))
        self.assertTrue(verify_quote.verify("困者坐而見制", verify_quote.dongpo_text(47)))

    def test_自撰不通過(self):
        self.assertFalse(verify_quote.verify("蘇軾以為，處屯之世宜靜以待時", verify_quote.dongpo_text(3)))

    def test_只忽略空白不忽略標點(self):
        src = verify_quote.dongpo_text(3)
        self.assertTrue(verify_quote.verify("因世之 “屯”，\n而務往以求功", src))
        self.assertFalse(verify_quote.verify("因世之屯而務往以求功", src), "去掉標點就不該算原文")

    def test_經傳也可核(self):
        self.assertTrue(verify_quote.verify("雲雷，屯；君子以經綸", verify_quote.jing_text(3)))
        self.assertFalse(verify_quote.verify("雲雷，屯；君子以經世", verify_quote.jing_text(3)))

    def test_三家都可核(self):
        self.assertTrue(verify_quote.verify("行吾義而已", verify_quote.work_entry("yichuan", 47)["text"]))
        self.assertTrue(verify_quote.verify("當務晦黙", verify_quote.work_entry("benyi", 47)["text"]))

    def test_未收的數據要報錯而不是靜默通過(self):
        with self.assertRaises(LookupError):
            verify_quote.work_entry("dongpo", 99)


class TestAssets(unittest.TestCase):
    """64 張卦象圖與經文表必須一一對上。缺一張，占到它就發不出圖。"""

    def setUp(self):
        self.dir = SKILL / "assets" / "hexagrams"
        if not self.dir.exists() or not any(self.dir.glob("*.png")):
            self.skipTest("卦象圖尚未生成")

    def test_六十四張齊全且命名一致(self):
        rows = load(SKILL / "data" / "hexagrams.json")
        want = {f"{r['no']:02d}-{r['name']}.png" for r in rows}
        have = {p.name for p in self.dir.glob("*.png")}
        self.assertEqual(have, want, f"缺 {sorted(want - have)}；多 {sorted(have - want)}")

    def test_都不是空文件(self):
        for p in sorted(self.dir.glob("*.png")):
            self.assertGreater(p.stat().st_size, 1000, f"{p.name} 過小，多半沒渲染出來")


class TestMovingMarks(unittest.TestCase):
    """動爻記號畫錯位置，圖上就會指着另一條爻說它在動——而且看不出來。"""

    def setUp(self):
        import render_hexagrams
        self.r = render_hexagrams

    def test_老陽記圈老陰記叉(self):
        marks = self.r.moving_marks("100010", [1, 4])  # 屯：初九陽動、六四陰動
        self.assertEqual(len(marks), 2)
        self.assertIn("<circle", marks[0], "初九是陽爻，該記 ○")
        self.assertIn("<path", marks[1], "六四是陰爻，該記 ×")

    def test_記號對準所指的那一爻(self):
        """爻位自下而上，圖自上而下畫。這個翻轉錯了，記號會整體上下顛倒。"""
        import re
        for pos in range(1, 7):
            mark = self.r.moving_marks("111111", [pos])[0]
            cy = float(re.search(r'cy="([\d.]+)"', mark).group(1))
            bar_top = self.r.TOP + (6 - pos) * self.r.PITCH
            self.assertAlmostEqual(cy, bar_top + self.r.BAR_T / 2, places=3, msg=f"第 {pos} 爻")

    def test_上爻在最上初爻在最下(self):
        import re
        ys = [float(re.search(r'cy="([\d.]+)"', self.r.moving_marks("111111", [p])[0]).group(1))
              for p in range(1, 7)]
        self.assertEqual(ys, sorted(ys, reverse=True), "爻位越高，y 應越小")

    def test_無動爻就沒有記號(self):
        self.assertEqual(self.r.moving_marks("100010", []), [])

    def test_圖上寫出的爻題與_cast_一致(self):
        for pos in range(1, 7):
            for yang in (True, False):
                self.assertEqual(self.r.yao_title(pos, yang), cast_mod.yao_title(pos, yang))

    def test_svg_帶動爻時寫出爻題(self):
        h = self.r.hexagram(3)
        out = self.r.svg(h, [1, 4])
        self.assertIn("動爻", out)
        self.assertIn("初九、六四", out)
        self.assertNotIn("動爻", self.r.svg(h), "無動爻時不該有這一行")

    def test_無動爻直接用內置圖(self):
        p = self.r.render_cast(47, [])
        self.assertEqual(p.name, "47-困.png")
        self.assertTrue(p.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
