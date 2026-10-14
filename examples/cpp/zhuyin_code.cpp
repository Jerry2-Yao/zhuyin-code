// 注音碼 C++ 範例（C++17，無外部相依）
//
// 編譯：
//   MSVC：cl /std:c++17 /utf-8 /EHsc /O2 zhuyin_code.cpp
//   GCC ：g++ -std=c++17 -O2 -o zhuyin_code zhuyin_code.cpp
// 執行：zhuyin_code [repo 根目錄，預設 ../..]
//
// 說明：C++ 標準函式庫沒有 Unicode NFKC 正規化，這裡只處理最常見的
//       「全形 ASCII（U+FF01–FF5E）轉半形」與「全形空白 U+3000」。
//       需要完整 NFKC 時可改用 ICU（icu::Normalizer2）。
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

using Table = std::unordered_map<std::string, std::string>;

namespace {

bool isHan(char32_t cp) {
    return cp == 0x3007 || (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF) ||
           (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0x20000 && cp <= 0x3FFFF);
}

// UTF-8 解碼：回傳每個字元的 code point，並在 offs 記下它在原字串的位元組位置（offs.back() = 總長）
std::vector<char32_t> decodeUtf8(const std::string& s, std::vector<size_t>& offs) {
    std::vector<char32_t> cps;
    offs.clear();
    for (size_t i = 0; i < s.size();) {
        auto c = static_cast<unsigned char>(s[i]);
        int extra = c < 0x80 ? 0 : c < 0xE0 ? 1 : c < 0xF0 ? 2 : 3;
        char32_t cp = extra == 0 ? c : c & (0x3F >> extra);
        for (int k = 1; k <= extra && i + k < s.size(); k++)
            cp = (cp << 6) | (static_cast<unsigned char>(s[i + k]) & 0x3F);
        offs.push_back(i);
        cps.push_back(cp);
        i += extra + 1;
    }
    offs.push_back(s.size());
    return cps;
}

void appendUtf8(std::string& out, char32_t cp) {
    if (cp < 0x80) out += static_cast<char>(cp);
    else if (cp < 0x800) { out += static_cast<char>(0xC0 | cp >> 6); out += static_cast<char>(0x80 | (cp & 0x3F)); }
    else if (cp < 0x10000) {
        out += static_cast<char>(0xE0 | cp >> 12); out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | cp >> 18); out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F)); out += static_cast<char>(0x80 | (cp & 0x3F));
    }
}

size_t countUtf8(const std::string& s) {
    return std::count_if(s.begin(), s.end(), [](char c) { return (static_cast<unsigned char>(c) & 0xC0) != 0x80; });
}

Table loadTsv(const std::string& path) {
    Table table;
    std::ifstream in(path, std::ios::binary);
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        auto tab = line.find('\t');
        if (tab == std::string::npos) continue;
        auto end = line.find('\t', tab + 1);
        table[line.substr(0, tab)] = line.substr(tab + 1, end == std::string::npos ? std::string::npos : end - tab - 1);
    }
    return table;
}

size_t maxLen(const Table& t) {
    size_t m = 1;
    for (const auto& [k, v] : t) m = std::max(m, countUtf8(k));
    return m;
}

}  // namespace

class ZhuyinEncoder {
public:
    std::string symbolMode = "drop";              // drop：符號略過；keep：符號保留
    std::unordered_set<char32_t> symbolExceptions;  // 與 symbolMode 相反處理的符號

    static ZhuyinEncoder load(const std::string& dataDir, const std::string& scheme,
                              const std::optional<std::string>& profile) {
        ZhuyinEncoder e;
        e.chars_ = loadTsv(dataDir + "/" + scheme + "/chars.tsv");
        e.phrases_ = loadTsv(dataDir + "/" + scheme + "/phrases.tsv");
        if (profile) {
            // 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
            for (auto& [key, code] : loadTsv(dataDir + "/profiles/" + *profile + "/" + scheme + ".tsv"))
                (countUtf8(key) == 1 ? e.chars_ : e.overrides_)[key] = code;
        }
        e.maxPhrase_ = maxLen(e.phrases_);
        e.maxOverride_ = maxLen(e.overrides_);
        return e;
    }

    std::string encode(const std::string& text) const {
        std::vector<size_t> offs;
        auto cps = decodeUtf8(text, offs);
        for (auto& cp : cps) {  // 簡化版 NFKC：全形 ASCII 轉半形
            if (cp >= 0xFF01 && cp <= 0xFF5E) cp -= 0xFEE0;
            else if (cp == 0x3000) cp = U' ';
        }
        std::string out;
        size_t i = 0;
        while (i < cps.size()) {
            if (isHan(cps[i])) {
                size_t j = i;
                while (j < cps.size() && isHan(cps[j])) j++;
                out += encodeHan(text, offs, i, j);
                i = j;
                continue;
            }
            char32_t c = cps[i++];
            if ((c >= U'0' && c <= U'9') || (c >= U'A' && c <= U'Z')) out += static_cast<char>(c);
            else if (c >= U'a' && c <= U'z') out += static_cast<char>(c - 32);
            else if (c != U' ' && c != U'\t' && c != U'\r' && c != U'\n') {
                bool keep = symbolMode == "keep";
                if (symbolExceptions.count(c)) keep = !keep;
                if (keep) appendUtf8(out, c);
            }
        }
        return out;
    }

private:
    Table chars_, phrases_, overrides_;
    size_t maxPhrase_ = 1, maxOverride_ = 1;

    std::string encodeHan(const std::string& text, const std::vector<size_t>& offs, size_t from, size_t to) const {
        size_t n = to - from;
        std::vector<char> codes(n, 0);  // 0 代表尚未決定
        auto slice = [&](size_t a, size_t b) { return text.substr(offs[from + a], offs[from + b] - offs[from + a]); };
        // 第 1 步：場景詞組優先鎖定
        maxMatch(slice, overrides_, maxOverride_, codes, 0, n);
        // 第 2 步：未鎖定的空隙用一般詞庫修正多音字
        for (size_t s = 0; s < n;) {
            if (codes[s]) { s++; continue; }
            size_t e = s;
            while (e < n && !codes[e]) e++;
            maxMatch(slice, phrases_, maxPhrase_, codes, s, e);
            s = e;
        }
        // 第 3 步：其餘逐字查表；查無此字則略過
        std::string out;
        for (size_t k = 0; k < n; k++) {
            if (codes[k]) { out += codes[k]; continue; }
            if (auto it = chars_.find(slice(k, k + 1)); it != chars_.end()) out += it->second;
        }
        return out;
    }

    // 在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes
    template <typename Slice>
    static void maxMatch(Slice slice, const Table& table, size_t max, std::vector<char>& codes, size_t start, size_t end) {
        size_t i = start;
        while (i < end) {
            bool hit = false;
            for (size_t size = std::min(max, end - i); size >= 2; size--) {
                if (auto it = table.find(slice(i, i + size)); it != table.end()) {
                    for (size_t k = 0; k < size && k < it->second.size(); k++) codes[i + k] = it->second[k];
                    i += size;
                    hit = true;
                    break;
                }
            }
            if (!hit) i++;
        }
    }
};

// ── 範例：用共用樣本資料驗證 ──
int main(int argc, char** argv) {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif
    std::string root = argc > 1 ? argv[1] : "../..";
    auto encoder = ZhuyinEncoder::load(root + "/data", "zhuyin", "product");

    std::ifstream in(root + "/tests/samples.tsv", std::ios::binary);
    if (!in) { std::cerr << "找不到 samples.tsv\n"; return 2; }
    int fail = 0;
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        auto tab = line.find('\t');
        std::string name = line.substr(0, tab), expected = line.substr(tab + 1);
        std::string got = encoder.encode(name);
        bool ok = got == expected;
        if (!ok) fail++;
        std::cout << (ok ? "PASS  " : "FAIL  ") << std::left << std::setw(18) << got << " " << name << "\n";
    }
    std::cout << (fail == 0 ? std::string("全部通過") : std::to_string(fail) + " 筆不符") << "\n";
    return fail == 0 ? 0 : 1;
}
