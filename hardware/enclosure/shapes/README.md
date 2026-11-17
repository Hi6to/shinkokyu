# 外見の案の 3D プリント用データ

[docs/shapes.html](../../../docs/shapes.html) で残した案（案3・案5・案7・案15・案17）を、実際に刷れる部品にしたもの。3D で組み立て・分解・断面・人がつけた見え方を確かめるページと、案5 のスタンドの寸法つき図面は、[docs/shapes.html](../../../docs/shapes.html) の上の切り替え（「3Dプリント部品・人がつけた見え方」「案5 スタンドの図面」）にある（ダウンロードしてブラウザで開く）。

## 寸法の元

- 基板：B版 20.5 × 69.3 × 0.8mm（[docs/PCB_DESIGN.md](../../../docs/PCB_DESIGN.md)）。部品の位置は [hardware/carrier_b](../../carrier_b/) の KiCad から取った（X = kx − 98.2、Y = ky − 100）
  - XIAO の中心 X=12.4、ボタン SW1〜SW3 は X=30.4・38.2・46.0（真ん中から 3.7mm 横）、気圧センサー X=64.5
- 箱の太さ：チームの試し刷りの箱（[../stl/board_box.stl](../stl/board_box.stl)、73.2 × 24.4mm）と同じ。すき間 0.35、壁 1.6、基板の下 6.5（スピーカー）
- 本体の筒（案1）：外径 26mm（[../make_enclosure.py](../make_enclosure.py) の R_OUT）

## 案と部品の組み合わせ

| 案 | 使う部品 |
|---|---|
| 案3 ペン型＋クリップ | 案1の筒（チームのデータ）＋ pen_clip |
| 案5 スタンド | 案1の筒 ＋ stand_plain／stand_volcano／stand_rocket（＋ stand_rocket_tower）／stand_sword／stand_sprout（＋ stand_sprout_leaf）。stand_side_charge は図面と同じもの |
| 案7 ネックレス | necklace_back ＋ core_front ＋ core_dial ＋ core_socket ＋ adapter ＋ plunger × 3 |
| 案15 社員証ケース | core_back ＋ core_front ＋ core_dial ＋ core_socket ＋ adapter ＋ plunger × 3 ＋ idcase_frame_back ＋ idcase_frame_front |
| 案17 ひと息マッチ | match_store_sleeve（しまう箱。11/09）＋ match_tray ＋ core_back ＋ core_front ＋ core_dial ＋ core_socket ＋ adapter ＋ plunger × 3。前の match_sleeve（コアを入れたまま使う形）は、押し棒・円盤の軸・吹き口の受けのつばが当たって差しこめなかった |

「コア」（core_back と core_front）は、基板・電池・スピーカーが入る箱で、案7・案15・案17 で共通。

## ファイル（大きさは刷る向き、mm）

| ファイル | 部品 | 大きさ | 刷り方 |
|---|---|---|---|
| [stl/core_back.stl](stl/core_back.stl) | コア 下の殻（スピーカー・電池・基板をのせる） | 75.2 × 24.4 × 8.1 | 底を下にして刷る |
| [stl/core_front.stl](stl/core_front.stl) | コア 上の殻（ボタンの穴と印「▶・＋・－」・空気口の穴と円盤の軸） | 75.2 × 24.4 × 8.2 | 開いた側（合わせ面）を下にして刷る。上の面は幅 21mm の橋になる（サポートなし） |
| [stl/core_socket.stl](stl/core_socket.stl) | 吹き口の受け（コアの前に貼る） | 14.0 × 14.0 × 9.0 | つばを下にして刷る |
| [stl/adapter.stl](stl/adapter.stl) | 吹き口アダプター（簡易） | 14.0 × 14.0 × 20.0 | つばの側を下にして刷る |
| [stl/plunger.stl](stl/plunger.stl) | ボタンの押し棒（3本刷る） | 5.6 × 5.6 × 5.1 | つばを下にして刷る。3本 |
| [stl/core_dial.stl](stl/core_dial.stl) | 空気口の円盤（回して重さを変える） | 16.0 × 16.0 × 2.0 | 上の面を下にして刷る。M2 タッピングねじ 6mm ＋ ワッシャーで留める |
| [stl/plunger_long.stl](stl/plunger_long.stl) | ボタンの押し棒・長い（案17用、3本） | 5.6 × 5.6 × 6.9 | つばを下にして刷る。3本 |
| [stl/necklace_back.stl](stl/necklace_back.stl) | 案7 下の殻（ひもの輪つき） | 79.7 × 24.4 × 8.1 | 底を下にして刷る。上の殻は core_front |
| [stl/idcase_frame_back.stl](stl/idcase_frame_back.stl) | 案15 カードの枠（裏）＋コアを貼る板 | 96.0 × 88.4 × 3.2 | 板を下にして刷る |
| [stl/idcase_frame_front.stl](stl/idcase_frame_front.stl) | 案15 カードの枠（表の窓） | 96.0 × 64.0 × 1.2 | 平らに刷る |
| [stl/match_sleeve.stl](stl/match_sleeve.stl) | 案17 外箱（コアと内箱が入る） | 28.0 × 54.0 × 77.2 | 吹き口の側の壁を下にして、立てて刷る |
| [stl/match_tray.stl](stl/match_tray.stl) | 案17 内箱（2列） | 77.1 × 34.0 × 24.1 | 底を下にして刷る |
| [stl/match_store_sleeve.stl](stl/match_store_sleeve.stl) | 案17 しまう箱（コアと内箱を入れる。コアは外で使う。11/09） | 28.0 × 58.5 × 79.2 | 前の壁を下にして、立てて刷る。作るときは `match_store_sleeve()`（Windows の manifold3d は rotate がくずれるので、行列で回す版で書き出した） |
| [stl/pen_clip.stl](stl/pen_clip.stl) | 案3 クリップ（案1の筒にはめる） | 48.0 × 30.7 × 30.7 | アームを下にして、サポートなしで刷る |
| [stl/stand_plain.stl](stl/stand_plain.stl) | 案5 スタンド（そのまま） | 64.0 × 64.0 × 30.0 | 底を下にして刷る（高さ 30、本体が 10.5 刺さる） |
| [stl/stand_volcano.stl](stl/stand_volcano.stl) | 案5-A 火山 | 80.0 × 80.0 × 33.0 | 底を下にして刷る（高さ 33、本体が 10.5 刺さる） |
| [stl/stand_rocket.stl](stl/stand_rocket.stl) | 案5-C ロケット発射台 | 68.0 × 68.0 × 34.0 | 底を下にして刷る（高さ 30、本体が 10.5 刺さる） |
| [stl/stand_sword.stl](stl/stand_sword.stl) | 案5-D 岩に刺さった剣 | 77.6 × 77.6 × 44.0 | 底を下にして刷る（高さ 44、本体が 10.5 刺さる） |
| [stl/stand_sprout.stl](stl/stand_sprout.stl) | 案5-E 植木鉢の芽 | 60.0 × 59.2 × 44.0 | 底を下にして刷る（高さ 40、本体が 10.5 刺さる） |
| [stl/stand_rocket_tower.stl](stl/stand_rocket_tower.stl) | 案5-C 発射塔（別に刷って差す） | 22.5 × 95.0 × 9.0 | 寝かせて刷る |
| [stl/stand_sprout_leaf.stl](stl/stand_sprout_leaf.stl) | 案5-E 葉っぱ（別に刷って差す） | 44.0 × 12.0 × 3.0 | 平らに刷る |

## 刷り方

- PETG、層 0.2mm、壁 3本以上、サポートなし（どの部品もサポートなしで刷れる形にしてある）
- 光らせたい部品（コアの上の殻、スタンド）は半透明の白で刷る
- まず core_back だけを刷って、基板が棚にのるか、スピーカーと電池が下に入るかを確かめる

## 気をつけること

- 息の部屋：仕切りの、基板の首を通すすき間（高さ 0.9mm）はグルーでふさぐ。上と下の殻の合わせ目も、息の部屋のまわりはふさぐ
- 空気口の調節：丸い筒の案（案3・案5の本体＝案1）は、これまでどおり回すリング（[docs/ENCLOSURE.md](../../../docs/ENCLOSURE.md)）。箱の形の案（案7・案15・案17）は、息の部屋の上の面に大きい穴（直径 3mm）を1つあけ、その上で円盤（core_dial、直径 16mm）を回す。円盤の切れ目は回る向きに細くなり（幅 0.8 → 0）、穴の上に来た所の幅で開く広さが変わる（約 2.4mm² → 閉じる、8段階でカチッと止まる）。円盤は M2 のタッピングねじ（6mm）とワッシャーで軸に留める
- ボタンの向き：基板の表と裏を間違えないように、先に基板を当てて穴の位置を確かめる
- ボタンの印（11/07）：コアの上の面と、案17 の外箱の横の面に、SW1「▶」（曲送り）・SW2「＋」・SW3「－」（音量）を深さ 0.6 で彫った（[../../print/README.md](../../print/README.md#ボタンの印1107)）
- 案5：L字の USB-C ケーブルの頭を測ってから刷る（下の空間 直径 24 × 高さ、溝の幅 14）
- 案17：内箱を引き出すと光るようにするには、スイッチ（D6）を足す必要がある（データには入れていない）
- 吹き口アダプターは簡易版（差し込み 10mm、ストローの穴 6.4→6.0mm）。ストローに合わせて数字を変える

## 作り直し方

チームの make_enclosure.py と同じ準備（manifold3d・trimesh・numpy）で動く。

```bash
~/venvs/shinkokyu-cad/Scripts/python hardware/enclosure/shapes/make_shapes.py
~/venvs/shinkokyu-cad/Scripts/python hardware/enclosure/shapes/make_stand.py
```

寸法はファイルの最初にまとめてある。`stl/`（刷る向き）と `model/`（組み立てた向き、確認用。リポジトリには入れていない）が作られる。
