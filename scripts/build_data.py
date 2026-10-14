"""從開源碼表產生可攜式對照表（TSV）。

輸出（data/ 底下）：
  zhuyin/chars.tsv    字 → 注音碼按鍵（取最常用讀音的第一個注音符號）
  zhuyin/phrases.tsv  詞 → 按鍵序列（只收「與逐字預設結果不同」的詞，用來修正多音字）
  cangjie/chars.tsv   字 → 倉頡首碼

用法：uv run python scripts/build_data.py
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
DATA_DIR = ROOT / "data"

SOURCES = {
    "terra_pinyin.dict.yaml": "https://raw.githubusercontent.com/rime/rime-terra-pinyin/master/terra_pinyin.dict.yaml",
    "cangjie5.base.dict.yaml": "https://raw.githubusercontent.com/rime/rime-cangjie/master/cangjie5.base.dict.yaml",
}

# 標準（大千）注音鍵盤配置
ZHUYIN_KEYS = {
    "ㄅ": "1", "ㄆ": "Q", "ㄇ": "A", "ㄈ": "Z",
    "ㄉ": "2", "ㄊ": "W", "ㄋ": "S", "ㄌ": "X",
    "ㄍ": "E", "ㄎ": "D", "ㄏ": "C",
    "ㄐ": "R", "ㄑ": "F", "ㄒ": "V",
    "ㄓ": "5", "ㄔ": "T", "ㄕ": "G", "ㄖ": "B",
    "ㄗ": "Y", "ㄘ": "H", "ㄙ": "N",
    "ㄧ": "U", "ㄨ": "J", "ㄩ": "M",
    "ㄚ": "8", "ㄛ": "I", "ㄜ": "K", "ㄝ": ",",
    "ㄞ": "9", "ㄟ": "O", "ㄠ": "L", "ㄡ": ".",
    "ㄢ": "0", "ㄣ": "P", "ㄤ": ";", "ㄥ": "/",
    "ㄦ": "-",
}

# 拼音開頭 → 第一個注音符號（依序比對，長的放前面）
_PINYIN_HEADS = [
    ("zh", "ㄓ"), ("ch", "ㄔ"), ("sh", "ㄕ"),
    ("b", "ㄅ"), ("p", "ㄆ"), ("m", "ㄇ"), ("f", "ㄈ"),
    ("d", "ㄉ"), ("t", "ㄊ"), ("n", "ㄋ"), ("l", "ㄌ"),
    ("g", "ㄍ"), ("k", "ㄎ"), ("h", "ㄏ"),
    ("j", "ㄐ"), ("q", "ㄑ"), ("x", "ㄒ"),
    ("r", "ㄖ"), ("z", "ㄗ"), ("c", "ㄘ"), ("s", "ㄙ"),
    ("yu", "ㄩ"), ("yong", "ㄩ"), ("y", "ㄧ"), ("w", "ㄨ"),
    ("ai", "ㄞ"), ("ao", "ㄠ"), ("ang", "ㄤ"), ("an", "ㄢ"), ("a", "ㄚ"),
    ("ou", "ㄡ"), ("o", "ㄛ"),
    ("ei", "ㄟ"), ("eng", "ㄥ"), ("en", "ㄣ"), ("er", "ㄦ"), ("eh", "ㄝ"), ("ê", "ㄝ"), ("e", "ㄜ"),
]
_PINYIN_HEADS.sort(  # 最長比對優先（zh 先於 z、yong 先於 y）
    key=lambda p: -len(p[0]))


def pinyin_to_key(syllable: str) -> str | None:
    s = re.sub(r"\d", "", syllable.lower())
    for head, symbol in _PINYIN_HEADS:
        if s.startswith(head):
            return ZHUYIN_KEYS[symbol]
    return None


def download() -> None:
    RAW_DIR.mkdir(exist_ok=True)
    for name, url in SOURCES.items():
        target = RAW_DIR / name
        if not target.exists():
            print(f"下載 {url}")
            urllib.request.urlretrieve(url, target)


def iter_rime_entries(path: Path):
    """略過 YAML 檔頭，逐行回傳以 tab 分隔的欄位。"""
    in_body = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not in_body:
            in_body = line.strip() == "..."
            continue
        if not line or line.startswith("#"):
            continue
        yield line.split("\t")


def parse_weight(fields: list[str]) -> float:
    if len(fields) >= 3 and fields[2].endswith("%"):
        return float(fields[2][:-1])
    return 0.0


def build_zhuyin(unknown: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    entries = list(iter_rime_entries(RAW_DIR / "terra_pinyin.dict.yaml"))

    # 單字：取權重最高的讀音；同權重取先出現者
    best: dict[str, tuple[float, str]] = {}
    for f in entries:
        if len(f) < 2 or len(f[0]) != 1:
            continue
        key = pinyin_to_key(f[1])
        if key is None:
            unknown.add(f[1])
            continue
        w = parse_weight(f)
        if f[0] not in best or w > best[f[0]][0]:
            best[f[0]] = (w, key)
    chars = {c: k for c, (_, k) in best.items()}

    # 詞組：同一詞取權重最高者，只保留與逐字預設不同的
    phrase_best: dict[str, tuple[float, str]] = {}
    for f in entries:
        if len(f) < 2 or len(f[0]) < 2:
            continue
        syllables = f[1].split()
        if len(syllables) != len(f[0]):
            continue
        keys = [pinyin_to_key(s) for s in syllables]
        if None in keys:
            continue
        w = parse_weight(f)
        if f[0] not in phrase_best or w > phrase_best[f[0]][0]:
            phrase_best[f[0]] = (w, "".join(keys))
    phrases = {}
    for word, (_, code) in phrase_best.items():
        default = "".join(chars.get(c, "?") for c in word)
        if code != default:
            phrases[word] = code
    return chars, phrases


def build_cangjie() -> dict[str, str]:
    chars: dict[str, str] = {}
    for f in iter_rime_entries(RAW_DIR / "cangjie5.base.dict.yaml"):
        if len(f) < 2 or len(f[0]) != 1 or not f[1]:
            continue
        chars.setdefault(f[0], f[1][0].upper())  # 一字多碼取第一筆
    return chars


def write_tsv(path: Path, table: dict[str, str], header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}"] + [f"{k}\t{v}" for k, v in sorted(table.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: {len(table)} 筆")


def main() -> None:
    download()
    unknown: set[str] = set()
    z_chars, z_phrases = build_zhuyin(unknown)
    write_tsv(DATA_DIR / "zhuyin" / "chars.tsv", z_chars, "字\t注音碼按鍵｜來源 rime-terra-pinyin（CC BY-SA 3.0）")
    write_tsv(DATA_DIR / "zhuyin" / "phrases.tsv", z_phrases, "詞\t注音碼按鍵序列（只收與逐字預設不同者）｜來源 rime-terra-pinyin（CC BY-SA 3.0）")
    write_tsv(DATA_DIR / "cangjie" / "chars.tsv", build_cangjie(), "字\t倉頡首碼｜來源 rime-cangjie cangjie5.base（GPL）")
    if unknown:
        print(f"無法轉換的拼音（已略過）：{sorted(unknown)}")


if __name__ == "__main__":
    main()
