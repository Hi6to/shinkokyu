# 案15 社員証ケース（すべて FFF）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_only an15_idcase <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`core_case.gcode`](../../gcode/core_case.gcode) | PETG | 箱のコア（案7・15・17 共通）：下の殻・上の殻・吹き口の受け・押し棒 3本 | 1h 2m 51s | 14 g |
| 2 | [`core_dial.gcode`](../../gcode/core_dial.gcode) | PETG（0.12mm） | 空気口の円盤 2枚（層 0.12mm。1枚は予備） | 10m 30s | 1 g |
| 3 | [`core_tpu.gcode`](../../gcode/core_tpu.gcode) | TPU 95A | TPU：ストローをつかむ筒 ⑥ 2個 | 7m 6s | 1 g |
| 4 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 5 | [`idcase.gcode`](../../gcode/idcase.gcode) | PETG | 案15：カードの枠（裏・表） | 1h 26m 58s | 26 g |

合計（すべて）：約 **5.2 時間・54 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,980 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
