"""SQL Server 版注音碼：驗收測試與效能評測。

用法：
  uv run --with pyodbc python scripts/bench_sql.py <品名.csv> [--server localhost] [--database ZhuyinCodeDemo]

會在指定資料庫執行 sql/01–04（重建對照表、函數與示範用 dbo.Product），然後：
  1. 載入時間：匯入對照表（01–03）的時間，資料庫只需要做一次
  2. 平均轉碼時間：函數直接轉碼、以及 INSERT／UPDATE 經 trigger 轉碼，每筆平均時間
  3. 記憶體：對照表在資料庫中的空間，以及實際載入 buffer pool 的大小
並以 tests/samples.tsv 驗收，若有 bench-out/python.tsv 則逐筆比對與其他語言的結果。
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
ROUNDS = 3


def read_csv_names(path: Path) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith('"') and line.endswith('"') and len(line) >= 2:
            line = line[1:-1].replace('""', '"')
        if line.strip():
            names.append(line)
    return names


def run_script(cur: pyodbc.Cursor, path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    for batch in re.split(r"^\s*GO\s*$", text, flags=re.M | re.I):
        if batch.strip():
            cur.execute(batch)
            while cur.nextset():  # 消化所有結果集
                pass


def server_ms(cur: pyodbc.Cursor, sql: str) -> float:
    """在伺服器端計時，排除網路與驅動的時間。"""
    cur.execute(f"""
        SET NOCOUNT ON;
        DECLARE @t0 DATETIME2(7) = SYSDATETIME();
        {sql};
        SELECT DATEDIFF_BIG(MICROSECOND, @t0, SYSDATETIME()) / 1000.0;""")
    while cur.description is None:
        cur.nextset()
    return float(cur.fetchone()[0])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--server", default="localhost")
    ap.add_argument("--database", default="ZhuyinCodeDemo")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    conn = pyodbc.connect(
        f"Driver={{ODBC Driver 18 for SQL Server}};Server={args.server};Database={args.database};"
        "Trusted_Connection=yes;TrustServerCertificate=yes",
        autocommit=True,
    )
    cur = conn.cursor()
    version = cur.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30))").fetchone()[0]

    # ── 1. 載入（匯入對照表）──
    t0 = time.perf_counter()
    for name in ("01_schema.sql", "02_data.sql", "03_function.sql"):
        run_script(cur, SQL_DIR / name)
    load_s = time.perf_counter() - t0
    run_script(cur, SQL_DIR / "04_trigger_example.sql")

    # ── 驗收 ──
    fail = 0
    for line in (ROOT / "tests" / "samples.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("\t")[:2]
        got = cur.execute("SELECT dbo.fn_ZhuyinCode(?, 'zhuyin', 'product')", name).fetchone()[0]
        if got != expected:
            fail += 1
            print(f"FAIL  {got:<18} {name}（預期 {expected}）")
    print(f"驗收 tests/samples.tsv：{'全部通過' if fail == 0 else f'{fail} 筆不符'}")

    # ── 2. 轉碼時間 ──
    names = read_csv_names(args.csv)
    cur.execute("IF OBJECT_ID('tempdb..#names') IS NOT NULL DROP TABLE #names;"
                "CREATE TABLE #names (id INT PRIMARY KEY, name NVARCHAR(400));")
    cur.fast_executemany = True
    cur.executemany("INSERT #names VALUES (?, ?)", list(enumerate(names)))
    n = len(names)

    server_ms(cur, "SELECT dbo.fn_ZhuyinCode(name, 'zhuyin', 'product') AS c INTO #warm FROM #names; DROP TABLE #warm")
    fn_ms = statistics.median(
        server_ms(cur, "SELECT dbo.fn_ZhuyinCode(name, 'zhuyin', 'product') AS c INTO #o FROM #names; DROP TABLE #o")
        for _ in range(ROUNDS)
    )
    ins_ms, upd_ms = [], []
    for _ in range(ROUNDS):
        cur.execute("TRUNCATE TABLE dbo.Product")
        ins_ms.append(server_ms(cur, "INSERT dbo.Product (PRO_NAME) SELECT name FROM #names ORDER BY id"))
        upd_ms.append(server_ms(cur, "UPDATE dbo.Product SET PRO_NAME = PRO_NAME"))
    ins_ms, upd_ms = statistics.median(ins_ms), statistics.median(upd_ms)

    # 與其他語言比對（bench-out/python.tsv 由 examples/python bench 產生）
    rows = cur.execute("SELECT PH_CODE, PRO_NAME FROM dbo.Product ORDER BY PRO_ID").fetchall()
    ref_path = ROOT / "bench-out" / "python.tsv"
    if ref_path.exists():
        ref = [line.split("\t")[0] for line in ref_path.read_text(encoding="utf-8").splitlines()]
        diff = [(r.PRO_NAME, r.PH_CODE, e) for r, e in zip(rows, ref) if r.PH_CODE != e]
        print(f"與其他語言逐筆比對 {len(ref)} 筆：{'完全一致' if not diff and len(ref) == len(rows) else f'{len(diff)} 筆不同'}")
        for name, got, exp in diff[:10]:
            print(f"  {name}：SQL={got}  其他語言={exp}")

    # ── 3. 記憶體／空間 ──
    disk_kb = cur.execute("""
        SELECT SUM(a.total_pages) * 8 FROM sys.partitions p
        JOIN sys.allocation_units a ON a.container_id = p.partition_id
        WHERE p.object_id IN (OBJECT_ID('dbo.ZhuyinChar'), OBJECT_ID('dbo.ZhuyinPhrase'))""").fetchone()[0]
    buffer_kb = cur.execute("""
        SELECT COUNT(*) * 8 FROM sys.dm_os_buffer_descriptors b
        JOIN sys.allocation_units a ON a.allocation_unit_id = b.allocation_unit_id
        JOIN sys.partitions p ON p.hobt_id = a.container_id
        WHERE b.database_id = DB_ID()
          AND p.object_id IN (OBJECT_ID('dbo.ZhuyinChar'), OBJECT_ID('dbo.ZhuyinPhrase'))""").fetchone()[0]

    print(f"=== 注音碼效能評測（SQL Server {version}） ===")
    print(f"商品筆數        : {n}")
    print(f"1. 載入時間      : {load_s:.1f} 秒（匯入對照表，資料庫只需做一次）")
    print(f"2. 平均轉碼時間  : 函數直接呼叫 {fn_ms * 1000 / n:.1f} µs / 筆")
    print(f"                   INSERT 經 trigger {ins_ms * 1000 / n:.1f} µs / 筆（含寫入與索引維護）")
    print(f"                   UPDATE 經 trigger {upd_ms * 1000 / n:.1f} µs / 筆（含寫入與索引維護）")
    print(f"3. 對照表空間    : {disk_kb / 1024:.1f} MB（資料＋索引），實際載入 buffer pool {buffer_kb / 1024:.1f} MB")
    print(f"（伺服器端計時，{ROUNDS} 次取中位數）")


if __name__ == "__main__":
    main()
