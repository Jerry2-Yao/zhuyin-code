"""用使用者提供的實際商品資料驗證注音碼。"""

import pytest

from zhuyin_code import Encoder

# (PRO_NAME, PH_CODE) —— 來源：使用者既有系統的商品檔截圖
SAMPLES = [
    ("SF-9950三花彩色長袖圓領L", "SF9950NCHNTVMXL"),
    ("SF-9950三花彩色長袖圓領M", "SF9950NCHNTVMXM"),
    ("SF-9950三花彩色長袖圓領XL", "SF9950NCHNTVMXXL"),
    ("新嬌生嬰兒滋潤洗髮精500ML", "VRGU-YBVZR500ML"),  # 品名由碼反推，待使用者確認
    ("優生寬口徑奶瓶蓋", "UGDDRSQE"),
    ("麗奇牙周對策牙刷短刷頭", "XFU52HUG2GW"),
    ("麗奇牙周對策牙刷標準刷頭", "XFU52HUG15GW"),
    ("嬌生沐浴精1000ML", "RGAMR1000ML"),
    ("嬌生嬰兒牛奶沐浴乳1000ML", "RGU-SSAMB1000ML"),
    ("嬌生嬰兒睡眠沐浴精1000ML", "RGU-GAAMR1000ML"),
    ("優生矽晶安撫標準型奶嘴L", "UGVR0Z15VSYL"),
    ("優生矽晶安撫雙扁型奶嘴初S", "UGVR0ZG1VSYTS"),
    ("優生矽晶安撫拇指型奶嘴初S", "UGVR0ZA5VSYTS"),
    ("優生矽晶安撫拇指型奶嘴L", "UGVR0ZA5VSYL"),
    # 「UG2VDDVEY2 優生??寬口吸管組-大」截圖字跡不清，待確認後補上
]


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
