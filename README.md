# 注音碼（zhuyin-code）

> 把商品名稱轉成「唸得出來就打得出來」的搜尋碼。

```
SF-9950三花彩色長袖圓領L   →   SF9950NCHNTVMXL
優生寬口徑奶瓶蓋           →   UGDDRSQE
嬌生嬰兒睡眠沐浴精1000ML   →   RGU-GAAMR1000ML
```

## 由來

30 多年前，百貨五金的批發中盤商開始電腦化，最大的難題是**出貨時怎麼把商品快速輸入電腦**：

1. 商品不可能逐一貼店內碼，上面只有原廠印刷的品名；廠商的商品編號又可能重複，不能拿來用。
2. 商品種類繁多，商品檔超過 5 萬筆的業者比比皆是。

「注音碼」的作法是：品名的每個中文字取**第一個注音符號**在鍵盤上對應的按鍵，英數字照抄。出貨人員看著商品**唸得出名稱**，就能輸入品名的一部分，系統列出符合的商品清單，再從中挑選即可。

當年靠倚天中文系統的「中文轉注音」功能產生注音碼。進入 Windows 時代後，中文由作業系統處理，這個功能就沒了。本專案把注音碼重新實作成**開源對照表＋各語言薄殼**，任何平台、任何程式語言都能使用。

> 附註：Windows 11 的微軟注音輸入法雖然有 `IFELanguage::GetPhonetic` 介面，但對中文會回傳 `E_NOTIMPL`（實測），沒辦法拿來使用。

## 編碼規則

| 輸入字元 | 處理方式 | 例 |
|---|---|---|
| 中文字 | 依**編碼體系**每字取 1 鍵（見下） | 三 → `N` |
| 英文、數字 | 照抄並轉大寫（全形先轉半形） | `ｍｌ` → `ML` |
| 空白 | 略過 | |
| 符號 | 依 `config.toml` 設定略過或保留 | `SF-9950` → `SF9950` |

### 編碼體系（scheme）

| 體系 | 取法 | 範例 | 多音字問題 |
|---|---|---|---|
| `zhuyin` 注音 | 最常用讀音的**第一個注音符號** → 大千鍵盤按鍵 | 三ㄙ→`N`、安ㄢ→`0`、兒ㄦ→`-` | 有，以詞組表與場景覆寫表處理 |
| `cangjie` 倉頡 | 倉頡五代的**第一碼** | 三→`M`、花→`T` | 沒有（倉頡依字形編碼） |

不熟悉注音的使用者可以改用倉頡。如果資料庫為每個商品預先存好各體系的碼，系統就能依使用者的偏好切換。

### 大千注音鍵盤對照

```
ㄅ1 ㄉ2 ˇ3 ˋ4 ㄓ5 ˊ6 ˙7 ㄚ8 ㄞ9 ㄢ0 ㄦ-
ㄆQ ㄊW ㄍE ㄐR ㄔT ㄗY ㄧU ㄛI ㄟO ㄣP
ㄇA ㄋS ㄎD ㄑF ㄕG ㄘH ㄨJ ㄜK ㄠL ㄤ;
ㄈZ ㄌX ㄏC ㄒV ㄖB ㄙN ㄩM ㄝ, ㄡ. ㄥ/
```

⚠️ 注音碼裡的數字和 `-` **不一定是品名原本就有的字元**。例如「安」的ㄢ會變成 `0`，「兒」的ㄦ會變成 `-`。所以「略過符號」只能對**品名原文**做，不能把轉好的碼再刪一次。

## 多音字與場景覆寫

同一個字在不同詞中讀音不同，例如「長袖」讀ㄔ（`T`），「長大」讀ㄓ（`5`）。轉碼時依下面的優先順序處理：

1. **場景覆寫表**（`data/profiles/<場景>/<體系>.tsv`）：最長比對，命中的詞先鎖定。
2. **一般詞組表**（`data/<體系>/phrases.tsv`）：在還沒鎖定的區段中做最長比對。
3. **單字表**（`data/<體系>/chars.tsv`）：剩下的字逐字查。

場景覆寫表的優先權最高。一般詞庫偶爾會跨詞誤判，例如「彩色長袖」裡被切出「色長」（職稱，讀ㄓㄤˇ），只要在商品場景加一行「長袖→TV」就能修正。不同場景（商品、人名…）可以各自維護一份覆寫表。

## 資料格式（跨語言共用）

所有對照表都是 **UTF-8、LF 換行、Tab 分隔**，`#` 開頭的行是註解：

```
data/
├── zhuyin/chars.tsv          字 → 鍵（預設讀音），41,000+ 字
├── zhuyin/phrases.tsv        詞 → 鍵序列（只收與逐字結果不同的詞）
├── cangjie/chars.tsv         字 → 倉頡首碼，21,000+ 字
└── profiles/product/zhuyin.tsv  商品場景覆寫表
```

```tsv
# 範例：data/profiles/product/zhuyin.tsv
長袖	TV
短袖	2V
```

覆寫表中**單一字**的條目會蓋過單字表，**兩字以上**的條目則是優先比對的詞組。

## 支援語言

注音碼的核心是 `data/` 底下的對照表，**任何語言都能使用**。[`examples/`](examples/) 目錄提供 **C#、JavaScript、Java、Python、C、C++** 六種語言的單檔範例，都對同一份真實商品資料驗證，輸出完全一致。

| C# | JavaScript | Java | Python | C | C++ |
|:-:|:-:|:-:|:-:|:-:|:-:|
| ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## SQL Server 版

[`sql/`](sql/) 提供純 T-SQL 的實作：轉碼函數 `dbo.fn_ZhuyinCode`，以及商品新增或修改時**由 trigger 自動產生注音碼**的範例。3,000 筆實際商品的結果，跟其他語言逐筆完全一致；轉碼約 2.5 ms／筆，日常建檔感覺不到延遲。詳見 [sql/README.md](sql/README.md)。

## 效能評測

以 **3,000 筆實際商品名稱**（品名 3–29 字，共 15,619 個中文字，對照表覆蓋率 100%）實測，每種語言跑 3 次取中位數：

| 語言 | 載入時間 | 平均每筆轉碼 | 每秒可轉 | 載入記憶體 |
|---|--:|--:|--:|--:|
| C | 12.0 ms | 0.73 µs | 約 137 萬筆 | 2.6 MB |
| C++ | 13.6 ms | 1.81 µs | 約 55 萬筆 | 3.3 MB |
| Java | 53.4 ms | 2.57 µs | 約 39 萬筆 | 6.2 MB |
| JavaScript | 27.5 ms | 4.14 µs | 約 24 萬筆 | 3.1 MB |
| C# | 27.1 ms | 4.50 µs | 約 22 萬筆 | 4.6 MB |
| Python | 26.3 ms | 10.44 µs | 約 10 萬筆 | 4.1 MB |

<sub>測試環境：Intel Core i5-13450HX、32 GB RAM、Windows 11；.NET 10、Node.js 24、Java 25、Python 3.12；C/C++ 以 Zig 0.16（clang）`-O2` 編譯。</sub>

- **載入只需一次**：程式啟動時讀取對照表（約 4.7 萬筆），之後的轉碼都在記憶體查表完成。
- **速度不是瓶頸**：最慢的 Python 每秒也能轉 10 萬筆，5 萬筆商品全部重算約 0.5 秒。
- **結果一致**：6 種語言對這 3,000 筆的轉碼結果逐筆完全相同。

量測方式和自行評測的方法，見 [examples/README.md](examples/README.md#效能評測)。

## 其他語言實作規格

`examples/` 已經涵蓋常用語言。要移植到其他語言（Go、PHP、T-SQL…）時，請遵循以下規格，並用 [`tests/samples.tsv`](tests/samples.tsv) 驗收：

```
encode(text):
  1. text = Unicode NFKC 正規化（全形 → 半形）
  2. 把 text 切成「連續中文字」與「非中文」兩種區段
     中文字範圍：U+3007、U+3400–4DBF、U+4E00–9FFF、U+F900–FAFF、U+20000–3FFFF
  3. 中文區段：
       a. 用場景覆寫詞組做左到右最長比對，命中處鎖定該詞的碼（每字 1 鍵）
       b. 未鎖定的連續空隙中，用 phrases 做左到右最長比對
       c. 其餘字查 chars（場景單字覆寫優先）；查不到就略過
  4. 非中文區段逐字處理：
       ASCII 英數字 → 轉大寫輸出
       空白 → 略過
       其他符號 → mode = "drop" 時略過、"keep" 時保留；列在 exceptions 的符號反向處理
  5. 串接所有結果
```

[`tests/samples.tsv`](tests/samples.tsv) 是各語言共用的驗收資料，所有實作的結果都必須完全相同。

## 使用（Python）

需要 [uv](https://docs.astral.sh/uv/)。

```bash
uv run zhuyin-code "SF-9950三花彩色長袖圓領L"      # 注音碼（預設 product 場景）
uv run zhuyin-code -s cangjie "優生寬口徑奶瓶蓋"    # 倉頡首碼
uv run pytest                                     # 以真實商品資料驗證
uv run python scripts/build_data.py               # 從上游重新產生 data/
```

```python
from zhuyin_code import Encoder

enc = Encoder.load("zhuyin", profile="product")
enc.encode("優生矽晶安撫標準型奶嘴L")   # 'UGVR0Z15VSYL'
```

## 資料庫整合建議

搜尋碼應該在商品建檔或改名時**預先算好存起來**，查詢時才能用索引：

```sql
CREATE TABLE ProductSearchCode (
    product_id INT          NOT NULL,
    scheme     VARCHAR(16)  NOT NULL,   -- 'zhuyin' / 'cangjie'
    code       VARCHAR(100) NOT NULL,
    PRIMARY KEY (product_id, scheme)
);
CREATE INDEX IX_ProductSearchCode ON ProductSearchCode (scheme, code);

-- 依使用者慣用的體系查詢
SELECT product_id FROM ProductSearchCode
WHERE scheme = @userScheme AND code LIKE @input + '%';
```

## 授權

- **程式碼**：[MIT](LICENSE)
- **對照表資料**：沿用上游授權，詳見 [data/LICENSES.md](data/LICENSES.md)
  - `data/zhuyin/`：CC BY-SA 3.0（衍生自 rime-terra-pinyin / CC-CEDICT）
  - `data/cangjie/`：GPL（衍生自 rime-cangjie）
