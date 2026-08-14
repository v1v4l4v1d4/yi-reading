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
        return reading_mod.reading(values)["judgement"]

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
        本 = reading_mod.reading([8, 9, 9, 9, 8, 8])["cast"]["primary"]["no"]
        之 = reading_mod.reading([8, 9, 9, 9, 8, 8])["cast"]["relating"]["no"]
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
        之 = reading_mod.reading([9, 8, 9, 9, 9, 9])["cast"]["relating"]["no"]
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
            j = reading_mod.reading(values)["judgement"]
            self.assertTrue(j["readings"], f"mask={mask:06b} 選不出經文")
            for r in j["readings"]:
                self.assertTrue(r["text"].strip())
            self.assertEqual(sum(1 for r in j["readings"] if r["role"] == "主"), 1)


class TestCommentary(unittest.TestCase):
    """注解的可用性必須如實上報——這條是「不得冒充原文」的機器判據。"""

    @classmethod
    def setUpClass(cls):
        cls.cov = load(SKILL / "data" / "commentary" / "coverage.json")["dongpo"]

    def test_覆蓋表自洽(self):
        covered, missing = set(self.cov["covered"]), set(self.cov["missing"])
        self.assertEqual(covered | missing, set(range(1, 65)))
        self.assertEqual(covered & missing, set())

    def test_聲稱有原文的都真有文件(self):
        for no in self.cov["covered"]:
            path = SKILL / "data" / "commentary" / "dongpo" / f"{no:02d}.json"
            self.assertTrue(path.exists(), f"第 {no} 卦聲稱已收錄但文件不在")
            self.assertGreater(len(load(path)["text"]), 200, f"第 {no} 卦原文過短")

    def test_聲稱沒有的就不能有文件(self):
        for no in self.cov["missing"]:
            path = SKILL / "data" / "commentary" / "dongpo" / f"{no:02d}.json"
            self.assertFalse(path.exists(), f"第 {no} 卦聲稱缺失卻存在文件——來源記錄不可信")

    def test_沒有原文時如實說明(self):
        entry = reading_mod.commentary([64])[0]
        self.assertFalse(entry["available"])
        self.assertIn("reason", entry)
        self.assertNotIn("text", entry)

    def test_有原文時給出處(self):
        entry = reading_mod.commentary([3])[0]
        self.assertTrue(entry["available"])
        self.assertIn("zh.wikisource.org", entry["source_url"])
        self.assertIn("屯", entry["text"])

    def test_頁面殘留模板痕跡就算抓壞了(self):
        """曾經有 14 個頁面把 {{header}} 的參數行當正文抓了進來。"""
        for no in self.cov["covered"]:
            text = load(SKILL / "data" / "commentary" / "dongpo" / f"{no:02d}.json")["text"]
            first = text.splitlines()[0]
            self.assertFalse(first.startswith(("|", "{{", "}}")), f"第 {no} 卦仍有模板殘留")
            self.assertNotIn("| title", text, f"第 {no} 卦仍有模板殘留")

    def test_每一則注都必須落在對應的卦(self):
        rows = {r["no"]: r for r in load(SKILL / "data" / "hexagrams.json")}
        for no in self.cov["covered"]:
            d = load(SKILL / "data" / "commentary" / "dongpo" / f"{no:02d}.json")
            self.assertEqual(d["no"], no)
            self.assertEqual(d["name"], rows[no]["name"])


class TestVerifyQuote(unittest.TestCase):
    def test_原文通過(self):
        self.assertTrue(verify_quote.verify("因世之“屯”，而務往以求功", verify_quote.dongpo_text(3)))

    def test_自撰不通過(self):
        self.assertFalse(verify_quote.verify("蘇軾以為，處屯之世宜靜以待時", verify_quote.dongpo_text(3)))

    def test_只忽略空白不忽略標點(self):
        src = verify_quote.dongpo_text(3)
        self.assertTrue(verify_quote.verify("因世之 “屯”，\n而務往以求功", src))
        self.assertFalse(verify_quote.verify("因世之屯而務往以求功", src), "去掉標點就不該算原文")

    def test_經傳也可核(self):
        self.assertTrue(verify_quote.verify("雲雷，屯；君子以經綸", verify_quote.jing_text(3)))
        self.assertFalse(verify_quote.verify("雲雷，屯；君子以經世", verify_quote.jing_text(3)))

    def test_缺原文時報缺而不是報無(self):
        with self.assertRaises(LookupError):
            verify_quote.dongpo_text(64)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
