/*
 * 注音碼 for SQL Server —— 3. 轉碼函數 dbo.fn_ZhuyinCode
 *
 * 用法：
 *   SELECT dbo.fn_ZhuyinCode(N'SF-9950三花彩色長袖圓領L', 'zhuyin', 'product');  -- SF9950NCHNTVMXL
 *   SELECT dbo.fn_ZhuyinCode(N'優生寬口徑奶瓶蓋', 'cangjie', '');               -- 倉頡首碼
 *
 * 參數：
 *   @name    品名（最長 4000 個 UTF-16 單位）
 *   @scheme  編碼體系：'zhuyin'（注音）、'cangjie'（倉頡首碼）
 *   @profile 場景覆寫表：'product'、''（不套用場景）
 *
 * 演算法與其他語言版本相同（見 README「其他語言實作規格」）：
 *   1. 拆字：擴充區罕用字的 UTF-16 代理對視為 1 字；全形 ASCII 轉半形
 *   2. 場景詞組：左到右最長比對，命中處先鎖定
 *   3. 一般詞組：只在未鎖定的區段內做最長比對（修正多音字）
 *   4. 其餘逐字查表；英數字轉大寫，空白略過，符號依 ZhuyinSetting 設定
 *
 * 效能寫法：
 *   - 拆字用內嵌資料表函數 dbo.fn_ZhuyinSplit（搭配數字表），會被展開進查詢，一次處理整個品名
 *   - 不使用表變數（在純量函數中每次寫入表變數都很昂貴），已決定的碼記在字串 @slots
 *   - 迴圈只走實際命中的詞組（通常 0–3 個），每次一個查詢
 *
 * 與其他語言版本的差異：T-SQL 沒有 Unicode NFKC 正規化，只處理全形 ASCII 與全形空白（同 C/C++ 範例）。
 */

-- 拆字：每個字一列。k = 第幾個字（從 1 起），u = 在字串中的 UTF-16 位置（從 1 起），ulen = 佔幾個 UTF-16 單位
CREATE OR ALTER FUNCTION dbo.fn_ZhuyinSplit (@s NVARCHAR(4000))
RETURNS TABLE
AS
RETURN
    WITH units AS (
        SELECT n AS u,
               UNICODE(SUBSTRING(@s COLLATE Latin1_General_100_BIN2, n, 1)) AS c,
               UNICODE(SUBSTRING(@s COLLATE Latin1_General_100_BIN2, n + 1, 1)) AS c2
        FROM dbo.ZhuyinTally
        WHERE n <= DATALENGTH(@s) / 2
    ), chars AS (
        SELECT u, c,
               CASE WHEN c BETWEEN 55296 AND 56319 AND c2 BETWEEN 56320 AND 57343 THEN 2 ELSE 1 END AS ulen,
               CASE WHEN c BETWEEN 55296 AND 56319 AND c2 BETWEEN 56320 AND 57343
                        THEN 65536 + (c - 55296) * 1024 + (c2 - 56320)      -- 代理對合成
                    WHEN c BETWEEN 65281 AND 65374 THEN c - 65248            -- 全形 ASCII（U+FF01–FF5E）轉半形
                    WHEN c = 12288 THEN 32                                   -- 全形空白（U+3000）
                    ELSE c END AS cp
        FROM units
        WHERE c NOT BETWEEN 56320 AND 57343                                  -- 低代理是前一字的後半，略過
    )
    SELECT CAST(ROW_NUMBER() OVER (ORDER BY u) AS INT) AS k,
           u, ulen, cp,
           CAST(CASE WHEN cp = c OR ulen = 2 THEN SUBSTRING(@s COLLATE Latin1_General_100_BIN2, u, ulen)
                     ELSE NCHAR(cp) END AS NVARCHAR(2)) COLLATE Latin1_General_100_BIN2 AS ch,
           CAST(CASE WHEN cp = 12295                       -- 〇 U+3007
                       OR cp BETWEEN 13312 AND 19903       -- 擴充 A  U+3400–4DBF
                       OR cp BETWEEN 19968 AND 40959       -- 基本區  U+4E00–9FFF
                       OR cp BETWEEN 63744 AND 64255       -- 相容區  U+F900–FAFF
                       OR cp BETWEEN 131072 AND 262143     -- 擴充 B 以後 U+20000–3FFFF
                     THEN 1 ELSE 0 END AS BIT) AS han
    FROM chars;
GO

CREATE OR ALTER FUNCTION dbo.fn_ZhuyinCode
(
    @name    NVARCHAR(4000),
    @scheme  VARCHAR(16) = 'zhuyin',
    @profile VARCHAR(32) = 'product'
)
RETURNS NVARCHAR(4000)
AS
BEGIN
    IF @name IS NULL RETURN NULL;
    SET @profile = ISNULL(@profile, '');

    DECLARE @s NVARCHAR(4000) = @name COLLATE Latin1_General_100_BIN2;
    -- @slots：第 k 個字由詞組決定的碼；NCHAR(2) = 尚未決定（長度以 UTF-16 單位數估，一定夠用）
    DECLARE @undecided NCHAR(1) = NCHAR(2);
    DECLARE @slots NVARCHAR(4000) = REPLICATE(@undecided, DATALENGTH(@name) / 2);
    DECLARE @pass INT = CASE WHEN @profile = '' THEN 2 ELSE 1 END;
    DECLARE @pf VARCHAR(32), @pos INT, @k INT, @len INT, @code VARCHAR(50);

    -- ── 第 2、3 步：場景詞組（pass 1）優先鎖定，再用一般詞庫（pass 2）比對未鎖定的區段 ──
    WHILE @pass <= 2
    BEGIN
        SET @pf = CASE WHEN @pass = 1 THEN @profile ELSE '' END;
        SET @pos = 1;
        WHILE 1 = 1
        BEGIN
            -- 從 @pos 起找「位置最前、同位置最長」且整段都還沒決定的詞
            -- （詞只含中文字，所以不會跨過英數字或符號）
            SET @k = NULL;
            SELECT TOP (1) @k = t.k, @len = p.char_len, @code = p.code
            FROM dbo.fn_ZhuyinSplit(@s) AS t
            JOIN dbo.ZhuyinPhrase AS p
              ON p.scheme = @scheme AND p.profile = @pf AND p.first_ch = t.ch AND p.char_len >= 2
             AND p.phrase = SUBSTRING(@s, t.u, DATALENGTH(p.phrase) / 2)
            WHERE t.han = 1 AND t.k >= @pos
              AND SUBSTRING(@slots, t.k, p.char_len) COLLATE Latin1_General_100_BIN2 = REPLICATE(@undecided, p.char_len)
            ORDER BY t.k, p.char_len DESC
            OPTION (LOOP JOIN);  -- 每個字用索引查詞組（品名很短，避免最佳化工具誤選 merge join 掃整張表）
            IF @k IS NULL BREAK;
            SET @slots = STUFF(@slots, @k, @len, @code);
            SET @pos = @k + @len;
        END
        SET @pass += 1;
    END

    -- ── 第 4 步：組出結果 ──
    DECLARE @keep BIT = CASE WHEN (SELECT value FROM dbo.ZhuyinSetting WHERE name = 'symbol_mode') = N'keep' THEN 1 ELSE 0 END;
    DECLARE @exceptions NVARCHAR(200) = ISNULL((SELECT value FROM dbo.ZhuyinSetting WHERE name = 'symbol_exceptions'), N'');
    DECLARE @result NVARCHAR(4000);

    SELECT @result = STRING_AGG(
               CASE
                   WHEN t.han = 1 THEN                                                 -- 中文字
                       CASE WHEN SUBSTRING(@slots, t.k, 1) COLLATE Latin1_General_100_BIN2 <> @undecided
                            THEN SUBSTRING(@slots, t.k, 1)                             -- 詞組已決定
                            ELSE COALESCE(o.code, c.code, '') END                      -- 場景單字覆寫 > 單字表；查無此字則略過
                   WHEN t.cp BETWEEN 48 AND 57 OR t.cp BETWEEN 65 AND 90 THEN NCHAR(t.cp)   -- 0-9、A-Z
                   WHEN t.cp BETWEEN 97 AND 122 THEN NCHAR(t.cp - 32)                      -- a-z 轉大寫
                   WHEN t.cp IN (9, 10, 13, 32) THEN N''                                   -- 空白
                   WHEN @keep ^ CASE WHEN CHARINDEX(t.ch, @exceptions COLLATE Latin1_General_100_BIN2) > 0 THEN 1 ELSE 0 END = 1
                       THEN t.ch COLLATE DATABASE_DEFAULT                                  -- 保留的符號
                   ELSE N''
               END, N'') WITHIN GROUP (ORDER BY t.k)
    FROM dbo.fn_ZhuyinSplit(@s) AS t
    LEFT JOIN dbo.ZhuyinPhrase AS o
           ON t.han = 1 AND o.scheme = @scheme AND o.profile = @profile AND o.profile <> '' AND o.char_len = 1 AND o.phrase = t.ch
    LEFT JOIN dbo.ZhuyinChar AS c
           ON t.han = 1 AND c.scheme = @scheme AND c.ch = t.ch
    OPTION (LOOP JOIN);  -- 每個字用索引查單字表

    RETURN ISNULL(@result, N'');
END
