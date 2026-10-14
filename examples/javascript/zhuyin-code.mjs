// 注音碼 JavaScript（Node.js）範例
// 執行：node zhuyin-code.mjs [repo 根目錄，預設 ../..]
import fs from "node:fs";
import path from "node:path";

const isHan = (cp) =>
  cp === 0x3007 ||
  (cp >= 0x3400 && cp <= 0x4dbf) ||
  (cp >= 0x4e00 && cp <= 0x9fff) ||
  (cp >= 0xf900 && cp <= 0xfaff) ||
  (cp >= 0x20000 && cp <= 0x3ffff);

function loadTsv(file) {
  const table = new Map();
  if (!fs.existsSync(file)) return table;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line || line.startsWith("#")) continue;
    const [key, value] = line.split("\t");
    table.set(key, value);
  }
  return table;
}

const maxLen = (table) => Math.max(1, ...[...table.keys()].map((k) => Array.from(k).length));

export class ZhuyinEncoder {
  constructor(chars, phrases, overrides, { symbolMode = "drop", symbolExceptions = [] } = {}) {
    this.chars = chars;
    this.phrases = phrases;
    this.overrides = overrides;
    this.maxPhrase = maxLen(phrases);
    this.maxOverride = maxLen(overrides);
    this.symbolMode = symbolMode; // drop：符號略過；keep：符號保留
    this.symbolExceptions = new Set(symbolExceptions); // 與 symbolMode 相反處理的符號
  }

  static load(dataDir, scheme = "zhuyin", profile = null, options = {}) {
    const chars = loadTsv(path.join(dataDir, scheme, "chars.tsv"));
    const phrases = loadTsv(path.join(dataDir, scheme, "phrases.tsv"));
    const overrides = new Map();
    if (profile) {
      // 場景覆寫：單字蓋 chars，詞組放 overrides（比對時優先鎖定）
      for (const [key, code] of loadTsv(path.join(dataDir, "profiles", profile, `${scheme}.tsv`))) {
        (Array.from(key).length === 1 ? chars : overrides).set(key, code);
      }
    }
    return new ZhuyinEncoder(chars, phrases, overrides, options);
  }

  encode(text) {
    const cps = Array.from(text.normalize("NFKC")); // 以 code point 為單位（含擴充區漢字）
    let out = "";
    let i = 0;
    while (i < cps.length) {
      if (isHan(cps[i].codePointAt(0))) {
        let j = i;
        while (j < cps.length && isHan(cps[j].codePointAt(0))) j++;
        out += this.#encodeHan(cps.slice(i, j));
        i = j;
        continue;
      }
      const c = cps[i++];
      if (/^[A-Za-z0-9]$/.test(c)) out += c.toUpperCase();
      else if (!/^\s$/u.test(c)) {
        let keep = this.symbolMode === "keep";
        if (this.symbolExceptions.has(c)) keep = !keep;
        if (keep) out += c;
      }
    }
    return out;
  }

  #encodeHan(run) {
    const codes = new Array(run.length).fill(null);
    // 第 1 步：場景詞組優先鎖定
    maxMatch(run, this.overrides, this.maxOverride, codes, 0, run.length);
    // 第 2 步：未鎖定的空隙用一般詞庫修正多音字
    for (let s = 0; s < run.length; ) {
      if (codes[s] !== null) { s++; continue; }
      let e = s;
      while (e < run.length && codes[e] === null) e++;
      maxMatch(run, this.phrases, this.maxPhrase, codes, s, e);
      s = e;
    }
    // 第 3 步：其餘逐字查表；查無此字則略過
    return codes.map((c, k) => c ?? this.chars.get(run[k]) ?? "").join("");
  }
}

// 在 [start, end) 內左到右最長比對，命中的詞把每字的碼填入 codes
function maxMatch(run, table, max, codes, start, end) {
  let i = start;
  while (i < end) {
    let hit = false;
    for (let size = Math.min(max, end - i); size >= 2; size--) {
      const code = table.get(run.slice(i, i + size).join(""));
      if (code) {
        for (let k = 0; k < size; k++) codes[i + k] = code[k];
        i += size;
        hit = true;
        break;
      }
    }
    if (!hit) i++;
  }
}

// ── 範例：用共用樣本資料驗證 ──
const root = process.argv[2] ?? path.join("..", "..");
const encoder = ZhuyinEncoder.load(path.join(root, "data"), "zhuyin", "product");
let fail = 0;
for (const line of fs.readFileSync(path.join(root, "tests", "samples.tsv"), "utf8").split(/\r?\n/)) {
  if (!line || line.startsWith("#")) continue;
  const [name, expected] = line.split("\t");
  const got = encoder.encode(name);
  if (got !== expected) fail++;
  console.log(`${got === expected ? "PASS" : "FAIL"}  ${got.padEnd(18)} ${name}`);
}
console.log(fail === 0 ? "全部通過" : `${fail} 筆不符`);
process.exit(fail === 0 ? 0 : 1);
