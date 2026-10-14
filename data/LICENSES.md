# 資料來源與授權

本專案的**程式碼**採用 MIT 授權（見根目錄 `LICENSE`）。`data/` 底下的**對照表**是從下列開源碼表轉換而來，依上游授權條款釋出：

| 檔案 | 來源 | 授權 |
|---|---|---|
| `zhuyin/chars.tsv`、`zhuyin/phrases.tsv` | [rime/rime-terra-pinyin](https://github.com/rime/rime-terra-pinyin) 的 `terra_pinyin.dict.yaml`，該檔衍生自 [CC-CEDICT](https://cc-cedict.org/) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `cangjie/chars.tsv` | [rime/rime-cangjie](https://github.com/rime/rime-cangjie) 的 `cangjie5.base.dict.yaml`（單字碼表《五倉世紀》） | GPL |
| `profiles/` | 本專案自建 | MIT |

## 轉換方式

由 `scripts/build_data.py` 產生，處理步驟如下：

- **注音**：每個字取權重最高的拼音讀音，再換成第一個注音符號所在的大千鍵盤按鍵。詞組只保留「與逐字預設結果不同」的條目。
- **倉頡**：每個字取第一筆編碼的首碼。

## 使用注意

- 依 CC BY-SA 3.0，再散布 `data/zhuyin/` 或其衍生資料時，須標示出處，並以相同授權釋出。
- 依 GPL，再散布 `data/cangjie/` 時須遵循 GPL 條款。
- 如果需要更寬鬆的授權，可以改用 MIT 授權的 [mozillazg/pinyin-data](https://github.com/mozillazg/pinyin-data)，或 [Unicode Unihan](https://www.unicode.org/charts/unihan.html) 的 `kMandarin` / `kCangjie` 欄位自行產生。
