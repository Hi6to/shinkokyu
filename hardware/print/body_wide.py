"""
案1 の筒の「ゆったり版」（11/07）。今の案1（外径 26、body_parts.py とチームの make_enclosure.py）は残したまま、
中に入る部品に余裕を持たせた別の版を作る。

なぜ作るか（今の案1 で、部品の外形を筒の内側と比べた結果。部品の高さは仮の値。下の PARTS）：
- 2枚目の XIAO（Sense 版）を1枚目の上に重ねると、上の角が筒の軸から約 14.0mm。今の内側の半径 11.5 では入らない
- スピーカー φ20 を基板を支える棚（基板の裏から 1.2 下）の下に置くと、下の角が約 12.3mm。入らない
- 基板の溝のすき間は片側 0.2（チームの試し刷りの箱は 0.35）

ゆったり版で変えたこと：
- 筒の外径 26 → 32（内径 23 → 28.8）。壁の厚さ 1.6 は同じ
- 基板の溝のすき間を片側 0.2 → 0.35（チームの試し刷りの箱と同じ）
- 前の部屋 C の中（息の部屋）の太さは今の案1 と同じ（半径 11.5）。息の判定のしきい値を変えずに済むように、壁を厚くした
- 座標・基板の位置・ボタン・溝の位置・USB の口・吹き口の穴（φ10.2）は今の案1 と同じ。吹き口アダプター（②④⑤⑥）はそのまま使える

座標（今の案1 と同じ）：X＝筒の軸（基板の USB の端が 0、前が +）、Y＝横、Z＝基板の裏が 0。筒の軸の高さ ZC＝0.4

作ったあと、check() で確かめる：
1. 部品がそれぞれ1つにつながっているか
2. 中に入る部品（基板・XIAO 2枚・ボタン・スピーカー・電池）が殻にぶつからないか、内側までの余裕
3. 組み立てたとき、部品どうしがぶつからないか（A・B・C・E・F）
"""
import math
import numpy as np
from manifold3d import Manifold, CrossSection

# ---------------- 寸法 ----------------
R_OUT = 16.0          # 筒の外の半径（外径 32）
WALL = 1.6
R_IN = R_OUT - WALL   # 14.4（内径 28.8）
ZC = 0.4
BOTTOM_DEPTH = R_IN + 0.3   # 下の殻の内側の一番深い所（45° の屋根の平らな橋）。今の案1 と同じ決め方

BOARD_T, BOARD_W, BOARD_MAIN_L = 0.8, 20.5, 55.3
Z_SPLIT = BOARD_T + 0.1
CLR = 0.35                        # 基板の溝のすき間（片側）
SLOT_HALF = BOARD_W / 2 + CLR     # 10.6
LEDGE_INNER, LEDGE_DEPTH = 9.85, 1.2

X_REAR, X_FRONT = -3.5, 60.3
GROOVE_X = (56.1, 58.3)
GROOVE_R = R_IN + 0.6             # 15.0（C のつばが入る溝）

SPK_X, SPK_R = 38.8, 10.0
RIB_T, RIB_R_IN, RIB_Z_TOP = 1.0, 10.2, -1.5
GRILLE_D = 1.5
SEG = 160

SW = [(30.4, 3.7), (38.2, 3.7), (46.0, 3.7)]
BTN_TOP = BOARD_T + 1.5
BOSS_H = 3.0
MARKS = ["play", "plus", "minus"]
MARK_Y, MARK_S, MARK_W, MARK_H = -3.7, 4.4, 1.0, 0.5

# 中に入る部品の外形（組み立ての座標。高さは仮の値で、実物を測って直す）
XIAO_H = 5.0          # XIAO 1枚の高さ（基板 ＋ 部品 ＋ USB-C の口）。仮
SPK_T = 5.0           # スピーカーの厚さ。仮（チームの試し刷りの箱は「スピーカーの厚さ＋余り」で 6.5 をとっている）
PARTS = {
    # 名前: (x0, x1, y0, y1, z0, z1)
    "基板（本体）":            (0.0, BOARD_MAIN_L, -BOARD_W / 2, BOARD_W / 2, 0.0, BOARD_T),
    "XIAO（1枚目）":           (1.9, 22.9, -8.9, 8.9, BOARD_T, BOARD_T + XIAO_H),
    "XIAO Sense（重ねた2枚目）": (1.9, 22.9, -8.9, 8.9, BOARD_T + XIAO_H, BOARD_T + 2 * XIAO_H),
    "ボタン3つと押し棒のつば":   (27.4, 49.0, 0.7, 6.7, BOARD_T, BTN_TOP + 0.6),
    "電池 26×15×4":            (1.0, 27.0, -7.5, 7.5, -LEDGE_DEPTH - 0.3 - 4.0, -LEDGE_DEPTH - 0.3),
}
SPEAKER = (SPK_X, SPK_R, -LEDGE_DEPTH - 0.3 - SPK_T, -LEDGE_DEPTH - 0.3)   # 中心の X、半径、下と上の Z

# ---------------- 道具 ----------------
def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])

def extrude_x(pts, x0, x1):
    cs = CrossSection([pts])
    if cs.area() <= 0:
        cs = CrossSection([pts[::-1]])
    return cs.extrude(x1 - x0).transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])

def cyl_ax(r0, r1, x0, x1, y=0.0, z=ZC, seg=SEG):
    """X の向きの円すい台（r0 → r1）"""
    assert x1 > x0, (x0, x1)
    return Manifold.cylinder(x1 - x0, r0, r1, seg).transform([[0, 0, 1, x0], [1, 0, 0, y], [0, 1, 0, z]])

def cyl_z(r, z0, z1, x, y, seg=48):
    return Manifold.cylinder(z1 - z0, r, r, seg).translate([x, y, z0])

def profile_outer():
    return [(R_OUT * math.cos(t), ZC + R_OUT * math.sin(t)) for t in np.linspace(0, 2 * math.pi, SEG, endpoint=False)]

def profile_inner(up=False):
    """内側の断面。下の殻は下が 45° の屋根＋平らな橋（up=True で上下を返して上の殻用）"""
    a45 = math.radians(45)
    pts = [(R_IN * math.cos(t), ZC + R_IN * math.sin(t)) for t in np.linspace(-math.pi / 2 + a45, 3 * math.pi / 2 - a45, SEG)]
    y45, z45 = R_IN * math.sin(a45), ZC - R_IN * math.cos(a45)
    yb = y45 + ((ZC - BOTTOM_DEPTH) - z45)
    pts += [(-yb, ZC - BOTTOM_DEPTH), (yb, ZC - BOTTOM_DEPTH)]
    if up:
        pts = [(y, 2 * ZC - z) for (y, z) in pts][::-1]
    return pts

def mark_2d(kind, s=MARK_S, w=MARK_W):
    h = s / 2
    bar = CrossSection.square([s, w]).translate([-h, -w / 2])
    if kind == "minus":
        return bar
    if kind == "plus":
        return bar + CrossSection.square([w, s]).translate([-w / 2, -h])
    return CrossSection([[(-h * 0.85, -h), (h, 0.0), (-h * 0.85, h)]])

# ---------------- B 下の殻 ----------------
def lower_shell():
    outer = extrude_x(profile_outer(), X_REAR, X_FRONT)
    shell = outer - extrude_x(profile_inner(), X_REAR - 1, X_FRONT + 1)
    for s in (1, -1):
        lo, hi = sorted((s * LEDGE_INNER, s * (R_OUT + 1)))
        shell += box(0, BOARD_MAIN_L, lo, hi, -LEDGE_DEPTH, 0)          # 基板の裏を支える棚
        lo, hi = sorted((s * SLOT_HALF, s * (R_OUT + 1)))
        shell += box(0, BOARD_MAIN_L, lo, hi, 0, Z_SPLIT)               # 基板が横にずれない壁
    for x0 in (SPK_X - SPK_R - 0.3 - RIB_T, SPK_X + SPK_R + 0.3):      # スピーカーの前後の輪
        ring = cyl_ax(R_IN + 0.9, R_IN + 0.9, x0, x0 + RIB_T) - cyl_ax(RIB_R_IN, RIB_R_IN, x0 - 1, x0 + RIB_T + 1)
        shell += ring ^ box(x0 - 1, x0 + RIB_T + 1, -30, 30, -30, RIB_Z_TOP)
    shell = shell ^ outer
    shell = shell ^ box(X_REAR - 1, X_FRONT + 1, -30, 30, -30, Z_SPLIT)
    shell -= cyl_ax(GROOVE_R, GROOVE_R, *GROOVE_X)
    for dx in (-5.6, -2.8, 0, 2.8, 5.6):                                 # スピーカーの音の穴
        for dy in (-2.8, 0, 2.8):
            shell -= cyl_z(GRILLE_D / 2, -30, -5, SPK_X + dx, dy, 24)
    return shell

# ---------------- A 上の殻 ----------------
def upper_shell():
    outer = extrude_x(profile_outer(), X_REAR, X_FRONT)
    shell = outer - extrude_x(profile_inner(up=True), X_REAR - 1, X_FRONT + 1)
    for s in (1, -1):                                                   # 基板のふちを上から押さえる帯
        lo, hi = sorted((s * LEDGE_INNER, s * (R_OUT + 1)))
        shell += box(1.0, BOARD_MAIN_L, lo, hi, Z_SPLIT, Z_SPLIT + 0.6)
    shell = shell ^ outer
    shell = shell ^ box(X_REAR - 1, X_FRONT + 1, -30, 30, Z_SPLIT, 40)
    shell -= cyl_ax(GROOVE_R, GROOVE_R, *GROOVE_X)
    z_ceil = ZC + BOTTOM_DEPTH                                          # 内側の天井（平らな橋）
    for x, y in SW:
        zt = ZC + math.sqrt(R_OUT ** 2 - y ** 2)
        shell += cyl_z(3.4, z_ceil - 0.01, zt + BOSS_H, x, y)           # 天井から上だけ（天井の下にぶら下げない）
        shell -= cyl_z(2.1, 0, zt + BOSS_H + 1, x, y)
    band = cyl_ax(R_OUT + MARK_H, R_OUT + MARK_H, X_REAR, X_FRONT) - cyl_ax(R_OUT - 0.3, R_OUT - 0.3, X_REAR - 1, X_FRONT + 1)
    for (x, _), kind in zip(SW, MARKS):                                 # ボタンの印（0.5 浮き出し）
        shell += mark_2d(kind).extrude(R_OUT + 2).translate([x, MARK_Y, ZC]) ^ band
    return shell

def plunger():
    zt = ZC + math.sqrt(R_OUT ** 2 - SW[0][1] ** 2)
    length = (zt + BOSS_H + 1.0) - BTN_TOP
    return Manifold.cylinder(0.6, 2.9, 2.9, 32) + Manifold.cylinder(length, 1.85, 1.85, 32), length

# ---------------- C 前の部屋 ----------------
CH_R = 11.5                 # 息の部屋の半径（今の案1 と同じ）
C_FL = (56.3, 58.1)         # つば＝仕切りの壁（溝 56.1〜58.3 に入る）
C_NECK = (58.1, 60.4)       # 殻の前のふちの内側を通る所
NECK_R = R_IN - 0.2         # 14.2
C_MAIN = (60.4, 74.0)
C_CONE = (74.0, 83.0)       # 45° で細くなる（16 → 7）
C_TIP = (83.0, 90.0)        # ④ を差す筒（外径 14）
SOCK = 6.0                  # 差し込みの深さ（穴 φ10.2）
RING = (60.6, 68.8)
LIP = (69.0, 70.5)
LIP_R = R_OUT + 0.8
WIN_X, WIN_SPAN, WIN_W = 64.7, 150.0, 3.0

def front_chamber():
    m = cyl_ax(GROOVE_R - 0.15, GROOVE_R - 0.15, *C_FL)
    m += cyl_ax(NECK_R, NECK_R, *C_NECK)
    m += cyl_ax(R_OUT, R_OUT, *C_MAIN)
    m += cyl_ax(R_OUT, 7.0, *C_CONE)
    m += cyl_ax(7.0, 7.0, *C_TIP)
    m += cyl_ax(LIP_R, LIP_R, LIP[0], LIP[0] + 0.8) + cyl_ax(LIP_R, R_OUT, LIP[0] + 0.8, LIP[1])
    # 中（息の部屋）：つば（仕切り）より前を、首から前まで同じ半径でくりぬく。首と太い筒は同じ内側の面でつながる
    bore_x0 = C_TIP[1] - SOCK                                           # 84.0
    m -= cyl_ax(CH_R, CH_R, C_FL[1], 72.4)
    m -= cyl_ax(CH_R, 2.5, 72.4 - 0.01, 81.4)                          # 45° で細く（刷るとき、広がる向きなので張り出しなし）
    m -= cyl_ax(2.5, 5.1, 81.4 - 0.01, bore_x0 + 0.01)                 # 差し込みの穴の天井（45°）
    m -= cyl_ax(5.1, 5.1, bore_x0, C_TIP[1] + 1)                       # 差し込みの穴 φ10.2
    m -= box(C_FL[0] - 1, C_FL[1] + 1, -6.3, 6.3, -0.3, 1.1)           # 基板のタブを通す穴（首のまわりはグルーでふさぐ）
    m -= cyl_ax(0.3, 0.3, C_FL[0] - 1, C_FL[1] + 1, 0, ZC - 6.0)       # 通り道の穴 φ0.6
    n = 40                                                              # 三角の窓
    for i in range(n):
        a0, a1 = WIN_SPAN * i / n, WIN_SPAN * (i + 1) / n
        w = WIN_W * (1 - (a0 + a1) / 2 / WIN_SPAN)
        if w < 0.15:
            break
        pts = []
        for a in (a0 - 0.3, a1 + 0.3):
            t = math.radians(a)
            for r in (CH_R - 0.5, R_OUT + 0.5):
                for x in (WIN_X - w / 2, WIN_X + w / 2):
                    pts.append((x, r * math.sin(t), ZC + r * math.cos(t)))
        m -= Manifold.hull_points(pts)
    for k in range(8):                                                  # カチッと止まる浅い溝
        t = math.radians(WIN_SPAN * k / 7 + 180)
        pts = []
        for x in (RING[0] + 1.2, RING[1] - 1.2):
            for dt in (-1.6, 1.6):
                tt = t + math.radians(dt)
                for r in (R_OUT - 0.4, R_OUT + 0.5):
                    pts.append((x, r * math.sin(tt), ZC + r * math.cos(tt)))
        m -= Manifold.hull_points(pts)
    return m

# ---------------- E 回すリング ----------------
def ring_E():
    ri, ro, w = R_OUT + 0.15, R_OUT + 1.65, RING[1] - RING[0]
    m = Manifold.cylinder(w, ro, ro, SEG) - Manifold.cylinder(w + 2, ri, ri, SEG).translate([0, 0, -1])
    m -= Manifold.cube([0.8, 4, w + 2]).translate([-0.4, ri - 1, -1])
    m += Manifold.sphere(0.45, 16).translate([0, -ri, w / 2])
    for k in range(40):
        a = 2 * math.pi * k / 40
        if abs(math.sin(a / 2)) < 0.08:
            continue
        m -= Manifold.cylinder(w + 2, 0.45, 0.45, 12).translate([ro * math.sin(a), ro * math.cos(a), -1])
    return m

def ring_E_assembled():
    """組み立ての座標（軸は X。切れ目は上＝窓の始まり 0°）"""
    m = ring_E()
    return m.transform([[0, 0, 1, RING[0]], [1, 0, 0, 0], [0, 1, 0, ZC]])

# ---------------- F 後ろのキャップ ----------------
def cap_F():
    plug_r = R_IN - 0.2
    m = Manifold.cylinder(2.0, R_OUT, R_OUT, SEG) + Manifold.cylinder(5.0, plug_r, plug_r, SEG)
    m -= Manifold.cylinder(6, plug_r - 1.2, plug_r - 1.2, SEG).translate([0, 0, 2.0])
    zc_usb = BOARD_T + 1.6 - ZC
    m -= box(-6.75, 6.75, zc_usb - 4.4, zc_usb + 4.4, -1, 8)
    return m

def cap_F_assembled():
    """つばの外の面が X = X_REAR - 2、差しこみが殻の中（X_REAR〜X_REAR+3）。口の横長は Y の向き"""
    return cap_F().transform([[0, 0, 1, X_REAR - 2.0], [1, 0, 0, 0], [0, 1, 0, ZC]])

# ---------------- 確かめ ----------------
def pieces(m):
    return len(m.decompose())

def components():
    comps = {k: box(*v) for k, v in PARTS.items()}
    sx, sr, sz0, sz1 = SPEAKER
    comps["スピーカー φ20"] = Manifold.cylinder(sz1 - sz0, sr, sr, 96).translate([sx, 0, sz0])
    return comps

def check(verbose=True):
    """作った形を確かめる。問題があれば AssertionError"""
    A, B, C = upper_shell(), lower_shell(), front_chamber()
    Ering, F = ring_E_assembled(), cap_F_assembled()
    pl, _ = plunger()
    rep = []
    # 1. 1つにつながっているか（押し棒・リングも）
    for name, m in [("A 上の殻", A), ("B 下の殻", B), ("C 前の部屋", C), ("E リング", Ering), ("F キャップ", F), ("押し棒", pl)]:
        n = pieces(m)
        rep.append(f"{name}：{n} 個の形" + ("" if n == 1 else "  ← つながっていない"))
        assert n == 1, name
    # 2. 中の部品が殻にぶつからないか、余裕
    shells = A + B + C
    comps = components()
    for name, c in comps.items():
        hit = (c ^ shells).volume()
        if name.startswith("基板"):
            rep.append(f"{name}：殻とのかさなり {hit:.2f} mm3（溝のすき間は片側 {CLR}）")
        else:
            rep.append(f"{name}：殻とのかさなり {hit:.2f} mm3、内側までの余裕 約 {clearance(c, shells):.1f} mm")
        assert hit < 1e-3, name
    # 3. 組み立てたときに部品どうしがぶつからないか
    for (n1, m1), (n2, m2) in [(("A", A), ("B", B)), (("A", A), ("C", C)), (("B", B), ("C", C)),
                               (("C", C), ("E", Ering)), (("A", A), ("E", Ering)), (("B", B), ("E", Ering)),
                               (("A", A), ("F", F)), (("B", B), ("F", F))]:
        v = (m1 ^ m2).volume()
        rep.append(f"{n1} と {n2} のかさなり {v:.3f} mm3")
        assert v < 0.01, (n1, n2, v)
    if verbose:
        print("\n".join(rep))
    return rep

def clearance(c, shells, step=0.1, upto=3.0):
    """部品の外形を、Y・Z の向きに少しずつ大きくして、殻にふれるまでの量（mm）"""
    bb = c.bounding_box()
    cx, cy, cz = [(bb[i] + bb[i + 3]) / 2 for i in range(3)]
    d = 0.0
    while d < upto:
        d2 = d + step
        sx = 1.0
        sy = (bb[4] - bb[1] + 2 * d2) / (bb[4] - bb[1])
        sz = (bb[5] - bb[2] + 2 * d2) / (bb[5] - bb[2])
        g = c.translate([-cx, -cy, -cz]).scale([sx, sy, sz]).translate([cx, cy, cz])
        if (g ^ shells).volume() > 1e-3:
            return d
        d = d2
    return upto

if __name__ == "__main__":
    check()
