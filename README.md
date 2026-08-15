# 乂

<sub>**English** · [简体中文](README.zh.md)</sub>

A conversational I Ching skill. It casts a hexagram, decides which line of the
classic actually applies, sends you the diagram, and reads it back to you —
with verbatim commentary from three Song-dynasty masters. Repo and skill name:
`yi-reading`.

**It does not tell fortunes.** The premise is Jung's synchronicity: the hexagram
does not forecast anything. It renders the state of mind you were in when you
asked into a shape you can look at. You see where you are standing, and the next
move grows out of having seen it. So there are no auspicious/inauspicious
verdicts here, and no answers to "will it work out" or "when".

## Install

```bash
npx skills add v1v4l4v1d4/yi-reading --skill yi-reading
```

## What it does

1. Takes the tangle you arrive with and narrows it to **a question that can be
   cast** — one about position and direction, not about outcome
2. Reads the rewritten question back and waits for you to confirm it
3. Casts by the **three-coin method**, six throws, reporting every throw
4. Sends the hexagram image (and the relating hexagram, if any line is moving)
5. Selects the line to read by Zhu Xi's *Kaobianzhan* (考變占) — **and tells you
   why that line and not another**
6. Reads it. **Brief by default**: plain language, under 200 characters, one
   sentence on what the hexagram is and two or three on your situation. It asks
   whether you want it opened up before giving the long form — original quotes,
   the commentators, line by line. Your preference is remembered

```
$ python3 skills/yi-reading/scripts/reading.py --values 9,8,8,6,7,8

第1擲　背、背、背　＝ 9　老陽　（動爻）
...
本卦　䷂ 水雷屯（第 3 卦）
動爻　初九、六四
之卦　䷬ 澤地萃（第 45 卦）

── 斷卦：二爻變 ──
朱熹《易學啟蒙·考變占》：二爻變，則以本卦二變爻辭占，仍以上爻為主。
兩爻俱動，讀本卦這兩條爻辭，以在上的第 4 爻為主。

[主] 水雷屯 六四　六四：乘馬班如，求婚媾，往，吉无不利。
[輔] 水雷屯 初九　初九：磐桓，利居貞，利建侯。
```

## Three rules written into the code

**The randomness comes from `secrets`, not `random`.** A reproducible
pseudo-random number and synchronicity are mutually exclusive — doing this with
a number that could have been computed in advance defeats the entire premise.
A static check in the test suite enforces it.

**If you attribute a line to someone, it has to be theirs.** A language model
can write a passage that sounds like Su Shi far more easily than it can quote
one, and the reader cannot tell the difference. Hence `verify_quote.py`: a
quotation must be a character-for-character substring of the stored source.
Only whitespace is ignored — punctuation and character variants are never
normalised, because normalising is just permission to alter the text. `--any`
searches all three commentaries plus the classic and reports where the line
came from, ready to paste into a citation. Anything in your own words stays in
your own voice: **quote it or don't sign someone's name to it.**

**The six-line-to-hexagram table is never transcribed by hand.**
`build_table.py` derives all 64 entries from the Unicode trigram symbols and
then checks itself against the structural invariant of the King Wen sequence
(each pair is either the inversion or the complement of the other). While
writing the design doc I transcribed that table by hand and got two entries
wrong — 屯 and 未濟 — and proofreading did not catch either. This kind of data
can only be held down by a machine.

## Development

```bash
python3 -m unittest discover -s tests -v      # 69 tests, standard library only
```

Build-time scripts (run only when changing data or restyling):

```bash
python3 skills/yi-reading/scripts/build_table.py       # derive the hexagram table
python3 skills/yi-reading/scripts/fetch_texts.py       # fetch the classic and its wings
python3 skills/yi-reading/scripts/fetch_commentary.py  # fetch all three commentaries, all 64
python3 skills/yi-reading/scripts/render_hexagrams.py  # render the 64 base images (build-time, needs rsvg-convert)
```

Sources and reasoning: [`skills/yi-reading/REFERENCE.md`](skills/yi-reading/REFERENCE.md)
(in Chinese).

## Commentaries

All three, complete, all 64 hexagrams, from the Siku Quanshu editions on
Chinese Wikisource:

| Commentator | Juan | Note |
|---|---|---|
| Su Shi 蘇軾, *Dongpo Yizhuan* | 1–6 | Hexagrams 1–35 also exist as punctuated subpages; those are preferred |
| Cheng Yi 程頤, *Yichuan Yizhuan* | 1–4 | Siku edition, unpunctuated |
| Zhu Xi 朱熹, *Zhouyi Benyi* | 1–2 | Siku edition, unpunctuated |

The Siku editions carry no punctuation, so quotations from them are kept short
and anything longer is paraphrased in the skill's own voice. Variant characters
are everywhere — 兌 alone appears as 兌, 兑 and 兊 — which is why the text is
split by hexagram *diagram* rather than by name. A `□` marks a character absent
from the scan's font; it is left as is and never guessed at.

## Known gaps

- The yarrow-stalk method is not implemented (the interface is reserved). The
  default is the coin method — which is what Jung used when he cast for the
  Wilhelm/Baynes edition
- The 64 built-in images carry no moving-line marks, since 2⁶ combinations
  cannot be pre-generated. When a line moves, the ○/× marks are composited onto
  the base image with the standard library — **no runtime dependency**.
  `rsvg-convert` is needed only at build time, to render the 64 base images

## Text sources and licence

**The classic and all three commentaries are in the public domain** — the
*Zhouyi* and its wings are pre-Qin, and Su Shi, Cheng Yi and Zhu Xi were all
Song-dynasty writers. The transcriptions bundled here come from **Chinese
Wikisource** (every data file carries its own `source_url`), which publishes
under CC BY-SA 4.0; keep the attribution if you reuse them. The 64 hexagram
images are generated by `scripts/render_hexagrams.py` and involve no
third-party assets.

The code is MIT licensed — see [LICENSE](LICENSE).
