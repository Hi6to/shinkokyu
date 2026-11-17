# 案17 マッチ箱（FFF ＋ 光造形）

プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。
上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。

SD カードにまとめてコピーする：`python3 make_print.py --sd fff_resin an17_match <SDカードの場所>`（hardware/print で）

| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |
|---|---|---|---|---|---|
| 1 | [`core_case_match.gcode`](../../gcode/core_case_match.gcode) | PETG | 箱のコア（案17 用。押し棒が外箱の壁の分だけ長い） | 1h 3m 51s | 14 g |
| 2 | [`core_tpu.gcode`](../../gcode/core_tpu.gcode) | TPU 95A | TPU：ストローをつかむ筒 ⑥ 2個 | 7m 6s | 1 g |
| 3 | [`adapter.gcode`](../../gcode/adapter.gcode) | PETG（0.12mm） | 吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100% | 2h 24m 57s | 12 g |
| 4 | [`match_sleeve.gcode`](../../gcode/match_sleeve.gcode) | PETG | 案17：外箱（立てて刷る。ふち 5mm つき） | 1h 55m 23s | 28 g |
| 5 | [`match_tray.gcode`](../../gcode/match_tray.gcode) | PETG | 案17：内箱（2列） | 1h 1m 54s | 14 g |

合計（すべて）：約 **6.5 時間・68 g**。キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 2,310 円（店のフィラメントなら 550円/時）。
時間は PrusaSlicer の見積もりで、実際とずれることがある。

## 光造形（ELEGOO Mars4 Ultra）で刷る部品

`resin/` の STL を、店のパソコンの ELEGOO の切り分けソフト（CHITUBOX など）に入れて、サポートを自動でつけて刷る。**光造形のデータ（.goo など）はここでは作れない**ため、STL を持っていく。

| ファイル | 光造形にする理由 |
|---|---|
| `resin/core_dial.stl` | 空気口の円盤：細くなっていく切れ目（0.8 → 0mm）を最後まで形にできる |

- 店の樹脂は水で洗えるタイプだけ。もろいので、ねじは軽くしめる（円盤はワッシャーをはさむ）
- 光造形は1日 2,200円（1人1日）。洗いと仕上げの光当てで約2時間かかる

部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。
