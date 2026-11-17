"""本体の筒（3D プリンター用）の形を作る。docs/ENCLOSURE.md のたたき台をもとにする

使い方：<形を作る Python> make_enclosure.py
- 出力：stl/ の中に部品ごとの STL
- 必要なもの：manifold3d・trimesh・numpy（hardware/enclosure/README.md）

座標（mm）：
- X：筒の軸。基板の後ろの端（USB-C の側）が 0、前（気圧センサーのタブ）が +
- Y：横。基板の真ん中が 0
- Z：上下。基板の裏の面が 0、部品の付いた表が +0.8
"""

import math
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold

OUT = Path(__file__).parent / "stl"

# ---------- 寸法 ----------
R_OUT = 13.0          # 筒の外の半径（外径 26）
R_IN = 11.5           # 筒の内の半径（内径 23）
ZC = 0.4              # 筒の軸の高さ（基板の厚さの真ん中）
BOTTOM_DEPTH = 11.8   # 下の殻の内側の一番深い所（軸から）。底は 45° の屋根の形にして、支えなしで刷れるようにする

BOARD_T = 0.8         # 基板の厚さ
BOARD_W = 20.5        # 基板の幅
BOARD_MAIN_L = 55.3   # 基板の本体の長さ（首とタブを除く）
Z_SPLIT = BOARD_T + 0.1   # 上と下の殻の合わせ面（基板の表 +0.1）
SLOT_HALF = BOARD_W / 2 + 0.2   # 基板を置く溝の幅の半分（すき間 0.2）
LEDGE_INNER = 9.85    # 基板の裏を支える棚の内側のはし（基板のふち 10.25 から 0.4 だけ下に入る）
LEDGE_DEPTH = 1.2     # 棚の厚さ

X_REAR = -3.5         # 下の殻の後ろの端（後ろのキャップ F が差さる分 3mm＋すき間 0.5）
GROOVE_X = (56.1, 58.3)   # 前の部屋（C）の仕切りのつばが入る溝。基板の首（55.3〜59.3）の上
GROOVE_R = 12.1
X_FRONT = 60.3        # 下の殻の前の端（溝の前に 2mm のふち）

SPK_X = 38.8          # スピーカー（φ20）の中心。基板の下、アンプのあたり
SPK_R = 10.0
RIB_T = 1.0           # スピーカーが前後にずれないようにする、壁ぞいの輪の厚さ
RIB_R_IN = 10.2
RIB_Z_TOP = -1.5
GRILLE_D = 1.5        # スピーカーの音の穴

SEG = 128             # 円の細かさ


def profile_outer():
    pts = [(R_OUT * math.cos(t), ZC + R_OUT * math.sin(t))
           for t in np.linspace(0, 2 * math.pi, SEG, endpoint=False)]
    return pts


def profile_inner():
    """筒の内側の断面。上は円、下は 45° の屋根＋平らな橋（下の殻を、合わせ面を下にして支えなしで刷るため）"""
    a45 = math.radians(45)
    # 円の部分：下から 45° より上（角度は真下を -90° として、-45°〜225°）
    pts = [(R_IN * math.cos(t), ZC + R_IN * math.sin(t))
           for t in np.linspace(-math.pi / 2 + a45, 3 * math.pi / 2 - a45, SEG)]
    # 45° の線で下へ下り、BOTTOM_DEPTH で平らにする
    y45 = R_IN * math.sin(a45)
    z45 = ZC - R_IN * math.cos(a45)
    d = (ZC - BOTTOM_DEPTH) - z45   # 負の値
    yb = y45 + d                    # 平らな橋のはし
    pts += [(-yb, ZC - BOTTOM_DEPTH), (yb, ZC - BOTTOM_DEPTH)]
    return pts


def extrude_x(pts, x0, x1):
    """(Y, Z) の断面を、X の x0〜x1 に押し出す"""
    cs = CrossSection([pts])
    m = cs.extrude(x1 - x0)
    # (u, v, w) → (X=w, Y=u, Z=v)
    m = m.transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])
    return m


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl_x(r, x0, x1, y=0.0, z=ZC):
    m = Manifold.cylinder(x1 - x0, r, r, SEG)   # Z の向きの円柱
    m = m.transform([[0, 0, 1, x0], [1, 0, 0, y], [0, 1, 0, z]])
    return m


def cyl_z(r, z0, z1, x, y):
    return Manifold.cylinder(z1 - z0, r, r, 32).translate([x, y, z0])


def lower_shell():
    outer = extrude_x(profile_outer(), X_REAR, X_FRONT)
    inner = extrude_x(profile_inner(), X_REAR - 1, X_FRONT + 1)
    shell = outer - inner

    # 基板の溝：裏を支える棚と、横にずれないようにする壁（基板の本体の長さだけ）
    for s in (1, -1):
        lo, hi = sorted((s * LEDGE_INNER, s * 14))
        shell += box(0, BOARD_MAIN_L, lo, hi, -LEDGE_DEPTH, 0)
        lo, hi = sorted((s * SLOT_HALF, s * 14))
        shell += box(0, BOARD_MAIN_L, lo, hi, 0, Z_SPLIT)

    # スピーカーの前後の輪（壁ぞい）
    for x0 in (SPK_X - SPK_R - 0.3 - RIB_T, SPK_X + SPK_R + 0.3):
        ring = cyl_x(12.4, x0, x0 + RIB_T) - cyl_x(RIB_R_IN, x0 - 1, x0 + RIB_T + 1)
        shell += ring ^ box(x0 - 1, x0 + RIB_T + 1, -20, 20, -20, RIB_Z_TOP)

    # 外にはみ出した分を削り、合わせ面より上を落とす
    shell = shell ^ extrude_x(profile_outer(), X_REAR, X_FRONT)
    shell = shell ^ box(X_REAR - 1, X_FRONT + 1, -20, 20, -20, Z_SPLIT)

    # 前の部屋（C）の仕切りのつばが入る溝
    shell -= cyl_x(GROOVE_R, GROOVE_X[0], GROOVE_X[1])

    # スピーカーの音の穴（底の平らな所）
    for dx in (-5.6, -2.8, 0, 2.8, 5.6):
        for dy in (-2.8, 0, 2.8):
            shell -= cyl_z(GRILLE_D / 2, -20, -5, SPK_X + dx, dy)
    return shell


def test_sample():
    """試し刷り：幅の違う溝が5本ある板（30 × 14 × 5 mm）。基板の切れ端（0.8mm）を差して、溝の幅を決める

    - 溝の幅：左から 0.9・1.0・1.1・1.2・1.3 mm（深さ 3mm、横に貫通）
    - 角が1つ欠けている側が左（0.9mm）
    """
    plate = box(0, 30, 0, 14, 0, 5)
    for i, w in enumerate((0.9, 1.0, 1.1, 1.2, 1.3)):
        x = 5 + 5 * i
        plate -= box(x - w / 2, x + w / 2, -1, 15, 2, 6)
    # 向きの印：左手前の角を 45° に欠く
    cut = CrossSection([[(-1, -1), (3, -1), (-1, 3)]]).extrude(7).translate([0, 0, -1])
    plate -= cut
    return plate


def board_box():
    """試し刷り：今の基板（枠から外したもの）とスピーカーが入る、上が開いた箱

    - 基板は四角い枠に入り、両端の台にのる（基板の下 6.5mm にスピーカーとその線、あとで電池）
    - スピーカー（φ20）は基板の下に下向き。底のくぼみに置き、底の穴から音が出る
    - 後ろの壁に USB-C の切り欠き（箱に入れたまま書き込める）。上は開いていて、ボタンと気圧センサーに届く
    """
    WALL, FLOOR = 1.6, 1.6
    CLR = 0.35                    # 基板とのすき間
    UNDER = 6.5                   # 基板の下の高さ（スピーカーの厚さ＋余り）
    ABOVE = 3.0                   # 基板の表から壁の上まで
    L = 69.3                      # 基板の長さ（タブまで）
    x0, x1 = -CLR, L + CLR
    yh = BOARD_W / 2 + CLR
    zb = FLOOR + UNDER            # 基板の裏の高さ（箱の外の底から）
    ztop = zb + BOARD_T + ABOVE

    box_ = box(x0 - WALL, x1 + WALL, -yh - WALL, yh + WALL, 0, ztop)
    box_ -= box(x0, x1, -yh, yh, FLOOR, ztop + 1)

    # 基板をのせる台（スピーカーのある所は空ける）
    for xa, xb in ((x0, SPK_X - SPK_R - 1.0), (SPK_X + SPK_R + 1.0, BOARD_MAIN_L)):
        for s in (1, -1):
            lo, hi = sorted((s * 9.6, s * (yh + 0.5)))
            box_ += box(xa, xb, lo, hi, FLOOR - 0.5, zb)
    # タブ（幅 12mm）の下の台：裏の穴（J7）をよけて、両わきだけ
    for s in (1, -1):
        lo, hi = sorted((s * 5.4, s * (yh + 0.5)))
        box_ += box(BOARD_MAIN_L + 4.0, x1, lo, hi, FLOOR - 0.5, zb)

    # スピーカーを置くくぼみと、音の穴
    box_ -= Manifold.cylinder(1.0, SPK_R + 0.3, SPK_R + 0.3, SEG).translate([SPK_X, 0, FLOOR - 0.6])
    for dx, dy in [(0, 0)] + [(3.2 * math.cos(math.radians(a)), 3.2 * math.sin(math.radians(a))) for a in range(0, 360, 60)]             + [(6.2 * math.cos(math.radians(a)), 6.2 * math.sin(math.radians(a))) for a in range(0, 360, 30)]:
        box_ -= cyl_z(GRILLE_D / 2, -1, FLOOR + 1, SPK_X + dx, dy)

    # 後ろの壁の USB-C の切り欠き（ケーブルの太い所が入る幅）
    box_ -= box(x0 - WALL - 1, x0 + 0.1, -6.75, 6.75, zb - 0.2, ztop + 1)
    return box_


def to_print_pose(m):
    """合わせ面を下にして、プリンターの台に置く向きにする（X の軸まわりに 180° 回す）"""
    m = m.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, Z_SPLIT]])
    lo = np.array(m.bounding_box()[:3])
    return m.translate([-lo[0], -lo[1], -lo[2]])


def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                         faces=np.asarray(mesh.tri_verts), process=True)
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    tm.export(path)
    ext = tm.bounds[1] - tm.bounds[0]
    print(f"{path.name}：{ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm、"
          f"体積 {tm.volume / 1000:.2f} cm3、水が漏れない形={tm.is_watertight}")


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    bb = board_box()
    lo = np.array(bb.bounding_box()[:3])
    save(bb.translate([-lo[0], -lo[1], -lo[2]]), "board_box.stl")
    b = lower_shell()
    save(b, "B_lower_shell_model.stl")        # 組み立ての座標のまま（確かめる用）
    save(to_print_pose(b), "B_lower_shell.stl")  # 刷る向き


if __name__ == "__main__":
    main()
