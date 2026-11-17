# design.py から KiCad の回路図（.kicad_sch）を作る
# 部品の端子ごとに短い線とネットの名前（ラベル）を付ける方式。同じ名前のラベルどうしがつながる。
import math
import os
import uuid
from sexpr import Sym, parse, dump, find, find1
from design import PARTS
import make_lib

S = Sym
import variant
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = variant.ROOT
PROJECT = variant.PROJECT
KICAD_SYM = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\share\kicad\symbols")
JFONT = "Yu Gothic"
POWER_NETS = {"GND": "power:GND", "+3V3": "power:+3V3", "VBUS": "power:VBUS"}

# ---- 置き場所 (x, y, 回転) 単位 mm（1.27mm の格子）
PLACE = {
    "U1": (76.2, 63.5, 0),
    "J1": (162.56, 45.72, 0), "Q1": (190.5, 45.72, 90), "JP1": (190.5, 63.5, 0),
    "JP2": (226.06, 45.72, 0), "J2": (233.68, 63.5, 0), "TP1": (256.54, 43.18, 0), "TP3": (266.7, 43.18, 0),
    "D1": (190.5, 88.9, 180), "D2": (190.5, 101.6, 180), "TP2": (226.06, 86.36, 0),
    "U2": (330.2, 55.88, 0), "C1": (304.8, 88.9, 0), "C2": (314.96, 88.9, 0), "C3": (325.12, 88.9, 0),
    "R3": (304.8, 71.12, 90),
    "J3": (375.92, 50.8, 0), "J4": (403.86, 63.5, 0),
    "U3": (185.42, 175.26, 0), "C4": (213.36, 175.26, 0), "C5": (223.52, 175.26, 0), "JP3": (205.74, 195.58, 0),
    "J7": (259.08, 175.26, 0),
    "R1": (167.64, 228.6, 0), "R2": (180.34, 228.6, 0), "J5": (220.98, 228.6, 0),
    "SW1": (45.72, 160.02, 0), "SW2": (45.72, 175.26, 0), "SW3": (45.72, 190.5, 0), "J6": (106.68, 172.72, 0),
}
# 名前と値の位置を手で決める部品 (dx, dy, 角度, 寄せ)
FIELDS = {"Q1": {"Reference": (3.81, 6.35, 0, "right"), "Value": (3.81, 8.89, 0, "right")},  # 回転した記号は寄せが左右逆になる
          "U3": {"Reference": (-10.16, -8.89, 0, "left"), "Value": (-15.24, 12.7, 0, "left")}}
# 同じネットの端子を線でまとめる（後ろの端子 → 前の端子）
JOIN = {("U3", "6"): ("U3", "8"), ("U3", "7"): ("U3", "1")}
FLAGS = [("GND", 248.92, 104.14), ("VAMP", 261.62, 104.14)]

BLOCKS = [
    ((15.24, 22.86, 135.89, 127.0), "マイコン：XIAO nRF52840（自分ではんだ付けする）"),
    ((142.24, 22.86, 278.13, 127.0), "電源：電池・逆接続の保護・アンプの電源"),
    ((284.48, 22.86, 410.21, 127.0), "アンプ：MAX98357A（I2S）とスピーカー"),
    ((142.24, 135.89, 278.13, 207.01), "気圧センサー：DPS368（基板のはみ出し部分＝切り離せる）"),
    ((142.24, 210.82, 278.13, 248.92), "I2C の本体側（プルアップ・外付け用の端子）"),
    ((15.24, 135.89, 135.89, 248.92), "ボタン・予備の端子"),
]
NOTES = [
    (20.32, 93.98, [
        "D0 曲送り / D1 音量＋ / D2 音量− （ボタンの反対側は GND。XIAO の中のプルアップを使う）",
        "D3 圧電ブザー（アンプが動かないときの予備） / D6 予備",
        "D4・D5 気圧センサー（I2C） / D7 アンプのオン・オフ",
        "D8〜D10 アンプへの音の信号（I2S）。nRF52840 はピンをプログラムで入れ替えられる",
        "電池の＋（VBAT）は、基板の窓から XIAO の裏の BAT+ に線でつなぐ（TP1）",
    ]),
    (144.78, 109.22, [
        "Q1：電池の＋−を逆につないでも壊れないようにする。JP1 は Q1 が動かないときだけつなぐ",
        "JP2：はじめからつながっている。電源スイッチを付けるときは切って、J2 にスイッチをつなぐ",
        "D1・D2：USB の 5V と電池の高い方からアンプに電気を送る（電池なしでも USB だけで試せる）",
    ]),
    (287.02, 106.68, [
        "SD_MODE：D7 を高くすると鳴る（左の音）、低くすると止まる。R3 は SD_MODE を守る抵抗",
        "音量（GAIN）：何もつながない＝9dB（音量はプログラムで変える）。GAIN と SD_MODE は J4 の穴にも出してある",
        "J4：アンプが動かないとき、外付けのアンプ基板を同じ並びでつなぐ",
    ]),
    (144.78, 201.93, [
        "SDO は何もつながない＝アドレス 0x77。JP3 をつなぐと 0x76。CSB は 3V3（I2C を使う）",
        "切り離したら、J7 と本体側の J5 を4本の線でつなぐ（3V3・GND・SDA・SCL）",
    ]),
    (20.32, 203.2, [
        "SW1〜SW3：上から押す小さなボタン（TS-1187A、5.1mm 角・高さ 1.5mm）",
        "J6：普通のボタンを線でつなぐとき・圧電ブザー（D3）・予備（D6）",
    ]),
]


NS = uuid.UUID("6f1c2a52-3b7e-4c8e-9a51-2d0c5e7a9b10")
_n = [0]


def uid(key=None):
    """作り直しても同じ番号になるようにする（基板との対応が切れないように）"""
    if key is None:
        _n[0] += 1
        key = "auto-%d" % _n[0]
    if variant.V != "A":   # B版は別の番号にする（A版の番号は変えない）
        key = variant.V + "-" + key
    return str(uuid.uuid5(NS, key))


def fnt(size=1.27, face=None, justify=None, hide=False):
    f = [S("font")]
    if face:
        f.append([S("face"), face])
    f.append([S("size"), size, size])
    e = [S("effects"), f]
    if justify:
        e.append([S("justify")] + [S(j) for j in justify])
    if hide:
        e.append([S("hide"), S("yes")])
    return e


# ---------- 記号の読み込み ----------
_cache = {}


def load_lib(lib):
    if lib not in _cache:
        if lib == "shinkokyu":
            _cache[lib] = [S("kicad_symbol_lib")] + [f() for f in make_lib.SYMBOLS.values()]
        else:
            _cache[lib] = parse(open(os.path.join(KICAD_SYM, lib + ".kicad_sym"), encoding="utf-8").read())
    return _cache[lib]


def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    t = load_lib(lib)
    syms = {s[1]: s for s in find(t, "symbol")}
    s = syms[name]
    ext = find1(s, "extends")
    if ext:  # 派生した記号は、元の記号をもとに平らにする
        base = [x for x in syms[ext[1]]]
        props = {p[1]: p for p in find(s, "property")}
        out = [S("symbol"), name]
        for x in base[2:]:
            if isinstance(x, list) and x[0] == "property" and x[1] in props:
                out.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == "symbol":
                out.append([S("symbol"), x[1].replace(ext[1], name, 1)] + x[2:])
            else:
                out.append(x)
        s = out
    s = [S("symbol"), lib_id] + s[2:]
    return s


def sym_pins(s):
    out = []

    def walk(e):
        for x in e:
            if isinstance(x, list) and x:
                if x[0] == "pin":
                    at = find1(x, "at")
                    out.append(dict(num=find1(x, "number")[1], x=float(at[1]), y=float(at[2]), a=float(at[3])))
                elif x[0] == "symbol":
                    walk(x)
    walk(s)
    return out


def xf(px, py, rot):
    """記号の中の座標（上が＋）→ 回路図の上のずれ（下が＋）"""
    x, y = px, -py
    r = math.radians(rot)
    return (x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r))


def snap(v):
    return round(v / 0.01) * 0.01


# ---------- 回路図を組み立てる ----------
items = []
lib_syms = {}
root_uuid = uid("root")
pwr_n = [0]


def sym_instance(lib_id, ref, value, x, y, rot, footprint="", dnp=False, extra=None, in_bom=True, hide_ref=False,
                 hide_val=False):
    if lib_id not in lib_syms:
        lib_syms[lib_id] = lib_symbol(lib_id)
    ls = lib_syms[lib_id]
    lprops = {p[1]: p for p in find(ls, "property")}

    def field(name, val, hide):
        o = FIELDS.get(ref, {}).get(name)
        if o:
            return [S("property"), name, val, [S("at"), x + o[0], y + o[1], (o[2] - rot) % 180],
                    fnt(justify=[o[3]], hide=hide)]
        if name in lprops:
            a = find1(lprops[name], "at")
            ox, oy = xf(float(a[1]), float(a[2]), rot)
            ang = float(a[3])  # KiCad が記号の回転を足して表示する
            j = find1(find1(lprops[name], "effects"), "justify")
            return [S("property"), name, val, [S("at"), snap(x + ox), snap(y + oy), ang],
                    fnt(justify=[str(v) for v in j[1:]] if j else None, hide=hide)]
        return [S("property"), name, val, [S("at"), x, y, 0], fnt(hide=hide)]

    inst = [S("symbol"), [S("lib_id"), lib_id], [S("at"), x, y, rot], [S("unit"), 1],
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes" if in_bom else "no")],
            [S("on_board"), S("yes")], [S("dnp"), S("yes" if dnp else "no")], [S("uuid"), uid("sym-" + ref)]]
    inst.append(field("Reference", ref, hide_ref))
    inst.append(field("Value", value, hide_val))
    inst.append([S("property"), "Footprint", footprint, [S("at"), x, y, 0], fnt(hide=True)])
    ds = lprops["Datasheet"][2] if "Datasheet" in lprops else ""
    inst.append([S("property"), "Datasheet", ds, [S("at"), x, y, 0], fnt(hide=True)])
    inst.append([S("property"), "Description", "", [S("at"), x, y, 0], fnt(hide=True)])
    for k, v in (extra or {}).items():
        inst.append([S("property"), k, v, [S("at"), x, y, 0], fnt(hide=True)])
    for p in sym_pins(ls):
        inst.append([S("pin"), p["num"], [S("uuid"), uid()]])
    inst.append([S("instances"), [S("project"), PROJECT, [S("path"), "/" + root_uuid, [S("reference"), ref], [S("unit"), 1]]]])
    items.append(inst)
    return ls


def wire(x1, y1, x2, y2):
    items.append([S("wire"), [S("pts"), [S("xy"), x1, y1], [S("xy"), x2, y2]],
                  [S("stroke"), [S("width"), 0], [S("type"), S("default")]], [S("uuid"), uid()]])


def label(name, x, y, ox, oy):
    if ox > 0.5:
        ang, j = 0, ["left", "bottom"]
    elif ox < -0.5:
        ang, j = 180, ["right", "bottom"]
    elif oy < -0.5:
        ang, j = 90, ["left", "bottom"]
    else:
        ang, j = 270, ["right", "bottom"]
    items.append([S("label"), name, [S("at"), x, y, ang], fnt(justify=j), [S("uuid"), uid()]])


def global_label(name, x, y, ox, oy):
    ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(round(ox), round(oy))]
    j = "left" if ang in (0, 90) else "right"
    items.append([S("global_label"), name, [S("shape"), S("passive")], [S("at"), x, y, ang],
                  [S("fields_autoplaced"), S("yes")], fnt(size=1.0, justify=[j]), [S("uuid"), uid()],
                  [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), x, y, 0],
                   fnt(justify=[j], hide=True)]])


def power(net, x, y, ox, oy):
    pwr_n[0] += 1
    lib_id = POWER_NETS[net]
    if net == "GND":
        rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[(round(ox), round(oy))]
    else:
        rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[(round(ox), round(oy))]
    sym_instance(lib_id, "#PWR%02d" % pwr_n[0], net, x, y, rot, in_bom=False, hide_ref=True)


def attach(net, px, py, ox, oy, stub=2.54, mark=True):
    ex, ey = snap(px + ox * stub), snap(py + oy * stub)
    wire(px, py, ex, ey)
    if not mark:
        return ex, ey
    if net in POWER_NETS:
        if abs(oy) > 0.5:
            power(net, ex, ey, ox, oy)
        else:  # 横向きの端子は、電源の記号が重なるので、同じ名前のグローバルラベルにする
            global_label(net, ex, ey, ox, oy)
    else:
        label(net, ex, ey, ox, oy)
    return ex, ey


def place_part(ref):
    p = PARTS[ref]
    x, y, rot = PLACE[ref]
    extra = {}
    if p["lcsc"]:
        extra["LCSC"] = p["lcsc"]
    extra["JLC"] = "DNP" if p["dnp"] else ("手で付ける" if (p["hand"] or not p["lcsc"]) else "JLC")
    ls = sym_instance(p["sym"], ref, p["value"], x, y, rot, footprint=p["fp"], dnp=p["dnp"], extra=extra)
    groups = {}
    for pn in sym_pins(ls):
        dx, dy = xf(pn["x"], pn["y"], rot)
        a = math.radians(pn["a"])
        ddx, ddy = xf(math.cos(a), math.sin(a), rot)
        key = (snap(x + dx), snap(y + dy))
        groups.setdefault(key, []).append((pn["num"], (-round(ddx), -round(ddy))))
    ends = {}
    for (px, py), lst in groups.items():
        netset = {p["pins"][n] for n, _ in lst if n in p["pins"]}
        if not netset:
            continue
        assert len(netset) == 1, (ref, lst, netset)
        num = lst[0][0]
        ends[num] = attach(netset.pop(), px, py, *lst[0][1], mark=(ref, num) not in JOIN)
    for (r, n), (r2, n2) in JOIN.items():
        if r == ref:
            (x1, y1), (x2, y2) = ends[n], ends[n2]
            wire(x1, y1, x2, y2)


def text(t, x, y, size=1.5, bold=False):
    f = [S("font"), [S("face"), JFONT], [S("size"), size, size]]
    if bold:
        f.append([S("bold"), S("yes")])
    items.append([S("text"), t, [S("exclude_from_sim"), S("no")], [S("at"), x, y, 0],
                  [S("effects"), f, [S("justify"), S("left"), S("bottom")]], [S("uuid"), uid()]])


def box(x1, y1, x2, y2):
    items.append([S("rectangle"), [S("start"), x1, y1], [S("end"), x2, y2],
                  [S("stroke"), [S("width"), 0.2], [S("type"), S("dash")]], [S("fill"), [S("type"), S("none")]],
                  [S("uuid"), uid()]])


if variant.V == "B":
    BLOCKS[0] = (BLOCKS[0][0], "マイコン：XIAO nRF52840（JLCPCB が付ける）")
    NOTES[0] = (NOTES[0][0], NOTES[0][1], NOTES[0][2][:4] + [
        "XIAO の裏の BAT+（19）と GND（20）も、基板の端子に機械ではんだ付けされる（窓と線は要らない）"])


def build():
    for ref in PARTS:
        place_part(ref)
    for net, x, y in FLAGS:
        sym_instance("power:PWR_FLAG", "#FLG%02d" % (FLAGS.index((net, x, y)) + 1), "PWR_FLAG", x, y, 0,
                     in_bom=False, hide_ref=True)
        attach(net, x, y, 0, 1)
    for (x1, y1, x2, y2), title in BLOCKS:
        box(x1, y1, x2, y2)
        text(title, x1 + 1.27, y1 + 3.81, 2.0, True)
    for x, y, lines in NOTES:
        for i, ln in enumerate(lines):
            text(ln, x, y + i * 2.54, 1.4)
    sub = "A版：XIAO は自分ではんだ付け" if variant.V == "A" else "B版：XIAO も JLCPCB が付ける"
    text("シン呼吸 ポータブル版：XIAO nRF52840 を載せる基板（回路図・%s）" % sub, 15.24, 15.24, 3.0, True)
    sch = [S("kicad_sch"), [S("version"), 20250610], [S("generator"), "eeschema"], [S("generator_version"), "10.0"],
           [S("uuid"), root_uuid], [S("paper"), "A3"],
           [S("title_block"), [S("title"), "シン呼吸 ポータブル版 キャリア基板 %s版" % variant.V],
            [S("date"), "2026-10-21"], [S("rev"), "0.1"], [S("company"), "JPHACKS 2026 チーム「こんにちは」"]],
           [S("lib_symbols")] + list(lib_syms.values())]
    sch += items
    sch += [[S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]], [S("embedded_fonts"), S("no")]]
    return sch


if __name__ == "__main__":
    sch = build()
    with open(os.path.join(ROOT, PROJECT + ".kicad_sch"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(sch) + "\n")
    print("ok", len(items))
