# SQL Server 版

把注音碼直接做在 SQL Server 裡：商品新增或修改時，由 **trigger** 呼叫 **T-SQL 函數**自動產生搜尋碼，應用程式完全不用改。

## 安裝

依序執行（SSMS 開啟後執行，或用 `sqlcmd`）：

| 檔案 | 內容 |
|---|---|
| [01_schema.sql](01_schema.sql) | 對照表結構：`ZhuyinChar`（單字）、`ZhuyinPhrase`（詞組、場景覆寫）、`ZhuyinSetting`（符號設定）、`ZhuyinTally`（數字表） |
| [02_data.sql](02_data.sql) | 對照表資料，約 6.8 萬筆。由 `scripts/build_sql.py` 從 `data/` 產生 |
| [03_function.sql](03_function.sql) | 轉碼函數 `dbo.fn_ZhuyinCode` |
| [04_trigger_example.sql](04_trigger_example.sql) | 範例：示範用商品檔 `dbo.Product`，加上自動產生搜尋碼的 trigger |

```bash
sqlcmd -S <伺服器> -d <資料庫> -E -f 65001 -i 01_schema.sql
sqlcmd -S <伺服器> -d <資料庫> -E -f 65001 -i 02_data.sql
sqlcmd -S <伺服器> -d <資料庫> -E -f 65001 -i 03_function.sql
```

`-f 65001` 讓 sqlcmd 以 UTF-8 讀取檔案。用 SSMS 開啟則不需要，檔案有 BOM，會自動判斷。

需要 **SQL Server 2017 以上**，因為函數用到 `STRING_AGG`。

## 函數用法

```sql
SELECT dbo.fn_ZhuyinCode(N'SF-9950三花彩色長袖圓領L', 'zhuyin', 'product');  -- SF9950NCHNTVMXL
SELECT dbo.fn_ZhuyinCode(N'優生寬口徑奶瓶蓋', 'cangjie', '');               -- OHJRHVTT（倉頡首碼）
```

| 參數 | 說明 |
|---|---|
| `@name` | 品名 |
| `@scheme` | `'zhuyin'`（注音）或 `'cangjie'`（倉頡首碼） |
| `@profile` | 場景覆寫表，例如 `'product'`；傳 `''` 表示不套用場景 |

符號要略過或保留，請改 `dbo.ZhuyinSetting` 資料表，作用等同 `config.toml`。

## Trigger 範例

```sql
CREATE OR ALTER TRIGGER dbo.trg_Product_SearchCode
ON dbo.Product
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT UPDATE(PRO_NAME) RETURN;          -- 只有品名異動才重算

    UPDATE p
    SET PH_CODE = dbo.fn_ZhuyinCode(i.PRO_NAME, 'zhuyin', 'product'),
        CJ_CODE = dbo.fn_ZhuyinCode(i.PRO_NAME, 'cangjie', '')
    FROM dbo.Product AS p
    JOIN inserted AS i ON i.PRO_ID = p.PRO_ID;
END
```

幾個設計重點：

- **只在品名異動時重算**：`IF NOT UPDATE(PRO_NAME) RETURN`，例如只改價格就不會觸發轉碼。
- **整批處理**：`inserted` 包含這次新增或修改的所有列，一次 INSERT 多筆也能正確處理。
- **不會無限遞迴**：trigger 裡更新本表，不會再觸發自己。資料庫的 `RECURSIVE_TRIGGERS` 預設是 OFF，而且內層的 UPDATE 只改搜尋碼欄位，`UPDATE(PRO_NAME)` 為假，會直接 RETURN。
- **搜尋碼要建索引**：出貨時用 `WHERE PH_CODE LIKE @輸入 + '%'` 查詢，可以用到索引。

### 為什麼用 trigger，而不是計算欄位？

| 做法 | 能否建索引 | 說明 |
|---|---|---|
| **Trigger（採用）** | ✅ | 搜尋碼存成一般欄位，可以建索引 |
| 計算欄位 `PH_CODE AS dbo.fn_ZhuyinCode(...)` | ❌ | 函數會讀取對照表，屬於非確定性函數，無法 `PERSISTED`，也就不能建索引，每次查詢都要逐筆重算 |

### 一個商品需要多種編碼體系時

範例中的商品檔有 `PH_CODE`（注音）和 `CJ_CODE`（倉頡）兩個欄位。如果體系會越來越多，建議改用一張獨立的搜尋碼表，新增體系時不用改商品檔的結構：

```sql
CREATE TABLE dbo.ProductSearchCode (
    PRO_ID INT          NOT NULL,
    scheme VARCHAR(16)  NOT NULL,
    code   VARCHAR(100) NOT NULL,
    PRIMARY KEY (PRO_ID, scheme)
);
CREATE INDEX IX_ProductSearchCode ON dbo.ProductSearchCode (scheme, code);
```

## 實作說明

演算法和其他語言版本相同（見根目錄 README 的「其他語言實作規格」）。T-SQL 特有的處理如下：

- **定序**：字元比對一律使用 `Latin1_General_100_BIN2`。如果資料庫是不分大小寫、全半形的定序（例如 `Chinese_Taiwan_Stroke_CI_AS`），比對可能把不同的字當成相同，BIN2 則是逐碼精確比對。
- **擴充區罕用字**：在 NVARCHAR 中佔 2 個 UTF-16 單位（代理對），函數會把它們合成 1 個字處理，結果和其他語言一致。
- **全形轉半形**：T-SQL 沒有 Unicode NFKC 正規化，只處理全形英數字和全形空白，跟 C/C++ 範例相同。
- **效能寫法**：
  - 純量函數中每寫入一次表變數都很昂貴，所以函數完全不使用表變數。
  - 拆字用內嵌資料表函數 `dbo.fn_ZhuyinSplit` 搭配數字表，一次拆完整個品名。
  - 迴圈只走實際命中的詞組。
  - 查表的查詢加上 `OPTION (LOOP JOIN)`，避免最佳化工具誤判品名長度，去掃描整張對照表。

## 效能評測

用 `scripts/bench_sql.py` 執行：重建對照表、驗收，然後用 3,000 筆實際商品量測。

```bash
uv run --with pyodbc python scripts/bench_sql.py 品名.csv --server localhost --database 測試資料庫
```

3,000 筆實際商品的實測結果（SQL Server 2022 Developer Edition，與其他語言同一台電腦，伺服器端計時，3 次取中位數）：

| 項目 | 結果 |
|---|--:|
| 驗收（tests/samples.tsv） | 全部通過 |
| 與其他 6 種語言逐筆比對 3,000 筆 | **完全一致** |
| 1. 載入時間（匯入對照表，只需一次） | 23.7 秒 |
| 2. 平均轉碼時間：直接呼叫函數 | 2.45 ms／筆 |
| 2. 平均轉碼時間：INSERT 經 trigger（注音＋倉頡兩種碼，含寫入與索引維護） | 3.44 ms／筆 |
| 2. 平均轉碼時間：UPDATE 經 trigger（同上） | 3.40 ms／筆 |
| 3. 對照表空間（資料＋索引） | 2.3 MB，實際載入 buffer pool 2.2 MB |

**怎麼解讀這些數字**

- **日常使用完全沒問題**：建檔或改名一次一筆，trigger 只多花約 3 ms，使用者感覺不到。
- **大量匯入要預留時間**：5 萬筆商品一次匯入或全部重算，大約需要 3 分鐘。如果常常需要大批重算，可以改成由應用程式端計算（其他語言每筆只要微秒級），再批次寫回；或改用 SQLCLR。
- **為什麼比其他語言慢上千倍**：T-SQL 純量函數裡每執行一個查詢，固定就要數十到數百微秒的開銷，每筆品名需要 3–5 個查詢。開發過程中的優化紀錄如下：

  | 版本 | 寫法 | 每筆 |
  |---|---|--:|
  | 1 | 逐字迴圈＋表變數 | 4.9 ms |
  | 2 | 集合式拆字＋表變數 | 3.0 ms |
  | 3（目前） | 不用表變數、內嵌 TVF 拆字、`LOOP JOIN` 提示 | 2.45 ms |

- 想要再快一個數量級的話，可以考慮 **SQLCLR**，把 C# 範例編成組件掛進 SQL Server，每筆預期是微秒級。代價是部署比較複雜：SQL Server 2017 起預設啟用 `clr strict security`，組件需要簽章。
