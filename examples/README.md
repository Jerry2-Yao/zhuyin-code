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

## 效能評測

使用時分兩個階段：**載入**（讀取對照表、建立字典，啟動時只需做一次）和**轉碼**（每次都在記憶體查表）。每個範例都提供 `bench` 模式，可以分別量測這兩段：

```bash
python zhuyin_code.py bench 品名.csv [轉碼結果輸出檔]
node --expose-gc zhuyin-code.mjs bench 品名.csv
java ZhuyinCode.java bench 品名.csv
dotnet run -c Release zhuyin_code.cs bench 品名.csv
./zhuyin_code bench 品名.csv          # C / C++
```

`品名.csv` 是單欄的 CSV（UTF-8，可以有 BOM 和 `"..."` 引號），一行一個品名。

### 實測結果

測試資料是 **3,000 筆實際商品名稱**，品名長度 3–29 字（中位數 22），共 15,619 個中文字，對照表覆蓋率 100%。每種語言跑 3 次，表中取中位數。

| 語言 | 1. 載入時間 | 2. 平均轉碼時間 | 每秒可轉 | 3. 載入記憶體 |
|---|--:|--:|--:|--:|
| C | 12.0 ms | **0.73 µs**／筆 | 約 137 萬筆 | **2.6 MB** |
| C++ | 13.6 ms | 1.81 µs／筆 | 約 55 萬筆 | 3.3 MB |
| Java | 53.4 ms | 2.57 µs／筆 | 約 39 萬筆 | 6.2 MB |
| JavaScript | 27.5 ms | 4.14 µs／筆 | 約 24 萬筆 | 3.1 MB |
| C# | 27.1 ms | 4.50 µs／筆 | 約 22 萬筆 | 4.6 MB |
| Python | 26.3 ms | 10.44 µs／筆 | 約 10 萬筆 | 4.1 MB |

測試環境：Intel Core i5-13450HX、32 GB RAM、Windows 11。各語言版本：.NET 10、Node.js 24、Java 25、Python 3.12。C/C++ 用 Zig 0.16（clang）以 `-O2` 編譯。

**怎麼解讀這些數字**

- 最慢的 Python 一秒也能轉 10 萬筆。商品檔 5 萬筆全部重算，Python 約 0.5 秒，C 約 0.04 秒。不管用哪種語言，轉碼速度都不會是瓶頸。
- 載入只在程式啟動時做一次，都在 60 ms 以內。常駐的服務（API、ERP 後端）載入一次後就能一直使用。
- 記憶體都在 2.6–6.2 MB 之間，對任何環境都不是負擔。

**量測方式**

- 載入時間：計時 `load()`，從讀檔到 3 個對照表建好字典為止，共約 4.7 萬筆。
- 平均轉碼時間：先暖機 1 輪，再將全部品名轉 10 輪（共 30,000 次），總時間 ÷ 次數。
- 載入記憶體：載入前後的記憶體差值。各語言用自己的標準方法量，所以只能比較數量級，不適合逐位數比較：

  | 語言 | 量測方式 |
  |---|---|
  | Python | `tracemalloc` |
  | JavaScript | 強制 GC 後的 V8 `heapUsed` 差值 |
  | Java | GC 後的 heap 使用量差值 |
  | C# | `GC.GetTotalMemory(true)` 差值 |
  | C | 對照表實際配置的位元組數 |
  | C++ | `operator new` 實際配置的位元組數 |

- 正確性：6 種語言對這 3,000 筆品名的轉碼結果**逐筆完全一致**（輸出檔的 MD5 雜湊值相同）。

**目前的範例以易讀為主，沒有特別做效能最佳化。** 例如 C# 版查詢詞組時，每次都會產生新的字串，C++ 版也會用 `substr` 複製字串。如果需要更快，可以改用 span 或 `string_view` 查表，不過以上面的數字來看，實務上沒有必要。

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
