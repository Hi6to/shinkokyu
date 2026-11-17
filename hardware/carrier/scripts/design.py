# シン呼吸 ポータブル版：XIAO nRF52840 を載せる基板の部品とつながり
# 回路図（make_sch.py）と基板（make_pcb.py）は、どちらもこのファイルから作る。

# (記号, 型, 値, JLCPCB の部品番号, 付けない(DNP), 端子→ネット, メモ)
PARTS = {
    # ---- マイコン（自分ではんだ付け）
    "U1": dict(sym="shinkokyu:XIAO_nRF52840", fp="shinkokyu:XIAO_nRF52840_Hybrid", value="XIAO nRF52840",
               lcsc=None, hand=True,
               pins={"1": "BTN_NEXT", "2": "BTN_UP", "3": "BTN_DOWN", "4": "PIEZO", "5": "SDA", "6": "SCL",
                     "7": "IO6", "8": "AMP_EN", "9": "I2S_BCLK", "10": "I2S_LRCLK", "11": "I2S_DIN",
                     "12": "+3V3", "13": "GND", "14": "VBUS"},
               note="自分ではんだ付けする"),
    # ---- アンプ
    "U2": dict(sym="Audio:MAX98357A", fp="Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm",
               value="MAX98357AETE+T", lcsc="C910544",
               pins={"1": "I2S_DIN", "2": "GAIN", "3": "GND", "4": "SD_MODE", "7": "VAMP", "8": "VAMP",
                     "9": "SPK_P", "10": "SPK_N", "11": "GND", "14": "I2S_LRCLK", "15": "GND", "16": "I2S_BCLK",
                     "17": "GND"}),
    "C1": dict(sym="Device:C", fp="Capacitor_SMD:C_0603_1608Metric", value="10uF", lcsc="C19702",
               pins={"1": "VAMP", "2": "GND"}),
    "C2": dict(sym="Device:C", fp="Capacitor_SMD:C_0603_1608Metric", value="10uF", lcsc="C19702",
               pins={"1": "VAMP", "2": "GND"}),
    "C3": dict(sym="Device:C", fp="Capacitor_SMD:C_0402_1005Metric", value="100nF", lcsc="C1525",
               pins={"1": "VAMP", "2": "GND"}),
    "R3": dict(sym="Device:R", fp="Resistor_SMD:R_0402_1005Metric", value="4.7k", lcsc="C25900",
               pins={"1": "AMP_EN", "2": "SD_MODE"}, note="SD_MODE を守る直列の抵抗"),
    "J3": dict(sym="Connector_Generic:Conn_01x02", fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
               value="SPEAKER", lcsc=None, hand=True, pins={"1": "SPK_P", "2": "SPK_N"}, note="スピーカーの線"),
    "J4": dict(sym="Connector_Generic:Conn_01x07", fp="Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical",
               value="AMP_EXT", lcsc=None, hand=True,
               pins={"1": "I2S_LRCLK", "2": "I2S_BCLK", "3": "I2S_DIN", "4": "GAIN", "5": "SD_MODE", "6": "GND",
                     "7": "VAMP"},
               note="予備：外付けのアンプ基板（Adafruit と同じ並び）"),
    # ---- 電源
    "J1": dict(sym="Connector_Generic:Conn_01x02", fp="Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical",
               value="BATTERY", lcsc=None, hand=True, pins={"1": "BAT_RAW", "2": "GND"},
               note="電池の線（2.0mm 間隔＝PH コネクタも付けられる）"),
    "Q1": dict(sym="Transistor_FET:AO3401A", fp="Package_TO_SOT_SMD:SOT-23", value="AO3401A", lcsc="C15127",
               pins={"1": "GND", "2": "VBAT_Q", "3": "BAT_RAW"}, note="電池の＋−を逆につないだときに守る"),
    "JP1": dict(sym="Jumper:SolderJumper_2_Open", fp="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                value="Q1_BYPASS", lcsc=None, pins={"1": "BAT_RAW", "2": "VBAT_Q"},
                note="予備：Q1 が動かないときだけ、はんだでつなぐ"),
    "JP2": dict(sym="Jumper:SolderJumper_2_Bridged", fp="Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm",
                value="PWR_BYPASS", lcsc=None, pins={"1": "VBAT_Q", "2": "VBAT"},
                note="はじめからつながっている。電源スイッチを付けるときは切る"),
    "J2": dict(sym="Connector_Generic:Conn_01x02", fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
               value="PWR_SW", lcsc=None, hand=True, pins={"1": "VBAT_Q", "2": "VBAT"},
               note="予備：電源スイッチの線"),
    "TP1": dict(sym="Connector:TestPoint", fp="TestPoint:TestPoint_Pad_1.5x1.5mm", value="XIAO_BAT+", lcsc=None,
                pins={"1": "VBAT"}, back=True, note="裏側。窓から XIAO の裏の BAT+ に線でつなぐ"),
    "D1": dict(sym="Device:D", fp="Diode_SMD:D_SMA", value="M7", lcsc="C95872",
               pins={"1": "VAMP", "2": "VBUS"}, note="USB の 5V → アンプ"),
    "D2": dict(sym="Device:D_Schottky", fp="Diode_SMD:D_SOD-123", value="B5819W", lcsc="C8598",
               pins={"1": "VAMP", "2": "VBAT"}, note="電池 → アンプ"),
    # ---- 気圧センサー（切り離せる部分）
    "U3": dict(sym="shinkokyu:DPS368", fp="shinkokyu:Infineon_PG-VLGA-8-2", value="DPS368XTSA1", lcsc="C3232508",
               pins={"1": "GND", "2": "+3V3", "3": "SDA", "4": "SCL", "5": "DPS_SDO", "6": "+3V3", "7": "GND",
                     "8": "+3V3"}),
    "C4": dict(sym="Device:C", fp="Capacitor_SMD:C_0402_1005Metric", value="100nF", lcsc="C1525",
               pins={"1": "+3V3", "2": "GND"}, note="VDD"),
    "C5": dict(sym="Device:C", fp="Capacitor_SMD:C_0402_1005Metric", value="100nF", lcsc="C1525",
               pins={"1": "+3V3", "2": "GND"}, note="VDDIO"),
    "JP3": dict(sym="Jumper:SolderJumper_2_Open", fp="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                value="ADDR_0x76", lcsc=None, pins={"1": "DPS_SDO", "2": "GND"},
                note="ふだんは開けたまま（0x77）。つなぐと 0x76"),
    "J7": dict(sym="Connector_Generic:Conn_01x04", fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
               value="TAB_WIRE", lcsc=None, hand=True, pins={"1": "+3V3", "2": "GND", "3": "SDA", "4": "SCL"},
               note="切り離したあと、ここに線をつなぐ"),
    # ---- I2C（本体側）
    "R1": dict(sym="Device:R", fp="Resistor_SMD:R_0402_1005Metric", value="4.7k", lcsc="C25900",
               pins={"1": "+3V3", "2": "SDA"}),
    "R2": dict(sym="Device:R", fp="Resistor_SMD:R_0402_1005Metric", value="4.7k", lcsc="C25900",
               pins={"1": "+3V3", "2": "SCL"}),
    "J5": dict(sym="Connector_Generic:Conn_01x04", fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
               value="I2C_EXT", lcsc=None, hand=True, pins={"1": "+3V3", "2": "GND", "3": "SDA", "4": "SCL"},
               note="切り離したセンサーや、外付けのセンサー基板をつなぐ"),
    # ---- ボタン・予備の端子
    "SW1": dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", value="NEXT",
                lcsc="C318884", mpn="TS-1187A-B-A-B", pins={"1": "BTN_NEXT", "2": "GND"}, note="曲送り"),
    "SW2": dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", value="VOL+",
                lcsc="C318884", mpn="TS-1187A-B-A-B", pins={"1": "BTN_UP", "2": "GND"}, note="音量＋"),
    "SW3": dict(sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", value="VOL-",
                lcsc="C318884", mpn="TS-1187A-B-A-B", pins={"1": "BTN_DOWN", "2": "GND"}, note="音量−"),
    "J6": dict(sym="Connector_Generic:Conn_01x06", fp="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
               value="IO", lcsc=None, hand=True,
               pins={"1": "GND", "2": "BTN_NEXT", "3": "BTN_UP", "4": "BTN_DOWN", "5": "PIEZO", "6": "IO6"},
               note="外付けのボタン・圧電ブザー（D3）・予備（D6）"),
    # ---- 確認用の端子
    "TP2": dict(sym="Connector:TestPoint", fp="TestPoint:TestPoint_Pad_D1.5mm", value="5V", lcsc=None,
                pins={"1": "VBUS"}),
}

# ---- B版：XIAO も JLCPCB が付ける。XIAO の裏の BAT+ と GND も、基板の端子に機械ではんだ付けされる
from variant import V  # noqa: E402
if V == "B":
    PARTS["U1"] = dict(sym="shinkokyu:XIAO_nRF52840_SMD", fp="shinkokyu:XIAO_nRF52840_SMD",
                       value="XIAO nRF52840", mpn="102010448", lcsc="C17209540",
                       pins=dict(PARTS["U1"]["pins"], **{"19": "VBAT", "20": "GND"}),
                       note="JLCPCB が付ける。裏の BAT+（19）と GND（20）も基板の端子にはんだ付けされる")
    del PARTS["TP1"]    # 窓から線をつなぐ端子は要らない

for _r, _p in PARTS.items():
    _p.setdefault("dnp", False)
    _p.setdefault("hand", False)
    _p.setdefault("back", False)
    _p.setdefault("note", "")


def nets():
    out = {}
    for ref, p in PARTS.items():
        for pin, n in p["pins"].items():
            out.setdefault(n, []).append((ref, pin))
    return out
