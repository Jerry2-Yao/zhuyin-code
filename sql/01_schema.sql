/*
 * 注音碼 for SQL Server —— 1. 對照表結構
 * 需求：SQL Server 2017 以上（函數使用 STRING_AGG）
 *
 * 字元比對一律使用 Latin1_General_100_BIN2（二進位定序）：
 *   - 資料庫若是 CI（不分大小寫）、全半形不敏感等定序，「字」的比對可能被視為相等而查錯
 *   - BIN2 以 UTF-16 碼位逐一比對，確保一字一碼
 */
SET NOCOUNT ON;

-- 先移除依賴這些表的函數，才能重建
IF OBJECT_ID(N'dbo.fn_ZhuyinCode', N'FN') IS NOT NULL DROP FUNCTION dbo.fn_ZhuyinCode;
IF OBJECT_ID(N'dbo.fn_ZhuyinSplit', N'IF') IS NOT NULL DROP FUNCTION dbo.fn_ZhuyinSplit;
IF OBJECT_ID(N'dbo.ZhuyinChar', N'U') IS NOT NULL DROP TABLE dbo.ZhuyinChar;
IF OBJECT_ID(N'dbo.ZhuyinPhrase', N'U') IS NOT NULL DROP TABLE dbo.ZhuyinPhrase;
IF OBJECT_ID(N'dbo.ZhuyinSetting', N'U') IS NOT NULL DROP TABLE dbo.ZhuyinSetting;

-- 單字表：字 → 碼（對應 data/<scheme>/chars.tsv）
CREATE TABLE dbo.ZhuyinChar (
    scheme VARCHAR(16)                                NOT NULL,  -- 'zhuyin' / 'cangjie'
    ch     NVARCHAR(2) COLLATE Latin1_General_100_BIN2 NOT NULL, -- 一個字（擴充區罕用字佔 2 個 UTF-16 單位）
    code   VARCHAR(4)                                 NOT NULL,
    CONSTRAINT PK_ZhuyinChar PRIMARY KEY (scheme, ch)
);

-- 詞組表：一般詞庫（profile = ''）與場景覆寫（profile = 'product' 等）共用
--   對應 data/<scheme>/phrases.tsv 與 data/profiles/<profile>/<scheme>.tsv
--   場景覆寫中的單字條目（char_len = 1）會蓋過單字表
CREATE TABLE dbo.ZhuyinPhrase (
    scheme   VARCHAR(16)                                 NOT NULL,
    profile  VARCHAR(32)                                 NOT NULL,  -- '' = 一般詞庫
    phrase   NVARCHAR(50) COLLATE Latin1_General_100_BIN2 NOT NULL,
    first_ch NVARCHAR(2)  COLLATE Latin1_General_100_BIN2 NOT NULL, -- 詞的第一個字，用來快速縮小候選範圍
    char_len TINYINT                                     NOT NULL,  -- 詞的字數（擴充區罕用字算 1 字）
    code     VARCHAR(50)                                 NOT NULL,  -- 每字 1 鍵，長度 = char_len
    CONSTRAINT PK_ZhuyinPhrase PRIMARY KEY (scheme, profile, phrase)
);
CREATE INDEX IX_ZhuyinPhrase_First ON dbo.ZhuyinPhrase (scheme, profile, first_ch, char_len DESC) INCLUDE (phrase, code);

-- 數字表 1..4000：函數用來把品名一次拆成逐字（集合式處理，比逐字迴圈快很多）
IF OBJECT_ID(N'dbo.ZhuyinTally', N'U') IS NOT NULL DROP TABLE dbo.ZhuyinTally;
CREATE TABLE dbo.ZhuyinTally (n SMALLINT NOT NULL PRIMARY KEY);
WITH d AS (SELECT v FROM (VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS t(v))
INSERT dbo.ZhuyinTally (n)
SELECT a.v * 1000 + b.v * 100 + c.v * 10 + e.v + 1 FROM d a, d b, d c, d e WHERE a.v < 4;

-- 設定（對應 config.toml）
CREATE TABLE dbo.ZhuyinSetting (
    name  VARCHAR(50)    NOT NULL PRIMARY KEY,
    value NVARCHAR(200)  NOT NULL
);
INSERT dbo.ZhuyinSetting (name, value) VALUES
    ('symbol_mode', N'drop'),       -- drop：品名中的符號一律略過；keep：一律保留
    ('symbol_exceptions', N'');     -- 與 symbol_mode 相反處理的符號，直接把符號串在一起，例如 N'+#'
