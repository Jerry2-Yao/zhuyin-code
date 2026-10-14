# 各語言範例

六種語言的完整實作，都讀取同一份 `data/` 對照表，對同一份 [`tests/samples.tsv`](../tests/samples.tsv)（真實商品資料）驗證，**輸出結果完全一致**。

每個範例都是**單一檔案、無外部相依**，可以直接複製到自己的專案。

| 語言 | 檔案 | 執行方式（在該語言的資料夾內） | 需求 |
|---|---|---|---|
| C# | [csharp/zhuyin_code.cs](csharp/zhuyin_code.cs) | `dotnet run zhuyin_code.cs` | .NET 10 以上（舊版可放進一般 console 專案） |
| JavaScript | [javascript/zhuyin-code.mjs](javascript/zhuyin-code.mjs) | `node zhuyin-code.mjs` | Node.js 16 以上 |
| Java | [java/ZhuyinCode.java](java/ZhuyinCode.java) | `java ZhuyinCode.java` | Java 11 以上 |
| Python | [python/zhuyin_code.py](python/zhuyin_code.py) | `python zhuyin_code.py` | Python 3.9 以上 |
| C | [c/zhuyin_code.c](c/zhuyin_code.c) | `gcc -std=c99 -O2 -o zhuyin_code zhuyin_code.c && ./zhuyin_code` | C99 編譯器 |
| C++ | [cpp/zhuyin_code.cpp](cpp/zhuyin_code.cpp) | `g++ -std=c++17 -O2 -o zhuyin_code zhuyin_code.cpp && ./zhuyin_code` | C++17 編譯器 |

MSVC 的編譯指令：

- C：`cl /utf-8 zhuyin_code.c`
- C++：`cl /std:c++17 /utf-8 /EHsc zhuyin_code.cpp`

範例預設讀取 `../..` 作為 repo 根目錄，也可以用第一個參數指定。執行結果如下：

```
PASS  SF9950NCHNTVMXL    SF-9950三花彩色長袖圓領L
PASS  UGDDRSQE           優生寬口徑奶瓶蓋
...
全部通過
```

## 在自己的程式裡使用

每個範例的編碼器都提供一樣的介面：**載入（資料目錄、體系、場景）→ encode（品名）**。

```csharp
var enc = ZhuyinEncoder.Load("data", "zhuyin", "product");   // C#
enc.Encode("優生寬口徑奶瓶蓋");                                // "UGDDRSQE"
```

```js
const enc = ZhuyinEncoder.load("data", "zhuyin", "product");  // JavaScript
enc.encode("優生寬口徑奶瓶蓋");                               // "UGDDRSQE"
```

```java
ZhuyinCode enc = ZhuyinCode.load(Path.of("data"), "zhuyin", "product");  // Java
enc.encode("優生寬口徑奶瓶蓋");                                          // "UGDDRSQE"
```

把 `"zhuyin"` 換成 `"cangjie"` 就會改用倉頡首碼。

## 實作重點與差異

- **以 Unicode code point 為單位處理字元**。C#、Java、JavaScript 的字串是 UTF-16，罕用字（擴充 B 區以後，例如𠀀）會佔兩個 char，所以範例都改用 `Rune`、`codePoints()`、`Array.from()` 逐字處理，C/C++ 則自行解碼 UTF-8。
- **全形轉半形（NFKC 正規化）**：C#、Java、JavaScript、Python 使用內建的完整 NFKC。C/C++ 的標準函式庫沒有 NFKC，範例只轉換全形 ASCII（U+FF01–FF5E）和全形空白，商品資料一般已經夠用。如果需要完整的 NFKC，可以改用 ICU。
- **符號設定**：範例沒有解析 `config.toml`，而是把符號模式（drop/keep）和例外清單做成編碼器的屬性，方便直接在程式裡設定。
- 演算法規格見根目錄 [README](../README.md#其他語言實作規格)。
