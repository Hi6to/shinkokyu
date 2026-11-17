# 基板を作る（KiCad についている Python で実行）
#   1) 部品を置き、外形・銅を置かない場所・文字を入れて shinkokyu_carrier.kicad_pcb に保存
#   2) 配線のプログラム（route.py）のために、端子の形を pads.json に書き出す
import json
import os
import pcbnew
from sexpr import parse, find, find1
from design import PARTS
import layout as L

import variant
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = variant.ROOT
PCB = os.path.join(ROOT, variant.PROJECT + ".kicad_pcb")
SCH = os.path.join(ROOT, variant.PROJECT + ".kicad_sch")
PADS = os.path.join(HERE, "pads_%s.json" % variant.V)
KFP = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\share\kicad\footprints")
MM = pcbnew.FromMM
OX, OY = 100.0, 100.0   # 図面の中で基板を置く位置（layout.py の座標に足す）


def V(x, y):
    return pcbnew.VECTOR2I(MM(x + OX), MM(y + OY))


def mm(v, o):
    return pcbnew.ToMM(v) - o


POWER = ("GND", "+3V3", "VBUS")


def pcb_net(n):
    """回路図と同じネットの名前（ラベルでつないだネットは、先頭に / が付く）"""
    return n if n in POWER else "/" + n


def sch_paths():
    """回路図の記号の番号（基板の部品と回路図を対応させるため）"""
    t = parse(open(SCH, encoding="utf-8").read())
    root = find1(t, "uuid")[1]
    out = {}
    for s in find(t, "symbol"):
        props = {p[1]: p[2] for p in find(s, "property")}
        out[props["Reference"]] = ("/%s/%s" % (root, find1(s, "uuid")[1]), props.get("Datasheet", ""))
    return out


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(variant.LIBDIR, "shinkokyu.pretty") if lib == "shinkokyu" else os.path.join(KFP, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_line(board, x1, y1, x2, y2, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x1, y1))
    s.SetEnd(V(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def add_text(board, x, y, txt, size, layer, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(V(x, y))
    t.SetLayer({"F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS}[layer])
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(max(0.12, size * 0.15)))
    t.SetTextAngleDegrees(angle)
    if layer.startswith("B."):
        t.SetMirrored(True)
    board.Add(t)


def rule_area(board, x1, y1, x2, y2, layers, name):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(MM(x + OX), MM(y + OY))
    board.Add(z)


def build():
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    # 設計ルール（JLCPCB の2層の基板で作れる範囲より少し余裕をもたせる）
    ds = board.GetDesignSettings()
    ds.m_MinClearance = MM(0.15)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_TrackMinWidth = MM(0.15)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_ViasMinAnnularWidth = MM(0.13)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_HoleClearance = MM(0.25)
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_MinSilkTextHeight = MM(0.8)
    ds.m_MinSilkTextThickness = MM(0.12)
    ds.m_MinResolvedSpokes = 1
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(0.15))
    nc.SetTrackWidth(MM(0.2))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))
    nets = {}
    for p in PARTS.values():
        for n in p["pins"].values():
            if n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, pcb_net(n))
                board.Add(ni)
                nets[n] = ni
    paths = sch_paths()
    for ref, p in PARTS.items():
        fp = load_fp(p["fp"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        if ref in paths:
            fp.SetPath(pcbnew.KIID_PATH(paths[ref][0]))
            fp.SetField("Datasheet", paths[ref][1])
        x, y, rot, back = L.PLACE[ref]
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        if back:  # 基板に入れてからでないと裏返せない
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        attrs = fp.GetAttributes() & ~pcbnew.FP_EXCLUDE_FROM_BOM   # 回路図の部品表と同じにする
        if p["hand"] or not p["lcsc"] or p["dnp"]:
            attrs |= pcbnew.FP_EXCLUDE_FROM_POS_FILES               # JLCPCB では付けない
        fp.SetAttributes(attrs)
        if p["lcsc"]:
            fp.SetField("LCSC", p["lcsc"])
        fp.SetField("JLC", "DNP" if p["dnp"] else ("手で付ける" if (p["hand"] or not p["lcsc"]) else "JLC"))
        for f in fp.GetFields():
            if f.GetName() in ("LCSC", "JLC"):
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            n = p["pins"].get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
            elif pad.GetNumber() and pad.IsOnCopperLayer():   # 回路図でつながない端子（KiCad と同じ名前にする）
                nc = "unconnected-(%s-NC-Pad%s)" % (ref, pad.GetNumber())
                ni = pcbnew.NETINFO_ITEM(board, nc)
                board.Add(ni)
                pad.SetNet(ni)
        # ボタンは、同じ番号の足が部品の中でつながっている
        if ref.startswith("SW"):
            fp.SetDuplicatePadNumbersAreJumpers(True)
        # 部品の名前：つなぐ所や切り替える所（J・JP・TP・SW）だけ表に印刷する
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        r.SetTextThickness(MM(0.13))
        r.SetVisible(ref in L.REF_POS)
        if ref in L.REF_POS:
            r.SetPosition(V(*L.REF_POS[ref]))
            r.SetTextAngleDegrees(0)
    # 外形
    pts = L.OUTLINE + [L.OUTLINE[0]]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        add_line(board, x1, y1, x2, y2, pcbnew.Edge_Cuts)
    # 切り離す線
    add_line(board, L.CUT_X, -L.NECK_W / 2 + 0.3, L.CUT_X, L.NECK_W / 2 - 0.3, pcbnew.F_SilkS, 0.15)
    add_line(board, L.CUT_X, -L.NECK_W / 2 + 0.3, L.CUT_X, L.NECK_W / 2 - 0.3, pcbnew.B_SilkS, 0.15)
    # 銅を置かない場所
    for x1, y1, x2, y2, lay, name in L.KEEPOUT:
        layers = [pcbnew.F_Cu, pcbnew.B_Cu] if lay == "both" else [pcbnew.F_Cu]
        rule_area(board, x1, y1, x2, y2, layers, name)
    # 文字
    for x, y, txt, size, layer, ang in L.TEXTS:
        add_text(board, x, y, txt, size, layer, ang)
    for ref, names in L.PINLABELS.items():
        fp = board.FindFootprintByReference(ref)
        for pad in fp.Pads():
            i = int(pad.GetNumber()) - 1
            px, py = mm(pad.GetPosition().x, OX), mm(pad.GetPosition().y, OY)
            if ref == "J7":
                add_text(board, px + 2.6, py, names[i], 0.8, "B.SilkS", 0)
            else:
                k = 2.8 if ref == "J3" else 2.4
                dy = k if py < 0 else -k
                add_text(board, px, py + dy, names[i], 0.8, "B.SilkS", 90)
    return board


def dump_pads(board, path):
    out = {"pads": [], "outline": L.OUTLINE, "holes": [], "keepout": [], "nets": {}}
    ux, uy = L.PLACE["U1"][:2]
    if variant.V == "A":   # A版だけ、XIAO の裏の BAT+ に届く窓がある
        out["holes"].append([ux - 1.2, uy + 2.6, ux + 2.0, uy + 6.3])
    for x1, y1, x2, y2, lay, name in L.KEEPOUT:
        out["keepout"].append([x1, y1, x2, y2, lay])
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            layers = []
            if pad.IsOnLayer(pcbnew.F_Cu):
                layers.append("F")
            if pad.IsOnLayer(pcbnew.B_Cu):
                layers.append("B")
            polys = {}
            for l, lid in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
                if l in layers:
                    ps = pad.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE)
                    o = ps.Outline(0)
                    polys[l] = [[mm(o.CPoint(i).x, OX), mm(o.CPoint(i).y, OY)] for i in range(o.PointCount())]
            drill = pcbnew.ToMM(pad.GetDrillSize().x) if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0
            out["pads"].append({"ref": fp.GetReference(), "num": pad.GetNumber(), "net": pad.GetNetname(),
                                "x": mm(pad.GetPosition().x, OX), "y": mm(pad.GetPosition().y, OY),
                                "layers": layers, "poly": polys, "drill": drill})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    b = build()
    pcbnew.SaveBoard(PCB, b)
    dump_pads(b, PADS)
    print("ok", len(list(b.GetFootprints())), "footprints")
