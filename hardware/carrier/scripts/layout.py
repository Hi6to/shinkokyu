# 基板の形と部品の置き場所（単位 mm、KiCad の向き：x は右、y は下が＋、角度は反時計回り）
# x=0 が USB の端。XIAO の D0〜D6 の列が +y 側、5V〜D7 の列が -y 側。

W = 20.5            # 本体の幅
MAIN_END = 53.5     # 本体の終わり
NECK_END = 57.5     # 首の終わり（ここからタブ）
TAB_END = 67.5      # タブの終わり
NECK_W = 5.5        # 首の幅
TAB_W = 12.0        # タブの幅
CUT_X = 55.5        # 切り離す線

from variant import V  # noqa: E402

# B版は、XIAO の USB-C の口（公式の基板データで、ピンの中心から 12.05mm）が基板の外に出ないように、USB の端を 1.8mm のばす
START = 0 if V == "A" else -1.8

# 外形（時計回り）
OUTLINE = [(START, -W / 2), (MAIN_END, -W / 2), (MAIN_END, -NECK_W / 2), (NECK_END, -NECK_W / 2),
           (NECK_END, -TAB_W / 2), (TAB_END, -TAB_W / 2), (TAB_END, TAB_W / 2), (NECK_END, TAB_W / 2),
           (NECK_END, NECK_W / 2), (MAIN_END, NECK_W / 2), (MAIN_END, W / 2), (START, W / 2)]

# (x, y, 角度, 裏側)
PLACE = {
    "U1": (10.6, 0, 0, False),
    "TP1": (14.0, 4.45, 0, True),
    # -y の縁の列
    "J4": (24.0, -8.85, 90, False),
    "J2": (49.0, -8.85, 90, False),
    # +y の縁の列
    "J6": (27.0, 8.85, 90, False),
    "J5": (44.0, 8.85, 90, False),
    # ボタン
    "SW1": (28.6, 3.7, 0, False),
    "SW2": (36.4, 3.7, 0, False),
    "SW3": (44.2, 3.7, 0, False),
    # アンプ（左と上が XIAO からの信号、右がスピーカー、下が電源）
    "U2": (28.55, -3.05, 0, False),
    "R3": (25.3, -2.3, 0, False),
    "C3": (29.05, -0.3, 0, False),
    "C1": (32.3, -0.4, 0, False),
    "C2": (35.4, -0.4, 0, False),
    "J3": (32.6, -3.9, 90, False),
    # 電源
    "D1": (40.6, -5.0, 0, False),
    "D2": (39.5, -1.6, 0, False),
    "TP2": (43.3, -1.6, 0, False),
    "Q1": (46.3, -5.0, 0, False),
    "JP1": (47.0, -1.5, 0, False),
    "JP2": (50.6, -1.5, 0, False),
    "J1": (49.9, -5.0, 90, False),
    # I2C のプルアップ
    "R1": (50.0, 4.5, 90, False),
    "R2": (51.5, 4.5, 90, False),
    # タブ（気圧センサー）
    "U3": (62.7, 0.0, 90, False),     # 左の列（首の側）：SCL・SDA・CSB・GND
    "C4": (64.6, 1.4, 90, False),     # VDD（8番）のそば
    "C5": (64.6, -1.4, 90, False),    # VDDIO（6番）のそば
    "JP3": (63.0, -3.9, 0, False),    # SDO（5番）のそば
    "J7": (59.3, 3.81, 180, False),   # 下から 3V3・GND・SDA・SCL
}

# 銅を置かない場所 (x1, y1, x2, y2, 層)。"both"＝表と裏、"F"＝表だけ
KEEPOUT = [
    (17.5, -0.3, 22.5, 3.9, "both", "XIAO のアンテナ"),
    (1.1, -2.2, 5.5, 2.2, "F", "XIAO の裏の SWD の端子"),
    (18.4, -6.6, 21.2, -2.9, "F", "XIAO の裏の NFC の端子"),
    (7.3, 3.0, 9.4, 5.9, "F", "XIAO の裏の GND の端子"),
]
if V == "B":
    PLACE.pop("TP1")
    # B版では XIAO の裏の GND の端子を基板の端子にはんだ付けするので、そこは銅を置かない場所にしない
    KEEPOUT = [k for k in KEEPOUT if "GND の端子" not in k[5]]
# 表の GND の面を作らない場所（XIAO の下）
NO_TOP_POUR = (START, -W / 2, 21.2, W / 2)

# 部品の中の GND の端子どうしを先に短くつなぐ（(a, b)）。ROOT の端子からビアで裏の GND へ落とす
GND_LOCAL = [("U3.7", "U3.1"), ("U2.3", "U2.17"), ("U2.11", "U2.17"), ("U2.15", "U2.17")]
GND_LOCAL_ROOT = {"U3.1", "U2.3"}

# 線の太さ（mm）
WIDTH = {"VAMP": 0.4, "VBAT": 0.4, "VBAT_Q": 0.4, "BAT_RAW": 0.4, "VBUS": 0.4, "SPK_P": 0.3, "SPK_N": 0.3,
         "GND": 0.3, "+3V3": 0.25}
DEFAULT_WIDTH = 0.2
CLEARANCE = 0.2        # 配線のプログラムが守るすき間（DRC は 0.15 で確かめる）
EDGE_CLEARANCE = 0.4
VIA = (0.6, 0.3)       # ビアの直径・穴

# 基板の文字（x, y, 文字, 大きさ, 層, 角度）
TEXTS = [
    (1.3, 0.0, "USB", 1.0, "F.SilkS", 90),
    (CUT_X, -3.5, "CUT", 0.8, "F.SilkS", 0),
    (28.6, 3.7, "NEXT", 1.0, "B.SilkS", 0),
    (36.4, 3.7, "VOL+", 1.0, "B.SilkS", 0),
    (44.2, 3.7, "VOL-", 1.0, "B.SilkS", 0),
    (6.5, -3.4, "shinkokyu v0.1 " + V, 0.8, "B.SilkS", 0),
    (63.5, 5.2, "DPS368", 0.8, "B.SilkS", 0),
    (43.3, 0.3, "5V", 0.8, "F.SilkS", 0),
]
if V == "A":
    TEXTS.append((16.6, 4.45, "BAT+", 0.8, "B.SilkS", 90))   # 窓のとなりの TP1
# 表に印刷する部品の名前と位置（はんだのジャンパーだけ）
REF_POS = {"JP1": (47.0, 0.3), "JP2": (50.6, 0.3), "JP3": (65.7, -3.9)}
# 端子の穴ごとの名前（裏の印刷）。基板の内側に向けて縦に書く
PINLABELS = {
    "J3": ["SPK+", "SPK-"],
    "J4": ["LRC", "BCK", "DIN", "GAIN", "SD", "GND", "VIN"],
    "J2": ["SW", "SW"],
    "J6": ["GND", "D0", "D1", "D2", "D3", "D6"],
    "J5": ["3V3", "GND", "SDA", "SCL"],
    "J7": ["3V3", "GND", "SDA", "SCL"],
    "J1": ["BAT+", "BAT-"],
}
