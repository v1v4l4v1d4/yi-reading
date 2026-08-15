# AGENTS.md

给在这个仓库里干活的 agent。

## 这是什么

一个 `npx skills` 标准 skills 仓库。目前只有一个 skill：`skills/yi-reading/`。

```
README.md              仓库说明（英文，主体）
README.zh.md           仓库说明（简体中文）
AGENTS.md              本文件
CLAUDE.md              一行，指向本文件
LICENSE                MIT
skills.sh.json         skills.sh 注册元数据
tests/test_yi.py       回归测试，零依赖
skills/
  yi-reading/
    SKILL.md           对话流程、解读写法、禁止事项
    REFERENCE.md       断卦规则的原文出处与验算
    scripts/           起卦、断卦、验引文、数简读字数；另有四个构建期脚本
    data/              经传、注解、覆盖记录
    assets/hexagrams/  64 张 PNG（svg/ 下为源）
```

改动文档时注意：**README.md 是英文主体，README.zh.md 是中文版，两边都要改。**
两个文件顶部互相链接。

## 四条不能破的规矩

**1. 随机源是 `secrets`。** `cast.py` 里不许出现 `import random`。
可复现的伪随机与共时性互斥——这是这个项目的立足点，不是风格偏好。
`tests/test_yi.py::TestRandomSource` 有静态检查。

**2. 引谁的话必须真是谁的话。** 这条有机器判据，不靠自觉：
`verify_quote.py` 要求引文是库中原文的逐字子串（`--any` 还会报出处）。
三家注各 64 卦，测试逐卦查文件在不在、卷次对不对、有没有模板残留。
**转述不署名**——要么真引，要么别挂在注家名下。

**3. 卦画数据不手抄。** 六爻与卦名的对应无法肉眼校对。
要改就改 `build_table.py`（从八卦符号推导＋结构不变量自校验），
不要直接编辑 `hexagrams.json` 里的 `lines`。

**4. 数据与图必须待在 `skills/yi-reading/` 内部。**
`npx skills add` 只安装 `skills/<name>/` 这个目录；挪到仓库根，
skill 装到用户机器上就是坏的。

## 改动之后

```bash
python3 -m unittest discover -s tests
```

62 个测试，只用标准库，跑完不到一秒。**断卦逻辑改了必须全绿再提交**
——考变占选错句子不会报错，输出照样通顺，没有任何外部信号。

改数据或图：

```bash
python3 skills/yi-reading/scripts/build_table.py            # → data/_table.json
python3 skills/yi-reading/scripts/fetch_texts.py            # → data/hexagrams.json
python3 skills/yi-reading/scripts/fetch_commentary.py       # → data/commentary/（三家）
python3 skills/yi-reading/scripts/render_hexagrams.py       # → assets/（需 rsvg-convert）
```

抓取一律走 MediaWiki API，不解析 HTML。ctext.org 对自动访问弹验证码，
不是可用来源，也不要去绕过。

**判定「某个源不存在」之前，先用 `list=allpages&apprefix=` 把命名空间枚举一遍。**
这个坑踩过两次：先是只验了 `東坡易傳/01` 就断言 64 卦齐全，
后是只看了那套子页就断言只有 35 卦——两次都是拿样本当全集。

## 新增 skill

放在 `skills/<name>/`，带 `SKILL.md`（frontmatter 需 `name` 与 `description`），
然后在 `skills.sh.json` 的分组里登记。
