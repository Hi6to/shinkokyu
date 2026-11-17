"""
外見の案（案3・案5・案7・案15・案17）の 3D プリント用データを作る。
寸法の元：
- 基板 B版 20.5 × 69.3 × 0.8mm（docs/PCB_DESIGN.md）。部品の位置は hardware/carrier_b の KiCad（X = kx − 98.2、Y = ky − 100）
  XIAO 中心 X=12.4、ボタン SW1〜3 は X=30.4 / 38.2 / 46.0・Y=+3.7、気圧センサー X=64.5、スピーカー中心 X=38.8（make_enclosure.py）
- チームの試し刷りの箱 73.2 × 24.4 × 11.9mm（hardware/enclosure/README.md）：すき間 0.35、壁 1.6、基板の下 6.5
- 本体の筒（案1）外径 26mm（make_enclosure.py の R_OUT = 13.0）
座標：X＝基板の長さ方向（USB の端が 0）、Y＝基板の幅、Z＝基板の裏が 0。単位は mm。
"""
import math, pathlib, json, numpy as np, trimesh
from manifold3d import Manifold, CrossSection

HERE = pathlib.Path(__file__).parent
OUT = HERE / "stl"; OUT_M = HERE / "model"   # stl＝刷る向き、model＝組み立てた向き（確認用）
SEG = 96

# ---------------- 共通の寸法 ----------------
BW, BT, CLR, WALL = 20.5, 0.8, 0.35, 1.6
BOARD_L, MAIN_L = 69.3, 55.3
IN_W = BW + 2 * CLR                 # 21.2
OUT_W = IN_W + 2 * WALL             # 24.4（試し刷りの箱と同じ）
UNDER, ABOVE = 6.5, 4.8             # 基板の裏から下 6.5（スピーカー）／基板の裏から上 4.8（XIAO 3.5 ＋ 余り）
ZB_IN, ZT_IN = -UNDER, ABOVE
ZB, ZT = ZB_IN - WALL, ZT_IN + WALL  # -8.1 / 6.4
XB_IN, XF_IN = -CLR, 71.6
XB, XF = XB_IN - WALL, XF_IN + WALL  # -1.95 / 73.2
PART_X0, PART_T = 56.7, 1.2          # 仕切り（基板の首 55.3〜59.3 を通す）
BTN = [(30.4, 3.7), (38.2, 3.7), (46.0, 3.7)]
BTN_TOP = BT + 1.5                   # ボタンの上の面（ボタンの高さ 1.5）
# ボタンの印（11/07）：SW1＝曲送り「▶」、SW2＝音量「＋」、SW3＝音量「－」（firmware/shinkokyu の割り当て）
# 押し棒の穴の横（Y を反対にした所）に、深さ 0.6 で彫る。▶ は吹き口の向き（＋X）を指す
MARKS = ["play", "plus", "minus"]
MARK_Y, MARK_S, MARK_W, MARK_D = -3.7, 4.4, 1.0, 0.6
# 空気口の調節（箱型の案）：大きい穴 1つ（直径 3.0）＋ 回す円盤（直径 16、厚さ 1.6）
DIAL_C = (65.0, 0.0)                 # 円盤の中心（息の部屋の上の面）
DIAL_R, DIAL_HOLE, DIAL_T, DIAL_D = 4.5, 3.0, 1.6, 16.0
DIAL_WMAX, DIAL_SPAN = 0.8, 210.0     # 円盤の切れ目：幅 0.8 → 0 に細くなる（0〜210°）。開く広さ 約 2.4mm² → 0
SPK_X, SPK_R = 38.8, 10.0
CH_Z = (ZB_IN + ZT_IN) / 2           # 息の部屋の真ん中の高さ
USB_W, USB_Z0 = 13.5, -0.6           # USB-C の切り欠き（ケーブルの太い所が入る幅＝チームの箱と同じ）

def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])
def cyl_z(r, z0, z1, x=0, y=0, seg=48):
    return Manifold.cylinder(z1 - z0, r, r, seg).translate([x, y, z0])
def cyl_x(r, x0, x1, y=0, z=0, seg=48):
    return Manifold.cylinder(x1 - x0, r, r, seg).rotate([0, 90, 0]).translate([x0, y, z])
def cyl_y(r, y0, y1, x=0, z=0, seg=48):
    return Manifold.cylinder(y1 - y0, r, r, seg).rotate([-90, 0, 0]).translate([x, y0, z])
def lathe(profile, seg=SEG):
    return Manifold.revolve(CrossSection([[(r, z) for r, z in profile]]), seg)
def capsule(p, q, r):
    return Manifold.hull(Manifold.sphere(r, 16).translate(p) + Manifold.sphere(r, 16).translate(q))
def mark_2d(kind, s=MARK_S, w=MARK_W):
    """ボタンの印の平面の形（原点が中心）"""
    h = s / 2
    bar = CrossSection.square([s, w]).translate([-h, -w / 2])
    if kind == "minus":
        return bar
    if kind == "plus":
        return bar + CrossSection.square([w, s]).translate([-w / 2, -h])
    return CrossSection([[(-h * 0.85, -h), (h, 0.0), (-h * 0.85, h)]])  # play：＋X を指す三角

# ---------------- コア（電子部品の箱）：案7・案15・案17 で共通 ----------------
def core_shell():
    outer = box(XB, XF, -OUT_W / 2, OUT_W / 2, ZB, ZT)
    inner = box(XB_IN, XF_IN, -IN_W / 2, IN_W / 2, ZB_IN, ZT_IN)
    m = outer - inner
    # 仕切り（下の半分は基板の首の下まで、上の半分は首の上から）。首のまわりはグルーでふさぐ
    m += box(PART_X0, PART_X0 + PART_T, -IN_W / 2, IN_W / 2, ZB_IN, 0)
    m += box(PART_X0, PART_X0 + PART_T, -IN_W / 2, IN_W / 2, BT + 0.1, ZT_IN)
    # 基板をのせる棚（下）と、上から押さえる帯（上）
    for s in (1, -1):
        y0, y1 = sorted([s * 9.85, s * IN_W / 2])
        m += box(0.0, MAIN_L, y0, y1, -1.2, 0)
        m += box(1.0, MAIN_L, y0, y1, BT + 0.1, BT + 0.7)
    # USB-C の切り欠き（後ろの壁）
    m -= box(XB - 1, XB_IN + 0.1, -USB_W / 2, USB_W / 2, USB_Z0, ZT + 1)
    # ボタンの穴（押し棒を通す）
    for x, y in BTN:
        m -= cyl_z(2.1, ZT_IN - 0.1, ZT + 1, x, y)
    # ボタンの印（上の面に深さ 0.6 で彫る。彫るので、案17 の外箱にもぶつからない）
    for (x, _), kind in zip(BTN, MARKS):
        m -= mark_2d(kind).extrude(MARK_D + 1).translate([x, MARK_Y, ZT - MARK_D])
    # スピーカーの音の穴（底）
    for dx, dy in [(0, 0)] + [(3.2 * math.cos(math.radians(a)), 3.2 * math.sin(math.radians(a))) for a in range(0, 360, 60)] \
            + [(6.2 * math.cos(math.radians(a)), 6.2 * math.sin(math.radians(a))) for a in range(0, 360, 30)]:
        m -= cyl_z(0.75, ZB - 1, ZB_IN + 0.1, SPK_X + dx, dy, 16)
    # 息の部屋：前の壁の穴（吹き口の受けへ）
    m -= cyl_x(2.5, XF_IN - 0.1, XF + 1, 0, CH_Z)
    # 空気口の調節：大きい穴1つ＋その上で回す円盤（円盤の軸・カチッと止まるくぼみ・目印）
    cx, cy = DIAL_C
    m -= cyl_z(DIAL_HOLE / 2, ZT_IN - 0.1, ZT + 0.1, cx + DIAL_R, cy, 32)
    m += cyl_z(2.0, ZT - 0.01, ZT + DIAL_T + 0.2, cx, cy, 32)
    m -= cyl_z(0.8, ZT - 1.2, ZT + DIAL_T + 1, cx, cy, 16)            # M2 のタッピングねじの下穴
    for k in range(8):
        a = math.radians(180 - 30 * k)
        m -= cyl_z(0.5, ZT - 0.4, ZT + 0.1, cx + 6.6 * math.cos(a), cy + 6.6 * math.sin(a), 16)
    m -= box(cx - 9.6, cx - 8.2, cy - 0.3, cy + 0.3, ZT - 0.3, ZT + 0.1)   # 目印の線
    return m

def core_halves():
    m = core_shell()
    back = m.trim_by_plane([0, 0, -1], 0)    # z ≤ 0
    front = m.trim_by_plane([0, 0, 1], 0)    # z ≥ 0
    return back, front

def socket():
    """吹き口の受け（コアの前の壁に貼る）。中に吹き口アダプターの差し込み（直径 10）が入る"""
    f = box(0, 2, -7, 7, -6, 6)
    tube = cyl_x(7, 0, 9, 0, 0)
    m = f + tube
    m -= cyl_x(5.1, 2.5, 10, 0, 0)       # 差し込みの穴 10.2
    m -= cyl_x(2.5, -1, 3, 0, 0)         # 息の通り道 5.0
    return m

def adapter():
    """吹き口アダプター（簡易版）：差し込み 10.0 × 6 ＋ つば ＋ ストローを差す筒（内径 6.4→6.0）"""
    m = cyl_x(5.0, 0, 6, 0, 0) + cyl_x(7, 6, 8, 0, 0) + cyl_x(4.6, 8, 20, 0, 0)
    inner = Manifold.cylinder(14, 3.2, 3.0, 48).rotate([0, 90, 0]).translate([7, 0, 0])
    m -= inner
    m -= cyl_x(3.0, -1, 8, 0, 0)
    m -= cyl_x(4.6, -0.5, 1.2, 0, 0)      # フィルターをはさむくぼみ（直径 9.2 × 1.2）
    return m

def dial():
    """空気口の円盤。切れ目が回る向きに細くなり、穴の上に来た所の幅で開く広さが変わる（8段階でカチッと止まる）"""
    cx, cy = DIAL_C
    m = cyl_z(DIAL_D / 2, 0, DIAL_T, seg=72)
    m -= cyl_z(2.15, -1, DIAL_T + 1, seg=32)                      # 軸の穴（4.3）
    for k in range(24):                                            # ふちのギザギザ（指をかける）
        a = 2 * math.pi * k / 24
        m -= cyl_z(0.6, -1, DIAL_T + 1, (DIAL_D / 2 + 0.25) * math.cos(a), (DIAL_D / 2 + 0.25) * math.sin(a), 12)
    n = 30
    pts = []
    for i in range(n + 1):
        a = math.radians(DIAL_SPAN * i / n)
        w = DIAL_WMAX * (1 - i / n) + 0.02
        pts.append((DIAL_R * math.cos(a), DIAL_R * math.sin(a), w))
    for (x1, y1, w1), (x2, y2, w2) in zip(pts, pts[1:]):
        if w1 < 0.12: break
        m -= Manifold.hull(cyl_z(w1 / 2, -1, DIAL_T + 1, x1, y1, 12) + cyl_z(max(w2, 0.1) / 2, -1, DIAL_T + 1, x2, y2, 12))
    m += Manifold.sphere(0.45, 16).translate([6.6 * math.cos(math.pi), 6.6 * math.sin(math.pi), 0])   # 裏の小さな突起（カチッ）
    m -= box(6.0, 7.6, -0.35, 0.35, DIAL_T - 0.3, DIAL_T + 1)                                      # 上の面の目印（いちばん開く向き）
    return m.translate([cx, cy, ZT + 0.05])

def plunger(extra=0.0):
    """ボタンの押し棒：つば（内側）＋軸。extra は外の箱の壁の分（案17）"""
    length = (ZT - BTN_TOP) + 1.0 + extra
    m = cyl_z(2.8, 0, 0.6) + cyl_z(1.85, 0, length)
    return m

# ---------------- 案7 ネックレス ----------------
def necklace_back(back):
    m = back
    for s in (1, -1):
        lug = box(XB - 4.5, XB + 0.2, s * 7.6 - 2.2, s * 7.6 + 2.2, ZB, ZB + 4.0)
        lug -= cyl_z(1.3, ZB - 1, ZB + 5, XB - 2.4, s * 7.6, 24)
        m += lug
    return m

# ---------------- 案15 社員証ケース ----------------
CARD_W, CARD_H = 54.0, 86.0
FR_X0, FR_X1 = -14.0, 82.0               # 枠の上下（X）
FR_Y1 = -OUT_W / 2 - 0.0                 # コアの横のへり
FR_Y0 = FR_Y1 - 64.0
def idcase_frame_back():
    plate = box(FR_X0, FR_X1, FR_Y0, OUT_W / 2, ZB - 2.0, ZB)          # コアを貼る部分まで続く板
    rails = box(FR_X0, FR_X1, FR_Y0, FR_Y1, ZB, ZB + 1.2)
    cy0 = FR_Y0 + (FR_Y1 - FR_Y0 - (CARD_W + 0.6)) / 2
    cx0 = FR_X0 + 3.0
    rails -= box(cx0 - 10, cx0 + CARD_H + 0.6, cy0, cy0 + CARD_W + 0.6, ZB - 0.1, ZB + 1.3)  # カードを差すすき間（上が開く）
    m = plate + rails
    # ストラップの穴
    sx = (FR_Y0 + FR_Y1) / 2
    m -= box(FR_X0 + 1.2, FR_X0 + 4.2, sx - 7, sx + 7, ZB - 3, ZB + 3)
    return m, (cx0, cy0)

def idcase_frame_front(cxy):
    cx0, cy0 = cxy
    m = box(FR_X0, FR_X1, FR_Y0, FR_Y1, ZB + 1.2, ZB + 2.4)
    m -= box(cx0 + 4, cx0 + CARD_H - 4, cy0 + 4, cy0 + CARD_W - 4, ZB, ZB + 3)   # 窓
    sx = (FR_Y0 + FR_Y1) / 2
    m -= box(FR_X0 + 1.2, FR_X0 + 4.2, sx - 7, sx + 7, ZB - 3, ZB + 4)
    return m

# ---------------- 案17 ひと息マッチ ----------------
def rot_core_to_match(m):
    """コアを横に寝かせる：コアの +Z（ボタン）→ 外箱の +Y の壁、コアの +Y → 外箱の −Z"""
    return m.rotate([-90, 0, 0])
MW, MC = 54.0, 0.2                       # 外箱の幅、コアとのすき間（片側）
def match_parts():
    core_th = ZT - ZB                    # 14.5
    comp_y1 = MW / 2 - WALL
    comp_y0 = comp_y1 - core_th - 2 * MC
    zin0, zin1 = WALL, WALL + OUT_W + 2 * MC
    H = zin1 + WALL
    x0, x1 = XB - MC, XF + MC             # コアの前後
    L0, L1 = x0, x1 + WALL
    # コアをどこに置くか（回したあとのコアの位置合わせ）
    # 回すと コアの z → y、コアの y → −z。コアの z=ZT が comp_y1−MC に、コアの y=0 が zin の真ん中に来るように動かす
    dy = (comp_y1 - MC) - ZT
    dz = (zin0 + zin1) / 2
    place = lambda m: rot_core_to_match(m).translate([0, dy, dz])
    sleeve = box(L0, L1, -MW / 2, MW / 2, 0, H)
    sleeve -= box(L0 - 1, x1, -MW / 2 + WALL, comp_y0 - 1.2, zin0, zin1)      # 内箱の入る所
    sleeve -= box(L0 - 1, x1, comp_y0, comp_y1, zin0, zin1)                    # コアの入る所
    # 吹き口の受けを通す穴（前の壁）。コアの前の穴の位置に合わせる
    sp = np.array([0.0, 0.0, CH_Z]); sp = np.array([sp[0], sp[2] + dy, -sp[1] + dz])   # (x, y, z) 回したあと
    sleeve -= cyl_x(7.3, x1 - 1, L1 + 1, sp[1], sp[2])
    # ボタンの押し棒の穴（+Y の壁）
    for x, y in BTN:
        sleeve -= cyl_y(2.1, comp_y1 - 0.5, MW / 2 + 1, x, -y + dz)
    # ボタンの印（+Y の外の面に深さ 0.6 で彫る。コアの上の面の印と同じ並び）
    for (x, _), kind in zip(BTN, MARKS):
        sleeve -= mark_2d(kind).extrude(MARK_D + 1).rotate([90, 0, 0]).translate([x, MW / 2 + 1, -MARK_Y + dz])
    # 空気口の円盤を回す窓（+Y の壁）
    sleeve -= cyl_y(9.6, comp_y1 - 1, MW / 2 + 1, DIAL_C[0], -DIAL_C[1] + dz, 64)
    # マッチの「すり板」：横の面の浅いくぼみ（-Y の壁）
    sleeve -= box(L0 + 8, L1 - 8, -MW / 2 - 1, -MW / 2 + 0.6, 6, H - 6)
    # 内箱
    tw0, tw1 = -MW / 2 + WALL + 0.35, comp_y0 - 1.2 - 0.35
    tz0, tz1 = zin0 + 0.35, zin1 - 0.35
    tl0, tl1 = L0 - 2.0, x1 - 0.5
    t = box(tl0, tl1, tw0, tw1, tz0, tz1)
    t -= box(tl0 + 1.6, tl1 - 1.2, tw0 + 1.2, tw1 - 1.2, tz0 + 1.2, tz1 + 1)
    mid = (tw0 + tw1) / 2
    t += box(tl0 + 1.6, tl1 - 1.2, mid - 0.6, mid + 0.6, tz0, tz1 - 2)        # 2列に分ける仕切り
    for k in range(7):                                                         # 使い終わった列（-Y 側）の乾かす穴
        t -= cyl_z(1.2, tz0 - 1, tz0 + 2, tl0 + 8 + k * 9.5, (tw0 + mid) / 2, 16)
    t -= box(tl0 - 1, tl0 + 2.6, mid - 8, mid + 8, tz1 - 6, tz1 + 1)           # 指をかける切り欠き
    t -= box(tl0 - 0.3, tl0 + 0.4, tw0 + 3, mid - 3, tz1 - 9, tz1 - 4)         # 印（使い終わった）
    t -= box(tl0 - 0.3, tl0 + 0.4, mid + 3, tw1 - 3, tz1 - 9, tz1 - 4)         # 印（これから使う）
    return sleeve, t, place, H

# ---------------- 案17 を「しまう箱」にした版（11/09） ----------------
# 外箱に入れたままでは、押し棒・円盤の軸・吹き口の受けのつばが当たって差しこめなかった。
# コアは箱の外で使い、しまうときに内箱（ノズルなど）と一緒に入れる形にする。内箱の入る所は前と同じ
STORE_DY = 4.5    # コアの入る所を、ボタンの面の側へ広げる分（押し棒 2.8・円盤を M2 なべねじ＋ワッシャーで留めた所 約 3.9 が出ている）
STORE_FX = 2.0    # コアの入る所だけ前へのばす分（吹き口の受けのつば 2.0 が中に入る。受けの筒は前の壁の穴から出る）
def match_store_sleeve():
    core_th = ZT - ZB
    comp_y1 = MW / 2 - WALL
    comp_y0 = comp_y1 - core_th - 2 * MC
    zin0, zin1 = WALL, WALL + OUT_W + 2 * MC
    H = zin1 + WALL
    x1 = XF + MC
    L0, L1 = XB - MC, x1 + STORE_FX + WALL
    dy, dz = (comp_y1 - MC) - ZT, (zin0 + zin1) / 2                       # コアの置き方は前と同じ（仕切りの側に寄せる）
    sleeve = box(L0, L1, -MW / 2, MW / 2 + STORE_DY, 0, H)
    sleeve -= box(L0 - 1, x1, -MW / 2 + WALL, comp_y0 - 1.2, zin0, zin1)                # 内箱の入る所（前と同じ）
    sleeve -= box(L0 - 1, x1 + STORE_FX, comp_y0, comp_y1 + STORE_DY, zin0, zin1)      # コアの入る所（広げた）
    sleeve -= cyl_x(7.3, x1 + STORE_FX - 1, L1 + 1, CH_Z + dy, dz)                      # 吹き口の受けの筒が出る穴
    sleeve -= box(L0 + 8, L1 - 8, -MW / 2 - 1, -MW / 2 + 0.6, 6, H - 6)                 # マッチの「すり板」（前と同じ）
    return sleeve, H

# ---------------- 案3 ペンのクリップ ----------------
def pen_clip():
    """案1の筒（外径 26）にはめるクリップ。リングは八角形の外形で、サポートなしで刷れる"""
    RI = BODY_R + 0.15
    ap = RI + 2.2                                    # 八角形の向かい合う面の半分
    cs = CrossSection.circle(ap / math.cos(math.pi / 8), 8).rotate(22.5)
    ring = Manifold.extrude(cs, 10).rotate([0, 90, 0])          # 軸は X、底の面は z = -ap
    hole = Manifold.cylinder(12, RI, RI, 72).rotate([0, 90, 0]).translate([-1, 0, 0])
    y1 = RI * 1.4142 - RI - 1.0
    tri = [(-RI * 0.7071, RI * 0.7071), (-(RI + 1.0), y1), (-(RI + 1.0), -y1), (-RI * 0.7071, -RI * 0.7071)]   # 45°の屋根＋上に 8.9mm の橋（リングは閉じたまま）
    cs_t = CrossSection([tri])
    if cs_t.area() <= 0: cs_t = CrossSection([tri[::-1]])
    roof = Manifold.extrude(cs_t, 12).rotate([0, 90, 0]).translate([-1, 0, 0])   # 穴の上をとがらせて、サポートなしで刷る
    ring -= (hole + roof)
    ring = ring.translate([0, 0, ap])                 # 底を z=0 に
    arm = box(0, 48, -3.5, 3.5, 0, 1.8)
    tip = Manifold.hull(cyl_y(1.2, -3.5, 3.5, 46.5, 1.8) + box(45, 48, -3.5, 3.5, 0, 1.8))
    return ring + arm + tip

# ---------------- 案5 スタンド（中の形は共通） ----------------
BODY_R = 13.0   # 差す筒の外の半径（案1 は 13.0。ゆったり版は set_body_r(16.0)。11/07）
HOLE_D, CAV_D, LEDGE_ID, SLOT_W, FLOOR = 2 * BODY_R + 2 * 0.35, 24.0, 19.0, 14.0, 2.0
def set_body_r(r):
    """クリップとスタンドを、外の半径 r の筒に合わせる（穴と、穴のまわりの上の部分だけが変わる）"""
    global BODY_R, HOLE_D
    BODY_R, HOLE_D = r, 2 * r + 2 * 0.35
INSERT = 10.5
def stand_inner(H):
    zl = H - INSERT
    zc = zl - (CAV_D - LEDGE_ID) / 2
    inner = lathe([(0, FLOOR), (CAV_D / 2, FLOOR), (CAV_D / 2, zc), (LEDGE_ID / 2, zl), (HOLE_D / 2, zl),
                   (HOLE_D / 2, H - 0.8), (HOLE_D / 2 + 0.8, H + 0.01), (0, H + 0.01)])
    slot = box(-SLOT_W / 2, SLOT_W / 2, -80, 0, FLOOR, H + 30)
    return inner + slot
def feet(r):
    m = Manifold()
    for k in range(4):
        a = math.radians(45 + 90 * k)
        m += cyl_z(4.2, -0.01, 1.0, r * math.cos(a), r * math.sin(a), 32)
    return m

def stand_plain():
    H = 30.0
    m = lathe([(0, 0), (32, 0), (32, H - 1), (31, H), (0, H)])
    return m - stand_inner(H) - feet(25), H

def stand_volcano():
    H = 33.0
    dr = BODY_R - 13.0
    m = lathe([(0, 0), (40, 0), (39.5, 2), (31, 13), (23 + dr * 0.5, 25), (17.5 + dr, 31.5), (16.6 + dr, H), (0, H)])
    m -= lathe([(0, H - 1.6), (15.6 + dr, H - 1.6), (16.4 + dr, H + 0.1), (0, H + 0.1)])   # 火口のくぼみ
    # 溶岩の筋（彫る）：溝の向き（-Y）以外の3本
    for a in (40, 150, 215):
        t = math.radians(a)
        pts = [(17.4 + dr, 31), (24 + dr * 0.5, 23.6), (31.4, 13.4), (39.2, 2.4)]
        for (r1, z1), (r2, z2) in zip(pts, pts[1:]):
            m -= capsule([r1 * math.cos(t), r1 * math.sin(t), z1], [r2 * math.cos(t), r2 * math.sin(t), z2], 1.3)
    return m - stand_inner(H) - feet(28), H

def flame_frustum(H, R0, R1, amp, seg=144, layers=24):
    """炎の形の円すい台（下が広い）。上にいくほど内側にすぼまるので、サポートなしで刷れる"""
    verts, faces = [], []
    for j in range(layers + 1):
        t = j / layers; z = H * t; base = R0 + (R1 - R0) * t; a = amp * (1 - t)
        for i in range(seg):
            th = 2 * math.pi * i / seg
            r = base + a * (0.6 * math.sin(7 * th + 2.2 * t) + 0.4 * math.sin(4 * th - 3 * t))
            verts.append((r * math.cos(th), r * math.sin(th), z))
    for j in range(layers):
        for i in range(seg):
            a0, a1 = j * seg + i, j * seg + (i + 1) % seg
            b0, b1 = a0 + seg, a1 + seg
            faces += [(a0, a1, b1), (a0, b1, b0)]
    c0 = len(verts); verts.append((0, 0, 0)); c1 = len(verts); verts.append((0, 0, H))
    for i in range(seg):
        faces.append((c0, (i + 1) % seg, i)); faces.append((c1, layers * seg + i, layers * seg + (i + 1) % seg))
    tm = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    from manifold3d import Mesh
    return Manifold(Mesh(vert_properties=np.asarray(tm.vertices, dtype=np.float32), tri_verts=np.asarray(tm.faces, dtype=np.uint32)))

TOWER_XY = (24.0, 12.0)
def stand_rocket():
    H = 30.0
    pad = cyl_z(34, 0, 4, seg=SEG)
    fl = flame_frustum(H - 4, 30, 15.8 + (BODY_R - 13.0), 2.6).translate([0, 0, 4])
    fins = Manifold()
    for a in (90, 210, 330):
        dr = BODY_R - 13.0                               # 筒が太いときは、ひれを外へ（穴にかからないように）
        sh = CrossSection([[(14 + dr, 0), (27 + dr, 0), (27 + dr, 10), (16 + dr, 30), (14 + dr, 30)]])
        fin = Manifold.extrude(sh, 2.4).translate([0, 0, -1.2]).rotate([90, 0, 0]).rotate([0, 0, a]).translate([0, 0, 4])
        fins += fin
    m = pad + fl + fins
    m -= box(TOWER_XY[0] - 2.75, TOWER_XY[0] + 2.75, TOWER_XY[1] - 2.75, TOWER_XY[1] + 2.75, 0.8, 4.1)   # 発射塔を差す穴
    return m - stand_inner(H) - feet(26), H

def rocket_tower():
    """発射塔（寝かせて刷る）。下の差し込み 5 × 5 × 3"""
    t = box(-4.5, 4.5, -4.5, 4.5, 0, 92)
    for z in range(8, 90, 12):
        t -= box(-5, 5, -1.2, 1.2, z, z + 7) + box(-1.2, 1.2, -5, 5, z, z + 7)   # 窓（はしごに見える）
    t += box(-2.5, 2.5, -2.5, 2.5, -3, 0.01)                                      # 差し込み
    t += box(-18, 0, -2, 2, 66, 70)                                                # アーム
    return t

def stand_sword():
    rnd = np.random.default_rng(23)
    tiers = Manifold.cylinder(6, 42, 42, 8).rotate([0, 0, 22.5]) + Manifold.cylinder(5, 34, 34, 8).translate([0, 0, 6])
    pts = []
    for k in range(70):
        z = 11 + 33 * (k % 10) / 9
        th = 2 * math.pi * rnd.random()
        r = (30 - 0.38 * (z - 11)) * (0.82 + 0.25 * rnd.random())
        pts.append((r * math.cos(th), r * math.sin(th), z))
    for k in range(10):
        th = 2 * math.pi * k / 10; pts.append(((18.5 + BODY_R - 13.0) * math.cos(th), (18.5 + BODY_R - 13.0) * math.sin(th), 44.0))
    boulder = Manifold.hull_points(pts)
    boulder = boulder.trim_by_plane([0, 0, -1], -44.0)
    H = 44.0
    m = tiers + boulder
    for k in range(7):                                   # 放射状の割れ目（彫る）
        a = 2 * math.pi * k / 7 + 0.3
        if abs(math.degrees(a) % 360 - 270) < 25: continue
        r0, r1 = 15.5 + BODY_R - 13.0, 22 + BODY_R - 13.0
        m -= capsule([r0 * math.cos(a), r0 * math.sin(a), H], [r1 * math.cos(a), r1 * math.sin(a), H - 6], 0.9)
    return m - stand_inner(H) - feet(30), H

def stand_sprout():
    H = 40.0
    pot = lathe([(0, 0), (22, 0), (23, 1), (27, 36), (30, 36.5), (30, 44), (27, 44), (26.5, H), (0, H)])
    k = (18.79 + BODY_R - 13.0) / 18.79                       # 穴が太くなった分だけ外へ
    pot -= cyl_z(1.65, H - 5, H + 1, 17 * k, 8 * k, 24)    # 葉っぱの差し込み穴
    return pot - stand_inner(H) - feet(16), H

def sprout_leaf():
    sh = CrossSection([[(0, 0), (6, 6), (14, 11), (24, 10), (30, 6), (22, 2), (12, -1)][::-1]])
    leaf = Manifold.extrude(sh, 2.0)
    stem = Manifold.cylinder(14, 1.5, 1.5, 24).rotate([0, 90, 0]).translate([-11, 0.5, 1.0])   # 茎を葉に 3 重ねる（11/07 修正：前は先の1点だけで接していた）
    return leaf + stem

# ---------------- 書き出し ----------------
REPORT = []
def to_tm(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)
def on_bed(m, rx=0, ry=0):
    m = m.rotate([rx, ry, 0])
    lo = np.array(m.bounding_box()[:3]); hi = np.array(m.bounding_box()[3:])
    return m.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
def save(m, name, idea, label, pose=(0, 0), note=""):
    OUT.mkdir(exist_ok=True); OUT_M.mkdir(exist_ok=True)
    to_tm(m).export(OUT_M / name)
    p = on_bed(m, *pose); tm = to_tm(p); tm.export(OUT / name)
    ext = tm.bounds[1] - tm.bounds[0]
    REPORT.append(dict(file=name, idea=idea, label=label, size=[round(float(e), 1) for e in ext],
                       vol=round(tm.volume / 1000, 2), ok=bool(tm.is_watertight), note=note))
    print(f"{name:28s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f}  {tm.volume/1000:6.2f} cm3  watertight={tm.is_watertight}")

if __name__ == "__main__":
    back, front = core_halves()
    save(back, "core_back.stl", "core", "コア 下の殻（スピーカー・電池・基板をのせる）", note="底を下にして刷る")
    save(front, "core_front.stl", "core", "コア 上の殻（ボタンの穴・空気口の穴と円盤の軸）", note="開いた側（合わせ面）を下にして刷る。上の面は幅 21mm の橋になる（サポートなし）")
    save(socket().translate([XF, 0, CH_Z]), "core_socket.stl", "core", "吹き口の受け（コアの前に貼る）", (0, -90), "つばを下にして刷る")
    save(adapter().translate([XF + 2, 0, CH_Z]), "adapter.stl", "core", "吹き口アダプター（簡易）", (0, -90), "つばの側を下にして刷る")
    for i, (x, y) in enumerate(BTN):
        if i == 0: save(plunger().translate([x, y, BTN_TOP]), "plunger.stl", "core", "ボタンの押し棒（3本刷る）", note="つばを下にして刷る。3本")
    save(dial(), "core_dial.stl", "core", "空気口の円盤（回して重さを変える）", (180, 0), "上の面を下にして刷る。M2 タッピングねじ 6mm ＋ ワッシャーで留める")
    save(plunger(MC + WALL).translate([BTN[0][0], BTN[0][1], BTN_TOP]), "plunger_long.stl", "match", "ボタンの押し棒・長い（案17用、3本）", note="つばを下にして刷る。3本")
    save(necklace_back(back), "necklace_back.stl", "necklace", "案7 下の殻（ひもの輪つき）", note="底を下にして刷る。上の殻は core_front")
    fb, cxy = idcase_frame_back()
    save(fb, "idcase_frame_back.stl", "idcase", "案15 カードの枠（裏）＋コアを貼る板", note="板を下にして刷る")
    save(idcase_frame_front(cxy), "idcase_frame_front.stl", "idcase", "案15 カードの枠（表の窓）", note="平らに刷る")
    sleeve, tray, place, MH = match_parts()
    save(sleeve, "match_sleeve.stl", "match", "案17 外箱（コアと内箱が入る）", (0, 90), "吹き口の側の壁を下にして、立てて刷る")
    save(tray, "match_tray.stl", "match", "案17 内箱（2列）", note="底を下にして刷る")
    save(match_store_sleeve()[0], "match_store_sleeve.stl", "match", "案17 しまう箱（コアと内箱を入れる。11/09）", (0, 90), "前の壁を下にして、立てて刷る")
    save(pen_clip().translate([60, 0, -13 - 2.2]), "pen_clip.stl", "pen", "案3 クリップ（案1の筒にはめる）", note="アームを下にして、サポートなしで刷る")
    for fn, name, label in [(stand_plain, "stand_plain.stl", "案5 スタンド（そのまま）"), (stand_volcano, "stand_volcano.stl", "案5-A 火山"),
                            (stand_rocket, "stand_rocket.stl", "案5-C ロケット発射台"), (stand_sword, "stand_sword.stl", "案5-D 岩に刺さった剣"),
                            (stand_sprout, "stand_sprout.stl", "案5-E 植木鉢の芽")]:
        m, H = fn(); save(m, name, "stand", label, note=f"底を下にして刷る（高さ {H:g}、本体が 10.5 刺さる）")
    save(rocket_tower().translate(list(TOWER_XY) + [4]), "stand_rocket_tower.stl", "stand", "案5-C 発射塔（別に刷って差す）", (90, 0), "寝かせて刷る")
    save(sprout_leaf().translate([17, 8, 40]), "stand_sprout_leaf.stl", "stand", "案5-E 葉っぱ（別に刷って差す）", note="平らに刷る")
    json.dump(dict(report=REPORT, match=dict(H=MH)), open(HERE / "report.json", "w"), ensure_ascii=False, indent=1)
