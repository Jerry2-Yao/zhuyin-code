"""把 data/ 的 TSV 對照表轉成 SQL Server 匯入腳本 sql/02_data.sql。

用法：uv run python scripts/build_sql.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT = ROOT / "sql" / "02_data.sql"
BATCH = 1000  # INSERT ... VALUES 一次最多 1000 列


def load_tsv(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("\t")[:2]
            rows.append((key, value))
    return rows


def q(s: str) -> str:
    return s.replace("'", "''")


def inserts(table: str, columns: str, values: list[str]) -> list[str]:
    out = []
    for i in range(0, len(values), BATCH):
        out.append(f"INSERT dbo.{table} ({columns}) VALUES\n" + ",\n".join(values[i : i + BATCH]) + ";")
    return out


def main() -> None:
    sql = [
        "/*",
        " * 注音碼 for SQL Server —— 2. 對照表資料",
        " * 由 scripts/build_sql.py 從 data/ 自動產生，請勿手動修改。",
        " * 資料授權見 data/LICENSES.md。",
        " */",
        "SET NOCOUNT ON;",
        "TRUNCATE TABLE dbo.ZhuyinChar;",
        "TRUNCATE TABLE dbo.ZhuyinPhrase;",
        "",
    ]
    for scheme_dir in sorted(p for p in DATA_DIR.iterdir() if (p / "chars.tsv").exists()):
        scheme = scheme_dir.name
        chars = load_tsv(scheme_dir / "chars.tsv")
        sql.append(f"-- {scheme} 單字表：{len(chars)} 筆")
        sql += inserts("ZhuyinChar", "scheme, ch, code", [f"('{scheme}',N'{q(k)}','{q(v)}')" for k, v in chars])

        sources = [("", scheme_dir / "phrases.tsv")]
        sources += [(p.name, p / f"{scheme}.tsv") for p in sorted((DATA_DIR / "profiles").iterdir())]
        for profile, path in sources:
            if not path.exists():
                continue
            rows = load_tsv(path)
            label = f"場景 {profile}" if profile else "一般詞庫"
            sql.append(f"-- {scheme} 詞組表（{label}）：{len(rows)} 筆")
            sql += inserts(
                "ZhuyinPhrase",
                "scheme, profile, phrase, first_ch, char_len, code",
                [f"('{scheme}','{profile}',N'{q(k)}',N'{q(k[0])}',{len(k)},'{q(v)}')" for k, v in rows],
            )
        sql.append("")
    sql.append("SELECT scheme, COUNT(*) AS chars FROM dbo.ZhuyinChar GROUP BY scheme;")
    sql.append("SELECT scheme, profile, COUNT(*) AS phrases FROM dbo.ZhuyinPhrase GROUP BY scheme, profile;")
    OUT.write_text("\n".join(sql) + "\n", encoding="utf-8-sig", newline="\n")  # 加 BOM，SSMS / sqlcmd 才會以 UTF-8 讀取
    print(f"{OUT.relative_to(ROOT)}：{OUT.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
