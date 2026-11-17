# B版：XIAO nRF52840 も JLCPCB が付ける基板（KiCad 10）

A版（[hardware/carrier](../carrier/)）と同じ回路・部品の置き方で、XIAO も JLCPCB に付けてもらう版です。違いと確かめたことは [docs/PCB_DESIGN.md](../../docs/PCB_DESIGN.md) の「A版と B版」を見てください。

| ファイル | 中身 |
|---|---|
| [shinkokyu_carrier_b_schematic.pdf](shinkokyu_carrier_b_schematic.pdf) | 回路図（PDF） |
| [images/](images/) | 基板の絵 |
| [jlcpcb/](jlcpcb/) | JLCPCB に送るファイル（ガーバーの zip・部品表・部品の位置） |
| shinkokyu_carrier_b.kicad_pro / .kicad_sch / .kicad_pcb | KiCad のプロジェクト・回路図・基板 |

作り直し方とプログラムは [hardware/carrier/README.md](../carrier/README.md)（`bash hardware/carrier/scripts/build.sh B`）。
