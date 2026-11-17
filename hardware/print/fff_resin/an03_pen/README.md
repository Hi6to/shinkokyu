# 案3 ペン型（案1＋クリップ）（FFF ＋ 光造形）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_resin an03_pen <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`body_tube.gcode`](../../gcode/body_tube.gcode) | PETG | 案1 の筒：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本 | 1h 37m 7s | 17 g |
| 2 | [`body_tpu.gcode`](../../gcode/body_tpu.gcode) | TPU 95A | TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個 | 14m 24s | 1 g |
| 3 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 4 | [`pen_clip.gcode`](../../gcode/pen_clip.gcode) | PETG | 案3 クリップ | 30m 57s | 4 g |

合計（すべて）：約 **4.8 時間・34 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,650 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
