// 注音碼 Java 範例（Java 11+ 可直接執行單一原始檔）
// 執行：java ZhuyinCode.java [repo 根目錄，預設 ../..]
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public class ZhuyinCode {
    private final Map<String, String> chars, phrases, overrides;
    private final int maxPhrase, maxOverride;
    public String symbolMode = "drop";                     // drop：符號略過；keep：符號保留
    public Set<Integer> symbolExceptions = new HashSet<>(); // 與 symbolMode 相反處理的符號（code point）

    public ZhuyinCode(Map<String, String> chars, Map<String, String> phrases, Map<String, String> overrides) {
        this.chars = chars;
        this.phrases = phrases;
        this.overrides = overrides;
        this.maxPhrase = maxLen(phrases);
        this.maxOverride = maxLen(overrides);
    }

    public static ZhuyinCode load(Path dataDir, String scheme, String profile) throws IOException {
        Map<String, String> chars = loadTsv(dataDir.resolve(scheme).resolve("chars.tsv"));
        Map<String, String> phrases = loadTsv(dataDir.resolve(scheme).resolve("phrases.tsv"));
        Map<String, String> overrides = new HashMap<>();
        if (profile != null) {
            // 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
            Path p = dataDir.resolve("profiles").resolve(profile).resolve(scheme + ".tsv");
            for (var e : loadTsv(p).entrySet()) {
                String key = e.getKey();
                (key.codePointCount(0, key.length()) == 1 ? chars : overrides).put(key, e.getValue());
            }
        }
        return new ZhuyinCode(chars, phrases, overrides);
    }

    public String encode(String text) {
        // 以 code point 為單位，才能正確處理擴充區漢字（UTF-16 代理對）
        int[] cps = Normalizer.normalize(text, Normalizer.Form.NFKC).codePoints().toArray();
        StringBuilder out = new StringBuilder();
        int i = 0;
        while (i < cps.length) {
            if (isHan(cps[i])) {
                int j = i;
                while (j < cps.length && isHan(cps[j])) j++;
                out.append(encodeHan(cps, i, j));
                i = j;
                continue;
            }
            int c = cps[i++];
            if (c < 128 && Character.isLetterOrDigit(c)) {
                out.append(Character.toUpperCase((char) c));
            } else if (!Character.isWhitespace(c)) {
                boolean keep = symbolMode.equals("keep");
                if (symbolExceptions.contains(c)) keep = !keep;
                if (keep) out.appendCodePoint(c);
            }
        }
        return out.toString();
    }

    private String encodeHan(int[] cps, int from, int to) {
        int n = to - from;
        char[] codes = new char[n]; // '\0' 代表尚未決定
        // 第 1 步：場景詞組優先鎖定
        maxMatch(cps, from, overrides, maxOverride, codes, 0, n);
        // 第 2 步：未鎖定的空隙用一般詞庫修正多音字
        for (int s = 0; s < n; ) {
            if (codes[s] != 0) { s++; continue; }
            int e = s;
            while (e < n && codes[e] == 0) e++;
            maxMatch(cps, from, phrases, maxPhrase, codes, s, e);
            s = e;
        }
        // 第 3 步：其餘逐字查表；查無此字則略過
        StringBuilder sb = new StringBuilder();
        for (int k = 0; k < n; k++) {
            if (codes[k] != 0) sb.append(codes[k]);
            else sb.append(chars.getOrDefault(new String(cps, from + k, 1), ""));
        }
        return sb.toString();
    }

    // 在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes
    private static void maxMatch(int[] cps, int base, Map<String, String> table, int max,
                                 char[] codes, int start, int end) {
        int i = start;
        while (i < end) {
            boolean hit = false;
            for (int size = Math.min(max, end - i); size >= 2; size--) {
                String code = table.get(new String(cps, base + i, size));
                if (code != null) {
                    for (int k = 0; k < size; k++) codes[i + k] = code.charAt(k);
                    i += size;
                    hit = true;
                    break;
                }
            }
            if (!hit) i++;
        }
    }

    private static boolean isHan(int cp) {
        return cp == 0x3007 || (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF)
                || (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0x20000 && cp <= 0x3FFFF);
    }

    private static int maxLen(Map<String, String> table) {
        return table.keySet().stream().mapToInt(k -> k.codePointCount(0, k.length())).max().orElse(1);
    }

    private static Map<String, String> loadTsv(Path path) throws IOException {
        Map<String, String> table = new HashMap<>();
        if (!Files.exists(path)) return table;
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split("\t");
            table.put(f[0], f[1]);
        }
        return table;
    }

    // 讀取單欄 CSV（UTF-8，可含 BOM 與 "..." 引號）
    static List<String> readCsvNames(Path path) throws IOException {
        List<String> names = new ArrayList<>();
        for (String l : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (!l.isEmpty() && l.charAt(0) == '﻿') l = l.substring(1);
            if (l.length() >= 2 && l.startsWith("\"") && l.endsWith("\"")) l = l.substring(1, l.length() - 1).replace("\"\"", "\"");
            if (!l.isBlank()) names.add(l);
        }
        return names;
    }

    static long usedHeap() {
        Runtime rt = Runtime.getRuntime();
        for (int i = 0; i < 3; i++) System.gc();
        return rt.totalMemory() - rt.freeMemory();
    }

    static void bench(PrintStream out, Path root, Path csv, Path outFile) throws IOException {
        final int rounds = 10;
        List<String> names = readCsvNames(csv);

        long memBefore = usedHeap();
        long t0 = System.nanoTime();
        ZhuyinCode encoder = load(root.resolve("data"), "zhuyin", "product");
        double loadMs = (System.nanoTime() - t0) / 1e6;
        double memMb = (usedHeap() - memBefore) / 1024.0 / 1024.0;

        List<String> codes = new ArrayList<>();
        for (String n : names) codes.add(encoder.encode(n)); // 暖機
        t0 = System.nanoTime();
        for (int r = 0; r < rounds; r++)
            for (String n : names) encoder.encode(n);
        double perUs = (System.nanoTime() - t0) / 1e3 / (rounds * names.size());

        if (outFile != null) {
            StringBuilder sb = new StringBuilder();
            for (int k = 0; k < names.size(); k++) sb.append(codes.get(k)).append('\t').append(names.get(k)).append('\n');
            Files.writeString(outFile, sb.toString(), StandardCharsets.UTF_8);
        }
        out.println("=== 注音碼效能評測（Java） ===");
        out.printf("商品筆數        : %d%n", names.size());
        out.printf("1. 載入時間      : %.1f ms%n", loadMs);
        out.printf("2. 平均轉碼時間  : %.2f µs / 筆（%d 輪，共 %d 次）%n", perUs, rounds, rounds * names.size());
        out.printf("3. 載入記憶體    : %.1f MB（GC 後 heap 使用量差值）%n", memMb);
        java.lang.ref.Reference.reachabilityFence(encoder); // 確保量記憶體時 encoder 仍存活
    }

    // ── 範例：用共用樣本資料驗證；bench 模式做效能評測 ──
    // 用法：java ZhuyinCode.java [repo 根目錄]
    //       java ZhuyinCode.java bench <品名.csv> [轉碼結果輸出檔]
    public static void main(String[] args) throws IOException {
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        if (args.length > 1 && args[0].equals("bench")) {
            bench(out, Path.of("../.."), Path.of(args[1]), args.length > 2 ? Path.of(args[2]) : null);
            return;
        }
        Path root = Path.of(args.length > 0 ? args[0] : "../..");
        ZhuyinCode encoder = load(root.resolve("data"), "zhuyin", "product");
        int fail = 0;
        for (String line : Files.readAllLines(root.resolve("tests/samples.tsv"), StandardCharsets.UTF_8)) {
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split("\t");
            String got = encoder.encode(f[0]);
            boolean ok = got.equals(f[1]);
            if (!ok) fail++;
            out.printf("%s  %-18s %s%n", ok ? "PASS" : "FAIL", got, f[0]);
        }
        out.println(fail == 0 ? "全部通過" : fail + " 筆不符");
        System.exit(fail == 0 ? 0 : 1);
    }
}
