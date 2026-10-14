# 注音碼（zhuyin-code）

把商品名稱轉成「唸得出來就打得出來」的搜尋碼：

- **中文字**：每字取一鍵
  - `zhuyin`：最常用讀音的第一個注音符號 → 大千鍵盤按鍵（三ㄙ→N、安ㄢ→0、兒ㄦ→-）
  - `cangjie`：倉頡五代首碼（三→M、花→T）
- **英數字**：照抄轉大寫（全形自動轉半形）
- **符號**：依 `config.toml` 略過或保留

範例：`SF-9950三花彩色長袖圓領L` → `SF9950NCHNTVMXL`

## 架構：資料為核心，各語言只是薄殼

```
data/
  zhuyin/chars.tsv        字 → 鍵（預設讀音）
  zhuyin/phrases.tsv      詞 → 鍵序列（修正多音字，只收與逐字結果不同者）
  cangjie/chars.tsv       字 → 倉頡首碼
  profiles/<場景>/<體系>.tsv  場景覆寫（例：product 的「長袖→TV」），優先權最高
```

轉碼順序：場景詞組（最長比對）→ 一般詞組（最長比對）→ 逐字查表。
TSV 為 UTF-8、tab 分隔、`#` 開頭為註解，任何語言都能直接讀取。

## 使用

```bash
uv run python scripts/build_data.py           # 下載開源碼表並產生 data/
uv run zhuyin-code "SF-9950三花彩色長袖圓領L"   # 注音碼（預設 product 場景）
uv run zhuyin-code -s cangjie "優生寬口徑奶瓶蓋" # 倉頡首碼
uv run pytest                                  # 以實際商品資料驗證
```

資料授權見 [data/LICENSES.md](data/LICENSES.md)。
