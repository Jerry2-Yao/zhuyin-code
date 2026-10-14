/*
 * 注音碼 for SQL Server —— 4. 範例：商品檔新增／修改時，由 trigger 自動產生搜尋碼
 *
 * dbo.Product 是示範用的商品檔，請依實際的資料表調整欄位名稱。
 */
SET NOCOUNT ON;

IF OBJECT_ID(N'dbo.Product', N'U') IS NOT NULL DROP TABLE dbo.Product;
CREATE TABLE dbo.Product (
    PRO_ID   INT IDENTITY(1, 1) PRIMARY KEY,
    PRO_NAME NVARCHAR(100) NOT NULL,
    PRICE    DECIMAL(10, 1) NULL,
    PH_CODE  VARCHAR(100)  NULL,   -- 注音碼（trigger 自動維護）
    CJ_CODE  VARCHAR(100)  NULL    -- 倉頡首碼（trigger 自動維護；不需要可拿掉）
);
-- 搜尋用索引：出貨時輸入「注音碼開頭」查商品
CREATE INDEX IX_Product_PH_CODE ON dbo.Product (PH_CODE) INCLUDE (PRO_NAME);
CREATE INDEX IX_Product_CJ_CODE ON dbo.Product (CJ_CODE) INCLUDE (PRO_NAME);
GO

CREATE OR ALTER TRIGGER dbo.trg_Product_SearchCode
ON dbo.Product
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- 只有品名有異動時才重算（例如只改價格就不必重算）
    -- trigger 內再 UPDATE 本表不會無限遞迴：資料庫 RECURSIVE_TRIGGERS 預設為 OFF，
    -- 且內層 UPDATE 只改 PH_CODE / CJ_CODE，UPDATE(PRO_NAME) 為假，會直接 RETURN
    IF NOT UPDATE(PRO_NAME) RETURN;

    -- inserted 是本次新增／修改的所有列，一次處理整批（多筆 INSERT 也正確）
    UPDATE p
    SET PH_CODE = dbo.fn_ZhuyinCode(i.PRO_NAME, 'zhuyin', 'product'),
        CJ_CODE = dbo.fn_ZhuyinCode(i.PRO_NAME, 'cangjie', '')
    FROM dbo.Product AS p
    JOIN inserted AS i ON i.PRO_ID = p.PRO_ID;
END
GO

-- ── 示範 ──
INSERT dbo.Product (PRO_NAME, PRICE) VALUES
    (N'SF-9950三花彩色長袖圓領L', 450.0),
    (N'優生寬口徑奶瓶蓋', 30.0),
    (N'嬌生嬰兒睡眠沐浴精1000ML', 143.0);

UPDATE dbo.Product SET PRO_NAME = N'嬌生嬰兒牛奶沐浴乳1000ML' WHERE PRO_NAME = N'嬌生嬰兒睡眠沐浴精1000ML';

SELECT PRO_ID, PRO_NAME, PH_CODE, CJ_CODE FROM dbo.Product;

-- 出貨時的查詢：輸入注音碼開頭（可用到索引）
DECLARE @input VARCHAR(100) = 'UGDD';
SELECT PRO_ID, PRO_NAME, PH_CODE FROM dbo.Product WHERE PH_CODE LIKE @input + '%';
