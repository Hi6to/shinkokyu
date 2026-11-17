# 案5 スタンド・ゆったり版（案1 ゆったり版＋スタンド。スタンドは好きなものを1つ）（FFF ＋ 光造形）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_resin an05w_stand_wide <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`wide_body_tube.gcode`](../../gcode/wide_body_tube.gcode) | PETG | 案1 ゆったり版の筒（外径 32）：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本 | 2h 23m 48s | 29 g |
| 2 | [`body_tpu.gcode`](../../gcode/body_tpu.gcode) | TPU 95A | TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個 | 14m 24s | 1 g |
| 3 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 4 | [`wide_stand_side_charge.gcode`](../../gcode/wide_stand_side_charge.gcode) | PETG | 案5 横から充電するスタンド（ゆったり版用）（選んだものだけ） | 2h 14m 47s | 43 g |
| 5 | [`wide_stand_plain.gcode`](../../gcode/wide_stand_plain.gcode) | PETG | 案5 ふつうのスタンド（ゆったり版用）（選んだものだけ） | 2h 14m 35s | 43 g |
| 6 | [`wide_stand_volcano.gcode`](../../gcode/wide_stand_volcano.gcode) | PETG | 案5-A 火山（ゆったり版用）（選んだものだけ） | 2h 21m 18s | 45 g |
| 7 | [`wide_stand_rocket_base.gcode`](../../gcode/wide_stand_rocket_base.gcode) | PETG | 案5-C ロケット発射台（ゆったり版用。発射塔は光造形）（選んだものだけ） | 1h 55m 1s | 32 g |
| 8 | [`wide_stand_sword.gcode`](../../gcode/wide_stand_sword.gcode) | PETG | 案5-D 岩に刺さった剣（ゆったり版用）（選んだものだけ） | 2h 54m 54s | 52 g |
| 9 | [`wide_stand_sprout_pot.gcode`](../../gcode/wide_stand_sprout_pot.gcode) | PETG | 案5-E 植木鉢（ゆったり版用。葉っぱは光造形）（選んだものだけ） | 2h 13m 53s | 40 g |

合計（スタンドを除く）：約 **5.0 時間・43 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 1,980 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

## 光造形（ELEGOO Mars4 Ultra）で刷る部品

`resin/` の STL を、店のパソコンの ELEGOO の切り分けソフト（CHITUBOX など）に入れて、サポートを自動でつけて刷る。**光造形のデータ（.goo など）はここでは作れない**ため、STL を持っていく。

| ファイル | 光造形にする理由 |
|---|---|
| `resin/stand_rocket_tower.stl` | 発射塔：細い柱と格子がきれいに出る（飾りで、力がかからない） |
| `resin/stand_sprout_leaf.stl` | 葉っぱ：厚さ 3mm の薄い形と葉脈がきれいに出る（飾り） |

- 店の樹脂は水で洗えるタイプだけ。もろいので、ねじは軽くしめる（円盤はワッシャーをはさむ）
- 光造形は1日 2,200円（1人1日）。洗いと仕上げの光当てで約2時間かかる

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
