"""
3D プリンターに渡すデータ（G-code）を、shapes.html に残した案ごとに作る

使い方（このフォルダで）：python3 make_print.py
- 必要なもの：manifold3d・trimesh・numpy、PrusaSlicer 2.7（prusa-slicer のコマンド）
- 出力：
  - stl/            部品ごとの STL（刷る向きに置いたもの）
  - plates/         板ごとに部品を並べた STL（ほかのプリンター・ソフトで刷るときはこれを使う。Bambu A1 など）
  - gcode/          板（1回の印刷）ごとの G-code。同じ板を何度もリポジトリに入れないよう、ここに1つずつ置く
  - fff_only/<案>/  すべて FFF（Ender-3 V3 SE）で作る場合：刷る板の一覧（README.md・print_list.txt）
  - fff_resin/<案>/ 細かい部品だけ光造形（Mars4 Ultra）にする場合：刷る板の一覧と resin/ の STL
  - summary.json    板ごとの時間・フィラメントの量

SD カードに、その案で刷る G-code だけを順番の番号つきでコピーする：
  python3 make_print.py --sd fff_only an15_idcase <SDカードの場所>

案1 のゆったり版（外径 32、body_wide.py）も同じ流れで作る（案の名前は an01w・an03w・an05w。11/07）

UltiMaker S3・ABS グレーだけで作る場合（11/07）：python3 make_print.py --ultimaker-abs
- TPU の部品を ABS の形に変え（USB のふた G → lid_G_abs、⑥ → collet6_abs、② の坂を合わせて太く）、
  S3 の台（230 × 190）に並べた板の STL を ultimaker_abs/plates/ に、案ごとの一覧を ultimaker_abs/<案>/ に作る
- PrusaSlicer は使わない。板の STL を UltiMaker Cura に入れて、ultimaker_abs/README.md の設定でスライスし、.ufp を USB メモリで渡す
"""
import json, math, pathlib, re, shutil, subprocess, sys
import numpy as np, trimesh
from manifold3d import Manifold, Mesh, CrossSection

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "enclosure"))
import body_parts as BP, adapter_parts as AP, make_enclosure as E
import body_wide as BW   # 案1 のゆったり版（外径 32。11/07）
import bottle_parts as BT   # 案1 のペットボトル形（11/08）
sys.path.insert(0, str(HERE.parent / "enclosure" / "shapes"))

SHAPES_STL = HERE.parent / "enclosure" / "shapes" / "stl"
STL = HERE / "stl"; CACHE = HERE / "gcode"
CFG = HERE / "config"
YEN_PER_H = 330          # キカイノイエ：フィラメントを持ちこむ場合 330円/時（店のフィラメントを使うと 550円/時）

def to_tm(m):
    me = m.to_mesh()
    return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=True)

def rot_xy(m, rx=0, ry=0):
    """X のまわりに rx 度、次に Y のまわりに ry 度回す（Manifold.rotate と同じ順）。
    manifold3d 3.5.4（Windows）では rotate が 0 度でも形をくずすため、行列で回す（11/07）"""
    if not rx and not ry:
        return m
    a, b = math.radians(rx), math.radians(ry)
    rx_m = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry_m = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    r = np.round(ry_m @ rx_m, 12)
    return m.transform([list(r[0]) + [0], list(r[1]) + [0], list(r[2]) + [0]])

def on_bed(m, rx=0, ry=0):
    m = rot_xy(m, rx, ry)
    lo = np.array(m.bounding_box()[:3]); hi = np.array(m.bounding_box()[3:])
    return m.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])

# ---------- 部品（名前 → 刷る向きの形） ----------
def new_parts():
    BT.check(verbose=False)
    up_off = AP.L_TH[0] + 0.5
    return {
        "body_A_upper": on_bed(BP.upper_shell()),                      # 合わせ面が下（そのまま）
        "body_B_lower": E.to_print_pose(E.lower_shell()),              # チームの B（そのまま使う）
        "body_C_front": on_bed(BP.front_chamber(), 0, 90),             # 吹き口の側が下
        "body_E_ring": on_bed(BP.ring_E()),
        "body_F_cap": on_bed(BP.cap_F()),                              # つばが下
        "body_G_lid_TPU": on_bed(BP.lid_G()),
        "body_plunger": on_bed(BP.body_plunger()[0]),
        "adapter_2_straw_side": on_bed(AP.part2(), 180, 0),            # 前（ねじの側）が下
        "adapter_4_body_side": on_bed(AP.part4(), 180, 0),             # カップのふちが下
        "adapter_5_cap": on_bed(AP.cap5(), 180, 0),                    # 天井が下
        "adapter_6_sleeve_TPU": on_bed(AP.sleeve6()),
        # ペットボトル形（bottle_parts.py。確かめてから書き出す）
        "bottle_C_front": on_bed(BT.front_chamber(), 0, 90),                 # カップの側（先）が下
        "bottle_2_shoulder": on_bed(BT.part2(), 180, 0),                     # ねじの側が下
        "bottle_5_cap": on_bed(BT.cap5(), 180, 0),                           # 天井が下
        "bottle_6_sleeve_TPU": on_bed(BT.sleeve6()),
    }

def wide_parts():
    """案1 のゆったり版（body_wide.py）と、それに合わせたクリップ・スタンド（刷る向き）"""
    import make_shapes as S, make_stand as MS
    BW.check(verbose=False)                                            # つながり・中の部品・組み立てを確かめてから書き出す
    parts = {
        "wide_body_A_upper": on_bed(BW.upper_shell()),                 # 合わせ面が下（そのまま）
        "wide_body_B_lower": on_bed(BW.lower_shell(), 180, 0),         # 合わせ面が下
        "wide_body_C_front": on_bed(BW.front_chamber(), 0, 90),        # 吹き口の側が下
        "wide_body_E_ring": on_bed(BW.ring_E()),
        "wide_body_F_cap": on_bed(BW.cap_F()),                         # つばが下
        "wide_body_plunger": on_bed(BW.plunger()[0]),
    }
    S.set_body_r(BW.R_OUT)
    try:
        raw = {"wide_pen_clip": (S.pen_clip(), None)}
        for n in ("plain", "volcano", "rocket", "sword", "sprout"):
            raw[f"wide_stand_{n}"] = getattr(S, f"stand_{n}")()
        raw["wide_stand_side_charge"] = (MS.build(2 * BW.R_OUT), MS.H)
    finally:
        S.set_body_r(13.0)
    # スタンドに、ゆったり版の筒がぶつからずに入り、棚にのるか（向きを変える前の座標：穴の中心が原点、H は穴の上の高さ）
    body = Manifold.cylinder(80, BW.R_OUT, BW.R_OUT, 128)
    for n, (m, H) in raw.items():
        if H is not None:
            assert (m ^ body.translate([0, 0, H - 10.5])).volume() < 1e-3, f"{n} に筒がぶつかる"   # 10.5 差す
            assert (m ^ body.translate([0, 0, H - 10.6])).volume() > 0, f"{n} の棚に筒がのらない"
        parts[n] = on_bed(m)
    for n, m in parts.items():
        assert len(m.decompose()) == 1, f"{n} がつながっていない"
    return parts

# ---------- FFF で形がくずれにくい形にする決まり（11/08。調べた元は ultimaker_abs/README.md） ----------
# 11/07 に入れた：張り出しは 45° まで（屋根・坂）／橋は 5mm より短く（支えを形に入れる）／ABS は角を丸める
# 11/08 に足した：① 台にふれるふちを 45° に面取り（1層目が広がる「象の足」を防ぐ。穴のふちも広がり、小さく刷れる穴を補う）
#                 ② 横向きの穴は上をとがらせる（しずく形）③ 細い棒（直径 5mm 未満）は根元を 45° で太らせる
#                 ④ 支えの両はしの壁も線2本（0.8mm）にする
CH_BED, CH_SMALL = 0.4, 0.3     # 台のふちの面取りの高さ（大きい部品／小さい部品）

def bed_chamfer(m, c=CH_BED, n=4):
    """刷る向きの形 m の、台（z=0）にふれるふちを、高さ c・45° で面取りする（外のふちも、穴のふちも）。
    台から c×(n−1)/n までは、断面を段ごとに内側へずらした板を積み直し、その上の形と少し重ねてつなぐ。
    - manifold3d 3.5.4（Windows）では trim_by_plane がくずれ、同じ位置の面が重なる足し算・引き算も面が残る。
      そのため、もとの壁と同じ位置の壁ができないように、ずらした段だけを使う
    - ずらした断面は、細かすぎる点を間引いてから板にする（面積ゼロの三角を作らないため）
    - 台にふれる所が消えてしまう細い部品（c×2 より細い）は、確かめで止める"""
    lo, hi = np.array(m.bounding_box()[:3]), np.array(m.bounding_box()[3:])
    z_top = c * (n - 1) / n
    out = m ^ E.box(lo[0] - 1, hi[0] + 1, lo[1] - 1, hi[1] + 1, z_top - 0.02, hi[2] + 1)
    for k in range(n - 1):
        z0, z1 = c * k / n, c * (k + 1) / n
        cs = m.slice((z0 + z1) / 2)
        if cs.is_empty(): continue
        out += cs.offset(-(c - z1)).simplify(0.002).extrude(z1 - z0 + 0.02).translate([0, 0, z0])
    a0, a1 = len(m.slice(0.05).decompose()), len(out.slice(0.05).decompose())
    assert a1 >= a0, f"台にふれる所が {a0} → {a1} に減った（細すぎる所がある）"
    return out

def plunger_abs(r_head, length, r_shaft=1.85, t_head=0.6, h=0.5, c=CH_SMALL):
    """押し棒（ABS 版）：つば（r_head・厚さ t_head）＋軸（直径 3.7 の細い棒）。断面を回して1つの形で作る（足し算をしない）。
    - 細い棒は根元が折れやすいので、つばの上 h を 45° で太らせる（穴には入らない高さ）
    - 台にふれるつばのふちを c だけ 45° で面取り"""
    prof = [(0, 0), (r_head - c, 0), (r_head, c), (r_head, t_head), (r_shaft + h, t_head), (r_shaft, t_head + h), (r_shaft, length), (0, length)]
    return Manifold.revolve(CrossSection([prof]), 64)

def teardrop_y(xc, zc, r, y0, y1, up=-1, flat=None, eps=0.05):
    """Y の向きの横穴（中心 xc, zc・半径 r）の上をとがらせる形（組み立ての座標。up は刷るときの上：X の +1 / -1）。
    45° の2本の線は、円に接する線より eps だけ内側にずらす（接する所で面が重なり、形がくずれるのを防ぐ）。
    flat を与えると、先を幅 flat で平らに切る（大きい穴で、とがりが長くなりすぎないように）"""
    k = r * math.sqrt(2) - eps * math.sqrt(2)                # 線：u + |v| = k（u は上の向き、v は横）
    u_hi = (k + math.sqrt(2 * r * r - k * k)) / 2           # 線と円が交わる2点のうち、とがりに近い方
    v_lo = k - u_hi
    pts = [(0.0, 0.0), (u_hi, v_lo), (u_hi, -v_lo)]
    pts += [(k, 0.0)] if flat is None else [(k - flat / 2, flat / 2), (k - flat / 2, -flat / 2)]
    return Manifold.hull_points([(xc + up * u, y, zc + v) for (u, v) in pts for y in (y0, y1)])

def match_sleeve_holes(S):
    """マッチの外箱の横穴（押し棒の穴 3つ・円盤の窓）をしずく形にする形を、刷る向きの座標で返す。
    外箱は立てて刷る（吹き口の側の壁が下）。組み立ての X が小さい向きが、刷るときの上"""
    WALL, MC, MW = S.WALL, S.MC, S.MW
    comp_y1 = MW / 2 - WALL
    zin0, zin1 = WALL, WALL + S.OUT_W + 2 * MC
    H, L1 = zin1 + WALL, S.XF + MC + WALL
    dz = (zin0 + zin1) / 2
    cut = Manifold()
    for x, y in S.BTN:
        cut += teardrop_y(x, -y + dz, 2.1, comp_y1 - 0.5, MW / 2 + 1)
    cut += teardrop_y(S.DIAL_C[0], -S.DIAL_C[1] + dz, 9.6, comp_y1 - 1, MW / 2 + 1, flat=4.0)   # 窓は先を幅 4 で平らに
    T = [[0, 0, 1, -H / 2], [0, 1, 0, 0], [-1, 0, 0, L1]]          # 組み立て → 刷る向き（立てる）
    # 確かめ用：もとの丸い穴（少し細く・短く）。同じ写し方で STL の中が空いていれば、写し方が合っている
    holes = Manifold()
    for x, y in S.BTN:
        h = MW / 2 + 0.6 - (comp_y1 - 0.4)
        holes += Manifold.cylinder(h, 2.0, 2.0, 32).transform([[1, 0, 0, x], [0, 0, 1, comp_y1 - 0.4], [0, -1, 0, -y + dz]])
    return cut.transform(T), holes.transform(T)

def pose_pair(shell, sup, rx=0, ry=0, flip_b=False):
    """殻と支えを、殻の外形に合わせて同じように刷る向きに置く（殻だけ台のふちを面取り）"""
    if flip_b:
        F = [[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, E.Z_SPLIT]]
        shell, sup = shell.transform(F), sup.transform(F)
        lo = np.array(shell.bounding_box()[:3]); d = [-lo[0], -lo[1], -lo[2]]
    else:
        shell, sup = rot_xy(shell, rx, ry), rot_xy(sup, rx, ry)
        lo, hi = np.array(shell.bounding_box()[:3]), np.array(shell.bounding_box()[3:])
        d = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]]
    return bed_chamfer(shell.translate(d)) + sup.translate(d)

def abs_parts():
    """ABS だけで作るときの部品（刷る向き）。TPU の部品の代わりと、試し刷りを受けて直した殻。どれも台のふちを面取り"""
    return {
        "body_G_lid_ABS": bed_chamfer(on_bed(BP.lid_G_abs()), CH_SMALL),                      # つばが下
        "adapter_2_straw_side_ABS": bed_chamfer(on_bed(AP.part2(True), 180, 0), CH_SMALL),    # 前（ねじの側）が下
        "adapter_6_collet_ABS": bed_chamfer(on_bed(AP.collet6_abs(), 180, 0), CH_SMALL),      # つばが下
        "body_A_upper_ABS": pose_pair(*BP.upper_shell_abs_parts()),                           # 合わせ面が下。内側の天井の下に、折って取る支え
        "body_B_lower_ABS": pose_pair(*BP.lower_shell_abs_parts(), flip_b=True),              # 合わせ面が下。同じく支え＋輪の下を 45°
        "body_C_front_ABS": bed_chamfer(on_bed(BP.front_chamber(True), 0, -90)),              # つば（仕切りの壁）が下
        # ペットボトル形（11/08）
        "bottle_C_front_ABS": bed_chamfer(on_bed(BT.front_chamber(True), 0, -90)),            # つば（仕切りの壁）が下、カップが上
        "bottle_2_shoulder_ABS": bed_chamfer(on_bed(BT.part2(), 180, 0), CH_SMALL),            # ねじの側が下
        "bottle_5_cap_ABS": bed_chamfer(on_bed(BT.cap5(), 180, 0), CH_SMALL),                  # 天井が下
        "bottle_6_collet_ABS": bed_chamfer(on_bed(BT.collet6(), 180, 0), CH_SMALL),            # つばが下
    }

# ほかの PC で作った STL（stl/）や shapes の STL に、台のふちの面取りなどを足して「_ABS」にするもの： 名前 → (元, 面取り, 押し棒か)
STL_ABS = {
    "body_E_ring": (STL, CH_SMALL, False), "body_F_cap": (STL, CH_BED, False), "body_plunger": (STL, CH_SMALL, True),
    "adapter_4_body_side": (STL, CH_SMALL, False), "adapter_5_cap": (STL, CH_SMALL, False),
    "wide_body_E_ring": (STL, CH_SMALL, False), "wide_body_F_cap": (STL, CH_BED, False), "wide_body_plunger": (STL, CH_SMALL, True),
    "wide_pen_clip": (STL, CH_BED, False), "wide_stand_plain": (STL, CH_BED, False),
    "core_socket": (SHAPES_STL, CH_SMALL, False), "plunger": (SHAPES_STL, CH_SMALL, True), "plunger_long": (SHAPES_STL, CH_SMALL, True),
    "core_dial": (SHAPES_STL, CH_SMALL, False), "pen_clip": (SHAPES_STL, CH_BED, False), "stand_plain": (SHAPES_STL, CH_BED, False),
}

def auto_breakaway(name, pitch=4.4, min_area=150.0):
    """刷る向きの STL（合わせ面が下で、中が台まで開いている殻）の、広い平らな天井の下に、折って取る支えの壁を入れる。
    天井の形（下から見た形）の内側だけに、長い向きの壁を pitch ごとに並べ、20mm ごとに横の壁でつなぐ。
    殻からは横にも下にも SUP_GAP だけ離す。台にとどかないかけらは消す"""
    from manifold3d import CrossSection
    shell = bed_chamfer(stl_manifold(STL / f"{name}.stl"))
    t = to_tm(shell)
    g, T = BP.SUP_GAP, BP.SUP_T
    nz, c = t.face_normals[:, 2], t.triangles_center
    sel = (nz < -0.985) & (c[:, 2] > 0.3)
    sup = Manifold()
    for z in np.unique(np.round(c[sel, 2], 1)):
        f = np.nonzero(sel & (np.abs(c[:, 2] - z) < 0.06))[0]
        if t.area_faces[f].sum() < min_area: continue
        foot = CrossSection()
        for tri in t.triangles[f]:
            q = tri[:, :2]
            d1, d2 = q[1] - q[0], q[2] - q[0]
            if d1[0] * d2[1] - d1[1] * d2[0] < 0: q = q[::-1]
            foot += CrossSection([q.tolist()])
        foot = foot.offset(-0.4)                                       # 天井のはしの 0.4 は、壁から渡せる
        lo, hi = np.array(foot.bounds()[:2]), np.array(foot.bounds()[2:])
        ax = 0 if hi[0] - lo[0] >= hi[1] - lo[1] else 1                # 長い向き
        span = hi[1 - ax] - lo[1 - ax]
        n = max(1, int(np.ceil(span / pitch)) - 1)                     # 壁と壁、壁と天井のはしが pitch 以下
        top = float(z) - g - 0.03
        grid = Manifold()
        for k in range(1, n + 1):
            v = lo[1 - ax] + span * k / (n + 1)
            b0 = [lo[0] - 1, lo[1] - 1]; b1 = [hi[0] + 1, hi[1] + 1]
            b0[1 - ax], b1[1 - ax] = v - T / 2, v + T / 2
            grid += E.box(b0[0], b1[0], b0[1], b1[1], 0, top)
        m = int(max(1, round((hi[ax] - lo[ax]) / 20.0)))
        for k in range(m + 1):
            v = lo[ax] + T / 2 + (hi[ax] - lo[ax] - T) * k / m              # 両はしの壁も厚さ T
            b0 = [lo[0], lo[1]]; b1 = [hi[0], hi[1]]
            b0[ax], b1[ax] = v - T / 2, v + T / 2
            if n > 1: b0[1 - ax] = lo[1 - ax] + span / (n + 1); b1[1 - ax] = lo[1 - ax] + span * n / (n + 1)
            else: continue
            grid += E.box(b0[0], b1[0], b0[1], b1[1], 0, top)
        sup += grid ^ foot.extrude(top + 1)
    for dx, dy, dz in ((0, 0, 0), (g, 0, 0), (-g, 0, 0), (0, g, 0), (0, -g, 0), (0, 0, -g)):
        sup -= shell.translate([dx, dy, dz])
    keep = [p for p in sup.decompose() if p.bounding_box()[2] < 0.01 and p.volume() > 1.0]   # 台にとどくものだけ
    sup = Manifold()
    for p in keep: sup += p
    return trimesh.util.concatenate([to_tm(shell), to_tm(sup)])

def stl_manifold(path):
    t = trimesh.load(path)
    return Manifold(Mesh(vert_properties=np.asarray(t.vertices, dtype=np.float32), tri_verts=np.asarray(t.faces, dtype=np.uint32)))

def round_corners(m, r, corners=("00", "01", "10", "11"), xy=None):
    """外形の箱の、縦（刷る向きの上下）の角を半径 r で丸める。ABS は角から反って浮くため（11/07）。
    corners は "xy"："0"＝小さい側、"1"＝大きい側。xy＝(x0, y0, x1, y1) で箱を指定（なければ全体の外形）"""
    lo, hi = np.array(m.bounding_box()[:3]), np.array(m.bounding_box()[3:])
    if xy is not None:
        lo[:2], hi[:2] = xy[:2], xy[2:]
    for c in corners:
        sx, sy = (1 if c[0] == "0" else -1), (1 if c[1] == "0" else -1)
        x, y = (lo[0] if c[0] == "0" else hi[0]), (lo[1] if c[1] == "0" else hi[1])
        sq = E.box(min(x, x + sx * r), max(x, x + sx * r), min(y, y + sy * r), max(y, y + sy * r), lo[2] - 1, hi[2] + 1)
        cyl = Manifold.cylinder(hi[2] - lo[2] + 4, r, r, 48).translate([x + sx * r, y + sy * r, lo[2] - 2])
        m -= sq - cyl
    return m

def shapes_abs():
    """案15・案17（と案7・15・17 共通の箱のコア）の ABS 版（11/07）。形は shapes の STL（刷る向き）のまま、
    ABS の反り対策だけ足す：外の縦の角を丸める・社員証の裏の板に窓（カードの下。ふち 6mm を残す）"""
    sys.path.insert(0, str(SHAPES_STL.parent))
    import make_shapes as S
    out = {}
    out["core_back_ABS"] = bed_chamfer(round_corners(stl_manifold(SHAPES_STL / "core_back.stl"), 2.0))
    nb = stl_manifold(SHAPES_STL / "necklace_back.stl")                # 案7：後ろのひもの輪（4.5 出ている）はそのまま、コアの角だけ
    lo, hi = np.array(nb.bounding_box()[:3]), np.array(nb.bounding_box()[3:])
    out["necklace_back_ABS"] = bed_chamfer(round_corners(nb, 2.0, xy=(lo[0] + 4.5, lo[1], hi[0], hi[1])))
    sleeve = round_corners(stl_manifold(SHAPES_STL / "match_sleeve.stl"), 2.5)
    tear, holes = match_sleeve_holes(S)
    assert (sleeve ^ holes).volume() < 0.05, (sleeve ^ holes).volume()     # 穴の位置の写し方が合っている
    out["match_sleeve_ABS"] = bed_chamfer(sleeve - tear)
    out["match_tray_ABS"] = bed_chamfer(round_corners(stl_manifold(SHAPES_STL / "match_tray.stl"), 2.0))
    out["match_store_sleeve_ABS"] = bed_chamfer(round_corners(stl_manifold(SHAPES_STL / "match_store_sleeve.stl"), 2.5))  # 11/09：しまう箱
    # 社員証：裏（コアを貼る板つき）。カードの下に窓
    t = trimesh.load(SHAPES_STL / "idcase_frame_back.stl")
    off = t.bounds[0] - np.array([S.FR_X0, S.FR_Y0, S.ZB - 2.0])
    cx0 = S.FR_X0 + 3.0
    cy0 = S.FR_Y0 + (S.FR_Y1 - S.FR_Y0 - (S.CARD_W + 0.6)) / 2
    L = 6.0
    win = E.box(cx0 + L, cx0 + S.CARD_H + 0.6 - L, cy0 + L, cy0 + S.CARD_W + 0.6 - L, S.ZB - 3, S.ZB + 0.1).translate(list(off))
    back = stl_manifold(SHAPES_STL / "idcase_frame_back.stl") - win
    out["idcase_frame_back_ABS"] = bed_chamfer(round_corners(back, 4.0))
    # 表の窓の枠：外のへり（y が小さい側）の2つの角だけ丸める（コアの側は、裏の板とそろえて四角のまま）
    out["idcase_frame_front_ABS"] = bed_chamfer(round_corners(stl_manifold(SHAPES_STL / "idcase_frame_front.stl"), 4.0, ("00", "10")), CH_SMALL)
    # ほかの部品：台のふちの面取り、押し棒は根元を太らせる
    for name, (src, c, pl) in STL_ABS.items():
        if pl: continue
        out[f"{name}_ABS"] = bed_chamfer(stl_manifold(src / f"{name}.stl"), c)
    # 押し棒（長さとつばは、元の STL と同じ）
    for name, r_head in (("body_plunger", 2.9), ("wide_body_plunger", 2.9), ("plunger", 2.8), ("plunger_long", 2.8)):
        t = trimesh.load(STL_ABS[name][0] / f"{name}.stl")
        out[f"{name}_ABS"] = plunger_abs(r_head, float(t.extents[2]))
    return out

def core_front_abs():
    """箱のコアの上の殻（ABS 版）：合わせ面を下にして刷ると、上の面の内側が幅 21.2 × 長さ 72 の支えのない橋になる。
    その下に、あとで折って取る支えの格子を入れる。殻の形は shapes の core_front.stl（刷る向き）のまま"""
    sys.path.insert(0, str(SHAPES_STL.parent))
    import make_shapes as S                       # 寸法だけ使う（rotate を使う関数は呼ばない）
    t = trimesh.load(SHAPES_STL / "core_front.stl")
    off = t.bounds[0] - np.array([S.XB, -S.OUT_W / 2, 0.0])     # 組み立ての座標 → STL の座標
    g, top = BP.SUP_GAP, S.ZT_IN - BP.SUP_GAP
    x0, x1 = S.XB_IN + 0.5, S.XF_IN - 0.5
    px0, px1 = S.PART_X0 - g, S.PART_X0 + S.PART_T + g          # 仕切り（天井からぶら下がる壁。下のはしは z=0.9）
    low = S.BT + 0.1 - g
    ys = [-8.4, -4.2, 0.0, 4.2, 8.4]                            # 基板を押さえる帯（|y| ≥ 9.85）にはふれない。橋は 4.2mm ずつ
    sup = Manifold()
    for y in ys:
        sup += E.box(x0, px0, y - BP.SUP_T / 2, y + BP.SUP_T / 2, 0, top)
        sup += E.box(px0 - 0.05, px1 + 0.05, y - BP.SUP_T / 2, y + BP.SUP_T / 2, 0, low)   # 低い所は前後に 0.05 重ねる（面をそろえない）
        sup += E.box(px1, x1, y - BP.SUP_T / 2, y + BP.SUP_T / 2, 0, top)
    yy = (ys[0] - BP.SUP_T / 2, ys[-1] + BP.SUP_T / 2)
    xs = list(np.linspace(x0 + BP.SUP_T / 2, px0 - BP.SUP_T / 2, 4)) + list(np.linspace(px1 + BP.SUP_T / 2, x1 - BP.SUP_T / 2, 2))   # 横の壁は少なめ（刷る時間）
    for x in xs:                                                # 横の壁は 0.02 低く（長い向きの壁と上の面をそろえない）
        sup += E.box(x - BP.SUP_T / 2, x + BP.SUP_T / 2, *yy, 0, top - 0.02)
    sup += E.box(S.PART_X0 + S.PART_T / 2 - BP.SUP_T / 2, S.PART_X0 + S.PART_T / 2 + BP.SUP_T / 2, *yy, 0, low - 0.02)   # 仕切りの真下
    sup = sup.translate(list(off))
    # 確かめ：殻を横と下に 0.24 ずらした形と、支えが重ならないこと（すき間がちゃんとある）
    shell = round_corners(stl_manifold(SHAPES_STL / "core_front.stl"), 2.0)   # 下の殻とそろえて、縦の角を丸める
    # 前の壁の息の穴（横向き。半径 2.5）の上をしずく形に（刷るときの上＝+Z）
    r = 2.5; a_ = r / math.sqrt(2)
    yz = ((0, S.CH_Z + r * math.sqrt(2)), (a_, S.CH_Z + a_), (-a_, S.CH_Z + a_), (a_, S.CH_Z), (-a_, S.CH_Z))
    tear = Manifold.hull_points([(x, y, z) for x in (S.XF_IN - 0.1, S.XF + 1) for (y, z) in yz])
    shell = bed_chamfer(shell - tear.translate(list(off)))
    for dx, dy, dz in ((0, 0, 0), (g - 0.01, 0, 0), (0.01 - g, 0, 0), (0, g - 0.01, 0), (0, 0.01 - g, 0), (0, 0, 0.01 - g)):
        hit = [c.volume() for c in (shell.translate([dx, dy, dz]) ^ sup).decompose()]
        assert max([abs(v) for v in hit] + [0]) < 1e-3, ((dx, dy, dz), hit)
    return trimesh.util.concatenate([to_tm(shell), to_tm(sup)])

FROM_SHAPES = ["core_back", "core_front", "core_socket", "core_dial", "plunger", "plunger_long", "necklace_back",
               "idcase_frame_back", "idcase_frame_front", "match_sleeve", "match_tray", "pen_clip",
               "stand_plain", "stand_side_charge", "stand_volcano", "stand_rocket", "stand_rocket_tower",
               "stand_sword", "stand_sprout", "stand_sprout_leaf"]

# ---------- 板（1回の印刷） ----------
# 名前: (設定, [部品…], 説明)
PROFILE = {"petg": ["ender3v3se_common.ini", "petg_020.ini"],
           "petg_tall": ["ender3v3se_common.ini", "petg_020.ini", "petg_020_tall.ini"],
           "adapter": ["ender3v3se_common.ini", "petg_012_adapter.ini"],
           "tpu": ["ender3v3se_common.ini", "tpu_020.ini"]}
PLATES = {
    "body_tube":    ("petg", ["body_A_upper", "body_B_lower", "body_C_front", "body_E_ring", "body_F_cap"] + ["body_plunger"] * 3,
                     "案1 の筒：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本"),
    "body_tpu":     ("tpu", ["body_G_lid_TPU", "adapter_6_sleeve_TPU", "adapter_6_sleeve_TPU"],
                     "TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個"),
    "core_case":    ("petg", ["core_back", "core_front", "core_socket"] + ["plunger"] * 3,
                     "箱のコア（案7・15・17 共通）：下の殻・上の殻・吹き口の受け・押し棒 3本"),
    "core_case_match": ("petg", ["core_back", "core_front", "core_socket"] + ["plunger_long"] * 3,
                     "箱のコア（案17 用。押し棒が外箱の壁の分だけ長い）"),
    "core_dial":    ("adapter", ["core_dial", "core_dial"],
                     "空気口の円盤 2枚（層 0.12mm。1枚は予備）"),
    "core_tpu":     ("tpu", ["adapter_6_sleeve_TPU", "adapter_6_sleeve_TPU"], "TPU：ストローをつかむ筒 ⑥ 2個"),
    "adapter":      ("adapter", ["adapter_2_straw_side", "adapter_4_body_side", "adapter_5_cap"] * 2,
                     "吹き口アダプター ②④⑤ を2組（洗って乾かす間に替えを使う）。層 0.12mm・中まで 100%"),
    "pen_clip":     ("petg", ["pen_clip"], "案3 クリップ"),
    "necklace":     ("petg", ["necklace_back", "core_front", "core_socket"] + ["plunger"] * 3,
                     "案7：ひもの輪つきの下の殻・上の殻・吹き口の受け・押し棒 3本"),
    "idcase":       ("petg", ["idcase_frame_back", "idcase_frame_front"], "案15：カードの枠（裏・表）"),
    "match_sleeve": ("petg_tall", ["match_sleeve"], "案17：外箱（立てて刷る。ふち 5mm つき）"),
    "match_tray":   ("petg", ["match_tray"], "案17：内箱（2列）"),
    "stand_plain":  ("petg", ["stand_plain"], "案5 ふつうのスタンド"),
    "stand_side_charge": ("petg", ["stand_side_charge"], "案5 横から充電するスタンド"),
    "stand_volcano": ("petg", ["stand_volcano"], "案5-A 火山"),
    "stand_rocket": ("petg", ["stand_rocket", "stand_rocket_tower"], "案5-C ロケット発射台＋発射塔"),
    "stand_rocket_base": ("petg", ["stand_rocket"], "案5-C ロケット発射台（発射塔は光造形）"),
    "stand_sword":  ("petg", ["stand_sword"], "案5-D 岩に刺さった剣"),
    "stand_sprout": ("petg", ["stand_sprout", "stand_sprout_leaf"], "案5-E 植木鉢＋葉っぱ"),
    "stand_sprout_pot": ("petg", ["stand_sprout"], "案5-E 植木鉢（葉っぱは光造形）"),
    # 案1 のペットボトル形（bottle_parts.py。11/08）
    "bottle_tube": ("petg", ["body_A_upper", "body_B_lower", "bottle_C_front", "body_E_ring", "body_F_cap"] + ["body_plunger"] * 3,
                    "案1 ペットボトル形の筒：上の殻 A・下の殻 B（今と同じ）・前の部屋 C（先がカップ）・リング E・キャップ F・押し棒 3本"),
    "bottle_tpu": ("tpu", ["body_G_lid_TPU", "bottle_6_sleeve_TPU", "bottle_6_sleeve_TPU"], "TPU：USB のふた G・ストローをつかむ筒 ⑥ 2個（ペットボトル形）"),
    "bottle_adapter": ("adapter", ["bottle_2_shoulder", "bottle_5_cap"] * 2,
                       "ペットボトル形の吹き口：肩 ②・キャップ ⑤ を2組。層 0.12mm・中まで 100%"),
    # 案1 のゆったり版（外径 32。body_wide.py）
    "wide_body_tube": ("petg", ["wide_body_A_upper", "wide_body_B_lower", "wide_body_C_front", "wide_body_E_ring", "wide_body_F_cap"] + ["wide_body_plunger"] * 3,
                       "案1 ゆったり版の筒（外径 32）：上の殻 A・下の殻 B・前の部屋 C・回すリング E・後ろのキャップ F・押し棒 3本"),
    "wide_pen_clip": ("petg", ["wide_pen_clip"], "案3 クリップ（ゆったり版の筒用）"),
    "wide_stand_plain": ("petg", ["wide_stand_plain"], "案5 ふつうのスタンド（ゆったり版用）"),
    "wide_stand_side_charge": ("petg", ["wide_stand_side_charge"], "案5 横から充電するスタンド（ゆったり版用）"),
    "wide_stand_volcano": ("petg", ["wide_stand_volcano"], "案5-A 火山（ゆったり版用）"),
    "wide_stand_rocket": ("petg", ["wide_stand_rocket", "stand_rocket_tower"], "案5-C ロケット発射台＋発射塔（ゆったり版用）"),
    "wide_stand_rocket_base": ("petg", ["wide_stand_rocket"], "案5-C ロケット発射台（ゆったり版用。発射塔は光造形）"),
    "wide_stand_sword": ("petg", ["wide_stand_sword"], "案5-D 岩に刺さった剣（ゆったり版用）"),
    "wide_stand_sprout": ("petg", ["wide_stand_sprout", "stand_sprout_leaf"], "案5-E 植木鉢＋葉っぱ（ゆったり版用）"),
    "wide_stand_sprout_pot": ("petg", ["wide_stand_sprout"], "案5-E 植木鉢（ゆったり版用。葉っぱは光造形）"),
}

# ---------- 案ごとの組み合わせ ----------
BODY = ["body_tube", "body_tpu", "adapter"]
CORE = ["core_case", "core_tpu", "adapter"]
IDEAS = {
    "an01_tube":     ("案1 筒（基本の本体）", BODY, []),
    "an03_pen":      ("案3 ペン型（案1＋クリップ）", BODY + ["pen_clip"], []),
    "an05_stand":    ("案5 スタンド（案1＋スタンド。スタンドは好きなものを1つ）", BODY + ["stand_side_charge", "stand_plain", "stand_volcano", "stand_rocket", "stand_sword", "stand_sprout"], []),
    "an07_necklace": ("案7 ネックレス", ["necklace", "core_tpu", "adapter"], []),
    "an15_idcase":   ("案15 社員証ケース", CORE + ["idcase"], []),
    "an17_match":    ("案17 マッチ箱", ["core_case_match", "core_tpu", "adapter", "match_sleeve", "match_tray"], []),
    "an01b_tube_bottle": ("案1 筒・ペットボトル形（本体 → 丸い肩 → キャップ）", ["bottle_tube", "bottle_tpu", "bottle_adapter"], []),
    # 案1 のゆったり版（外径 32）。吹き口アダプターと TPU の部品は今の案1 と同じ
    "an01w_tube_wide":  ("案1 筒・ゆったり版（外径 32）", ["wide_body_tube", "body_tpu", "adapter"], []),
    "an03w_pen_wide":   ("案3 ペン型・ゆったり版（案1 ゆったり版＋クリップ）", ["wide_body_tube", "body_tpu", "adapter", "wide_pen_clip"], []),
    "an05w_stand_wide": ("案5 スタンド・ゆったり版（案1 ゆったり版＋スタンド。スタンドは好きなものを1つ）",
                         ["wide_body_tube", "body_tpu", "adapter", "wide_stand_side_charge", "wide_stand_plain", "wide_stand_volcano",
                          "wide_stand_rocket", "wide_stand_sword", "wide_stand_sprout"], []),
}
# 光造形にする部品（理由は README）。FFF の板からは外す
RESIN = {"core_dial": "空気口の円盤：細くなっていく切れ目（0.8 → 0mm）を最後まで形にできる",
         "stand_rocket_tower": "発射塔：細い柱と格子がきれいに出る（飾りで、力がかからない）",
         "stand_sprout_leaf": "葉っぱ：厚さ 3mm の薄い形と葉脈がきれいに出る（飾り）"}
RESIN_SWAP = {"stand_rocket": "stand_rocket_base", "stand_sprout": "stand_sprout_pot",
              "wide_stand_rocket": "wide_stand_rocket_base", "wide_stand_sprout": "wide_stand_sprout_pot"}

def plates_for(idea, variant):
    _, plates, _ = IDEAS[idea]
    out = list(plates)
    if idea in ("an07_necklace", "an15_idcase", "an17_match") and variant == "fff_only":
        out.insert(1, "core_dial")
    if variant == "fff_resin":
        out = [RESIN_SWAP.get(p, p) for p in out]
    return out

def resin_for(idea):
    r = []
    if idea in ("an07_necklace", "an15_idcase", "an17_match"): r.append("core_dial")
    if idea in ("an05_stand", "an05w_stand_wide"): r += ["stand_rocket_tower", "stand_sprout_leaf"]
    return r

# ---------- スライス ----------
GAP, BED = 6.0, 220.0
def layout(parts):
    """部品を台の上に並べる（大きいものから、行ごとに詰める）。台の真ん中にそろえた1つの形にする"""
    ms = sorted((trimesh.load(STL / f"{p}.stl") for p in parts), key=lambda t: -(t.extents[1] * 1000 + t.extents[0]))
    rows, x, y, rowh, placed = [], 0.0, 0.0, 0.0, []
    for t in ms:
        w, h = t.extents[0], t.extents[1]
        if x > 0 and x + w > BED - 20:
            x, y, rowh = 0.0, y + rowh + GAP, 0.0
        t = t.copy(); t.apply_translation([x - t.bounds[0][0], y - t.bounds[0][1], -t.bounds[0][2]])
        placed.append(t); x += w + GAP; rowh = max(rowh, h)
    plate = trimesh.util.concatenate(placed)
    lo, hi = plate.bounds
    plate.apply_translation([BED / 2 - (lo[0] + hi[0]) / 2, BED / 2 + 10 - (lo[1] + hi[1]) / 2, 0])
    assert plate.bounds[0][0] > 5 and plate.bounds[1][0] < BED - 5 and plate.bounds[0][1] > 25 and plate.bounds[1][1] < BED - 5, plate.bounds
    return plate

def slice_plate(name):
    prof, parts, _ = PLATES[name]
    out = CACHE / f"{name}.gcode"
    plate_stl = HERE / "plates" / f"{name}.stl"
    plate_stl.parent.mkdir(exist_ok=True)
    layout(parts).export(plate_stl)
    cmd = ["prusa-slicer", "--export-gcode"]
    for c in PROFILE[prof]: cmd += ["--load", str(CFG / c)]
    cmd += ["--dont-arrange", str(plate_stl), "-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not out.exists():
        raise RuntimeError(f"{name}: {r.stdout[-800:]}{r.stderr[-800:]}")
    txt = out.read_text(errors="ignore")
    t = re.search(r"estimated printing time \(normal mode\) = (.+)", txt).group(1).strip()
    g = float(re.search(r"; total filament used \[g\] = ([\d.]+)", txt).group(1))
    sec = sum(int(v) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u] for v, u in re.findall(r"(\d+)([dhms])", t))
    return dict(time=t, minutes=round(sec / 60), grams=g, profile=prof, parts=parts)

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    STL.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    report = {}
    for name, m in new_parts().items():
        tm = to_tm(m); tm.export(STL / f"{name}.stl")
        ext = tm.bounds[1] - tm.bounds[0]
        report[name] = dict(size=[round(float(x), 1) for x in ext], vol_cm3=round(tm.volume / 1000, 2), watertight=bool(tm.is_watertight))
        print(f"{name:24s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f}  watertight={tm.is_watertight}")
    for name, m in wide_parts().items():
        tm = to_tm(m); tm.export(STL / f"{name}.stl")
        ext = tm.bounds[1] - tm.bounds[0]
        report[name] = dict(size=[round(float(x), 1) for x in ext], vol_cm3=round(tm.volume / 1000, 2), watertight=bool(tm.is_watertight))
        print(f"{name:24s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f}  watertight={tm.is_watertight}")
    for n in FROM_SHAPES:
        shutil.copy(SHAPES_STL / f"{n}.stl", STL / f"{n}.stl")
    used = {p for v in ("fff_only", "fff_resin") for i in IDEAS for p in plates_for(i, v)}
    info = {}
    for p in sorted(used):
        info[p] = slice_plate(p); print(f"slice {p:20s} {info[p]['time']:>12s} {info[p]['grams']:7.1f} g")
    summary = dict(parts=report, plates=info, ideas={})
    for variant in ("fff_only", "fff_resin"):
        for idea, (title, _, _) in IDEAS.items():
            d = HERE / variant / idea
            if d.exists(): shutil.rmtree(d)
            d.mkdir(parents=True)
            plates = plates_for(idea, variant)
            (d / "print_list.txt").write_text("".join(f"gcode/{p}.gcode\n" for p in plates), encoding="utf-8")
            res = resin_for(idea) if variant == "fff_resin" else []
            if res:
                (d / "resin").mkdir()
                for r in res: shutil.copy(STL / f"{r}.stl", d / "resin" / f"{r}.stl")
            write_readme(d, idea, title, variant, plates, res, info)
            summary["ideas"][f"{variant}/{idea}"] = dict(plates=plates, resin=res)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

def write_readme(d, idea, title, variant, plates, res, info):
    stand = idea.startswith("an05")
    L = [f"# {title}（{'すべて FFF' if variant == 'fff_only' else 'FFF ＋ 光造形'}）", "",
         "プリンター：**Creality Ender-3 V3 SE**（キカイノイエ）。G-code を SD カードに入れて刷る。",
         "上から順番に1枚ずつ刷る（材料が変わる板は、フィラメントを入れ替える）。G-code は [`../../gcode/`](../../gcode/) にある（ほかの案と同じ板は共通）。", "",
         f"SD カードにまとめてコピーする：`python3 make_print.py --sd {variant} {idea} <SDカードの場所>`（hardware/print で）", "",
         "| 順 | ファイル | 材料 | 中身 | 時間（見積もり） | 量 |", "|---|---|---|---|---|---|"]
    total_m = total_g = 0
    for i, p in enumerate(plates, 1):
        prof, _, desc = PLATES[p]; s = info[p]
        mat = {"petg": "PETG", "petg_tall": "PETG", "adapter": "PETG（0.12mm）", "tpu": "TPU 95A"}[prof]
        opt = stand and (p.startswith("stand_") or p.startswith("wide_stand_"))
        L.append(f"| {i} | [`{p}.gcode`](../../gcode/{p}.gcode) | {mat} | {desc}{'（選んだものだけ）' if opt else ''} | {s['time']} | {s['grams']:.0f} g |")
        if not opt: total_m += s["minutes"]; total_g += s["grams"]
    h = total_m / 60
    L += ["", f"合計（{'スタンドを除く' if stand else 'すべて'}）：約 **{h:.1f} 時間・{total_g:.0f} g**。"
              f"キカイノイエの料金はフィラメント持ちこみで 330円/時 → 約 {math.ceil(h) * YEN_PER_H:,} 円（店のフィラメントなら 550円/時）。",
          "時間は PrusaSlicer の見積もりで、実際とずれることがある。"]
    if res:
        L += ["", "## 光造形（ELEGOO Mars4 Ultra）で刷る部品", "",
              "`resin/` の STL を、店のパソコンの ELEGOO の切り分けソフト（CHITUBOX など）に入れて、サポートを自動でつけて刷る。"
              "**光造形のデータ（.goo など）はここでは作れない**ため、STL を持っていく。", "",
              "| ファイル | 光造形にする理由 |", "|---|---|"]
        L += [f"| `resin/{r}.stl` | {RESIN[r]} |" for r in res]
        L += ["", "- 店の樹脂は水で洗えるタイプだけ。もろいので、ねじは軽くしめる（円盤はワッシャーをはさむ）",
              "- 光造形は1日 2,200円（1人1日）。洗いと仕上げの光当てで約2時間かかる"]
    L += ["", "部品の説明・組み立て・気をつけることは [../../README.md](../../README.md)。"]
    (d / "README.md").write_text("\n".join(L) + "\n", encoding="utf-8")

def to_sd(variant, idea, dest):
    dest = pathlib.Path(dest); dest.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(plates_for(idea, variant), 1):
        shutil.copy(CACHE / f"{p}.gcode", dest / f"{i:02d}_{p}.gcode"); print(dest / f"{i:02d}_{p}.gcode")
    for r in (resin_for(idea) if variant == "fff_resin" else []):
        shutil.copy(STL / f"{r}.stl", dest / f"resin_{r}.stl"); print(dest / f"resin_{r}.stl")

# ---------- UltiMaker S3・ABS グレーだけで作る（11/07） ----------
UM = HERE / "ultimaker_abs"
UM_W, UM_D = 230.0, 190.0     # S3 の台（Cura の ultimaker_s3.def.json）
# 板の名前: (設定, [部品…], 説明)。設定は ultimaker_abs/README.md の表と同じ名前
# 1枚の板は、大きい部品1つか、小物だけ（11/08：途中で失敗しても、刷り直すのがその板だけですむように）
UM_PLATES = {
    # 案1 の筒
    "abs_body_A":       ("ふつう", ["body_A_upper_ABS"], "上の殻 A（中に折って取る支え）"),
    "abs_body_B":       ("ふつう", ["body_B_lower_ABS"], "下の殻 B（中に折って取る支え）"),
    "abs_body_C":       ("ふつう", ["body_C_front_ABS"], "前の部屋 C（つば＝仕切りの壁を下にして立てる）"),
    "abs_body_small":   ("ふつう", ["body_E_ring_ABS", "body_F_cap_ABS", "body_G_lid_ABS"] + ["body_plunger_ABS"] * 3,
                         "小物：回すリング E・後ろのキャップ F・USB のふた G・押し棒 3本"),
    # 吹き口アダプター（どの案も同じ。2組ほしいときは2回刷る）
    "abs_adapter_set":  ("細かい", ["adapter_2_straw_side_ABS", "adapter_4_body_side_ABS", "adapter_5_cap_ABS", "adapter_6_collet_ABS"],
                         "吹き口アダプター ②④⑤⑥ 1組"),
    # 箱のコア（案7・15・17）
    "abs_core_back":    ("ふつう", ["core_back_ABS"], "コアの下の殻（案15・17）"),
    "abs_core_front":   ("ふつう", ["core_front_ABS"], "コアの上の殻（中に折って取る支え。案7・15・17）"),
    "abs_core_small":   ("ふつう", ["core_socket_ABS"] + ["plunger_ABS"] * 3, "小物：吹き口の受け・押し棒 3本（案7・15・17）"),
    "abs_core_small_match": ("ふつう", ["core_socket_ABS"] + ["plunger_long_ABS"] * 3, "小物：吹き口の受け・長い押し棒 3本（案17）"),
    "abs_core_dial":    ("細かい", ["core_dial_ABS", "core_dial_ABS"], "空気口の円盤 2枚（1枚は予備）"),
    "abs_necklace_back": ("ふつう", ["necklace_back_ABS"], "案7：ひもの輪つきのコアの下の殻"),
    # 案3・5・15・17 の外側
    "abs_pen_clip":     ("ふつう", ["pen_clip_ABS"], "案3 クリップ"),
    "abs_stand_plain":  ("ふつう", ["stand_plain_ABS"], "案5 ふつうのスタンド"),
    "abs_idcase_back":  ("ふつう", ["idcase_frame_back_ABS"], "案15：カードの枠の裏（コアを貼る板つき）"),
    "abs_idcase_front": ("ふつう", ["idcase_frame_front_ABS"], "案15：カードの枠の表（窓）"),
    "abs_match_sleeve": ("ふつう", ["match_sleeve_ABS"], "案17：外箱（立てて刷る）"),
    "abs_match_tray":   ("ふつう", ["match_tray_ABS"], "案17：内箱"),
    "abs_match_store":  ("ふつう", ["match_store_sleeve_ABS"], "案17：しまう箱（コアと内箱を入れる。立てて刷る。11/09）"),
    # 案1 のゆったり版（外径 32）
    "abs_bottle_C":     ("ふつう", ["bottle_C_front_ABS"], "ペットボトル形の前の部屋 C（先がカップ。つば＝仕切りの壁を下にして立てる）"),
    "abs_bottle_adapter": ("細かい", ["bottle_2_shoulder_ABS", "bottle_5_cap_ABS", "bottle_6_collet_ABS"], "ペットボトル形の吹き口：肩 ②・キャップ ⑤・つかみ ⑥ 1組"),
    "abs_wide_body_A":  ("ふつう", ["wide_body_A_upper_ABS"], "ゆったり版の上の殻 A（中に折って取る支え）"),
    "abs_wide_body_B":  ("ふつう", ["wide_body_B_lower_ABS"], "ゆったり版の下の殻 B（中に折って取る支え）"),
    "abs_wide_body_C":  ("ふつう", ["wide_body_C_front_ABS"], "ゆったり版の前の部屋 C（つばを下）"),
    "abs_wide_body_small": ("ふつう", ["wide_body_E_ring_ABS", "wide_body_F_cap_ABS", "body_G_lid_ABS"] + ["wide_body_plunger_ABS"] * 3,
                         "ゆったり版の小物：E・F・USB のふた G・押し棒 3本"),
    "abs_wide_pen_clip":  ("ふつう", ["wide_pen_clip_ABS"], "案3 クリップ（ゆったり版の筒用）"),
    "abs_wide_stand_plain": ("ふつう", ["wide_stand_plain_ABS"], "案5 ふつうのスタンド（ゆったり版用）"),
}
# 案ごとに刷る板と回数（上から順に）
TUBE = [("abs_body_A", 1), ("abs_body_B", 1), ("abs_body_C", 1), ("abs_body_small", 1), ("abs_adapter_set", 2)]
WIDE = [("abs_wide_body_A", 1), ("abs_wide_body_B", 1), ("abs_wide_body_C", 1), ("abs_wide_body_small", 1), ("abs_adapter_set", 2)]
CORE = [("abs_core_back", 1), ("abs_core_front", 1), ("abs_core_small", 1), ("abs_core_dial", 1), ("abs_adapter_set", 2)]
UM_IDEAS = {
    "an01_tube":     ("案1 筒（基本の本体）", TUBE),
    "an03_pen":      ("案3 ペン型（案1＋クリップ）", TUBE + [("abs_pen_clip", 1)]),
    "an05_stand":    ("案5 スタンド（案1＋ふつうのスタンド）", TUBE + [("abs_stand_plain", 1)]),
    "an07_necklace": ("案7 ネックレス", [("abs_necklace_back", 1)] + CORE[1:]),
    "an15_idcase":   ("案15 社員証ケース", CORE + [("abs_idcase_back", 1), ("abs_idcase_front", 1)]),
    "an17_match":    ("案17 マッチ箱", [("abs_core_back", 1), ("abs_core_front", 1), ("abs_core_small", 1), ("abs_core_dial", 1),
                                         ("abs_adapter_set", 2), ("abs_match_store", 1), ("abs_match_tray", 1)]),
    "an01b_tube_bottle": ("案1 筒・ペットボトル形", [("abs_body_A", 1), ("abs_body_B", 1), ("abs_bottle_C", 1), ("abs_body_small", 1), ("abs_bottle_adapter", 2)]),
    "an01w_tube_wide":  ("案1 筒・ゆったり版（外径 32）", WIDE),
    "an03w_pen_wide":   ("案3 ペン型・ゆったり版", WIDE + [("abs_wide_pen_clip", 1)]),
    "an05w_stand_wide": ("案5 スタンド・ゆったり版（ふつうのスタンド）", WIDE + [("abs_wide_stand_plain", 1)]),
}

def ufp_info(name):
    """.ufp の中の G-code の見出しから（秒, グラム）。なければ None"""
    import zipfile
    f = UM / "ufp" / f"{name}.ufp"
    if not f.exists(): return None
    z = zipfile.ZipFile(f)
    head = z.read([n for n in z.namelist() if n.endswith(".gcode")][0])[:4000].decode("utf-8", "ignore")
    t = int(re.search(r";PRINT.TIME:(\d+)", head).group(1))
    v = float(re.search(r";EXTRUDER_TRAIN.0.MATERIAL.VOLUME_USED:([\d.]+)", head).group(1))
    return t, v * 1.04 / 1000          # ABS は約 1.04 g/cm3

def hm(sec):
    return f"{sec // 3600}時間{sec % 3600 // 60:02d}分" if sec >= 3600 else f"{sec // 60}分"

def layout_um(parts):
    """S3 の台に部品を並べる（大きいものから、行ごとに詰める）。真ん中にそろえた1つの形にする"""
    ms = sorted((trimesh.load(STL / f"{p}.stl") for p in parts), key=lambda t: -(t.extents[1] * 1000 + t.extents[0]))
    x = y = rowh = 0.0; placed = []
    for t in ms:
        w, h = t.extents[0], t.extents[1]
        if x > 0 and x + w > UM_W - 30:
            x, y, rowh = 0.0, y + rowh + GAP, 0.0
        t = t.copy(); t.apply_translation([x - t.bounds[0][0], y - t.bounds[0][1], -t.bounds[0][2]])
        placed.append(t); x += w + GAP; rowh = max(rowh, h)
    plate = trimesh.util.concatenate(placed)
    lo, hi = plate.bounds
    plate.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, 0])
    ext = plate.extents
    assert ext[0] < UM_W - 20 and ext[1] < UM_D - 20 and ext[2] < 190, ext   # ブリムと、2つ目のノズルの分のゆとり
    return plate

def ultimaker_abs():
    sys.stdout.reconfigure(encoding="utf-8")
    STL.mkdir(exist_ok=True)
    for name, m in abs_parts().items():
        tm = to_tm(m); tm.export(STL / f"{name}.stl")
        ext = tm.bounds[1] - tm.bounds[0]
        print(f"{name:26s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f}  watertight={tm.is_watertight}")
    tm = core_front_abs(); tm.export(STL / "core_front_ABS.stl")
    print(f"{'core_front_ABS':26s} {tm.extents[0]:6.1f} x {tm.extents[1]:6.1f} x {tm.extents[2]:6.1f}")
    for name, m in shapes_abs().items():
        tm = to_tm(m); tm.export(STL / f"{name}.stl")
        print(f"{name:26s} {tm.extents[0]:6.1f} x {tm.extents[1]:6.1f} x {tm.extents[2]:6.1f}  watertight={tm.is_watertight}")
    for n in FROM_SHAPES:
        shutil.copy(SHAPES_STL / f"{n}.stl", STL / f"{n}.stl")      # いつも shapes の新しい STL を使う（oira0822 さんの直しを取りこむ）
    try:
        for name, m in wide_parts().items():                           # ゆったり版の部品（main と同じもの）
            to_tm(m).export(STL / f"{name}.stl")
    except AssertionError as e:
        # manifold3d 3.5.4（Windows）は、形を「かたまりごとに分ける」計算もくずれ、body_wide.check が通らない。
        # そのときは、ほかの PC で作ってコミットしてある stl/wide_*.stl をそのまま使う（11/07）
        print(f"ゆったり版は作り直さず、今の stl/wide_*.stl を使う（{e}）")
    t = trimesh.load(STL / "wide_body_C_front.stl")                    # ABS 版の C：つば（仕切りの壁）を下に（直径 21 の橋がなくなる）
    t.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0])); t.apply_translation(-t.bounds[0])
    to_tm(bed_chamfer(Manifold(Mesh(vert_properties=np.asarray(t.vertices, dtype=np.float32), tri_verts=np.asarray(t.faces, dtype=np.uint32))))).export(STL / "wide_body_C_front_ABS.stl")
    for name in ("wide_body_A_upper", "wide_body_B_lower"):            # ABS 版：内側の天井の下に、折って取る支え
        auto_breakaway(name).export(STL / f"{name}_ABS.stl")
        print(f"{name}_ABS（支えつき）")
    (UM / "plates").mkdir(parents=True, exist_ok=True)
    for name, (_, parts, _) in UM_PLATES.items():
        plate = layout_um(parts); plate.export(UM / "plates" / f"{name}.stl")
        print(f"plate {name:22s} {plate.extents[0]:6.1f} x {plate.extents[1]:6.1f} x {plate.extents[2]:5.1f}")
    for idea in UM_IDEAS:
        write_um_readme(idea)

# 案ごとの説明（ultimaker_abs/<案>/README.md）の後ろに足すこと
UM_NOTES = {
    "an17_match": """
## しまう箱にした（11/09）

前の外箱（`abs_match_sleeve`）は、コアを入れたまま使う形だったが、**コアを差しこめなかった**（押し棒・円盤の軸・吹き口の受けのつばが当たる。組み立てた向きで部品の重なりを計算して確かめた）。
**コアは箱の外で使い、しまうときに内箱と一緒に入れる**形に変えた（`abs_match_store`）。内箱の入る所は前と同じ。

| 変えたところ | なぜ |
|---|---|
| コアの入る所を、ボタンの面の側へ 4.5mm 広げた（外箱の幅 54 → 58.5） | 押し棒（長いものは 2.8mm）と、円盤を M2 なべねじ＋ワッシャーで留めた所（約 3.9mm）がコアの面から出ている。入れても 0.8mm あまる |
| コアの入る所だけ、前へ 2mm のばした（長さ 77.2 → 79.2） | 吹き口の受けのつば（厚さ 2）が中に入る。受けの筒は前の壁の穴（直径 14.6）から出る |
| 押し棒の穴・円盤の窓・ボタンの印をなくした | コアは外で使うので要らない。横の穴がないので、ABS でもきれいに刷れる |
| 押し棒はふつうの長さ（`abs_core_small`） | 外の壁を通さないため。刷ってある長い押し棒（`abs_core_small_match`）のままでも、箱に入る |

- しまうとき：コアは**ボタンの面を外側（仕切りと反対）**に向け、吹き口の受けを前にして、後ろから差しこむ。受けの筒が前の壁の穴に入る。アダプター（②④⑤⑥）とストローは外して、内箱に入れる
- 差しこむ途中から奥まで、コア（押し棒・円盤・ねじ・受けつき）が箱に当たらないこと、内箱と当たらないことを計算で確かめた
- 前の外箱をすでに刷ってあって、切って使う場合は [sleeve_cut.svg](sleeve_cut.svg)（押し棒の面に幅 8.3 × 長さ 57.5 の切りこみ。受けのつばの角を丸める）
""",
}

def write_um_readme(idea):
    title, plates = UM_IDEAS[idea]
    d = UM / idea
    d.mkdir(parents=True, exist_ok=True)   # 消さずに上書き（OneDrive の中だと、フォルダを消せないことがある）
    L = [f"# {title}（UltiMaker S3・ABS グレーだけ）", "",
         "上から順に、1枚ずつ刷る。.ufp を USB メモリに入れて、S3 の画面から選ぶ。設定は [../README.md](../README.md)。"
         "1枚は大きい部品1つか小物だけなので、失敗したらその板だけ刷り直せばよい。", "",
         "| 順 | .ufp | 中身 | 回数 | 1回の時間 | 量 | 設定 |", "|---|---|---|---|---|---|---|"]
    tot_t = tot_g = 0; missing = []
    for i, (p, n) in enumerate(plates, 1):
        prof, _, desc = UM_PLATES[p]
        info = ufp_info(p)
        if info:
            L.append(f"| {i} | [`{p}.ufp`](../ufp/{p}.ufp) | {desc} | {n} | {hm(info[0])} | {info[1]:.0f} g | {prof} |")
            tot_t += info[0] * n; tot_g += info[1] * n
        else:
            L.append(f"| {i} | まだ（板の STL：[`{p}.stl`](../plates/{p}.stl)） | {desc} | {n} | | | {prof} |"); missing.append(p)
    L += ["", f"合計：約 {hm(int(tot_t))}・{tot_g:.0f} g" + ("" if not missing else f"（.ufp がまだの板 {len(missing)} 枚を除く。Cura で作る）")]
    (d / "README.md").write_text(chr(10).join(L) + chr(10) + UM_NOTES.get(idea, ""), encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--sd":
        to_sd(*sys.argv[2:5])
    elif len(sys.argv) == 2 and sys.argv[1] == "--ultimaker-abs":
        ultimaker_abs()
    else:
        main()
