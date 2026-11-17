# 自作の記号（XIAO nRF52840・DPS368）と型（フットプリント）を作る
import os
import uuid
from sexpr import Sym, dump

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "lib")
S = Sym


def font(size=1.27):
    return [S("effects"), [S("font"), [S("size"), size, size]]]


def prop(name, value, x=0, y=0, hide=False):
    p = [S("property"), name, value, [S("at"), x, y, 0]]
    if hide:
        p.append([S("hide"), S("yes")])
    p.append(font())
    return p


def pin(typ, x, y, ang, name, num, length=2.54):
    return [S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), length],
            [S("name"), name, font()], [S("number"), num, font()]]


# ---------- 記号 ----------
def sym_xiao(n="XIAO_nRF52840", back=False):
    left = [("1", "D0"), ("2", "D1"), ("3", "D2"), ("4", "D3"), ("5", "D4/SDA"), ("6", "D5/SCL"), ("7", "D6")]
    right = [("14", "5V", "power_out"), ("13", "GND", "power_in"), ("12", "3V3", "power_out"),
             ("11", "D10/MOSI", "bidirectional"), ("10", "D9/MISO", "bidirectional"),
             ("9", "D8/SCK", "bidirectional"), ("8", "D7", "bidirectional")]
    pins = []
    for i, (num, name) in enumerate(left):
        pins.append(pin("bidirectional", -15.24, 7.62 - 2.54 * i, 0, name, num, 5.08))
    for i, (num, name, typ) in enumerate(right):
        pins.append(pin(typ, 15.24, 7.62 - 2.54 * i, 180, name, num, 5.08))
    if back:  # XIAO の裏の端子（Seeed の記号と同じ番号）
        pins.append(pin("passive", -2.54, -15.24, 90, "BAT+", "19", 5.08))
        pins.append(pin("passive", 2.54, -15.24, 90, "GND", "20", 5.08))
    fpname = "shinkokyu:XIAO_nRF52840_SMD" if back else "shinkokyu:XIAO_nRF52840_Hybrid"
    desc = ("Seeed Studio XIAO nRF52840, reflow (SMD) mounting incl. back pads BAT+/GND" if back
            else "Seeed Studio XIAO nRF52840 (castellated / pin header)")
    return [S("symbol"), n,
            [S("pin_names"), [S("offset"), 1.016]],
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            prop("Reference", "U", -10.16, 12.7),
            prop("Value", n, 0, -12.7),
            prop("Footprint", fpname, 0, -15.24, True),
            prop("Datasheet", "https://wiki.seeedstudio.com/XIAO_BLE/", 0, 0, True),
            prop("Description", desc, 0, 0, True),
            [S("symbol"), n + "_0_1",
             [S("rectangle"), [S("start"), -10.16, 10.16], [S("end"), 10.16, -10.16],
              [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]],
            [S("symbol"), n + "_1_1"] + pins,
            [S("embedded_fonts"), S("no")]]


def sym_dps368():
    n = "DPS368"
    pins = [pin("power_in", 0, 10.16, 270, "VDD", "8"),
            pin("power_in", 5.08, 10.16, 270, "VDDIO", "6"),
            pin("bidirectional", -12.7, 2.54, 0, "SDI", "3"),
            pin("input", -12.7, 0, 0, "SCK", "4"),
            pin("input", -12.7, -2.54, 0, "CSB", "2"),
            pin("bidirectional", -12.7, -5.08, 0, "SDO", "5"),
            pin("power_in", 0, -10.16, 90, "GND", "1"),
            pin("passive", 5.08, -10.16, 90, "GND", "7")]
    return [S("symbol"), n,
            [S("pin_names"), [S("offset"), 1.016]],
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            prop("Reference", "U", -10.16, 8.89),
            prop("Value", "DPS368XTSA1", -3.81, -8.89),
            prop("Footprint", "shinkokyu:Infineon_PG-VLGA-8-2", 0, -12.7, True),
            prop("Datasheet", "https://www.infineon.com/dgdl/Infineon-DPS368-DataSheet-v01_01-EN.pdf", 0, 0, True),
            prop("Description", "Infineon DPS368 barometric pressure sensor, I2C/SPI, PG-VLGA-8-2", 0, 0, True),
            [S("symbol"), n + "_0_1",
             [S("rectangle"), [S("start"), -10.16, 7.62], [S("end"), 10.16, -7.62],
              [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]],
            [S("symbol"), n + "_1_1"] + pins,
            [S("embedded_fonts"), S("no")]]


SYMBOLS = {"XIAO_nRF52840": sym_xiao, "XIAO_nRF52840_SMD": lambda: sym_xiao("XIAO_nRF52840_SMD", True),
           "DPS368": sym_dps368}


def write_symbols():
    lib = [S("kicad_symbol_lib"), [S("version"), 20251024], [S("generator"), "shinkokyu"],
           [S("generator_version"), "10.0"]]
    for f in SYMBOLS.values():
        lib.append(f())
    with open(os.path.join(LIB, "shinkokyu.kicad_sym"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(lib) + "\n")


# ---------- 型（フットプリント） ----------
def uid():
    return [S("uuid"), str(uuid.uuid4())]


def fp_text_prop(name, value, x, y, layer, hide=False, size=1.0):
    p = [S("property"), name, value, [S("at"), x, y, 0], [S("layer"), layer]]
    if hide:
        p.append([S("hide"), S("yes")])
    p += [uid(), [S("effects"), [S("font"), [S("size"), size, size], [S("thickness"), 0.15]]]]
    return p


def line(x1, y1, x2, y2, layer, w=0.12):
    return [S("fp_line"), [S("start"), x1, y1], [S("end"), x2, y2],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("layer"), layer], uid()]


def rect(x1, y1, x2, y2, layer, w=0.12):
    return [S("fp_rect"), [S("start"), x1, y1], [S("end"), x2, y2],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("fill"), S("no")], [S("layer"), layer], uid()]


def circle(cx, cy, r, layer, w=0.12, fill=False):
    return [S("fp_circle"), [S("center"), cx, cy], [S("end"), cx + r, cy],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("fill"), S("yes" if fill else "no")],
            [S("layer"), layer], uid()]


def text(t, x, y, layer, size=0.8, rot=0):
    return [S("fp_text"), S("user"), t, [S("at"), x, y, rot], [S("layer"), layer], uid(),
            [S("effects"), [S("font"), [S("size"), size, size], [S("thickness"), 0.12]]]]


def footprint(name, descr, attr, items):
    return [S("footprint"), name, [S("version"), 20260206], [S("generator"), "pcbnew"],
            [S("generator_version"), "10.0"], [S("layer"), "F.Cu"], [S("descr"), descr]] + items[0] + \
        [[S("attr")] + [S(a) for a in attr], [S("duplicate_pad_numbers_are_jumpers"), S("no")]] + items[1] + \
        [[S("embedded_fonts"), S("no")]]


def fp_xiao():
    # 原点＝ピンの並びの中心。USB-C は -x 側。D0〜D6（1〜7）は +y 側、5V〜D7（14〜8）は -y 側。
    # 寸法は Seeed の XIAO-nRF52840-DIP / -SMD の型から（ピンの列の間は 15.24mm、本体 21 x 17.8mm）。
    props = [fp_text_prop("Reference", "REF**", 0, 0, "F.Fab"),
             fp_text_prop("Value", "XIAO_nRF52840_Hybrid", 0, 1.5, "F.Fab"),
             fp_text_prop("Datasheet", "", 0, 0, "F.Fab", True),
             fp_text_prop("Description", "", 0, 0, "F.Fab", True)]
    g = []
    pads = []
    for n in range(1, 15):
        if n <= 7:
            x, sy = -7.62 + (n - 1) * 2.54, 1
        else:
            x, sy = -7.62 + (14 - n) * 2.54, -1
        y = 7.62 * sy
        shape = "rect" if n == 1 else "circle"
        pads.append([S("pad"), str(n), S("thru_hole"), S(shape), [S("at"), x, y], [S("size"), 1.7, 1.7],
                     [S("drill"), 1.0], [S("layers"), "*.Cu", "*.Mask"], [S("remove_unused_layers"), S("no")], uid()])
        # 縁の端子（XIAO の外へ 1.0mm はみ出して、こてを当てやすくする）
        pads.append([S("pad"), str(n), S("smd"), S("roundrect"), [S("at"), x, 8.4 * sy], [S("size"), 1.6, 3.0],
                     [S("layers"), "F.Cu", "F.Mask"], [S("roundrect_rratio"), 0.2], uid()])
    # 本体の外形（USB 側 -10.55、反対側 +10.425、幅 ±8.9）
    g.append(rect(-10.55, -8.9, 10.425, 8.9, "F.Fab", 0.1))
    g.append(rect(-11.1, -10.15, 10.9, 10.15, "F.CrtYd", 0.05))
    # USB-C の位置
    g.append(rect(-11.85, -4.5, -10.55, 4.5, "F.Fab", 0.1))
    g.append(text("USB", -9.0, 0, "F.Fab", 1.0, 90))
    # XIAO の裏の BAT+ の端子を出す窓（基板に穴をあける）。BAT+ は (-0.31, +4.455)、2.5 x 1.1mm
    g.append(rect(-1.2, 2.6, 2.0, 6.3, "Edge.Cuts", 0.1))
    g.append(rect(-0.86, 3.2, 0.24, 5.7, "F.Fab", 0.05))
    g.append(text("BAT+", 0.6, 4.45, "F.Fab", 0.5, 90))
    # 1番ピンの印（XIAO の外に出る部分）
    g.append(circle(-7.62, 10.1, 0.15, "F.SilkS", 0.1, True))
    return footprint("XIAO_nRF52840_Hybrid",
                     "Seeed XIAO nRF52840: castellated (SMD) or pin header (THT) mounting, with a window to reach the BAT+ pad on the back",
                     ["through_hole"], (props, g + pads))


# XIAO の端子の位置（原点＝ピンの並びの中心、USB-C は -x 側、D0〜D6 は +y 側）
# Seeed 公式の XIAO-nRF52840-SMD の型と、公式の基板データ（Seeed Studio XIAO nRF52840 v1.3）から。
#   ピン n（1〜7）：x = -7.62 + (n-1)*2.54、y = +8.065 ／ ピン n（8〜14）：x = -7.62 + (14-n)*2.54、y = -8.1
#   裏の BAT+（19）：(-0.3135, 4.455)、裏の GND（20）：(-2.2185, 4.455)、どちらも 1.1 x 2.5mm
XIAO_SMD_PADS = [(str(n), -7.62 + (n - 1) * 2.54, 8.065) for n in range(1, 8)] +                 [(str(n), -7.62 + (14 - n) * 2.54, -8.1) for n in range(8, 15)]
XIAO_BACK_PADS = [("19", -0.3135, 4.455), ("20", -2.2185, 4.455)]


def fp_xiao_smd():
    props = [fp_text_prop("Reference", "REF**", 0, 0, "F.Fab"),
             fp_text_prop("Value", "XIAO_nRF52840_SMD", 0, 1.5, "F.Fab"),
             fp_text_prop("Datasheet", "", 0, 0, "F.Fab", True),
             fp_text_prop("Description", "", 0, 0, "F.Fab", True)]
    pads = []
    for num, x, y in XIAO_SMD_PADS:     # 縁の端子：2.0 x 2.75mm（Seeed の推奨）
        pads.append([S("pad"), num, S("smd"), S("roundrect"), [S("at"), x, y], [S("size"), 2.0, 2.75],
                     [S("layers"), "F.Cu", "F.Paste", "F.Mask"], [S("roundrect_rratio"), 0.25], uid()])
    for num, x, y in XIAO_BACK_PADS:    # 裏の端子
        pads.append([S("pad"), num, S("smd"), S("roundrect"), [S("at"), x, y], [S("size"), 1.1, 2.5],
                     [S("layers"), "F.Cu", "F.Paste", "F.Mask"], [S("roundrect_rratio"), 0.25], uid()])
    g = [rect(-10.55, -8.9, 10.425, 8.9, "F.Fab", 0.1),
         rect(-11.85, -4.5, -10.55, 4.5, "F.Fab", 0.1),
         text("USB", -9.0, 0, "F.Fab", 1.0, 90),
         rect(-12.0, -9.75, 10.95, 9.75, "F.CrtYd", 0.05),
         circle(-7.62, 9.95, 0.15, "F.SilkS", 0.1, True)]
    return footprint("XIAO_nRF52840_SMD",
                     "Seeed XIAO nRF52840 for reflow by the PCB assembler: castellated pads and back pads BAT+ (19) / GND (20)",
                     ["smd"], (props, g + pads))


def fp_dps368():
    # Infineon DPS368 PG-VLGA-8-2（2.0 x 2.5mm、0.65mm ピッチ）。データシート 9・10章の推奨パッド：0.35 x 0.35mm
    # 上から見て、上の列が左から 1・2・3・4、下の列が右から 5・6・7・8。空気の穴はふたの上（5番の近く）。
    props = [fp_text_prop("Reference", "REF**", 0, -2.1, "F.SilkS", size=0.6),
             fp_text_prop("Value", "DPS368", 0, 2.1, "F.Fab", size=0.6),
             fp_text_prop("Datasheet", "https://www.infineon.com/dgdl/Infineon-DPS368-DataSheet-v01_01-EN.pdf", 0, 0, "F.Fab", True),
             fp_text_prop("Description", "", 0, 0, "F.Fab", True)]
    pads = []
    xs = [-0.975, -0.325, 0.325, 0.975]
    for i, x in enumerate(xs):
        pads.append([S("pad"), str(i + 1), S("smd"), S("rect"), [S("at"), x, -0.725], [S("size"), 0.35, 0.35],
                     [S("layers"), "F.Cu", "F.Mask", "F.Paste"], [S("solder_mask_margin"), 0.05],
                     [S("solder_paste_margin"), -0.025], uid()])
    for i, x in enumerate(reversed(xs)):
        pads.append([S("pad"), str(i + 5), S("smd"), S("rect"), [S("at"), x, 0.725], [S("size"), 0.35, 0.35],
                     [S("layers"), "F.Cu", "F.Mask", "F.Paste"], [S("solder_mask_margin"), 0.05],
                     [S("solder_paste_margin"), -0.025], uid()])
    g = [rect(-1.25, -1.0, 1.25, 1.0, "F.Fab", 0.1),
         line(-1.25, -0.6, -0.85, -1.0, "F.Fab", 0.1),
         circle(0.6, 0.35, 0.2, "F.Fab", 0.05),
         rect(-1.6, -1.35, 1.6, 1.35, "F.CrtYd", 0.05),
         line(-1.4, -1.15, 1.4, -1.15, "F.SilkS"),
         line(-1.4, 1.15, 1.4, 1.15, "F.SilkS"),
         circle(-1.55, -1.5, 0.12, "F.SilkS", 0.1, True)]
    return footprint("Infineon_PG-VLGA-8-2", "Infineon DPS368/DPS310 PG-VLGA-8-2, 2.0x2.5mm, 0.65mm pitch (datasheet v1.1 fig.17/18)",
                     ["smd"], (props, g + pads))


def write_footprints():
    d = os.path.join(LIB, "shinkokyu.pretty")
    os.makedirs(d, exist_ok=True)
    for f in (fp_xiao, fp_xiao_smd, fp_dps368):
        e = f()
        with open(os.path.join(d, e[1] + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump(e) + "\n")


if __name__ == "__main__":
    os.makedirs(LIB, exist_ok=True)
    write_symbols()
    write_footprints()
    print("ok")
