# 案5 スタンド・ゆったり版（案1 ゆったり版＋スタンド。スタンドは好きなものを1つ）（すべて FFF）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_only an05w_stand_wide <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`wide_body_tube.gcode`](../../gcode/wide_body_tube.gcode) | PETG | 案1 ゆったり版の筒（外径 32）：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本 | 2h 23m 48s | 29 g |
| 2 | [`body_tpu.gcode`](../../gcode/body_tpu.gcode) | TPU 95A | TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個 | 14m 24s | 1 g |
| 3 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 4 | [`wide_stand_side_charge.gcode`](../../gcode/wide_stand_side_charge.gcode) | PETG | 案5 横から充電するスタンド（ゆったり版用）（選んだものだけ） | 2h 14m 47s | 43 g |
| 5 | [`wide_stand_plain.gcode`](../../gcode/wide_stand_plain.gcode) | PETG | 案5 ふつうのスタンド（ゆったり版用）（選んだものだけ） | 2h 14m 35s | 43 g |
| 6 | [`wide_stand_volcano.gcode`](../../gcode/wide_stand_volcano.gcode) | PETG | 案5-A 火山（ゆったり版用）（選んだものだけ） | 2h 21m 18s | 45 g |
| 7 | [`wide_stand_rocket.gcode`](../../gcode/wide_stand_rocket.gcode) | PETG | 案5-C ロケット発射台＋発射塔（ゆったり版用）（選んだものだけ） | 2h 51m 9s | 40 g |
| 8 | [`wide_stand_sword.gcode`](../../gcode/wide_stand_sword.gcode) | PETG | 案5-D 岩に刺さった剣（ゆったり版用）（選んだものだけ） | 2h 54m 54s | 52 g |
| 9 | [`wide_stand_sprout.gcode`](../../gcode/wide_stand_sprout.gcode) | PETG | 案5-E 植木鉢＋葉っぱ（ゆったり版用）（選んだものだけ） | 2h 15m 53s | 41 g |

合計（スタンドを除く）：約 **5.0 時間・43 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,980 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
