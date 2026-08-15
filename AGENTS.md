# AGENTS.md

給在這個倉庫裏幹活的 agent。

## 這是什麼

一個 `npx skills` 標準 skills 倉庫。目前只有一個 skill：`skills/yi-reading/`。

```
README.md              倉庫說明
AGENTS.md              本文件
CLAUDE.md              一行，指向本文件
skills.sh.json         skills.sh 注冊元數據
tests/test_yi.py       回歸測試，零依賴
skills/
  yi-reading/
    SKILL.md           對話流程、解讀寫法、禁止事項
    REFERENCE.md       斷卦規則的原文出處與驗算
    scripts/           起卦、斷卦、驗引文；另有三個構建期腳本
    data/              經傳、注解、覆蓋記錄
    assets/hexagrams/  64 張 PNG（svg/ 下為源）
```

## 四條不能破的規矩

**1. 隨機源是 `secrets`。** `cast.py` 裏不許出現 `import random`。
可復現的偽隨機與共時性互斥——這是這個項目的立足點，不是風格偏好。
`tests/test_yi.py::TestRandomSource` 有靜態檢查。

**2. 引誰的話必須真是誰的話。** 這條有機器判據，不靠自覺：
`verify_quote.py` 要求引文是庫中原文的逐字子串（`--any` 還會報出處）。
三家注各 64 卦，測試逐卦查文件在不在、卷次對不對、有沒有模板殘留。
**轉述不署名**——要麼真引，要麼別掛在注家名下。

**3. 卦畫數據不手抄。** 六爻與卦名的對應無法肉眼校對。
要改就改 `build_table.py`（從八卦符號推導＋結構不變量自校驗），
不要直接編輯 `hexagrams.json` 裏的 `lines`。

**4. 數據與圖必須待在 `skills/yi-reading/` 內部。**
`npx skills add` 只安裝 `skills/<name>/` 這個目錄；挪到倉庫根，
skill 裝到用戶機器上就是壞的。

## 改動之後

```bash
python3 -m unittest discover -s tests
```

62 個測試，只用標準庫，跑完不到一秒。**斷卦邏輯改了必須全綠再提交**
——考變占選錯句子不會報錯，輸出照樣通順，沒有任何外部信號。

改數據或圖：

```bash
python3 skills/yi-reading/scripts/build_table.py            # → data/_table.json
python3 skills/yi-reading/scripts/fetch_texts.py            # → data/hexagrams.json
python3 skills/yi-reading/scripts/fetch_commentary.py       # → data/commentary/（三家）
python3 skills/yi-reading/scripts/render_hexagrams.py       # → assets/（需 rsvg-convert）
```

抓取一律走 MediaWiki API，不解析 HTML。ctext.org 對自動訪問彈驗證碼，
不是可用來源，也不要去繞過。

**判定「某個源不存在」之前，先用 `list=allpages&apprefix=` 把命名空間枚舉一遍。**
這個坑踩過兩次：先是只驗了 `東坡易傳/01` 就斷言 64 卦齊全，
後是只看了那套子頁就斷言只有 35 卦——兩次都是拿樣本當全集。

## 新增 skill

放在 `skills/<name>/`，帶 `SKILL.md`（frontmatter 需 `name` 與 `description`），
然後在 `skills.sh.json` 的分組裏登記。
