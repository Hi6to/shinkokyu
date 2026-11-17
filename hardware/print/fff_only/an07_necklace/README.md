# 案7 ネックレス（すべて FFF）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_only an07_necklace <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`necklace.gcode`](../../gcode/necklace.gcode) | PETG | 案7：ひもの輪つきの下の殻・上の殻・吹き口の受け・押し棒 3本 | 1h 4m 48s | 14 g |
| 2 | [`core_dial.gcode`](../../gcode/core_dial.gcode) | PETG（0.12mm） | 空気口の円盤 2枚（層 0.12mm。1枚は予備） | 10m 30s | 1 g |
| 3 | [`core_tpu.gcode`](../../gcode/core_tpu.gcode) | TPU 95A | TPU：ストローをつかむ筒 ⑥ 2個 | 7m 6s | 1 g |
| 4 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |

合計（すべて）：約 **3.8 時間・27 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,320 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
