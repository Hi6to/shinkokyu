# 専用の基板の部品表（JLCPCB の部品番号つき）

回路図：[hardware/carrier/shinkokyu_carrier_schematic.pdf](../hardware/carrier/shinkokyu_carrier_schematic.pdf)（KiCad のファイルは [hardware/carrier/](../hardware/carrier/)）

在庫と値段は **2026/10/20 に JLCPCB の部品のページで調べたもの**です。注文する前に、もう一度確かめてください。

## JLCPCB に付けてもらう部品（1枚あたり）

「基本」は JLCPCB がいつも機械に載せている部品（追加の手数料なし）。「拡張」は1種類ごとに約 3ドルの手数料がかかります。

| 記号 | 部品 | 型番 | JLCPCB の部品番号 | 種類 | 在庫 | 単価（ドル） | 個数 | 何のため |
|---|---|---|---|---|---|---|---|---|
| U3 | 気圧センサー | DPS368XTSA1（Infineon） | [C3232508](https://jlcpcb.com/partdetail/InfineonTechnologies-DPS368XTSA1/C3232508) | 拡張 | 13,984 | 4.22 | 1 | 息の圧力を読む |
| U2 | アンプ | MAX98357AETE+T（Analog Devices） | [C910544](https://jlcpcb.com/partdetail/978950-MAX98357AETET/C910544) | 拡張 | 23,154 | 1.32 | 1 | スピーカーを鳴らす |
| Q1 | トランジスタ（P チャネル MOSFET） | AO3401A | [C15127](https://jlcpcb.com/partdetail/Alpha_OmegaSemicon-AO3401A/C15127) | 基本 | 711,156 | 0.10 | 1 | 電池の＋−を逆につないだときに守る |
| D1 | ダイオード | M7（1A） | [C95872](https://jlcpcb.com/partdetail/MDD_Microdiode_Semiconductor-M7/C95872) | 基本 | 5,936,213 | 0.01 | 1 | USB の 5V → アンプ |
| D2 | ショットキーダイオード | B5819W | [C8598](https://jlcpcb.com/partdetail/9093-B5819WSL/C8598) | 基本 | 466,424 | 0.03 | 1 | 電池 → アンプ |
| C1, C2 | コンデンサ 10µF | CL10A106KP8NNNC（0603） | [C19702](https://jlcpcb.com/partdetail/20411-CL10A106KP8NNNC/C19702) | 基本 | 10,116,649 | 0.03 | 2 | アンプの電源 |
| C3, C4, C5 | コンデンサ 0.1µF | CL05B104KO5NNNC（0402） | [C1525](https://jlcpcb.com/partdetail/1877-CL05B104KO5NNNC/C1525) | 基本 | 39,020,703 | 0.01 | 3 | アンプとセンサーの電源 |
| R1, R2, R3 | 抵抗 4.7kΩ | 0402WGF4701TCE（0402） | [C25900](https://jlcpcb.com/partdetail/26643-0402WGF4701TCE/C25900) | 基本 | 15,286,833 | 0.002 | 3 | I2C のプルアップ（R1・R2）、アンプの SD_MODE を守る（R3） |
| SW1〜SW3 | ボタン（上から押す、5.1mm 角・高さ 1.5mm） | TS-1187A-B-A-B | [C318884](https://jlcpcb.com/partdetail/XKBConnection-TS_1187A_B_AB/C318884) | 基本 | 274,136 | 0.02 | 3 | 曲送り・音量＋・音量− |

### B版で増える部品

| 記号 | 部品 | 型番 | JLCPCB の部品番号 | 種類 | 在庫 | 単価（ドル） | 個数 | 何のため |
|---|---|---|---|---|---|---|---|---|
| U1 | マイコン | Seeed Studio XIAO nRF52840（102010448） | [C17209540](https://jlcpcb.com/partdetail/C17209540) | 拡張 | 63（2026/10/21） | 10.74 | 1 | B版は XIAO も JLCPCB が付ける |

B版は TP1（窓の横の端子）がない。

A版の JLCPCB に渡すファイル（[hardware/carrier/jlcpcb/](../hardware/carrier/jlcpcb/)）：
- 基板：[shinkokyu_carrier_gerber.zip](../hardware/carrier/jlcpcb/shinkokyu_carrier_gerber.zip)
- 部品表：[BOM_JLCPCB.csv](../hardware/carrier/jlcpcb/BOM_JLCPCB.csv)
- 部品の位置：[CPL_JLCPCB.csv](../hardware/carrier/jlcpcb/CPL_JLCPCB.csv)

## 予備の部品の場所について

はじめは、あとで付けられる予備の抵抗の場所（R4〜R6）を作っていましたが、基板が混み合うので外しました。代わりに、アンプの GAIN（音量の段階）と SD_MODE（オン・オフ）を J4 の穴に出してあり、必要なときは穴に抵抗を付けて変えられます（くわしくは [PCB_DESIGN.md](PCB_DESIGN.md)）。

## はんだのジャンパー（部品ではなく、基板の銅の形）

| 記号 | はじめの状態 | 使い方 |
|---|---|---|
| JP1 | 開いている | Q1 が動かないときだけ、はんだでつなぐ（逆につないだときの守りはなくなる） |
| JP2 | つながっている | 電源スイッチを付けるときは、間の細い線をカッターで切って、J2 にスイッチをつなぐ |
| JP3 | 開いている | 気圧センサーのアドレスを 0x77 → 0x76 に変えたいときだけつなぐ |

## 自分で付けるもの（[BOM.md](BOM.md) で買う・持っているもの）

| 記号 | もの | つけ方 |
|---|---|---|
| U1 | XIAO nRF52840 | 縁の端子で基板に直接はんだ付けする（低く収まる）か、ピンヘッダで付ける（外せる） |
| TP1 | XIAO の電池の線 | 基板の窓から、XIAO の裏の BAT+ に細い線をつなぐ |
| J1 | 電池（110mAh、PH 2ピン） | 電池の線を穴に直接はんだ付けする（2.0mm 間隔なので、PH のコネクタも付けられる） |
| J3 | スピーカー | 線を2本 |
| J2・J4〜J7 | 予備の端子 | 必要なときだけ、線やピンヘッダを付ける |

B版の JLCPCB に渡すファイル（[hardware/carrier_b/jlcpcb/](../hardware/carrier_b/jlcpcb/)）：
- 基板：[shinkokyu_carrier_b_gerber.zip](../hardware/carrier_b/jlcpcb/shinkokyu_carrier_b_gerber.zip)
- 部品表：[BOM_JLCPCB.csv](../hardware/carrier_b/jlcpcb/BOM_JLCPCB.csv)
- 部品の位置：[CPL_JLCPCB.csv](../hardware/carrier_b/jlcpcb/CPL_JLCPCB.csv)

## 費用の目安（A版・B版それぞれ、2枚に部品を付けて、5枚作る場合）

DPS368 を付けるには Standard の取り付けが必要で、最初の目安より高くなった。注文するのは **B版だけ**（2026/10/21）。

B版の注文の画面の金額（2026/10/21、送料の前）：**¥16,779**

| 内訳 | 金額 |
|---|---|
| 基板（5枚・厚さ 0.8mm） | ¥633 |
| 取り付けの基本料金（Setup Fee） | ¥4,076 |
| メタルマスク（Stencil） | ¥1,309 |
| 部品（10種類、XIAO 2個を含む） | ¥5,516 |
| 拡張部品の手数料（Feeders Loading fee） | ¥2,453 |
| 取り付け（SMT Assembly） | ¥95 |
| 取り付けの治具（PCB assembly fixture） | ¥2,618 |
| 梱包 | ¥79 |

これに送料（日本まで）が加わる。実際の注文（2026/10/21）は DHL Express で送料 $69.44、合計 **$175.45**。A版は Standard で約 ¥13,000（送料の前）だった。

## 注文するときに確かめること

- 部品の向きを、JLCPCB の注文画面の「部品の位置の確認」で必ず見る。特に U2・U3（1番ピンの印）、D1・D2（帯の向き）、Q1、SW1〜SW3。正しい向きは [PCB_DESIGN.md の「注文の仕方」](PCB_DESIGN.md#注文の仕方) に書いた
- 在庫が少なくなっていたら、同じ型番の別の部品番号を探す
