"""
案1 の本体（丸い筒）のうち、チームの make_enclosure.py にまだない部品を作る。
寸法と座標は make_enclosure.py と同じ（X＝筒の軸、基板の USB の端が 0。Z＝基板の裏が 0。筒の軸の高さ ZC＝0.4）。
- A 上の殻：ボタンの押し棒の穴（外に高さ 3mm の筒をつけて、押し棒がぐらつかないようにする）
- C 前の部屋：一体の筒。後ろのつばは上下の殻の溝にはさまる。三角の窓の上で E が回る。前は 45° で細くなり、④ を差す穴がある
- E 回すリング：切れ目 0.8mm の割れたリング。C の後ろからはめ、殻の前の面とふちの間に閉じこめる（8段階でカチッ）
- F 後ろのキャップ：USB-C の口（ケーブルの太い所が入る 13.5 × 8.8）
- G USB のふた：TPU（ABS だけで作るときは lid_G_abs：かたい栓に、つぶれる細い山をつけて押しこんで止める）
- 押し棒（本体用）
"""
import math, sys, pathlib
import numpy as np
from manifold3d import Manifold, CrossSection
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "enclosure"))
import make_enclosure as E   # チームのデータ（B 下の殻）と同じ寸法を使う

R_OUT, R_IN, ZC = E.R_OUT, E.R_IN, E.ZC
SW = [(30.4, 3.7), (38.2, 3.7), (46.0, 3.7)]   # KiCad の SW1〜SW3（X = kx − 98.2、Y = ky − 100）
BTN_TOP = E.BOARD_T + 1.5
BOSS_H = 3.0                                    # 押し棒のガイドの筒（殻の外）
# ボタンの印（11/07）：SW1＝曲送り「▶」、SW2＝音量「＋」、SW3＝音量「－」（firmware/shinkokyu の割り当て）。
# 押し棒の穴の横（Y を反対にした所）に、高さ 0.5 で浮き出させる。▶ は吹き口の向き（＋X）を指す
# 彫らない理由：殻の天井は平らで、Y=±3.7 あたりは壁が 0.66mm しかなく、彫ると穴があく。浮き出しなら、指でさわっても分かる
MARKS = ["play", "plus", "minus"]
MARK_Y, MARK_S, MARK_W, MARK_H = -3.7, 4.4, 1.0, 0.5   # 印の中心の Y、大きさ、線の太さ、浮き出す高さ

def mark_2d(kind, s=MARK_S, w=MARK_W):
    """ボタンの印の平面の形（原点が中心）"""
    h = s / 2
    bar = CrossSection.square([s, w]).translate([-h, -w / 2])
    if kind == "minus":
        return bar
    if kind == "plus":
        return bar + CrossSection.square([w, s]).translate([-w / 2, -h])
    return CrossSection([[(-h * 0.85, -h), (h, 0.0), (-h * 0.85, h)]])  # play：＋X を指す三角

def mark_prism(kind, x, y, z0, z1):
    """印を Z の向きにのばした柱"""
    return mark_2d(kind).extrude(z1 - z0).translate([x, y, z0])

def cyl_ax(r0, r1, x0, x1, seg=E.SEG, z=ZC):
    """X の向きの円すい台（r0 → r1）"""
    assert x1 > x0, (x0, x1)
    m = Manifold.cylinder(x1 - x0, r0, r1, seg)
    return m.transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, z]])

def roof_inner():
    """上の殻の内側：下の殻の内側（45°の屋根）を上下にひっくり返した形"""
    return [(y, 2 * ZC - z) for (y, z) in E.profile_inner()]

def upper_shell():
    outer = E.extrude_x(E.profile_outer(), E.X_REAR, E.X_FRONT)
    inner = E.extrude_x(roof_inner()[::-1], E.X_REAR - 1, E.X_FRONT + 1)
    shell = outer - inner
    for s in (1, -1):                                   # 基板のふちを上から押さえる帯
        lo, hi = sorted((s * 9.85, s * 12.5))
        shell += E.box(1.0, E.BOARD_MAIN_L, lo, hi, E.Z_SPLIT, E.Z_SPLIT + 0.6)
    shell = shell ^ outer
    shell = shell ^ E.box(E.X_REAR - 1, E.X_FRONT + 1, -20, 20, E.Z_SPLIT, 30)
    shell -= E.cyl_x(E.GROOVE_R, *E.GROOVE_X)
    for x, y in SW:                                     # 押し棒のガイドの筒と穴
        zt = ZC + math.sqrt(R_OUT ** 2 - y ** 2)
        shell += E.cyl_z(3.4, ZC + E.BOTTOM_DEPTH - 0.01, zt + BOSS_H, x, y)   # 内側の天井から上だけ（天井の下にぶら下げない）
        shell -= E.cyl_z(2.1, 0, zt + BOSS_H + 1, x, y)
    # ボタンの印：筒の外の面から 0.5 だけ浮き出させる（丸い面に沿って同じ高さ。根元は壁の中に 0.3 埋める）
    band = cyl_ax(R_OUT + MARK_H, R_OUT + MARK_H, E.X_REAR, E.X_FRONT) - cyl_ax(R_OUT - 0.3, R_OUT - 0.3, E.X_REAR - 1, E.X_FRONT + 1)
    for (x, _), kind in zip(SW, MARKS):
        shell += mark_prism(kind, x, MARK_Y, ZC, ZC + R_OUT + 2) ^ band
    return shell

def body_plunger():
    zt = ZC + math.sqrt(R_OUT ** 2 - SW[0][1] ** 2)
    length = (zt + BOSS_H + 1.0) - BTN_TOP
    m = Manifold.cylinder(0.6, 2.9, 2.9, 32) + Manifold.cylinder(length, 1.85, 1.85, 32)
    return m, length

# ---- ABS 版の殻（11/07 の試し刷りで、殻の内側の天井が糸のように崩れたため）----
# 殻は合わせ面を下にして刷る。内側の一番奥（45° の屋根の先）が、幅 8.9 × 長さ 64 の「支えのない橋」になる。
# ABS は冷やす風を弱くするので、橋がたれて崩れやすい。スピーカーの輪と音の穴が橋にかかると、さらに崩れる。
# 対策：① 橋の下に、あとで折って取る「支え」を形に入れる（breakaway）② スピーカーの輪の下のふちを 45° にする
SUP_T, SUP_GAP = 0.8, 0.25      # 支えの壁の厚さ（2本の線）、支えと天井のすき間（はがせるように）

def breakaway(part, xs, ys, z_bed, z_top, up=1, pitch_x=20.0):
    """part の内側の天井を下から支える格子（組み立ての座標で作る）。
    ys の位置に長さの向きの壁（橋の線は横に渡るので、これが線を受ける）、pitch_x ごとに横の壁（倒れないように。多いと刷る時間がのびる）。z_bed（台）から z_top（天井）まで。up は刷るときの上の向き（+1 / -1）。
    part のまわり SUP_GAP は空ける（横にも上にも）。とがったかけらが残らないよう、最後に part と重なる分を消す"""
    x0, x1 = xs
    y0, y1 = min(ys) - SUP_T / 2, max(ys) + SUP_T / 2
    lo, hi = sorted((z_bed, z_top - up * (SUP_GAP + 0.03)))   # 0.03 多く空ける（ずらした part の面と同じ高さにしない）
    g = Manifold()
    for y in ys:
        g += E.box(x0, x1, y - SUP_T / 2, y + SUP_T / 2, lo, hi)
    n = max(1, round((x1 - x0) / pitch_x))
    for k in range(n + 1):                                   # 両はしの壁も厚さ SUP_T（11/08：前は半分の 0.4 になっていた）
        x = x0 + SUP_T / 2 + (x1 - x0 - SUP_T) * k / n
        g += E.box(x - SUP_T / 2, x + SUP_T / 2, y0, y1, lo, hi)
    keep = Manifold()
    for dx, dy in ((0, 0), (SUP_GAP, 0), (-SUP_GAP, 0), (0, SUP_GAP), (0, -SUP_GAP)):
        for dz in (0, -up * SUP_GAP):
            keep += part.translate([dx, dy, dz])
    return g - keep

BRIDGE_Z = E.BOTTOM_DEPTH       # 軸から橋（内側の一番奥の平らな所）まで
SUP_YS = (-2.2, 2.2)            # 橋（幅 8.9）の下の支えの壁の位置。橋は 4.4mm ずつに分かれる（3本にすると刷る時間が 50 分のびたため 2本）

def rib_fix(shell):
    """スピーカーの前後の輪（内側の半径 10.2 の円）の下の部分を 45° の V にする。
    刷る向き（ひっくり返す）では、円の下の部分が支えのない張り出しになるため。スピーカーにふれる高さは変えない"""
    r = E.RIB_R_IN
    a = r * math.sin(math.radians(45))
    inner = E.extrude_x(E.profile_inner(), E.X_REAR - 1, E.X_FRONT + 1)
    for x0 in (E.SPK_X - E.SPK_R - 0.3 - E.RIB_T, E.SPK_X + E.SPK_R + 0.3):
        pts = []
        for x in (x0 - 0.01, x0 + E.RIB_T + 0.01):
            pts += [(x, -a, ZC - a), (x, a, ZC - a), (x, 0.0, ZC - 2 * a)]
        shell -= Manifold.hull_points(pts) ^ inner
    return shell

def lower_shell_abs_parts():
    """B 下の殻（ABS 版）：輪の下を 45° にした殻と、橋の下の支え（刷る向きでは上が −Z）を別々に返す"""
    b = rib_fix(E.lower_shell())
    sup = breakaway(b, (E.X_REAR + 0.6, E.X_FRONT - 0.6), SUP_YS, E.Z_SPLIT, ZC - BRIDGE_Z, up=-1)
    return b, sup

def upper_shell_abs_parts():
    """A 上の殻（ABS 版）：殻と、橋の下の支え（押し棒の穴の下も。穴の中には入らない）を別々に返す"""
    a = upper_shell()
    sup = breakaway(a, (E.X_REAR + 0.6, E.X_FRONT - 0.6), SUP_YS, E.Z_SPLIT, ZC + BRIDGE_Z, up=1)
    return a, sup

def lower_shell_abs():
    b, sup = lower_shell_abs_parts()
    return b + sup

def upper_shell_abs():
    a, sup = upper_shell_abs_parts()
    return a + sup

# ---- C 前の部屋（吹き口の側を下にして立てて刷る。ABS 版はつばを下にする）----
C_FL = (56.3, 58.1)         # つば（溝 56.1〜58.3 に入る）
C_NECK = (58.1, 60.4)       # 殻の前のふちの内側を通る細い所（半径 11.3）
C_MAIN = (60.4, 74.0)       # 外径 26（殻と同じ太さ）。ここに E がのる
C_CONE = (74.0, 80.0)       # 45° で細くなる（刷るとき下になるので、張り出しを作らない）
C_TIP = (80.0, 87.0)        # 吹き口アダプター ④ の差し込みの筒（外径 14）
SOCK = 6.0                  # 差し込みの深さ（穴 φ10.2）
RING = (60.6, 68.8)         # E の場所（後ろは殻の前の面 60.3 で、前は LIP で止まる）
LIP = (69.0, 70.5)          # E が前に抜けないふち（半径 13.8）
WIN_X = 64.7                # 三角の窓の真ん中
WIN_SPAN, WIN_W = 150.0, 3.0

JOINT_CH = 0.8              # ABS 版：首と本体の境の外側の面取り（つばを下にして刷るときの張り出しを減らす）
def front_chamber(abs_=False):
    """abs_=True：UltiMaker S3・ABS 用（つばを下にして刷る）。仕切りの壁が台の上で刷れて、すき間なく平らにできる。
    そのかわり、首（半径 11.3）の上に本体（半径 13）が張り出すので、外のかどを 0.8 だけ 45° に面取りする"""
    m = cyl_ax(11.95, 11.95, *C_FL)
    m += cyl_ax(11.3, 11.3, *C_NECK)
    if abs_:
        m += cyl_ax(R_OUT - JOINT_CH, R_OUT, C_MAIN[0], C_MAIN[0] + JOINT_CH) + cyl_ax(R_OUT, R_OUT, C_MAIN[0] + JOINT_CH, C_MAIN[1])
    else:
        m += cyl_ax(R_OUT, R_OUT, *C_MAIN)
    m += cyl_ax(R_OUT, 7.0, *C_CONE)
    m += cyl_ax(7.0, 7.0, *C_TIP)
    m += cyl_ax(13.8, 13.8, LIP[0], LIP[0] + 0.7) + cyl_ax(13.8, R_OUT, LIP[0] + 0.7, LIP[1])
    # 中をくりぬく
    m -= cyl_ax(10.4, 10.4, C_FL[1], C_NECK[1] + 0.01)           # つば（58.1 まで）は仕切りの壁として残す
    # 首と太い筒をつなぐ壁：内側を 45° の坂にして、首（半径 10.4〜11.3）と太い筒（11.5〜13）を一続きにする
    # （11/07 修正：前は首と筒が角の線だけで接していて、仕切りのつばが筒から外れた別の部品になっていた）
    m -= cyl_ax(10.4, R_IN, C_NECK[1], C_NECK[1] + 1.1 + 0.01)
    m -= cyl_ax(R_IN, R_IN, C_NECK[1] + 1.1, 73.0)
    m -= cyl_ax(R_IN, 3.0, 73.0, 81.5)
    m -= cyl_ax(5.1, 5.1, C_TIP[1] - SOCK, C_TIP[1] + 1)          # 差し込みの穴 φ10.2
    # 基板のタブ（幅 12）を通す、つばの横長の穴（組み立てたあと、首のまわりをグルーでふさぐ）
    m -= E.box(C_FL[0] - 1, C_FL[1] + 1, -6.3, 6.3, -0.3, 1.1)
    m -= E.cyl_x(0.3, C_FL[0] - 1, C_FL[1] + 1, 0, ZC - 6.0)       # 通り道の穴 φ0.6
    if abs_:
        # FFF ではノズル（0.4）に近い細い穴はふさがりやすい。部屋の側にもすり鉢（深さ 0.4）をつけ、ふさがったら φ0.6 のドリルで開けやすくする
        # （台の側のすり鉢は、刷る前の「台のふちの面取り」でつく）
        m -= cyl_ax(0.3, 0.7, C_FL[1] - 0.4, C_FL[1] + 0.01, 32, ZC - 6.0)   # 部屋の側（x=58.1）が広い
    # 三角の窓（上 0° から +Y の向きに 150°。長さの向きの幅 3 → 0）
    n = 40
    for i in range(n):
        a0, a1 = WIN_SPAN * i / n, WIN_SPAN * (i + 1) / n
        w = WIN_W * (1 - (a0 + a1) / 2 / WIN_SPAN)
        if w < 0.15: break
        pts = []
        for a in (a0 - 0.3, a1 + 0.3):
            t = math.radians(a)
            for r in (R_IN - 0.5, R_OUT + 0.5):
                for x in (WIN_X - w / 2, WIN_X + w / 2):
                    pts.append((x, r * math.sin(t), ZC + r * math.cos(t)))
        m -= Manifold.hull_points(pts)
    # カチッと止まる浅い溝（8か所、深さ 0.4）。リングの突起は切れ目の反対側にある
    for k in range(8):
        t = math.radians(WIN_SPAN * k / 7 + 180)
        pts = []
        for x in (RING[0] + 1.2, RING[1] - 1.2):
            for dt in (-1.6, 1.6):
                tt = t + math.radians(dt)
                for r in (R_OUT - 0.4, R_OUT + 0.5):
                    pts.append((x, r * math.sin(tt), ZC + r * math.cos(tt)))
        m -= Manifold.hull_points(pts)
    return m

def ring_E():
    """C の後ろ（つばの側）からはめて、窓の上まで送る。C を殻に差すと、殻の前の面とふち LIP の間に閉じこめられる"""
    ri, ro, w = R_OUT + 0.15, R_OUT + 1.65, RING[1] - RING[0]
    m = Manifold.cylinder(w, ro, ro, E.SEG) - Manifold.cylinder(w + 2, ri, ri, E.SEG).translate([0, 0, -1])
    m -= Manifold.cube([0.8, 4, w + 2]).translate([-0.4, ri - 1, -1])           # 切れ目（ここから息が出る）
    m += Manifold.sphere(0.45, 16).translate([0, -ri, w / 2])                   # 内側の突起（切れ目の反対側）
    for k in range(36):                                                         # 外のギザギザ
        a = 2 * math.pi * k / 36
        if abs(math.sin(a / 2)) < 0.08: continue
        m -= Manifold.cylinder(w + 2, 0.45, 0.45, 12).translate([ro * math.sin(a), ro * math.cos(a), -1])
    return m

def cap_F():
    plug_r = R_IN - 0.2
    m = Manifold.cylinder(2.0, R_OUT, R_OUT, E.SEG) + Manifold.cylinder(5.0, plug_r, plug_r, E.SEG)
    m -= Manifold.cylinder(6, plug_r - 1.2, plug_r - 1.2, E.SEG).translate([0, 0, 2.0])
    # USB-C の口：ケーブルの太い所（幅 13.5 × 高さ 8.8）が入る。差し込み口の中心（基板の表＋1.6）にそろえる
    zc_usb = E.BOARD_T + 1.6 - ZC
    m -= E.box(-6.75, 6.75, zc_usb - 4.4, zc_usb + 4.4, -1, 8)
    return m

def lid_G():
    m = E.box(-6.55, 6.55, -4.2, 4.2, 0, 3.0) + E.box(-7.8, 7.8, -5.4, 5.4, -1.2, 0) + E.box(7.8, 13.0, -2.5, 2.5, -1.2, 0)
    return m

def lid_G_abs():
    """ABS だけで作る USB のふた（11/07）：TPU のようにたわまないので、
    栓（13.1 × 8.4、口 13.5 × 8.8 にすき間 0.2）の4つの面に、つぶれる細い山（半径 0.3、0.3 はみ出す）をつけて押しこむ。
    先は 0.4 の面取りで入れやすくする。つまみはそのまま"""
    m = E.box(-7.8, 7.8, -5.4, 5.4, -1.2, 0) + E.box(7.8, 13.0, -2.5, 2.5, -1.2, 0)
    plug = E.box(-6.55, 6.55, -4.2, 4.2, 0, 2.6)
    plug += Manifold.hull(E.box(-6.55, 6.55, -4.2, 4.2, 2.59, 2.6) + E.box(-6.15, 6.15, -3.8, 3.8, 2.99, 3.0))
    m += plug
    rib = lambda x, y: Manifold.cylinder(2.2, 0.3, 0.3, 16).translate([x, y, 0.2])
    for x in (-3.5, 3.5):
        m += rib(x, 4.2) + rib(x, -4.2)
    m += rib(6.55, 0) + rib(-6.55, 0)
    return m
