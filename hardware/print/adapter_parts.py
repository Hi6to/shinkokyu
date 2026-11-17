"""
洗って何度も使える吹き口アダプター（shapes.html の ②〜⑥）
- ② ストロー側：ストローを通し、前のねじに ⑤ をしめると ⑥ が締まってストローをつかむ。後ろに突起2つ
- ③ フィルター（買う）：ステンレス金網 φ12 ＋ 洗えるウレタン φ12 × 厚さ 2〜3
- ④ 本体側：本体の穴 φ10.2 に差す。カップの壁に L 字の溝。② を押して 55° 回すとカチッ（③ のスポンジがばねになる）
- ⑤ しめる帽子：内側にねじ。中の ⑥ を坂に押しこむ（電線を通す「ケーブルグランド」と同じ考え方）
- ⑥ やわらかい筒（TPU）：外が円すい
座標：Z が息の通る向き。④ の床の上の面が Z=0（② の後ろの面は Z=FILTER_GAP）
STRAW_OD を手持ちのストローの外径に変えて作り直す（11/08 に測って 6.0）

ABS だけで作る版（11/07、UltiMaker S3 で ABS グレーしか使えないため）：
- ⑥ を TPU のやわらかい筒から、ABS の「割れ目入りのつかみ（コレット）」に変える（collet6_abs）。
  ケーブルグランドの硬いつかみと同じで、⑤ をしめると、4本の指が坂に押されて内側に閉じ、ストローをつかむ
- 指を FFF で刷れる太さ（0.9mm 以上）にするため、② の坂を少し太くする（part2(abs_=True)）。ねじまでの壁は 1.4mm 残る
"""
import math
from manifold3d import Manifold, CrossSection

STRAW_OD = 6.0               # 11/08 実物を測った（外径ちょうど 6mm）。前は仮に 8.0 で、すき間ができてつかめなかった
FILTER_GAP = 2.0            # ③ をはさむすき間（金網 0.3 ＋ スポンジを押しつぶした分）
SEG = 96

def rotz(m, deg):
    """Z のまわりに deg 度回す。manifold3d 3.5.4（Windows）の rotate は形をくずすため、行列で回す（11/07）"""
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return m.transform([[c, -s_, 0, 0], [s_, c, 0, 0], [0, 0, 1, 0]])

def cyl(r, z0, z1, r1=None, seg=SEG):
    return Manifold.cylinder(z1 - z0, r, r if r1 is None else r1, seg).translate([0, 0, z0])

def thread(r, ecc, z0, z1, pitch=3.0):
    """丸いねじ山：中心をずらした円をねじりながら押し出す（山の高さ＝ecc×2）"""
    cs = CrossSection.circle(r, SEG).translate([ecc, 0])
    h = z1 - z0
    return cs.extrude(h, n_divisions=int(h / pitch * 36), twist_degrees=-360.0 * h / pitch).translate([0, 0, z0])

S = STRAW_OD / 2
# ② の各部の高さ（② の後ろの面が 0）
L_LUG = (1.0, 3.0)          # 突起の高さ
L_FL = (4.0, 5.0)           # つば
L_TH = (7.5, 14.0)          # ねじ（つばの前は 45° の坂で、ねじにつながる）
BODY_R, LUG_R, LUG_W = 7.8, 9.2, 3.0
TH_R, TH_E = 7.4, 0.6       # ねじ：外の半径 8.0、山の高さ 1.2、ピッチ 3（左ねじ：ストロー側から見て反時計回りで締まる。
                            #   ② のカチッも反時計回りなので、⑤ を締めるとき ② がゆるむ向きに回らない）

# ⑥ が入る円すいの坂（11/08 見直し：前は片側 9° で、⑤ を締めても ⑥ が約 0.1mm しか閉じなかった）
SEAT = (9.0, 14.0)          # 坂の高さ（② の中）
SEAT_K = 0.25               # 坂の傾き（高さ 1mm で半径 0.25 広がる。片側 約14°）
SEAT_R0 = S + 0.65          # 坂の下のはしの半径
def seat_r(z):
    return SEAT_R0 + SEAT_K * (z - SEAT[0])
TRAVEL = 1.5                # ⑤ で ⑥ を押しこめる量 → 半径で 1.5 × 0.25 ＝ 約 0.37mm 閉じる
C_BOT = SEAT[0] + 1.5       # ⑥ を入れただけのとき、⑥ の下のはし（坂の途中で止まる。下に 1.5 の余り）
C_TOP = SEAT[1] + 1.5       # ⑥ の円すいの上のはし＝つばの下（② の上の面から 1.5 浮く）
C_FL_H = 1.5                # ⑥ のつばの高さ
C_FL_R = S + 2.2            # ⑥ のつばの半径
C_CLR = 0.03                # ⑥ の外と坂のすき間（刷った面のでこぼこ分）
C_ID = S + 0.05             # ⑥ の穴（ストローより片側 0.05 だけ大きい：すっと通り、締めると食いこむ）

def part2(abs_=False):
    """② ストロー側（ABS 版も同じ形。11/08 から ⑥ の坂を1つにそろえた）"""
    m = cyl(BODY_R, 0, L_FL[0])
    m += cyl(10.5, L_FL[0], L_FL[1])
    m += cyl(10.5, L_FL[1], L_TH[0], 8.0)                         # 45° の坂（つばの前を、張り出しなしで刷る）
    m += cyl(TH_R - 0.1, L_TH[0] - 0.5, L_TH[1])
    m += thread(TH_R, TH_E, L_TH[0], L_TH[1]) ^ cyl(TH_R + TH_E, L_TH[0], L_TH[1])
    for a in (0, 180):                                             # 突起 2つ
        lug = Manifold.cube([LUG_R - BODY_R + 0.5, LUG_W, L_LUG[1] - L_LUG[0]]).translate([BODY_R - 0.5, -LUG_W / 2, L_LUG[0]])
        m += rotz(lug, a)
    # 中の通り道
    m -= cyl(4.5, -1, 1.2)                                         # ③ の上の空気の部屋
    m -= cyl(min(3.0, S - 0.6), 1.0, 2.6)                          # ストローの止まり（段。ストローより細く）
    m -= cyl(S + 0.2, 2.4, SEAT[0] + 0.01)                         # ストローを通す穴
    m -= cyl(seat_r(SEAT[0]), SEAT[0], SEAT[1] + 0.01, seat_r(SEAT[1]))   # ⑥ の坂
    m -= cyl(seat_r(SEAT[1]), SEAT[1], SEAT[1] + 5)
    # 目印：つばの下の面の小さな刻み（突起の向き）
    m -= Manifold.cube([1.5, 0.8, 0.6]).translate([8.6, -0.4, L_FL[0] - 0.3])
    return m

def collet6_abs():
    """⑥ つかみ（ABS・PETG）：割れ目 6本の指。外は ② の坂と同じ傾きの円すい、上につば
    組み立ての位置（⑥ を入れただけ）：下のはし C_BOT が坂にのる。⑤ が上から TRAVEL 押すと、指が坂で閉じてストローをつかむ"""
    m = cyl(seat_r(C_BOT) - C_CLR, C_BOT, C_TOP, seat_r(C_TOP) - C_CLR) + cyl(C_FL_R, C_TOP, C_TOP + C_FL_H)
    m -= cyl(C_ID, C_BOT - 1, C_TOP + C_FL_H + 1)
    m -= cyl(C_ID + 0.3, C_TOP + C_FL_H - 0.3, C_TOP + C_FL_H + 1, C_ID)  # 入り口の面取り（ストローを通しやすく）
    for a in (0, 60, 120):                                         # 割れ目 6本（幅 0.8、下のはしから 4.2。つばの輪は残す）
        m -= rotz(Manifold.cube([0.8, 2 * (S + 3), 4.2]).translate([-0.4, -(S + 3), C_BOT - 0.01]), a)
    return m

def sleeve6():
    """⑥ やわらかい筒（TPU）：② の坂にぴったり入り、⑤ で上から押すと縮んでストローをつかむ"""
    m = cyl(seat_r(SEAT[0]) - 0.05, SEAT[0], SEAT[1], seat_r(SEAT[1]) - 0.05) + cyl(seat_r(SEAT[1]) - 0.05, SEAT[1], C_TOP + C_FL_H - 0.5)
    m -= cyl(S - 0.05, SEAT[0] - 1, C_TOP + C_FL_H + 1)            # ストローより 0.1 細い（軽くつかむ）
    return m

CAP_IN_H = 7.5              # ⑤ の内側の高さ（下のはしから天井まで）
def cap5():
    """⑤ しめる帽子。組み立ての位置は「いちばん締めたとき」：天井の下＝C_TOP + C_FL_H − TRAVEL"""
    ceil = C_TOP + C_FL_H - TRAVEL                                 # 15.5
    z0, z1 = ceil - CAP_IN_H, ceil + 1.6                           # 下のはし 8.0、上 17.1
    m = cyl(9.0, z0, z1)
    m -= thread(TH_R + 0.3, TH_E, z0 - 0.5, ceil) ^ cyl(TH_R + TH_E + 0.3, z0 - 0.5, ceil)   # 内側のねじ（すき間 0.3）
    m -= cyl(TH_R + 0.25, z0 - 0.5, ceil)                          # ねじの谷の内側も空ける
    m -= cyl(TH_R + TH_E + 0.35, z0 - 1, z0 + 0.6, TH_R + TH_E + 0.05)  # 入り口の面取り
    m -= cyl(S + 0.4, ceil - 1, z1 + 1)                            # ストローを通す
    for k in range(18):                                            # 外のギザギザ
        a = 2 * math.pi * k / 18
        m -= cyl(0.6, z0 - 1, z1 + 1, seg=12).translate([9.25 * math.cos(a), 9.25 * math.sin(a), 0])
    return m

# ④（④ の床の上の面が 0。下に差し込み、上にカップ）
CUP_R_IN, CUP_R_OUT = 8.0, 10.5
RIM = FILTER_GAP + L_FL[0] + 1.6         # ② のつばがカップのふちにのる高さ（ここでは 1.6 だけ浮かせない：下で計算）
def part4():
    rim = FILTER_GAP + L_FL[0]             # ② のつばの下の面＝カップのふち
    m = cyl(CUP_R_OUT, -1.6, rim)
    m += cyl(5.0, -7.6, -1.6)                                      # 差し込み φ10 × 6
    m -= cyl(CUP_R_IN, 0, rim + 1)                                 # カップの中
    m -= cyl(6.2, -0.4, 0.01)                                      # ③ を置くくぼみ φ12.4 × 0.4
    m -= cyl(4.5, -1.7, 0.01)                                      # 息の穴
    m -= cyl(3.5, -8, -1.6)
    m -= cyl(5.5, -4.2, -3.0) - cyl(4.3, -5, -2)                   # O リングの溝（内径 8 × 太さ 1 用。なくても使える）
    # L 字の溝（2本）：ふちから下へ → 横に 55°。壁の外側 1mm は残す（外から見えない）
    lug_lo = FILTER_GAP + L_LUG[0] - 0.25
    lug_hi = FILTER_GAP + L_LUG[1] + 0.25
    def wedge(a0, a1, z0, z1, r0=CUP_R_IN - 0.5, r1=LUG_R + 0.3):
        pts = []
        for a in (a0, a1):
            t = math.radians(a)
            for r in (r0, r1):
                pts += [(r * math.cos(t), r * math.sin(t), z0), (r * math.cos(t), r * math.sin(t), z1)]
        return Manifold.hull_points(pts)
    half = math.degrees((LUG_W / 2 + 0.3) / CUP_R_IN)
    for base in (0, 180):
        m -= wedge(base - half, base + half, lug_lo, rim + 1)                      # 縦の溝
        for k in range(11):                                                         # 横の溝（細かく分けて円弧に沿わせる）
            m -= wedge(base - half + 5.5 * k, base + half + 5.5 * (k + 1), lug_lo, lug_hi)
        # カチッ：横の溝の天井に小さな山（40°）。乗り越えるとき ③ のスポンジが縮む
        t = math.radians(base + 40)
        bump = Manifold.cube([LUG_R + 0.3 - (CUP_R_IN - 0.05), 1.2, 0.35], center=False).translate([CUP_R_IN - 0.05, -0.6, lug_hi - 0.35])   # 11/08：山がカップの内側へ 0.5 出て、② の胴に当たっていた
        m += rotz(bump, base + 40) ^ cyl(LUG_R + 0.3, -2, rim)
    # 目印：外の面に小さなくぼみ（縦の溝の向き）
    m -= Manifold.cube([0.8, 1.2, 3]).translate([CUP_R_OUT - 0.4, -0.6, rim - 3])
    return m

def assembled(abs_=False, tight=False):
    """組み立てた位置（④ の座標）。tight=True で ⑤ をいちばん締めた位置（⑥ は TRAVEL 下がる。指が閉じる分は形に入れていない）"""
    up = FILTER_GAP
    six = collet6_abs() if abs_ else sleeve6()
    cap = cap5()
    if not tight:
        cap = cap.translate([0, 0, TRAVEL])
    elif abs_:
        six = six.translate([0, 0, -TRAVEL])
    return dict(part4=part4(), part2=part2(abs_).translate([0, 0, up]),
                sleeve6=six.translate([0, 0, up]), cap5=cap.translate([0, 0, up]))

def check(verbose=True):
    """形を確かめる（11/08）"""
    rep = []
    for n, f in [("②", part2), ("④", part4), ("⑤", cap5), ("⑥ ABS", collet6_abs), ("⑥ TPU", sleeve6)]:
        k = len(f().decompose()); rep.append(f"{n}：{k} 個の形"); assert k == 1, n
    straw = cyl(S, 2.6, 40)
    c = collet6_abs()
    rep.append(f"⑥ に通したストローのかさなり {(straw ^ c).volume():.3f} mm3（0 ならすっと通る）"); assert (straw ^ c).volume() < 1e-3
    rep.append(f"⑥（入れただけ）と ② のかさなり {(c ^ part2()).volume():.3f} mm3"); assert (c ^ part2()).volume() < 0.05
    low = c.translate([0, 0, -TRAVEL])
    rep.append(f"⑥ を {TRAVEL}mm 押しこんだ所まで下がれるか：② とのかさなり {(low ^ part2()).volume():.2f} mm3（坂に食いこむ分＝指が閉じる分）")
    close = SEAT_K * TRAVEL - (C_ID - S) - C_CLR
    rep.append(f"締めたとき、指がストローに食いこむ量：半径で約 {close:.2f} mm（坂 {SEAT_K} × {TRAVEL} − すき間 {C_ID - S:.2f} − {C_CLR}）"); assert close > 0.25
    gap = 2 * math.pi * C_ID - 6 * 0.8
    rep.append(f"指が閉じられる余り：割れ目 6本 × 0.8 ＝ 4.8mm（半径で {6 * 0.8 / (2 * math.pi):.2f} mm まで閉じられる）"); assert 6 * 0.8 / (2 * math.pi) > close
    # ⑤ を締めたとき：② と ⑤ のねじがかみ合う向きに回せばぶつからないか、⑤ の天井が ⑥ のつばに当たるか
    p2 = part2()
    best = min(((p2 ^ rotz(cap5(), a)).volume(), a) for a in range(0, 360, 5))
    rep.append(f"いちばん締めたときの ② と ⑤ のかさなり {best[0]:.2f} mm3（⑤ を {best[1]}° 回した向き）"); assert best[0] < 0.5
    ceil = C_TOP + C_FL_H - TRAVEL
    rep.append(f"⑤ の天井 {ceil:.1f}／⑥ のつばの上（入れただけ）{C_TOP + C_FL_H:.1f}／② の上の面 {L_TH[1]:.1f}：⑥ のつばは ② に当たる前に {C_TOP - L_TH[1]:.1f}mm 下がれる")
    assert C_TOP - L_TH[1] >= TRAVEL - 1e-6
    rep.append(f"⑤ の下のはし（締めたとき）{ceil - CAP_IN_H:.1f}：② のつばの坂（半径 9 の所は高さ {L_FL[1] + (10.5 - 9.0):.1f}）より上")
    assert ceil - CAP_IN_H > L_FL[1] + (10.5 - 9.0)
    rep.append(f"⑥ に当たる前に ⑤ が ② のねじにかかる長さ：{L_TH[1] - (ceil + TRAVEL - CAP_IN_H):.1f} mm（ピッチ 3 で約 {(L_TH[1] - (ceil + TRAVEL - CAP_IN_H)) / 3:.1f} 回り）")
    if verbose:
        print("\n".join(rep))
    return rep

if __name__ == "__main__":
    check()
