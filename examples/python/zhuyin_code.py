"""注音碼 Python 單檔範例（只用標準函式庫，可直接複製到任何專案使用）。

執行：python zhuyin_code.py [repo 根目錄，預設 ../..]
完整套件版（含 CLI、設定檔）見 src/zhuyin_code/。
"""

import sys
import unicodedata
from pathlib import Path


def is_han(cp: int) -> bool:
    return (cp == 0x3007 or 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF
            or 0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x3FFFF)


def load_tsv(path: Path) -> dict[str, str]:
    table: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("\t")[:2]
                table[key] = value
    return table


class ZhuyinEncoder:
    def __init__(self, chars, phrases, overrides, symbol_mode="drop", symbol_exceptions=()):
        self.chars, self.phrases, self.overrides = chars, phrases, overrides
        self.max_phrase = max(map(len, phrases), default=1)
        self.max_override = max(map(len, overrides), default=1)
        self.symbol_mode = symbol_mode  # drop：符號略過；keep：符號保留
        self.symbol_exceptions = set(symbol_exceptions)  # 與 symbol_mode 相反處理的符號

    @classmethod
    def load(cls, data_dir: Path, scheme="zhuyin", profile=None, **options):
        chars = load_tsv(data_dir / scheme / "chars.tsv")
        phrases = load_tsv(data_dir / scheme / "phrases.tsv")
        overrides = {}
        if profile:
            # 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
            for key, code in load_tsv(data_dir / "profiles" / profile / f"{scheme}.tsv").items():
                (chars if len(key) == 1 else overrides)[key] = code
        return cls(chars, phrases, overrides, **options)

    def encode(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        out, i, n = [], 0, len(text)
        while i < n:
            if is_han(ord(text[i])):
                j = i
                while j < n and is_han(ord(text[j])):
                    j += 1
                out.append(self._encode_han(text[i:j]))
                i = j
                continue
            c = text[i]
            i += 1
            if c.isascii() and c.isalnum():
                out.append(c.upper())
            elif not c.isspace():
                keep = (self.symbol_mode == "keep") != (c in self.symbol_exceptions)
                if keep:
                    out.append(c)
        return "".join(out)

    def _encode_han(self, run: str) -> str:
        codes = [None] * len(run)
        # 第 1 步：場景詞組優先鎖定
        _max_match(run, self.overrides, self.max_override, codes, 0, len(run))
        # 第 2 步：未鎖定的空隙用一般詞庫修正多音字
        s = 0
        while s < len(run):
            if codes[s] is not None:
                s += 1
                continue
            e = s
            while e < len(run) and codes[e] is None:
                e += 1
            _max_match(run, self.phrases, self.max_phrase, codes, s, e)
            s = e
        # 第 3 步：其餘逐字查表；查無此字則略過
        return "".join(c if c is not None else self.chars.get(run[k], "") for k, c in enumerate(codes))


def _max_match(run, table, max_len, codes, start, end):
    """在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes。"""
    i = start
    while i < end:
        for size in range(min(max_len, end - i), 1, -1):
            code = table.get(run[i:i + size])
            if code:
                codes[i:i + size] = list(code)
                i += size
                break
        else:
            i += 1


def read_csv_names(path: Path) -> list[str]:
    """讀取單欄 CSV（UTF-8，可含 BOM 與 "..." 引號）。"""
    names = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith('"') and line.endswith('"') and len(line) >= 2:
            line = line[1:-1].replace('""', '"')
        if line.strip():
            names.append(line)
    return names


def bench(root: Path, csv_path: Path, out_path: Path | None, rounds: int = 10) -> None:
    import time
    import tracemalloc

    names = read_csv_names(csv_path)

    t0 = time.perf_counter()
    encoder = ZhuyinEncoder.load(root / "data", "zhuyin", "product")
    load_ms = (time.perf_counter() - t0) * 1000

    tracemalloc.start()  # 另外載入一份量記憶體（tracemalloc 會拖慢速度，所以不和計時混在一起）
    probe = ZhuyinEncoder.load(root / "data", "zhuyin", "product")
    mem_mb = tracemalloc.get_traced_memory()[0] / 1024 / 1024
    tracemalloc.stop()
    del probe

    codes = [encoder.encode(n) for n in names]  # 暖機
    t0 = time.perf_counter()
    for _ in range(rounds):
        for n in names:
            encoder.encode(n)
    per_us = (time.perf_counter() - t0) * 1e6 / (rounds * len(names))

    if out_path:
        out_path.write_text("".join(f"{c}\t{n}\n" for c, n in zip(codes, names)), encoding="utf-8", newline="\n")
    print_report("Python", len(names), load_ms, per_us, rounds, mem_mb, "tracemalloc")


def print_report(lang, count, load_ms, per_us, rounds, mem_mb, mem_method):
    print(f"=== 注音碼效能評測（{lang}） ===")
    print(f"商品筆數        : {count}")
    print(f"1. 載入時間      : {load_ms:.1f} ms")
    print(f"2. 平均轉碼時間  : {per_us:.2f} µs / 筆（{rounds} 輪，共 {rounds * count} 次）")
    print(f"3. 載入記憶體    : {mem_mb:.1f} MB（{mem_method}）")


# ── 範例：用共用樣本資料驗證；bench 模式做效能評測 ──
# 用法：python zhuyin_code.py [repo 根目錄]
#       python zhuyin_code.py bench <品名.csv> [轉碼結果輸出檔]
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 2 and sys.argv[1] == "bench":
        bench(Path("../.."), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
        sys.exit(0)
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "../..")
    encoder = ZhuyinEncoder.load(root / "data", "zhuyin", "product")
    fail = 0
    for line in (root / "tests" / "samples.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("\t")[:2]
        got = encoder.encode(name)
        fail += got != expected
        print(f"{'PASS' if got == expected else 'FAIL'}  {got:<18} {name}")
    print("全部通過" if fail == 0 else f"{fail} 筆不符")
    sys.exit(1 if fail else 0)
