"""用使用者提供的實際商品資料驗證注音碼。"""

from pathlib import Path

import pytest

from zhuyin_code import Encoder

# (品名, 預期注音碼) —— 與其他語言範例共用 tests/samples.tsv
SAMPLES_FILE = Path(__file__).with_name("samples.tsv")
SAMPLES = [
    tuple(line.split("\t")[:2])
    for line in SAMPLES_FILE.read_text(encoding="utf-8").splitlines()
    if line and not line.startswith("#")
]
# 「UG2VDDVEY2 優生??寬口吸管組-大」截圖字跡不清，待確認後補上


@pytest.fixture(scope="module")
def zhuyin():
    return Encoder.load("zhuyin", profile="product")


@pytest.mark.parametrize(("name", "expected"), SAMPLES)
def test_product_samples(zhuyin, name, expected):
    assert zhuyin.encode(name) == expected


def test_er_maps_to_dash_even_when_symbols_dropped(zhuyin):
    # 「兒」的注音ㄦ在鍵盤上是 -，不能被「略過符號」誤刪
    assert zhuyin.encode("嬰兒") == "U-"


def test_fullwidth_and_lowercase(zhuyin):
    assert zhuyin.encode("ｓｆ－９９５０ ml") == "SF9950ML"


def test_symbol_keep_mode():
    enc = Encoder(chars={}, symbol_mode="keep", symbol_exceptions=frozenset({"/"}))
    assert enc.encode("A-B/C") == "A-BC"


def test_cangjie_first_code():
    cj = Encoder.load("cangjie")
    assert cj.encode("三花L") == "MTL"


def test_profile_phrase_beats_cross_word_match():
    # 一般詞庫有「色長」（sè zhǎng），沒套商品場景時會跨詞誤判
    plain = Encoder.load("zhuyin")
    assert plain.encode("彩色長袖") == "HN5V"
    assert Encoder.load("zhuyin", profile="product").encode("彩色長袖") == "HNTV"
