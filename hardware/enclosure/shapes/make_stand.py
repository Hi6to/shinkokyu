"""
案5 スタンド（横から充電する台）の 3D プリント用データを作る。
- 本体は案1の筒（外径 26mm、hardware/enclosure/make_enclosure.py の R_OUT = 13.0）
- USB-C の口を下にして差し、L字の USB-C ケーブルを横の溝から出して、立てたまま充電する
寸法はすべて mm。L字ケーブルの頭の大きさは製品で違うので、買ったケーブルを測って SLOT_W・CAV_H を合わせる。
"""
import math, pathlib, numpy as np, trimesh
from manifold3d import Manifold, CrossSection

OUT = pathlib.Path(__file__).parent / "stl"
SEG = 128

# ---- 寸法（ここを変えれば図面と STL の両方が変わる）----
BODY_D   = 26.0   # 本体（筒）の外径
CLR      = 0.35   # すき間（片側）。チームの箱と同じ
HOLE_D   = BODY_D + 2 * CLR   # 本体を差す穴 26.7
D_OUT    = 64.0   # 台の外径（倒れにくさのため 60 以上）
H        = 30.0   # 台の高さ
FLOOR    = 2.0    # 底の厚さ
CAV_D    = 24.0   # 下の空間の直径（L字プラグの頭が入る）
CAV_H    = 15.0   # 下の空間の高さ（底から）。L字プラグの頭の高さ＋余裕
LEDGE_ID = 19.0   # 本体を受ける棚の内径（棚の幅は (26-19)/2 = 3.5）
SLOT_W   = 14.0   # 横の溝の幅（チームの箱の USB の切り欠き 13.5 に合わせて少し広く）
TOP_CH   = 1.0    # 上のふちの面取り
FOOT_D, FOOT_T, FOOT_R = 8.4, 1.0, 25.0   # 滑り止めゴム足（直径8mm）を貼るくぼみ

Z_CAV_TOP = FLOOR + CAV_H                       # 17.0
Z_LEDGE   = Z_CAV_TOP + (CAV_D - LEDGE_ID) / 2  # 45°の屋根の上 = 棚の上の面 19.5
INSERT    = H - Z_LEDGE                         # 本体が刺さる深さ 10.5

def lathe(profile):
    """(r, z) の折れ線を z 軸まわりに回す"""
    return Manifold.revolve(CrossSection([[(r, z) for r, z in profile]]), SEG)

def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])

def build(body_d=BODY_D):
    """body_d：差す筒の外径（案1 は 26、ゆったり版は 32。11/07）"""
    HOLE_D = body_d + 2 * CLR
    R = D_OUT / 2
    outer = lathe([(0, 0), (R, 0), (R, H - TOP_CH), (R - TOP_CH, H), (0, H)])
    # 内側の空間：下の空間 → 45°の屋根 → 棚の穴 → 本体の穴（上のふちは面取り）
    inner = lathe([(0, FLOOR), (CAV_D / 2, FLOOR), (CAV_D / 2, Z_CAV_TOP), (LEDGE_ID / 2, Z_LEDGE),
                   (HOLE_D / 2, Z_LEDGE), (HOLE_D / 2, H - 0.8), (HOLE_D / 2 + 0.8, H + 0.01), (0, H + 0.01)])
    m = outer - inner
    # 横の溝（-Y 方向）。底の上から上のふちまで抜く
    m -= box(-SLOT_W / 2, SLOT_W / 2, -R - 1, 0, FLOOR, H + 1)
    # ゴム足のくぼみ（溝の向きを避けて 45°ずらす）
    for k in range(4):
        a = math.radians(45 + 90 * k)
        m -= Manifold.cylinder(FOOT_T, FOOT_D / 2, FOOT_D / 2, 48).translate([FOOT_R * math.cos(a), FOOT_R * math.sin(a), -0.01])
    return m

def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)
    OUT.mkdir(exist_ok=True)
    tm.export(OUT / name)
    ext = tm.bounds[1] - tm.bounds[0]
    print(f"{name}: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm, 体積 {tm.volume/1000:.2f} cm3, watertight={tm.is_watertight}")
    return tm

if __name__ == "__main__":
    print(f"穴 {HOLE_D:.1f} / 棚の上 {Z_LEDGE:.1f} / 刺さる深さ {INSERT:.1f}")
    save(build(), "stand_side_charge.stl")
