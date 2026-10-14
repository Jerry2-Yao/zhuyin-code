"""注音碼編碼引擎：品名 → 搜尋碼。

規則：
- 中文字：依編碼體系（scheme）查表，每字 1 鍵；先用最長詞組比對修正多音字
- 英數字：照抄並轉大寫（全形先轉半形）
- 空白：略過
- 符號：依設定 drop / keep，可設例外清單
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_HAN_CLASS = r"[〇㐀-䶿一-鿿豈-﫿\U00020000-\U0003ffff]"
_HAN = re.compile(_HAN_CLASS)
_RUNS = re.compile(rf"{_HAN_CLASS}+|(?:(?!{_HAN_CLASS}).)+", re.S)  # 切成「連續中文」與「非中文」區段


def load_tsv(path: Path) -> dict[str, str]:
    table: dict[str, str] = {}
    if not path.exists():
        return table
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("\t")[:2]
        table[key] = value
    return table


@dataclass
class Encoder:
    chars: dict[str, str]
    phrases: dict[str, str] = field(default_factory=dict)
    symbol_mode: str = "drop"  # drop：符號略過；keep：符號保留
    symbol_exceptions: frozenset[str] = frozenset()  # 與 symbol_mode 相反處理的符號

    overrides: dict[str, str] = field(default_factory=dict)  # 場景詞組，優先於 phrases

    def __post_init__(self) -> None:
        self._max_phrase = max((len(p) for p in self.phrases), default=1)
        self._max_override = max((len(p) for p in self.overrides), default=1)

    @classmethod
    def load(
        cls,
        scheme: str = "zhuyin",
        profile: str | None = None,
        config: Path | None = None,
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> "Encoder":
        chars = load_tsv(data_dir / scheme / "chars.tsv")
        phrases = load_tsv(data_dir / scheme / "phrases.tsv")
        overrides: dict[str, str] = {}
        if profile:
            # 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
            for key, code in load_tsv(data_dir / "profiles" / profile / f"{scheme}.tsv").items():
                if len(key) == 1:
                    chars[key] = code
                else:
                    overrides[key] = code
        opts = {}
        if config and config.exists():
            opts = tomllib.loads(config.read_text(encoding="utf-8")).get("symbols", {})
        return cls(
            chars=chars,
            phrases=phrases,
            overrides=overrides,
            symbol_mode=opts.get("mode", "drop"),
            symbol_exceptions=frozenset(opts.get("exceptions", [])),
        )

    def encode(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        out: list[str] = []
        for run in _RUNS.findall(text):
            if _HAN.match(run):
                out.append(self._encode_han(run))
                continue
            for c in run:
                if c.isascii() and c.isalnum():
                    out.append(c.upper())
                elif not c.isspace():
                    keep = self.symbol_mode == "keep"
                    if c in self.symbol_exceptions:
                        keep = not keep
                    if keep:
                        out.append(c)
        return "".join(out)

    def _encode_han(self, run: str) -> str:
        # 第 1 步：場景詞組優先鎖定（避免一般詞庫跨詞誤比對，例如「彩色長袖」被切出「色長」）
        codes: list[str | None] = [None] * len(run)
        self._max_match(run, self.overrides, self._max_override, codes)
        # 第 2 步：剩下未鎖定的區段用一般詞庫修正多音字
        start = 0
        while start < len(run):
            if codes[start] is not None:
                start += 1
                continue
            end = start
            while end < len(run) and codes[end] is None:
                end += 1
            gap: list[str | None] = [None] * (end - start)
            self._max_match(run[start:end], self.phrases, self._max_phrase, gap)
            codes[start:end] = gap
            start = end
        # 第 3 步：其餘逐字查表；查無此字則略過
        return "".join(c if c is not None else self.chars.get(run[i], "") for i, c in enumerate(codes))

    @staticmethod
    def _max_match(run: str, table: dict[str, str], max_len: int, codes: list[str | None]) -> None:
        """左到右最長比對，命中的詞把每字的碼填入 codes。"""
        i = 0
        while i < len(run):
            for size in range(min(max_len, len(run) - i), 1, -1):
                code = table.get(run[i : i + size])
                if code:
                    codes[i : i + size] = list(code)
                    i += size
                    break
            else:
                i += 1
