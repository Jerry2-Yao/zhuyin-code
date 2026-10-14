/*
 * 注音碼 C 範例（C99，無外部相依）
 *
 * 編譯：
 *   MSVC：cl /utf-8 /O2 zhuyin_code.c
 *   GCC ：gcc -std=c99 -O2 -o zhuyin_code zhuyin_code.c
 * 執行：zhuyin_code [repo 根目錄，預設 ../..]
 *       zhuyin_code bench <品名.csv> [轉碼結果輸出檔]
 *
 * 說明：C 標準函式庫沒有 Unicode NFKC 正規化，這裡只處理最常見的
 *       「全形 ASCII（U+FF01–FF5E）轉半形」與「全形空白 U+3000」。
 *       需要完整 NFKC 時可改用 ICU（unorm2_normalize）。
 */
#define _POSIX_C_SOURCE 199309L /* clock_gettime */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

/* ── 簡易雜湊表：UTF-8 字串 → UTF-8 字串 ── */
/* 對照表配置的位元組數（評測「載入記憶體」用；不含 malloc 自身的管理開銷） */
static size_t g_table_bytes = 0;

typedef struct { char *key; char *val; } Entry;
typedef struct { Entry *slots; size_t cap, count; int max_len; } Table;

static uint64_t fnv1a(const char *s, size_t n) {
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < n; i++) { h ^= (unsigned char)s[i]; h *= 1099511628211ULL; }
    return h;
}

static char *dupn(const char *s, size_t n) {
    char *p = malloc(n + 1);
    g_table_bytes += n + 1;
    memcpy(p, s, n);
    p[n] = '\0';
    return p;
}

static void table_init(Table *t) {
    t->cap = 1024;
    t->count = 0;
    t->max_len = 1;
    t->slots = calloc(t->cap, sizeof(Entry));
    g_table_bytes += t->cap * sizeof(Entry);
}

static Entry *table_find(const Table *t, const char *k, size_t kn) {
    size_t i = fnv1a(k, kn) & (t->cap - 1);
    while (t->slots[i].key) {
        if (strlen(t->slots[i].key) == kn && memcmp(t->slots[i].key, k, kn) == 0) return &t->slots[i];
        i = (i + 1) & (t->cap - 1);
    }
    return &t->slots[i]; /* 空格位 */
}

static void table_put(Table *t, const char *k, size_t kn, const char *v) {
    if ((t->count + 1) * 2 > t->cap) { /* 負載超過一半就擴充 */
        Entry *old = t->slots;
        size_t old_cap = t->cap;
        t->cap *= 2;
        t->slots = calloc(t->cap, sizeof(Entry));
        g_table_bytes += t->cap * sizeof(Entry) - old_cap * sizeof(Entry);
        for (size_t i = 0; i < old_cap; i++)
            if (old[i].key) *table_find(t, old[i].key, strlen(old[i].key)) = old[i];
        free(old);
    }
    Entry *e = table_find(t, k, kn);
    if (e->key) { g_table_bytes -= strlen(e->val) + 1; free(e->val); e->val = dupn(v, strlen(v)); return; }
    e->key = dupn(k, kn);
    e->val = dupn(v, strlen(v));
    t->count++;
}

static const char *table_get(const Table *t, const char *k, size_t kn) {
    const Entry *e = table_find(t, k, kn);
    return e->key ? e->val : NULL;
}

/* ── UTF-8 ── */
/* 解碼為 code point 陣列；offs[i] 為第 i 個字元在原字串的位元組位置，offs[n] = 總長 */
static size_t utf8_decode(const char *s, uint32_t *cps, size_t *offs) {
    size_t n = 0, i = 0, len = strlen(s);
    while (i < len) {
        unsigned char c = (unsigned char)s[i];
        int extra = c < 0x80 ? 0 : c < 0xE0 ? 1 : c < 0xF0 ? 2 : 3;
        uint32_t cp = extra == 0 ? c : c & (0x3F >> extra);
        for (int k = 1; k <= extra && i + k < len; k++) cp = (cp << 6) | ((unsigned char)s[i + k] & 0x3F);
        offs[n] = i;
        cps[n++] = cp;
        i += extra + 1;
    }
    offs[n] = len;
    return n;
}

static size_t utf8_count(const char *s) {
    size_t n = 0;
    for (; *s; s++) if (((unsigned char)*s & 0xC0) != 0x80) n++;
    return n;
}

static void utf8_append(char *out, size_t *o, uint32_t cp) {
    if (cp < 0x80) out[(*o)++] = (char)cp;
    else if (cp < 0x800) { out[(*o)++] = (char)(0xC0 | cp >> 6); out[(*o)++] = (char)(0x80 | (cp & 0x3F)); }
    else if (cp < 0x10000) {
        out[(*o)++] = (char)(0xE0 | cp >> 12); out[(*o)++] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[(*o)++] = (char)(0x80 | (cp & 0x3F));
    } else {
        out[(*o)++] = (char)(0xF0 | cp >> 18); out[(*o)++] = (char)(0x80 | ((cp >> 12) & 0x3F));
        out[(*o)++] = (char)(0x80 | ((cp >> 6) & 0x3F)); out[(*o)++] = (char)(0x80 | (cp & 0x3F));
    }
}

static int is_han(uint32_t cp) {
    return cp == 0x3007 || (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF) ||
           (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0x20000 && cp <= 0x3FFFF);
}

/* ── 對照表載入 ── */
/* single 不為 NULL 時：單字條目放 single，詞組放 t（用於場景覆寫） */
static void load_tsv(const char *path, Table *t, Table *single) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return;
    char line[4096];
    while (fgets(line, sizeof line, fp)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (!line[0] || line[0] == '#') continue;
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = '\0';
        char *val = tab + 1;
        val[strcspn(val, "\t")] = '\0';
        int n = (int)utf8_count(line);
        Table *dst = (single && n == 1) ? single : t;
        table_put(dst, line, strlen(line), val);
        if (n > dst->max_len) dst->max_len = n;
    }
    fclose(fp);
}

typedef struct {
    Table chars, phrases, overrides;
    int symbol_keep;               /* 0：符號略過（drop）；1：符號保留（keep） */
    const uint32_t *exceptions;    /* 與 symbol_keep 相反處理的符號 */
    size_t n_exceptions;
} Encoder;

static void encoder_load(Encoder *e, const char *data_dir, const char *scheme, const char *profile) {
    char path[1024];
    memset(e, 0, sizeof *e);
    table_init(&e->chars);
    table_init(&e->phrases);
    table_init(&e->overrides);
    snprintf(path, sizeof path, "%s/%s/chars.tsv", data_dir, scheme);
    load_tsv(path, &e->chars, NULL);
    snprintf(path, sizeof path, "%s/%s/phrases.tsv", data_dir, scheme);
    load_tsv(path, &e->phrases, NULL);
    if (profile) { /* 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定） */
        snprintf(path, sizeof path, "%s/profiles/%s/%s.tsv", data_dir, profile, scheme);
        load_tsv(path, &e->overrides, &e->chars);
    }
}

/* 在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes（0 代表未決定） */
static void max_match(const char *text, const size_t *offs, size_t base, const Table *t,
                      char *codes, size_t start, size_t end) {
    size_t i = start;
    while (i < end) {
        size_t size = (size_t)t->max_len < end - i ? (size_t)t->max_len : end - i;
        for (; size >= 2; size--) {
            size_t b = offs[base + i], e = offs[base + i + size];
            const char *code = table_get(t, text + b, e - b);
            if (code) {
                for (size_t k = 0; k < size && code[k]; k++) codes[i + k] = code[k];
                break;
            }
        }
        i += size >= 2 ? size : 1;
    }
}

/* text：UTF-8 品名；out：輸出緩衝區（建議 >= strlen(text) + 1） */
static void encode(const Encoder *e, const char *text, char *out) {
    size_t len = strlen(text);
    uint32_t *cps = malloc((len + 1) * sizeof *cps);
    size_t *offs = malloc((len + 1) * sizeof *offs);
    char *codes = malloc(len + 1);
    size_t n = utf8_decode(text, cps, offs), o = 0;

    for (size_t i = 0; i < n; i++) { /* 簡化版 NFKC：全形 ASCII 轉半形 */
        if (cps[i] >= 0xFF01 && cps[i] <= 0xFF5E) cps[i] -= 0xFEE0;
        else if (cps[i] == 0x3000) cps[i] = ' ';
    }

    size_t i = 0;
    while (i < n) {
        if (is_han(cps[i])) {
            size_t j = i;
            while (j < n && is_han(cps[j])) j++;
            size_t m = j - i;
            memset(codes, 0, m);
            /* 第 1 步：場景詞組優先鎖定 */
            max_match(text, offs, i, &e->overrides, codes, 0, m);
            /* 第 2 步：未鎖定的空隙用一般詞庫修正多音字 */
            for (size_t s = 0; s < m;) {
                if (codes[s]) { s++; continue; }
                size_t g = s;
                while (g < m && !codes[g]) g++;
                max_match(text, offs, i, &e->phrases, codes, s, g);
                s = g;
            }
            /* 第 3 步：其餘逐字查表；查無此字則略過 */
            for (size_t k = 0; k < m; k++) {
                if (codes[k]) { out[o++] = codes[k]; continue; }
                const char *code = table_get(&e->chars, text + offs[i + k], offs[i + k + 1] - offs[i + k]);
                if (code) { size_t cl = strlen(code); memcpy(out + o, code, cl); o += cl; }
            }
            i = j;
            continue;
        }
        uint32_t c = cps[i++];
        if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')) out[o++] = (char)c;
        else if (c >= 'a' && c <= 'z') out[o++] = (char)(c - 32);
        else if (c != ' ' && c != '\t' && c != '\r' && c != '\n') {
            int keep = e->symbol_keep;
            for (size_t k = 0; k < e->n_exceptions; k++) if (e->exceptions[k] == c) keep = !keep;
            if (keep) utf8_append(out, &o, c);
        }
    }
    out[o] = '\0';
    free(cps);
    free(offs);
    free(codes);
}

/* ── 效能評測 ── */
static double now_ms(void) {
#ifdef _WIN32
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart * 1000.0 / (double)f.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
#endif
}

/* 讀取單欄 CSV（UTF-8，可含 BOM 與 "..." 引號），回傳筆數 */
static size_t read_csv_names(const char *path, char ***names_out) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return 0;
    size_t n = 0, cap = 1024;
    char **names = malloc(cap * sizeof *names), line[4096];
    while (fgets(line, sizeof line, fp)) {
        line[strcspn(line, "\r\n")] = '\0';
        char *s = line;
        if ((unsigned char)s[0] == 0xEF && (unsigned char)s[1] == 0xBB && (unsigned char)s[2] == 0xBF) s += 3;
        size_t len = strlen(s);
        if (len >= 2 && s[0] == '"' && s[len - 1] == '"') { /* 去掉外層引號，"" 還原為 " */
            size_t o = 0;
            for (size_t i = 1; i < len - 1; i++) {
                s[o++] = s[i];
                if (s[i] == '"' && s[i + 1] == '"') i++;
            }
            s[o] = '\0';
        }
        if (strspn(s, " \t") == strlen(s)) continue;
        if (n == cap) names = realloc(names, (cap *= 2) * sizeof *names);
        names[n++] = dupn(s, strlen(s));
    }
    fclose(fp);
    *names_out = names;
    return n;
}

static int bench(const char *root, const char *csv, const char *out_path) {
    const int rounds = 10;
    char **names, path[1024], buf[4096];
    size_t n = read_csv_names(csv, &names);
    if (n == 0) { fprintf(stderr, "讀不到 %s\n", csv); return 2; }

    Encoder enc;
    size_t mem_before = g_table_bytes;
    double t0 = now_ms();
    snprintf(path, sizeof path, "%s/data", root);
    encoder_load(&enc, path, "zhuyin", "product");
    double load_ms = now_ms() - t0;
    double mem_mb = (double)(g_table_bytes - mem_before) / 1024.0 / 1024.0;

    FILE *out = out_path ? fopen(out_path, "wb") : NULL;
    for (size_t k = 0; k < n; k++) { /* 暖機 */
        encode(&enc, names[k], buf);
        if (out) fprintf(out, "%s\t%s\n", buf, names[k]);
    }
    if (out) fclose(out);
    t0 = now_ms();
    for (int r = 0; r < rounds; r++)
        for (size_t k = 0; k < n; k++) encode(&enc, names[k], buf);
    double per_us = (now_ms() - t0) * 1000.0 / ((double)rounds * (double)n);

    printf("=== 注音碼效能評測（C） ===\n");
    printf("商品筆數        : %zu\n", n);
    printf("1. 載入時間      : %.1f ms\n", load_ms);
    printf("2. 平均轉碼時間  : %.2f µs / 筆（%d 輪，共 %zu 次）\n", per_us, rounds, rounds * n);
    printf("3. 載入記憶體    : %.1f MB（對照表配置的位元組數）\n", mem_mb);
    return 0;
}

/* ── 範例：用共用樣本資料驗證；bench 模式做效能評測 ── */
int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif
    if (argc > 2 && strcmp(argv[1], "bench") == 0) return bench("../..", argv[2], argc > 3 ? argv[3] : NULL);
    const char *root = argc > 1 ? argv[1] : "../..";
    char path[1024], line[4096], out[4096];
    Encoder enc;
    snprintf(path, sizeof path, "%s/data", root);
    encoder_load(&enc, path, "zhuyin", "product");

    snprintf(path, sizeof path, "%s/tests/samples.tsv", root);
    FILE *fp = fopen(path, "rb");
    if (!fp) { fprintf(stderr, "找不到 %s\n", path); return 2; }
    int fail = 0;
    while (fgets(line, sizeof line, fp)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (!line[0] || line[0] == '#') continue;
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = '\0';
        const char *expected = tab + 1;
        encode(&enc, line, out);
        int ok = strcmp(out, expected) == 0;
        if (!ok) fail++;
        printf("%s  %-18s %s\n", ok ? "PASS" : "FAIL", out, line);
    }
    fclose(fp);
    if (fail == 0) printf("全部通過\n");
    else printf("%d 筆不符\n", fail);
    return fail == 0 ? 0 : 1;
}
