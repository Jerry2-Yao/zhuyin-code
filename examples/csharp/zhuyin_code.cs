// 注音碼 C# 範例（.NET 10 單檔程式）
// 執行：dotnet run zhuyin_code.cs [repo 根目錄，預設 ../..]
//       dotnet run -c Release zhuyin_code.cs bench <品名.csv> [轉碼結果輸出檔]
using System.Diagnostics;
using System.Text;

Console.OutputEncoding = Encoding.UTF8;
if (args.Length > 1 && args[0] == "bench")
{
    Bench.Run(Path.Combine("..", ".."), args[1], args.Length > 2 ? args[2] : null);
    return 0;
}
var root = args.Length > 0 ? args[0] : Path.Combine("..", "..");
var encoder = ZhuyinEncoder.Load(Path.Combine(root, "data"), "zhuyin", "product");

int fail = 0;
foreach (var line in File.ReadLines(Path.Combine(root, "tests", "samples.tsv")))
{
    if (line.Length == 0 || line.StartsWith('#')) continue;
    var f = line.Split('\t');
    var got = encoder.Encode(f[0]);
    if (got != f[1]) fail++;
    Console.WriteLine($"{(got == f[1] ? "PASS" : "FAIL")}  {got,-18} {f[0]}");
}
Console.WriteLine(fail == 0 ? "全部通過" : $"{fail} 筆不符");
return fail == 0 ? 0 : 1;

static class Bench
{
    // 讀取單欄 CSV（UTF-8，可含 BOM 與 "..." 引號）
    static List<string> ReadCsvNames(string path) =>
        File.ReadLines(path, Encoding.UTF8)
            .Select(l => l.Length >= 2 && l.StartsWith('"') && l.EndsWith('"') ? l[1..^1].Replace("\"\"", "\"") : l)
            .Where(l => l.Trim().Length > 0)
            .ToList();

    public static void Run(string root, string csvPath, string? outPath, int rounds = 10)
    {
        var names = ReadCsvNames(csvPath);

        long memBefore = GC.GetTotalMemory(forceFullCollection: true);
        var sw = Stopwatch.StartNew();
        var encoder = ZhuyinEncoder.Load(Path.Combine(root, "data"), "zhuyin", "product");
        double loadMs = sw.Elapsed.TotalMilliseconds;
        double memMb = (GC.GetTotalMemory(forceFullCollection: true) - memBefore) / 1024.0 / 1024.0;

        var codes = names.Select(encoder.Encode).ToList(); // 暖機
        sw.Restart();
        for (int r = 0; r < rounds; r++)
            foreach (var n in names) encoder.Encode(n);
        double perUs = sw.Elapsed.TotalMicroseconds / (rounds * names.Count);

        if (outPath != null)
            File.WriteAllText(outPath, string.Concat(names.Select((n, k) => $"{codes[k]}\t{n}\n")));
        Console.WriteLine("=== 注音碼效能評測（C#） ===");
        Console.WriteLine($"商品筆數        : {names.Count}");
        Console.WriteLine($"1. 載入時間      : {loadMs:F1} ms");
        Console.WriteLine($"2. 平均轉碼時間  : {perUs:F2} µs / 筆（{rounds} 輪，共 {rounds * names.Count} 次）");
        Console.WriteLine($"3. 載入記憶體    : {memMb:F1} MB（GC.GetTotalMemory 差值）");
        GC.KeepAlive(encoder);
    }
}

public class ZhuyinEncoder
{
    readonly Dictionary<string, string> chars, phrases, overrides;
    readonly int maxPhrase, maxOverride;
    public string SymbolMode { get; init; } = "drop";               // drop：符號略過；keep：符號保留
    public HashSet<string> SymbolExceptions { get; init; } = new();  // 與 SymbolMode 相反處理的符號

    public ZhuyinEncoder(Dictionary<string, string> chars, Dictionary<string, string> phrases,
                         Dictionary<string, string> overrides)
    {
        this.chars = chars;
        this.phrases = phrases;
        this.overrides = overrides;
        maxPhrase = MaxLen(phrases);
        maxOverride = MaxLen(overrides);
    }

    public static ZhuyinEncoder Load(string dataDir, string scheme = "zhuyin", string? profile = null)
    {
        var chars = LoadTsv(Path.Combine(dataDir, scheme, "chars.tsv"));
        var phrases = LoadTsv(Path.Combine(dataDir, scheme, "phrases.tsv"));
        var overrides = new Dictionary<string, string>();
        if (profile != null)
        {
            // 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
            foreach (var (key, code) in LoadTsv(Path.Combine(dataDir, "profiles", profile, $"{scheme}.tsv")))
                (key.EnumerateRunes().Count() == 1 ? chars : overrides)[key] = code;
        }
        return new ZhuyinEncoder(chars, phrases, overrides);
    }

    public string Encode(string text)
    {
        // 以 Rune（code point）為單位，才能正確處理擴充區漢字（UTF-16 代理對）
        var runes = text.Normalize(NormalizationForm.FormKC).EnumerateRunes().ToArray();
        var sb = new StringBuilder();
        int i = 0;
        while (i < runes.Length)
        {
            if (IsHan(runes[i].Value))
            {
                int j = i;
                while (j < runes.Length && IsHan(runes[j].Value)) j++;
                sb.Append(EncodeHan(runes[i..j].Select(r => r.ToString()).ToArray()));
                i = j;
                continue;
            }
            var c = runes[i++];
            if (c.IsAscii && char.IsAsciiLetterOrDigit((char)c.Value))
                sb.Append(char.ToUpperInvariant((char)c.Value));
            else if (!Rune.IsWhiteSpace(c))
            {
                bool keep = SymbolMode == "keep";
                if (SymbolExceptions.Contains(c.ToString())) keep = !keep;
                if (keep) sb.Append(c.ToString());
            }
        }
        return sb.ToString();
    }

    string EncodeHan(string[] run)
    {
        var codes = new char?[run.Length];
        // 第 1 步：場景詞組優先鎖定
        MaxMatch(run, overrides, maxOverride, codes, 0, run.Length);
        // 第 2 步：未鎖定的空隙用一般詞庫修正多音字
        for (int s = 0; s < run.Length;)
        {
            if (codes[s] != null) { s++; continue; }
            int e = s;
            while (e < run.Length && codes[e] == null) e++;
            MaxMatch(run, phrases, maxPhrase, codes, s, e);
            s = e;
        }
        // 第 3 步：其餘逐字查表；查無此字則略過
        var sb = new StringBuilder();
        for (int k = 0; k < run.Length; k++)
        {
            if (codes[k] is char c) sb.Append(c);
            else if (chars.TryGetValue(run[k], out var code)) sb.Append(code);
        }
        return sb.ToString();
    }

    // 在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes
    static void MaxMatch(string[] run, Dictionary<string, string> table, int max, char?[] codes, int start, int end)
    {
        int i = start;
        while (i < end)
        {
            bool hit = false;
            for (int size = Math.Min(max, end - i); size >= 2; size--)
            {
                if (table.TryGetValue(string.Concat(run[i..(i + size)]), out var code))
                {
                    for (int k = 0; k < size; k++) codes[i + k] = code[k];
                    i += size;
                    hit = true;
                    break;
                }
            }
            if (!hit) i++;
        }
    }

    static bool IsHan(int cp) =>
        cp == 0x3007 || (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF) ||
        (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0x20000 && cp <= 0x3FFFF);

    static int MaxLen(Dictionary<string, string> table) =>
        table.Count == 0 ? 1 : table.Keys.Max(k => k.EnumerateRunes().Count());

    static Dictionary<string, string> LoadTsv(string path)
    {
        var table = new Dictionary<string, string>();
        if (!File.Exists(path)) return table;
        foreach (var line in File.ReadLines(path, Encoding.UTF8))
        {
            if (line.Length == 0 || line.StartsWith('#')) continue;
            var f = line.Split('\t');
            table[f[0]] = f[1];
        }
        return table;
    }
}
