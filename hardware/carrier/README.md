# XIAO nRF52840 を載せる基板（KiCad 10）

設計の考え方は [docs/PCB_DESIGN.md](../../docs/PCB_DESIGN.md)、部品表は [docs/PCB_BOM.md](../../docs/PCB_BOM.md) を見てください。

| ファイル | 中身 |
|---|---|
| [shinkokyu_carrier_schematic.pdf](shinkokyu_carrier_schematic.pdf) | 回路図（PDF） |
| [images/](images/) | 基板の絵（3D の表・裏、銅と印刷の PDF） |
| [jlcpcb/](jlcpcb/) | JLCPCB に送るファイル（ガーバーの zip・部品表・部品の位置） |
| shinkokyu_carrier.kicad_pro / .kicad_sch / .kicad_pcb | KiCad のプロジェクト・回路図・基板 |
| lib/ | 自作の記号（XIAO nRF52840・DPS368）と型（フットプリント） |
| scripts/ | 回路図・基板・部品表を作るプログラム |

## A版と B版

同じプログラムで2つの版を作ります（環境変数 `VARIANT`）。

| 版 | フォルダ | XIAO |
|---|---|---|
| A | このフォルダ（hardware/carrier） | 自分ではんだ付け（窓から裏の BAT+ に線） |
| B | [hardware/carrier_b](../carrier_b/) | JLCPCB が付ける（裏の BAT+・GND も機械ではんだ） |

自作の記号と型（lib/）は A版・B版で共通です。

## 作り直し方

部品とつながりは `scripts/design.py`、置き場所と基板の形は `scripts/layout.py` にまとめてあります。次の1行で、回路図から JLCPCB に送るファイルまで全部作り直せます。

```bash
bash hardware/carrier/scripts/build.sh A B
```

中では次の順に動きます（KiCad についている Python と、numpy・scipy・pypdfium2・Pillow が入ったふつうの Python を使う）。

| プログラム | すること |
|---|---|
| make_lib.py | 自作の記号と型 |
| make_sch.py・check_sch.py | 回路図、ERC、つながりの照合、回路図の PDF |
| make_pcb.py | 部品を置いた基板と、端子の形（pads_A.json など） |
| route.py | 配線（routes_A.json など）。引けない線は、邪魔な線を外して引き直す |
| apply_routes.py | 配線と GND のベタを基板に入れる。ほかとつながらない GND があれば書き出し、`route.py repair` で線を足して作り直す |
| make_bom.py・make_fab.py | JLCPCB の部品表・ガーバー・部品の位置・画像 |
| verify_xiao.py | XIAO の公式の基板データを重ねて、端子ごとの信号・裏の端子の真下・USB-C の口を確かめる |

最後に DRC（基板の自動チェック）を、回路図との照合つきで行います。

```bash
"$HOME/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe" pcb drc --schematic-parity --severity-all -o drc.rpt shinkokyu_carrier.kicad_pcb
```

2026/10/21 の結果（A版・B版とも）：エラー 0。警告は「KiCad の部品ライブラリの設定がない」と「端子の枠の印刷が基板の縁にかかる」だけ。

KiCad を初めて開くと「グローバルライブラリの設定」を聞かれます。「デフォルトのグローバルライブラリをコピー」を選んでください。
