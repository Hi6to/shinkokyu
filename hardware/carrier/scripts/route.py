# 配線のプログラム（ふつうの Python ＋ numpy・scipy で実行）
# pads.json（make_pcb.py が書き出す）を読み、0.1mm の格子の上で、表と裏の2層の線を引く。
# 引けない線があると、邪魔をしている線をいったん外して引き直す（引き直し方式）。
# 結果は routes.json に書き出し、apply_routes.py で基板に入れる。
import heapq
import json
import math
import os
import sys
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as L  # noqa: E402
from variant import V  # noqa: E402

G = 0.1                     # 格子の間隔（mm）
OX, OY = -1.0, -11.5        # 格子の原点
NX, NY = 700, 230
LAYERS = ("F", "B")
VIA_D, VIA_DRILL = L.VIA
FINE_PITCH = ("U2", "U3")   # 端子の間がせまい部品。近くでは線を細くする
NECK_W = 0.2
NECK_RADIUS = 1.0
VIA_COST = 14.0             # ビア1つの重み（格子の数）
BOTTOM_COST = 1.4           # 裏の層の重み（裏は GND の面を広く残したい）
CONFLICT_COST = 40.0        # ほかの線と重なる格子の重み（引き直しのとき）
HISTORY_STEP = 6.0          # 何度も取り合いになる場所を、だんだん通りにくくする
MAX_RIPS = 10               # 1本の線を外してよい回数


def width(net):
    return L.WIDTH.get(net.lstrip("/"), L.DEFAULT_WIDTH)


xs_ = OX + (np.arange(NX) + 0.5) * G
ys_ = OY + (np.arange(NY) + 0.5) * G
GX, GY = np.meshgrid(xs_, ys_, indexing="xy")  # 形は (NY, NX)
STEPS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
         (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]


def in_poly(poly):
    inside = np.zeros(GX.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if y1 == y2:
            continue
        cond = (GY >= min(y1, y2)) & (GY < max(y1, y2))
        xc = x1 + (GY - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (GX < xc)
    return inside


def in_rect(x1, y1, x2, y2):
    return (GX >= x1) & (GX <= x2) & (GY >= y1) & (GY <= y2)


_disks = {}


def disk(r):
    key = round(r, 4)
    if key not in _disks:
        k = int(math.ceil(r / G))
        yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
        _disks[key] = (xx * xx + yy * yy) * G * G <= r * r + 1e-9
    return _disks[key]


def stamp(arr, cells, r, value=True):
    d = disk(r)
    k = d.shape[0] // 2
    for (i, j) in cells:
        i0, i1 = max(0, i - k), min(NY, i + k + 1)
        j0, j1 = max(0, j - k), min(NX, j + k + 1)
        sub = d[i0 - (i - k):i1 - (i - k), j0 - (j - k):j1 - (j - k)]
        arr[i0:i1, j0:j1][sub] = value


def edt(mask):
    """mask（True の場所）からの距離（mm）"""
    if not mask.any():
        return np.full(GX.shape, 99.0)
    return ndimage.distance_transform_edt(~mask) * G


class Router:
    def __init__(self, data):
        board = in_poly(data["outline"])
        for h in data["holes"]:
            board &= ~in_rect(*h)
        self.edge_dist = ndimage.distance_transform_edt(board) * G
        self.keep = {}
        for l in LAYERS:
            k = np.zeros(GX.shape, bool)
            for x1, y1, x2, y2, lay in data["keepout"]:
                if lay == "both" or lay == l:
                    k |= in_rect(x1, y1, x2, y2)
            self.keep[l] = edt(k)
        self.netnames = sorted({p["net"] for p in data["pads"] if p["net"]})
        self.nid = {n: i for i, n in enumerate(self.netnames)}
        self.pad_owner = {l: np.full(GX.shape, -1, np.int32) for l in LAYERS}
        self.smd = np.zeros(GX.shape, bool)
        fine = np.zeros(GX.shape, bool)
        drills = []
        terms = {}
        for p in data["pads"]:
            nid = self.nid.get(p["net"], -2)
            cells = {}
            for l in p["layers"]:
                m = in_poly(p["poly"][l])
                if not m.any():
                    i, j = self.ij(p["x"], p["y"])
                    m[i, j] = True
                po = self.pad_owner[l]
                po[m & (po == -1)] = nid
                cells[l] = m
                if p["drill"] == 0:
                    self.smd |= m
                    if p["ref"] in FINE_PITCH:
                        fine |= m
            if p["drill"]:
                drills.append((p["x"], p["y"], p["drill"]))
            if p["net"]:
                t = terms.setdefault(p["net"], {}).setdefault(p["ref"] + "." + p["num"], {})
                for l, c in cells.items():
                    t[l] = t.get(l, np.zeros(GX.shape, bool)) | c
        self.terms = {n: list(v.items()) for n, v in terms.items()}
        self.near_fine = edt(fine) <= NECK_RADIUS
        self.smd_dist = edt(self.smd)
        hb = np.zeros(GX.shape, bool)
        for x, y, d in drills:
            hb |= (GX - x) ** 2 + (GY - y) ** 2 <= (d / 2 + VIA_DRILL / 2 + 0.3) ** 2
        self.hole_block = hb
        self.cu = {}        # net -> {layer: 線とビアの銅}
        self.routes = {}    # net -> (tracks, vias)
        self.hist = {l: np.zeros(GX.shape) for l in LAYERS}
        self.static_dist = {}

    def ij(self, x, y):
        return int((y - OY) / G), int((x - OX) / G)

    def xy(self, i, j):
        return OX + (j + 0.5) * G, OY + (i + 0.5) * G

    def pad_dist(self, nid):
        if nid not in self.static_dist:
            self.static_dist[nid] = {l: edt((self.pad_owner[l] != -1) & (self.pad_owner[l] != nid)) for l in LAYERS}
        return self.static_dist[nid]

    def masks(self, net, w, soft):
        nid = self.nid[net]
        pd = self.pad_dist(nid)
        other = {l: np.zeros(GX.shape, bool) for l in LAYERS}
        fixed = {l: np.zeros(GX.shape, bool) for l in LAYERS}   # 外さない線（GND）
        for m, cu in self.cu.items():
            if m != net:
                for l in LAYERS:
                    (fixed if m == "GND" else other)[l] |= cu[l]
        od = {l: edt(other[l]) for l in LAYERS}
        fd = {l: edt(fixed[l]) for l in LAYERS}
        pd = {l: np.minimum(pd[l], fd[l]) for l in LAYERS}
        ok, cost = {}, {}
        for l in LAYERS:
            need = L.CLEARANCE + w / 2 + G / 2
            needn = L.CLEARANCE + NECK_W / 2 + G / 2
            base = (self.edge_dist >= L.EDGE_CLEARANCE + w / 2) & (self.keep[l] >= w / 2 + G)
            basen = (self.edge_dist >= L.EDGE_CLEARANCE + NECK_W / 2) & (self.keep[l] >= NECK_W / 2 + G)
            hard = base & (pd[l] >= need)
            hardn = basen & (pd[l] >= needn) & self.near_fine
            clash = od[l] < need
            clashn = od[l] < needn
            if soft:
                ok[l] = hard | hardn
                c = np.where(self.near_fine & hardn & ~hard, clashn, clash)
                cost[l] = (1.0 if l == "F" else BOTTOM_COST) + self.hist[l] + CONFLICT_COST * c
            else:
                ok[l] = (hard & ~clash) | (hardn & ~clashn)
                cost[l] = (1.0 if l == "F" else BOTTOM_COST) + self.hist[l]
        vr = VIA_D / 2
        via = (self.edge_dist >= L.EDGE_CLEARANCE + vr) & (self.smd_dist >= vr + 0.15) & ~self.hole_block & ~self.near_fine
        vclash = np.zeros(GX.shape, bool)
        for l in LAYERS:
            via &= (pd[l] >= L.CLEARANCE + vr + G / 2) & (self.keep[l] >= vr + G)
            vclash |= od[l] < L.CLEARANCE + vr + G / 2
        if not soft:
            via &= ~vclash
        for _, cells in self.terms[net]:
            for l, c in cells.items():
                ok[l] = ok[l] | c
        return ok, cost, via, vclash

    def search(self, tree, targets, ok, cost, via, vclash, soft):
        tgt = {l: np.full(GX.shape, -1, np.int32) for l in LAYERS}
        cx = []
        for t, cells in enumerate(targets):
            for l, c in cells.items():
                tgt[l][c & (tgt[l] == -1)] = t
            ys, xs = np.nonzero(np.logical_or.reduce(list(cells.values())))
            cx.append((xs.mean(), ys.mean(), (xs.max() - xs.min() + ys.max() - ys.min()) / 4))

        def h(i, j):
            return min(max(0.0, math.hypot(j - x, i - y) - r) for x, y, r in cx)

        INF = 1e18
        dist = [np.full(GX.shape, INF), np.full(GX.shape, INF)]
        prev = {}
        pq = []
        for li, l in enumerate(LAYERS):
            ys, xs = np.nonzero(tree[l])
            for i, j in zip(ys.tolist(), xs.tolist()):
                dist[li][i, j] = 0.0
                heapq.heappush(pq, (h(i, j), 0.0, li, i, j))
        oks = (ok["F"], ok["B"])
        costs = (cost["F"], cost["B"])
        tg = (tgt["F"], tgt["B"])
        while pq:
            f, d, li, i, j = heapq.heappop(pq)
            if d > dist[li][i, j]:
                continue
            t = tg[li][i, j]
            if t >= 0:
                path = [(li, i, j)]
                key = (li, i, j)
                while key in prev:
                    key = prev[key]
                    path.append(key)
                return path[::-1], int(t)
            okl, cl, dl = oks[li], costs[li], dist[li]
            for di, dj, c in STEPS:
                ni, nj = i + di, j + dj
                if 0 <= ni < NY and 0 <= nj < NX and okl[ni, nj]:
                    if di and dj and not (okl[i, nj] and okl[ni, j]):
                        continue
                    nd = d + c * cl[ni, nj]
                    if nd < dl[ni, nj]:
                        dl[ni, nj] = nd
                        prev[(li, ni, nj)] = (li, i, j)
                        heapq.heappush(pq, (nd + h(ni, nj), nd, li, ni, nj))
            if via[i, j]:
                lo = 1 - li
                nd = d + VIA_COST + (CONFLICT_COST * 4 if (soft and vclash[i, j]) else 0)
                if oks[lo][i, j] and nd < dist[lo][i, j]:
                    dist[lo][i, j] = nd
                    prev[(lo, i, j)] = (li, i, j)
                    heapq.heappush(pq, (nd + h(i, j), nd, lo, i, j))
        return None

    def route_net(self, net, soft):
        """このネットの線を全部引く。うまくいけば (tracks, vias, cu) を返す（まだ基板には入れない）"""
        w = width(net)
        terms = self.terms[net]
        ok, cost, via, vclash = self.masks(net, w, soft)
        tree = {l: terms[0][1].get(l, np.zeros(GX.shape, bool)).copy() for l in LAYERS}
        cu = {l: np.zeros(GX.shape, bool) for l in LAYERS}
        tracks, vias = [], []
        left = list(range(1, len(terms)))
        while left:
            res = self.search(tree, [terms[k][1] for k in left], ok, cost, via, vclash, soft)
            if res is None:
                return None, [terms[k][0] for k in left]
            path, hit = res
            k = left.pop(hit)
            for l, c in terms[k][1].items():
                tree[l] |= c
            self.to_copper(net, w, path, tree, cu, tracks, vias)
        return (tracks, vias, cu), []

    def to_copper(self, net, w, path, tree, cu, tracks, vias):
        segs, cur = [], []
        for li, i, j in path:
            if cur and cur[-1][0] != li:
                segs.append(cur)
                x, y = self.xy(i, j)
                vias.append({"net": net, "x": x, "y": y})
                for l in LAYERS:
                    stamp(cu[l], [(i, j)], VIA_D / 2)
                    tree[l][i, j] = True
                cur = []
            cur.append((li, i, j))
        segs.append(cur)
        runs = []
        for seg in segs:
            if not seg:
                continue
            cur2 = [seg[0]]
            for a, b in zip(seg, seg[1:]):
                if w > NECK_W and self.near_fine[a[1], a[2]] != self.near_fine[b[1], b[2]]:
                    runs.append((cur2 + [b], NECK_W if self.near_fine[a[1], a[2]] else w))
                    cur2 = [b]
                else:
                    cur2.append(b)
            runs.append((cur2, NECK_W if (w > NECK_W and self.near_fine[cur2[0][1], cur2[0][2]]) else w))
        for seg, ww in runs:
            l = LAYERS[seg[0][0]]
            cells = [(i, j) for _, i, j in seg]
            stamp(cu[l], cells, ww / 2)
            for i, j in cells:
                tree[l][i, j] = True
            pts = [cells[0]]
            for a, b, c in zip(cells, cells[1:], cells[2:]):
                if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                    pts.append(b)
            if len(cells) > 1:
                pts.append(cells[-1])
            for (i1, j1), (i2, j2) in zip(pts, pts[1:]):
                x1, y1 = self.xy(i1, j1)
                x2, y2 = self.xy(i2, j2)
                tracks.append({"net": net, "layer": l, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": ww})

    def victims(self, net, cu):
        """新しい線とぶつかるネット"""
        out = []
        dil = {l: edt(cu[l]) for l in LAYERS}
        for m, mcu in self.cu.items():
            if m == net or m == "GND":   # GND の短い線は外さない
                continue
            need = L.CLEARANCE + G
            for l in LAYERS:
                if (mcu[l] & (dil[l] < need)).any():
                    out.append(m)
                    break
        return out

    def run(self, nets):
        queue = list(nets)
        rips = {n: 0 for n in nets}
        failed = []
        steps = 0
        while queue and steps < 400:
            steps += 1
            net = queue.pop(0)
            res, _ = self.route_net(net, soft=False)
            if res is None:
                res, miss = self.route_net(net, soft=True)
                if res is None:
                    print("  あきらめた:", net, miss, flush=True)
                    failed.append(net)
                    continue
                vs = self.victims(net, res[2])
                for v in vs:
                    for l in LAYERS:
                        self.hist[l] += HISTORY_STEP * (self.cu[v][l] & res[2][l])
                    del self.cu[v]
                    del self.routes[v]
                    rips[v] += 1
                    if rips[v] > MAX_RIPS:
                        print("  何度も外された:", v, flush=True)
                        if v not in failed:
                            failed.append(v)
                    elif v not in queue:
                        queue.append(v)
                print("  %s のために外した: %s" % (net, vs), flush=True)
            self.cu[net] = res[2]
            self.routes[net] = (res[0], res[1])
        failed += [n for n in queue if n not in failed]
        return [n for n in failed if n not in self.routes]


def order(r):
    def span(net):
        pts = []
        for _, cells in r.terms[net]:
            for c in cells.values():
                ys, xs = np.nonzero(c)
                pts.append((xs.mean(), ys.mean()))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))
    nets = [n for n in r.terms if len(r.terms[n]) > 1 and n != "GND"]
    nets.sort(key=span)
    return nets


def gnd_local(r):
    """部品の中の GND の端子どうしを、ほかの線より先に短くつなぐ"""
    net = "GND"
    w = width(net)
    ok, cost, via, vclash = r.masks(net, w, soft=False)
    names = dict(r.terms[net])
    cu = {l: np.zeros(GX.shape, bool) for l in LAYERS}
    tracks, vias = [], []
    for a, b in L.GND_LOCAL:
        tree = {l: names[a].get(l, np.zeros(GX.shape, bool)).copy() for l in LAYERS}
        res = r.search(tree, [names[b]], ok, cost, np.zeros(GX.shape, bool), vclash, False)
        if res is None:
            print("  GND の近い端子をつなげない:", a, b)
            continue
        r.to_copper(net, w, res[0], tree, cu, tracks, vias)
    r.cu[net] = cu
    r.routes[net] = (tracks, vias)


def place_gnd_via(r, i, j, cu, vias, through, via):
    x, y = r.xy(i, j)
    vias.append({"net": "GND", "x": x, "y": y})
    for l in LAYERS:
        stamp(cu[l], [(i, j)], VIA_D / 2)
        stamp(through[l], [(i, j)], VIA_D / 2)
    stamp(via, [(i, j)], VIA_D + 0.3, False)   # 穴どうしを 0.3mm 以上離す


def gnd_stitch(r):
    """表と裏の GND のベタをつなぐビアを、空いている所にまんべんなく置く"""
    net = "GND"
    _, _, via, _ = r.masks(net, width(net), soft=False)
    tracks, vias = r.routes[net]
    cu = r.cu[net]
    for v in vias:  # すでにあるビアの近くには置かない
        i, j = r.ij(v["x"], v["y"])
        stamp(via, [(i, j)], 2.0, False)
    # GND のベタが両面にできそうな所だけ（XIAO の下は表のベタがないので除く）
    x0 = L.NO_TOP_POUR[2]
    n = 0
    step = int(2.5 / G)
    for i in range(step // 2, NY, step):
        for j in range(step // 2, NX, step):
            x, y = r.xy(i, j)
            if x < x0 + 0.5:
                continue
            # 近くで置ける場所を探す
            found = None
            for di in range(-6, 7, 2):
                for dj in range(-6, 7, 2):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < NY and 0 <= jj < NX and via[ii, jj]:
                        found = (ii, jj)
                        break
                if found:
                    break
            if found:
                ii, jj = found
                xx, yy = r.xy(ii, jj)
                vias.append({"net": net, "x": xx, "y": yy, "stitch": True})
                for l in LAYERS:
                    stamp(cu[l], [(ii, jj)], VIA_D / 2)
                stamp(via, [(ii, jj)], 2.0, False)
                n += 1
    print("GND のベタをつなぐビア", n, "個")


def gnd_fanout(r, data, only=None):
    """GND の表の端子から、近くにビアを置いて裏の GND のベタにつなぐ。only を指定すると、その端子だけ"""
    net = "GND"
    w = width(net)
    ok, cost, via, vclash = r.masks(net, w, soft=False)
    through = {l: np.zeros(GX.shape, bool) for l in LAYERS}   # 表と裏の両方にある GND（穴の端子・ビア）
    for p in data["pads"]:
        if p["net"] == net and p["drill"]:
            for l in LAYERS:
                through[l] |= in_poly(p["poly"][l])
    tracks, vias = list(r.routes[net][0]), list(r.routes[net][1])
    for v in vias:
        i, j = r.ij(v["x"], v["y"])
        for l in LAYERS:
            stamp(through[l], [(i, j)], VIA_D / 2)
        stamp(via, [(i, j)], VIA_D + 0.3, False)
    cu = {l: r.cu[net][l].copy() for l in LAYERS}
    done = 0
    connected = np.zeros(GX.shape, bool)    # もう裏につながった表の GND の銅
    local = {n for pair in L.GND_LOCAL for n in pair}
    if only is None:
        local |= L.GND_LOCAL_ROOT          # 先に裏へ落とした端子は飛ばす
    # 大きな裏の端子（EP）は最後に、ほかの GND の端子へつなぐ
    terms = sorted(r.terms[net], key=lambda t: t[0] == "U2.17")
    for name, cells in terms:
        if "B" in cells:     # 穴の端子は、もともと表と裏の両方にある
            continue
        if (only is not None and name not in only) or (only is None and name in local):
            continue
        tgt_via = via & (edt(cells["F"]) <= 2.5) & ~cells["F"]
        # 目標：ビアを置ける場所（表）か、すでにある表裏両方の GND か、裏につながった GND
        target = {"F": tgt_via | through["F"] | (connected & ~cells["F"])}
        if not target["F"].any():
            print("  GND のビアを置けない:", name)
            continue
        res = r.search({"F": cells["F"], "B": np.zeros(GX.shape, bool)}, [target], ok,
                       cost, np.zeros(GX.shape, bool), vclash, False)
        if res is None:
            print("  GND の端子から出られない:", name)
            continue
        path, _ = res
        print("  GND", name, "→", "ビア" if (tgt_via[path[-1][1], path[-1][2]] and not through["F"][path[-1][1], path[-1][2]]) else "ほかの GND", len(path), "マス")
        li, i, j = path[-1]
        tree = {l: np.zeros(GX.shape, bool) for l in LAYERS}
        need_via = bool(tgt_via[i, j]) and not through["F"][i, j] and not connected[i, j]
        r.to_copper(net, w, path, tree, cu, tracks, vias)
        connected |= cells["F"] | tree["F"]
        if need_via:
            place_gnd_via(r, i, j, cu, vias, through, via)
        done += 1
    r.cu[net] = cu
    r.routes[net] = (tracks, vias)
    print("GND の端子", done, "個をビアで裏につないだ")
    return done


def main():
    data = json.load(open(os.path.join(HERE, "pads_%s.json" % V), encoding="utf-8"))
    r = Router(data)
    gnd_local(r)
    # GND の表の端子は、ほかの線より先に、すぐ近くのビアで裏へ落とす
    local = {n for pair in L.GND_LOCAL for n in pair}
    smd_gnd = {n for n, c in r.terms["GND"] if "B" not in c and (n not in local or n in L.GND_LOCAL_ROOT)}
    gnd_fanout(r, data, only=smd_gnd)
    failed = r.run(order(r))
    gnd_stitch(r)
    tracks = [t for n in r.routes for t in r.routes[n][0]]
    vias = [v for n in r.routes for v in r.routes[n][1]]
    json.dump({"tracks": tracks, "vias": vias, "failed": failed},
              open(os.path.join(HERE, "routes_%s.json" % V), "w", encoding="utf-8"), indent=0)
    print("線", len(tracks), "本 / ビア", len(vias), "個 / つながらない", failed)


def stamp_segment(arr, r, x1, y1, x2, y2, w):
    n = max(1, int(math.hypot(x2 - x1, y2 - y1) / (G / 2)))
    cells = [r.ij(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(n + 1)]
    stamp(arr, cells, w / 2)


def load_routes(r, routes):
    """routes.json の線とビアを、ネットごとの銅にもどす"""
    for t in routes["tracks"]:
        cu = r.cu.setdefault(t["net"], {l: np.zeros(GX.shape, bool) for l in LAYERS})
        stamp_segment(cu[t["layer"]], r, t["x1"], t["y1"], t["x2"], t["y2"], t["w"])
        r.routes.setdefault(t["net"], ([], []))[0].append(t)
    for v in routes["vias"]:
        cu = r.cu.setdefault(v["net"], {l: np.zeros(GX.shape, bool) for l in LAYERS})
        i, j = r.ij(v["x"], v["y"])
        for l in LAYERS:
            stamp(cu[l], [(i, j)], VIA_D / 2)
        r.routes.setdefault(v["net"], ([], []))[1].append(v)


def island_mask(islands, layer):
    m = np.zeros(GX.shape, bool)
    for isl in islands:
        if isl["layer"] == layer:
            a = in_poly(isl["outline"])
            for h in isl["holes"]:
                a &= ~in_poly(h)
            m |= a
    return m


def repair():
    """塗りつぶしたあと、ほかとつながっていない GND のまとまりから、本体の GND まで線を足す"""
    data = json.load(open(os.path.join(HERE, "pads_%s.json" % V), encoding="utf-8"))
    path = os.path.join(HERE, "routes_%s.json" % V)
    routes = json.load(open(path, encoding="utf-8"))
    isl = json.load(open(os.path.join(HERE, "gnd_islands_%s.json" % V), encoding="utf-8"))
    r = Router(data)
    load_routes(r, routes)
    net = "GND"
    w = width(net)
    target = {l: island_mask(isl["main"], l) for l in LAYERS}
    fixed = 0
    for k, grp in enumerate(isl["groups"]):
        src = {l: island_mask(grp, l) for l in LAYERS}
        soft = False
        ok, cost, via, vclash = r.masks(net, w, soft=False)
        res = r.search(src, [target], ok, cost, via, vclash, False)
        if res is None:   # 信号の線に囲まれている：信号の線と重なってもよいことにして探し、あとで信号の線を引き直す
            soft = True
            ok, cost, via, vclash = r.masks(net, w, soft=True)
            res = r.search(src, [target], ok, cost, via, vclash, True)
        if res is None:
            print("  まとまり %d：本体の GND まで線を引けない" % (k + 1))
            continue
        tracks, vias = [], []
        tree = {l: np.zeros(GX.shape, bool) for l in LAYERS}
        new = {l: np.zeros(GX.shape, bool) for l in LAYERS}
        r.to_copper(net, w, res[0], tree, new, tracks, vias)
        victims = r.victims(net, new) if soft else []
        for v in victims:
            del r.cu[v]
            del r.routes[v]
        for l in LAYERS:
            r.cu[net][l] |= new[l]
        r.routes[net][0].extend(tracks)
        r.routes[net][1].extend(vias)
        msg = "  まとまり %d：線 %d 本・ビア %d 個で本体の GND につないだ" % (k + 1, len(tracks), len(vias))
        if victims:
            failed = r.run(victims)
            msg += "（引き直した信号の線：%s、引けなかった線：%s）" % (victims, failed)
        print(msg)
        fixed += 1
    routes = {"tracks": [t for n in r.routes for t in r.routes[n][0]],
              "vias": [v for n in r.routes for v in r.routes[n][1]],
              "failed": [n for n in routes.get("failed", []) if n not in r.routes]}
    json.dump(routes, open(path, "w", encoding="utf-8"), indent=0)
    return fixed


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "repair":
        repair()
    else:
        main()
