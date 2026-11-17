# 案5 スタンド（案1＋スタンド。スタンドは好きなものを1つ）（すべて FFF）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_only an05_stand <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`body_tube.gcode`](../../gcode/body_tube.gcode) | PETG | 案1 の筒：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本 | 1h 37m 7s | 17 g |
| 2 | [`body_tpu.gcode`](../../gcode/body_tpu.gcode) | TPU 95A | TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個 | 14m 24s | 1 g |
| 3 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 4 | [`stand_side_charge.gcode`](../../gcode/stand_side_charge.gcode) | PETG | 案5 横から充電するスタンド（選んだものだけ） | 2h 14m 19s | 44 g |
| 5 | [`stand_plain.gcode`](../../gcode/stand_plain.gcode) | PETG | 案5 ふつうのスタンド（選んだものだけ） | 2h 13m 36s | 44 g |
| 6 | [`stand_volcano.gcode`](../../gcode/stand_volcano.gcode) | PETG | 案5-A 火山（選んだものだけ） | 2h 19m 34s | 44 g |
| 7 | [`stand_rocket.gcode`](../../gcode/stand_rocket.gcode) | PETG | 案5-C ロケット発射台＋発射塔（選んだものだけ） | 2h 43m 13s | 39 g |
| 8 | [`stand_sword.gcode`](../../gcode/stand_sword.gcode) | PETG | 案5-D 岩に刺さった剣（選んだものだけ） | 2h 50m 9s | 50 g |
| 9 | [`stand_sprout.gcode`](../../gcode/stand_sprout.gcode) | PETG | 案5-E 植木鉢＋葉っぱ（選んだものだけ） | 2h 15m 23s | 41 g |

合計（スタンドを除く）：約 **4.3 時間・30 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,650 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
