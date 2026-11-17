"""
案1 の「ペットボトル形」（11/08）：本体 → 丸い肩 → 首 → キャップ、の自然な形にした版。今の案1（body_parts.py・adapter_parts.py）は残す。

今の形との違い
- ④（本体側の部品）をなくし、前の部屋 C の先そのものを「カップ」（L 字の溝・フィルターの座）にした。
  ④ の細い差しこみを本体の穴に押しこむ所がなくなる（すき間・もれ・ずれがなくなる）
- ② は「肩」になる：下は C と同じ太さ（φ26）で、丸く細くなって首（ねじ）につながる。
  肩をつかんで 55° 回すと「カチッ」（今と同じ L 字の溝。フィルターのスポンジがばね）
- ⑤ はペットボトルのキャップの形（φ20.6、たてのみぞ）。ねじは中に隠れる。ストローは真ん中から出る
- ⑥（ストローをつかむ割れた筒）・フィルター・ストロー（φ6）のつかみ方は、11/08 に直した形と同じ
- 殻 A・B、リング E、キャップ F、USB のふた G、押し棒は今のものをそのまま使う

座標：C は組み立ての座標（X＝筒の軸、body_parts.py と同じ）。②⑤⑥ は Z の軸で、② の後ろの面が 0（adapter_parts.py と同じ決め方）。
カップの座標（cup）：カップの床の上の面が 0。② の後ろの面は FILTER_GAP の高さ。

check() で確かめる：部品が1つにつながっているか／組み立てたときにぶつからないか／ストローが通り、締めると食いこむか／⑤ が締まるか
"""
import math
import numpy as np
from manifold3d import Manifold, CrossSection
import body_parts as BP
import make_enclosure as E
import adapter_parts as AP
from adapter_parts import cyl, thread, rotz, S, FILTER_GAP, SEAT_K, TRAVEL, C_FL_H, C_FL_R, C_ID, C_CLR, TH_R, TH_E, CAP_IN_H

ZC, R_OUT, R_IN = BP.ZC, BP.R_OUT, BP.R_IN

# ---------------- ② 肩（Z の軸。後ろの面が 0） ----------------
L_LUG = (1.0, 3.0)          # 突起の高さ（今と同じ）
BODY_R, LUG_R, LUG_W = 7.8, 9.2, 3.0
SK = 5.0                    # 肩のすその下の面（ここから下がカップに入る）
SH_TOP, SH_R1 = 11.0, 10.0  # 肩：半径 13 → 10（高さ 6。下は縦、上は 45°。下向きに刷っても張り出しが 45° をこえない）
NECK_TOP = 13.0             # 首：半径 10 → 8（45°）
L_TH = (13.0, 19.5)         # ねじ（今の形から 5.5 上へ）
DZ = L_TH[0] - AP.L_TH[0]   # 今の形との高さのずれ（5.5）
SEAT = (AP.SEAT[0] + DZ, AP.SEAT[1] + DZ)
def seat_r(z):
    return AP.SEAT_R0 + SEAT_K * (z - SEAT[0])
C_BOT, C_TOP = AP.C_BOT + DZ, AP.C_TOP + DZ
CAP_R = 10.3                # ⑤ の外の半径（φ20.6）

def shoulder_profile(n=24):
    pts = []
    for i in range(n + 1):
        s = i / n
        pts.append((R_OUT - (R_OUT - SH_R1) * s * s, SK + (SH_TOP - SK) * s))
    return pts

def part2():
    """② 肩（ストロー側）"""
    prof = [(0, 0), (BODY_R, 0), (BODY_R, SK)] + shoulder_profile() + [(8.0, NECK_TOP), (TH_R - 0.1, NECK_TOP), (TH_R - 0.1, L_TH[1]), (0, L_TH[1])]
    # 外の角：すその外のふちを 0.4 だけ面取り（C との境目をやわらかく）
    prof[2:4] = [(BODY_R, SK), (R_OUT - 0.4, SK), (R_OUT, SK + 0.4)]
    m = Manifold.revolve(CrossSection([prof]), 160)
    m += thread(TH_R, TH_E, L_TH[0], L_TH[1]) ^ cyl(TH_R + TH_E, L_TH[0], L_TH[1])
    for a in (0, 180):                                             # 突起 2つ（今と同じ）
        lug = Manifold.cube([LUG_R - BODY_R + 0.5, LUG_W, L_LUG[1] - L_LUG[0]]).translate([BODY_R - 0.5, -LUG_W / 2, L_LUG[0]])
        m += rotz(lug, a)
    # 中の通り道（今と同じ並び）
    m -= cyl(4.5, -1, 1.2)                                         # フィルターの上の空気の部屋
    m -= cyl(min(3.0, S - 0.6), 1.0, 2.6)                          # ストローの止まり（段）
    m -= cyl(S + 0.2, 2.4, SEAT[0] + 0.01)                         # ストローを通す穴
    m -= cyl(seat_r(SEAT[0]), SEAT[0], SEAT[1] + 0.01, seat_r(SEAT[1]))   # ⑥ の坂
    m -= cyl(seat_r(SEAT[1]), SEAT[1], SEAT[1] + 5)
    # 目印：肩のすそに、突起の向きの縦のみぞ（C の先の目印と合わせて差す）
    m -= Manifold.cube([0.8, 0.8, 2.2]).translate([R_OUT - 0.5, -0.4, SK - 0.1])
    return m

def collet6():
    """⑥ つかみ（11/08 に直した形を、首の高さへ）"""
    return AP.collet6_abs().translate([0, 0, DZ])

def sleeve6():
    return AP.sleeve6().translate([0, 0, DZ])

def cap5():
    """⑤ キャップ（ペットボトルのキャップの形）。組み立ての位置は「いちばん締めたとき」"""
    ceil = C_TOP + C_FL_H - TRAVEL
    z0, z1 = ceil - CAP_IN_H, ceil + 1.6
    prof = [(0, z0), (CAP_R - 0.3, z0), (CAP_R, z0 + 0.3), (CAP_R, z1 - 0.7), (CAP_R - 0.7, z1), (0, z1)]
    m = Manifold.revolve(CrossSection([prof]), 160)
    m -= thread(TH_R + 0.3, TH_E, z0 - 0.5, ceil) ^ cyl(TH_R + TH_E + 0.3, z0 - 0.5, ceil)   # 内側のねじ
    m -= cyl(TH_R + 0.25, z0 - 0.5, ceil)
    m -= cyl(TH_R + TH_E + 0.35, z0 - 1, z0 + 0.6, TH_R + TH_E + 0.05)  # 入り口の面取り
    m -= cyl(S + 0.4, ceil - 1, z1 + 1)                            # ストローを通す
    for k in range(30):                                            # たてのみぞ（ペットボトルのキャップ）
        a = 2 * math.pi * k / 30
        m -= cyl(0.4, z0 + 0.8, z1 - 1.0, seg=12).translate([(CAP_R + 0.12) * math.cos(a), (CAP_R + 0.12) * math.sin(a), 0])
    return m

# ---------------- C 前の部屋（先がカップ） ----------------
X_CUP = 78.0                # カップの床の上の面（組み立ての X）
RIM = FILTER_GAP + SK - 0.5 # カップのふち＝C の先の面（カップの座標）。② の肩のすそとの間は 0.5
X_FACE = X_CUP + RIM        # 84.5
ROOF = (X_CUP - 1.6 - 7.0, X_CUP - 1.6)   # 息の部屋の天井（45° で半径 11.5 → 4.5）

def cup_to_x(m):
    """カップの座標（Z の軸）→ 組み立ての座標（X の軸）"""
    return m.transform([[0, 0, 1, X_CUP], [1, 0, 0, 0], [0, 1, 0, ZC]])

def cup_cut():
    """カップの中・L 字の溝（カップの座標）。今の ④ と同じ溝・山"""
    cut = cyl(AP.CUP_R_IN, 0, RIM + 1)
    cut += cyl(6.2, -0.4, 0.01)                                     # フィルターの座 φ12.4 × 0.4
    cut += cyl(4.5, -1.7, 0.01)                                     # 息の穴
    lug_lo = FILTER_GAP + L_LUG[0] - 0.25
    lug_hi = FILTER_GAP + L_LUG[1] + 0.25
    def wedge(a0, a1, z0, z1, r0=AP.CUP_R_IN - 0.5, r1=LUG_R + 0.3):
        pts = []
        for a in (a0, a1):
            t = math.radians(a)
            for r in (r0, r1):
                pts += [(r * math.cos(t), r * math.sin(t), z0), (r * math.cos(t), r * math.sin(t), z1)]
        return Manifold.hull_points(pts)
    half = math.degrees((LUG_W / 2 + 0.3) / AP.CUP_R_IN)
    bumps = Manifold()
    for base in (0, 180):
        cut += wedge(base - half, base + half, lug_lo, RIM + 1)                   # 縦の溝
        for k in range(11):                                                        # 横の溝 55°
            cut += wedge(base - half + 5.5 * k, base + half + 5.5 * (k + 1), lug_lo, lug_hi)
        bump = Manifold.cube([LUG_R + 0.3 - (AP.CUP_R_IN - 0.05), 1.2, 0.35]).translate([AP.CUP_R_IN - 0.05, -0.6, lug_hi - 0.35])   # 山はカップの壁より外だけ（② の胴 φ15.6 に当てない）
        bumps += rotz(bump, base + 40) ^ cyl(LUG_R + 0.3, -2, RIM)
    return cut, bumps, lug_hi

def front_chamber(abs_=False):
    C_FL, C_NECK = BP.C_FL, BP.C_NECK
    m = BP.cyl_ax(11.95, 11.95, *C_FL)
    m += BP.cyl_ax(11.3, 11.3, *C_NECK)
    if abs_:
        ch = BP.JOINT_CH
        m += BP.cyl_ax(R_OUT - ch, R_OUT, C_NECK[1], C_NECK[1] + ch) + BP.cyl_ax(R_OUT, R_OUT, C_NECK[1] + ch, X_FACE - 0.4)
    else:
        m += BP.cyl_ax(R_OUT, R_OUT, C_NECK[1], X_FACE - 0.4)
    m += BP.cyl_ax(R_OUT, R_OUT - 0.4, X_FACE - 0.4, X_FACE)                  # 先の外のふちを 0.4 面取り
    m += BP.cyl_ax(13.8, 13.8, BP.LIP[0], BP.LIP[0] + 0.7) + BP.cyl_ax(13.8, R_OUT, BP.LIP[0] + 0.7, BP.LIP[1])
    # 中（息の部屋）
    m -= BP.cyl_ax(10.4, 10.4, C_FL[1], C_NECK[1] + 0.01)
    m -= BP.cyl_ax(10.4, R_IN, C_NECK[1], C_NECK[1] + 1.1 + 0.01)
    m -= BP.cyl_ax(R_IN, R_IN, C_NECK[1] + 1.1, ROOF[0] + 0.01)
    m -= BP.cyl_ax(R_IN, 4.5, ROOF[0], ROOF[1] + 0.01)                        # 天井（45°）
    cut, bumps, _ = cup_cut()
    m -= cup_to_x(cut)
    m += cup_to_x(bumps)
    # 基板のタブを通す穴・通り道の穴（今と同じ）
    m -= E.box(C_FL[0] - 1, C_FL[1] + 1, -6.3, 6.3, -0.3, 1.1)
    m -= E.cyl_x(0.3, C_FL[0] - 1, C_FL[1] + 1, 0, ZC - 6.0)
    if abs_:
        m -= BP.cyl_ax(0.3, 0.7, C_FL[1] - 0.4, C_FL[1] + 0.01, 32, ZC - 6.0)
    # 三角の窓・カチッの浅い溝（今と同じ）
    n = 40
    for i in range(n):
        a0, a1 = BP.WIN_SPAN * i / n, BP.WIN_SPAN * (i + 1) / n
        w = BP.WIN_W * (1 - (a0 + a1) / 2 / BP.WIN_SPAN)
        if w < 0.15: break
        pts = []
        for a in (a0 - 0.3, a1 + 0.3):
            t = math.radians(a)
            for r in (R_IN - 0.5, R_OUT + 0.5):
                for x in (BP.WIN_X - w / 2, BP.WIN_X + w / 2):
                    pts.append((x, r * math.sin(t), ZC + r * math.cos(t)))
        m -= Manifold.hull_points(pts)
    for k in range(8):
        t = math.radians(BP.WIN_SPAN * k / 7 + 180)
        pts = []
        for x in (BP.RING[0] + 1.2, BP.RING[1] - 1.2):
            for dt in (-1.6, 1.6):
                tt = t + math.radians(dt)
                for r in (R_OUT - 0.4, R_OUT + 0.5):
                    pts.append((x, r * math.sin(tt), ZC + r * math.cos(tt)))
        m -= Manifold.hull_points(pts)
    # 目印：先の外の面に、縦の溝の入り口の向きの短いみぞ（② の肩の目印と合わせる）
    m -= cup_to_x(Manifold.cube([0.8, 0.8, 2.2]).translate([R_OUT - 0.5, -0.4, RIM - 2.1]))
    return m

def assembled(locked=True, tight=True, abs_=True):
    """組み立ての座標（X の軸）。locked：② を 55° 回して止めた位置。tight：⑤ をいちばん締めた位置"""
    up = FILTER_GAP
    two = part2()
    six = collet6() if abs_ else sleeve6()
    cap = cap5()
    if not tight:
        cap = cap.translate([0, 0, TRAVEL])
    elif abs_:
        six = six.translate([0, 0, -TRAVEL])
    rot = 55 if locked else 0
    parts = dict(two=rotz(two, rot), six=rotz(six, rot), cap=rotz(cap, rot))   # ⑤ は ② のねじに合う向き（同じ回し方）
    return {k: cup_to_x(v.translate([0, 0, up])) for k, v in parts.items()}

def check(verbose=True):
    rep = []
    C = front_chamber(); Cabs = front_chamber(True)
    for n, m in [("C", C), ("C（ABS）", Cabs), ("② 肩", part2()), ("⑤ キャップ", cap5()), ("⑥ つかみ", collet6()), ("⑥ TPU", sleeve6())]:
        k = len(m.decompose()); rep.append(f"{n}：{k} 個の形"); assert k == 1, n
    # 組み立て：② を止めた位置で C とぶつからない
    for locked in (False, True):
        a = assembled(locked=locked, tight=False)
        v = (a["two"] ^ C).volume()
        rep.append(f"② と C のかさなり（{'55° 回して止めた' if locked else '差しただけ'}）{v:.3f} mm3"); assert v < 0.05
    # ② を押しこんで「カチッ」を越える所（突起が山の下）まで下げても、肩のすそが C の先の面に当たらない
    _, _, lug_hi = cup_cut()
    push = (FILTER_GAP + L_LUG[1]) - (lug_hi - 0.35 - 0.05)        # 突起の上が山の下をくぐるまで
    skirt = FILTER_GAP + SK - max(push, 0.25)
    rep.append(f"押しこんだときの肩のすそ {skirt:.2f} ／ C の先の面 {RIM:.2f}（カップの座標）"); assert skirt > RIM
    rep.append(f"止めた溝の上の C の厚さ（溝の天井〜先の面）{RIM - lug_hi:.2f} mm"); assert RIM - lug_hi >= 1.0
    # ⑤ を締めたとき
    t = assembled(tight=True)
    v = (t["cap"] ^ t["two"]).volume(); rep.append(f"いちばん締めた ⑤ と ② のかさなり {v:.3f} mm3"); assert v < 0.5
    v = (t["cap"] ^ C).volume(); rep.append(f"⑤ と C のかさなり {v:.3f} mm3"); assert v < 1e-3
    # ストロー
    straw = cup_to_x(cyl(S, FILTER_GAP + 2.6, 60))
    r = assembled(tight=False)
    v = (straw ^ (r["two"] + r["six"] + r["cap"])).volume(); rep.append(f"ストロー φ{2 * S:.0f} と ②⑤⑥（ゆるめた）のかさなり {v:.3f} mm3"); assert v < 1e-3
    close = SEAT_K * TRAVEL - (C_ID - S) - C_CLR
    rep.append(f"締めたときの食いこみ：半径で約 {close:.2f} mm")
    # 本体のほかの部品とぶつからない
    for n, m in [("A", BP.upper_shell()), ("B", E.lower_shell()), ("E", BP.ring_E().transform([[0, 0, 1, BP.RING[0]], [1, 0, 0, 0], [0, 1, 0, ZC]]))]:
        v = (m ^ C).volume(); rep.append(f"C と {n} のかさなり {v:.3f} mm3"); assert v < 0.01
    bb = t["cap"].bounding_box()
    rep.append(f"全長（後ろのキャップ F の端 {E.X_REAR - 2:.1f} 〜 ⑤ の上 {bb[3]:.1f}）約 {bb[3] - (E.X_REAR - 2):.0f} mm")
    if verbose:
        print("\n".join(rep))
    return rep

if __name__ == "__main__":
    check()
