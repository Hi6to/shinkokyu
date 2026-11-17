# routes.json の線とビアを基板に入れ、GND の面（ベタ）を作って塗りつぶす（KiCad の Python で実行）
import json
import math
import os
import pcbnew
import layout as L
from make_pcb import PCB, V, MM, HERE
import variant


def zone(board, net, layer, pts, name):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetZoneName(name)
    z.SetLocalClearance(MM(0.25))
    z.SetMinThickness(MM(0.25))
    z.SetThermalReliefGap(MM(0.3))
    z.SetThermalReliefSpokeWidth(MM(0.35))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(0)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(MM(x + 100.0), MM(y + 100.0))
    board.Add(z)
    return z


def gnd_groups(board, gnd, zf, zb):
    """GND の銅（ベタの島・線・ビア・端子）が、いくつのまとまりに分かれているか"""
    code = gnd.GetNetCode()
    pf, pb = zf.GetFilledPolysList(pcbnew.F_Cu), zb.GetFilledPolysList(pcbnew.B_Cu)
    polys = {"F": pf, "B": pb}
    nodes = [("isl", "F", i) for i in range(pf.OutlineCount())] + [("isl", "B", i) for i in range(pb.OutlineCount())]
    segs = [t for t in board.GetTracks() if t.GetNetCode() == code and t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetNetCode() == code and t.GetClass() == "PCB_VIA"]
    pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    nodes += [("seg", k) for k in range(len(segs))] + [("via", k) for k in range(len(vias))] +              [("pad", k) for k in range(len(pads))]
    parent = {n: n for n in nodes}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def join(a, b):
        parent[find(a)] = find(b)

    def island(l, pt):
        ps = polys[l]
        if not ps.Contains(pt):
            return None
        for i in range(ps.OutlineCount()):
            if ps.Outline(i).PointInside(pt):
                return ("isl", l, i)
        return None

    def lname(layer):
        return "F" if layer == pcbnew.F_Cu else "B"

    # 同じ部品の同じ番号の端子（例：A版の XIAO の穴と縁の端子）は重なっていて、つながっている
    same = {}
    for j, p in enumerate(pads):
        key = (p.GetParentFootprint().GetReference(), p.GetNumber())
        if key in same:
            join(("pad", j), ("pad", same[key]))
        else:
            same[key] = j
    for k, t in enumerate(segs):
        l = lname(t.GetLayer())
        for pt in (t.GetStart(), t.GetEnd()):
            isl = island(l, pt)
            if isl:
                join(("seg", k), isl)
            for j, u in enumerate(segs):
                if j != k and u.GetLayer() == t.GetLayer() and u.HitTest(pt, 0):
                    join(("seg", k), ("seg", j))
            for j, v in enumerate(vias):
                if v.HitTest(pt, 0):
                    join(("seg", k), ("via", j))
            for j, p in enumerate(pads):
                if p.IsOnLayer(t.GetLayer()) and p.HitTest(pt, 0):
                    join(("seg", k), ("pad", j))
    for j, v in enumerate(vias):
        for l in ("F", "B"):
            isl = island(l, v.GetPosition())
            if isl:
                join(("via", j), isl)
    for j, p in enumerate(pads):
        # 端子とベタは、端子のまわりの細い橋（スポーク）でつながる。端子のすぐ外の点がベタの中かを調べる
        bb = p.GetBoundingBox()
        cx, cy = p.GetPosition().x, p.GetPosition().y
        hx, hy = bb.GetWidth() / 2, bb.GetHeight() / 2
        gap = MM(0.15)
        pts = [p.GetPosition()]
        for ang in range(0, 360, 15):
            t = math.radians(ang)
            pts.append(pcbnew.VECTOR2I(int(cx + (hx + gap) * math.cos(t)), int(cy + (hy + gap) * math.sin(t))))
        for l, lid in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
            if p.IsOnLayer(lid):
                for pt in pts:
                    isl = island(l, pt)
                    if isl:
                        join(("pad", j), isl)
    groups = {}
    for n in nodes:
        groups.setdefault(find(n), []).append(n)
    return groups, find, polys, island


def bridge_islands(board, gnd, zf, zb, rounds=20):
    """塗りつぶした GND の面のうち、ほかとつながっていない島を探して、ビアでつなぐ"""
    vr = L.VIA[0] / 2
    added = 0
    for _ in range(rounds):
        groups, find, polys, island = gnd_groups(board, gnd, zf, zb)
        # 島をふくむまとまりだけを数える（島のない小さな銅は、ベタの外の線など）
        groups = {g: ns for g, ns in groups.items() if any(n[0] in ("isl", "pad") for n in ns)}
        if len(groups) <= 1:
            break

        def size(ns):
            return sum((polys[n[1]].Outline(n[2]).Area() if n[0] == "isl" else 0) for n in ns)
        main = max(groups, key=lambda g: size(groups[g]))
        holes = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
        holes += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
        best = None
        bb = board.GetBoardEdgesBoundingBox()
        step = MM(0.2)
        for x in range(bb.GetLeft(), bb.GetRight(), step):
            for y in range(bb.GetTop(), bb.GetBottom(), step):
                c = pcbnew.VECTOR2I(x, y)
                a, b = island("F", c), island("B", c)
                if not (a and b) or find(a) == find(b) or main not in (find(a), find(b)):
                    continue
                ring = [pcbnew.VECTOR2I(int(x + MM(vr + 0.1) * math.cos(t)), int(y + MM(vr + 0.1) * math.sin(t)))
                        for t in [k * math.pi / 4 for k in range(8)]]
                if not all(polys["F"].Contains(q) and polys["B"].Contains(q) for q in ring):
                    continue
                if any((h.x - x) ** 2 + (h.y - y) ** 2 < MM(L.VIA[0] + 0.4) ** 2 for h in holes):
                    continue
                best = c
                break
            if best:
                break
        if not best:
            print("  つなぐ場所が見つからないまとまり:", len(groups) - 1)
            for g, ns in groups.items():
                if g != main:
                    print("   ", [n for n in ns if n[0] == "pad"][:5], "島", [n for n in ns if n[0] == "isl"])
            break
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(best)
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetWidth(MM(L.VIA[0]))
        via.SetDrill(MM(L.VIA[1]))
        via.SetNet(gnd)
        board.Add(via)
        added += 1
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added


def poly_points(ps, i):
    def chain(c):
        return [[pcbnew.ToMM(c.CPoint(k).x) - 100.0, pcbnew.ToMM(c.CPoint(k).y) - 100.0] for k in range(c.PointCount())]
    return {"outline": chain(ps.Outline(i)), "holes": [chain(ps.Hole(i, h)) for h in range(ps.HoleCount(i))]}


def dump_isolated(board, gnd, zf, zb):
    """ほかとつながっていない GND のまとまりを、配線のプログラムで線を足せるように書き出す"""
    groups, find, polys, island = gnd_groups(board, gnd, zf, zb)
    groups = {g: ns for g, ns in groups.items() if any(n[0] in ("isl", "pad") for n in ns)}
    path = os.path.join(HERE, "gnd_islands_%s.json" % variant.V)
    if len(groups) <= 1:
        if os.path.exists(path):
            os.remove(path)
        return 0

    def size(ns):
        return sum((polys[n[1]].Outline(n[2]).Area() if n[0] == "isl" else 0) for n in ns)
    main = max(groups, key=lambda g: size(groups[g]))

    def islands(ns):
        return [dict(layer=n[1], **poly_points(polys[n[1]], n[2])) for n in ns if n[0] == "isl"]
    out = {"main": islands(groups[main]), "groups": [islands(ns) for g, ns in groups.items() if g != main]}
    json.dump(out, open(path, "w", encoding="utf-8"))
    return len(out["groups"])


def main():
    board = pcbnew.LoadBoard(PCB)
    r = json.load(open(os.path.join(HERE, "routes_%s.json" % variant.V), encoding="utf-8"))
    nets = {n: board.FindNet(n) for n in {t["net"] for t in r["tracks"]} | {v["net"] for v in r["vias"]} | {"GND"}}
    for t in r["tracks"]:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(V(t["x1"], t["y1"]))
        tr.SetEnd(V(t["x2"], t["y2"]))
        tr.SetWidth(MM(t["w"]))
        tr.SetLayer(pcbnew.F_Cu if t["layer"] == "F" else pcbnew.B_Cu)
        tr.SetNet(nets[t["net"]])
        board.Add(tr)
    stitch = []
    for v in r["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(V(v["x"], v["y"]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetWidth(MM(L.VIA[0]))
        via.SetDrill(MM(L.VIA[1]))
        via.SetNet(nets[v["net"]])
        board.Add(via)
        if v.get("stitch"):
            stitch.append((via, v))
    gnd = nets["GND"]
    zone(board, gnd, pcbnew.B_Cu, L.OUTLINE, "GND_B")
    x0 = L.NO_TOP_POUR[2]
    top = [(max(x, x0), y) for x, y in L.OUTLINE]
    zone(board, gnd, pcbnew.F_Cu, top, "GND_F")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    # 表と裏の両方のベタの中にない「つなぐためのビア」は、役に立たないので外す
    zf = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.F_Cu][0]
    zb = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.B_Cu][0]
    pf, pb = zf.GetFilledPolysList(pcbnew.F_Cu), zb.GetFilledPolysList(pcbnew.B_Cu)
    removed = 0
    for via, v in stitch:
        p = via.GetPosition()
        if not (pf.Contains(p) and pb.Contains(p)):
            board.Remove(via)
            removed += 1
    if removed:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print("役に立たないビアを", removed, "個外した")
    added = bridge_islands(board, gnd, zf, zb)
    print("分かれた GND の面をつなぐビアを", added, "個足した")
    pcbnew.SaveBoard(PCB, board)
    n = dump_isolated(board, gnd, zf, zb)
    print("ほかとつながっていない GND のまとまり:", n)
    return n
    print("ok", len(r["tracks"]), "tracks", len(r["vias"]), "vias")


if __name__ == "__main__":
    raise SystemExit(2 if main() else 0)
