import argparse
import sys
from pathlib import Path

from .encoder import Encoder

__all__ = ["Encoder"]


def main() -> None:
    parser = argparse.ArgumentParser(description="品名轉搜尋碼（注音碼／倉頡首碼）")
    parser.add_argument("names", nargs="+", help="品名，可一次多筆")
    parser.add_argument("-s", "--scheme", default="zhuyin", help="編碼體系：zhuyin、cangjie")
    parser.add_argument("-p", "--profile", default="product", help="場景覆寫表，例如 product、person")
    parser.add_argument("-c", "--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    encoder = Encoder.load(args.scheme, args.profile, args.config)
    for name in args.names:
        print(f"{encoder.encode(name)}\t{name}")
