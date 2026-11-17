# XIAO の公式の基板データ（Seeed Studio XIAO nRF52840 v1.3 の .kicad_pcb）を、作った基板の上に重ねて確かめる（KiCad の Python で実行）
#   1) 基板の XIAO の端子ごとに、真上に来る XIAO の端子の信号の名前が、設計どおりか
#   2) XIAO の裏の、はんだ付けしない端子（SWD・NFC）の真下に、基板の表の銅がないか
#   3) XIAO の USB-C の口が、基板の外にはみ出していないか
# 使い方：XIAO_PCB=<公式の .kicad_pcb> VARIANT=B python verify_xiao.py
import os
import sys
import pcbnew
import variant
import layout as L
from make_pcb import PCB, OX, OY

XIAO_PCB = os.environ["XIAO_PCB"]
# 公式の基板の座標 → この基板の XIAO の座標（ピンの並びの中心が原点、USB が -x）：180°回す
XC, YC = 148.5, 105.0
# 基板のネット → XIAO の信号の名前の最後の部分
EXPECT = {"BTN_NEXT": "D0", "BTN_UP": "D1", "BTN_DOWN": "D2", "PIEZO": "D3", "SDA": "D4", "SCL": "D5",
          "IO6": "D6", "AMP_EN": "D7", "I2S_BCLK": "D8", "I2S_LRCLK": "D9", "I2S_DIN": "D10",
          "+3V3": "3V3", "GND": "GND", "VBUS": "VBUS", "VBAT": "VBAT"}
MM = pcbnew.ToMM


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    board = pcbnew.LoadBoard(PCB)
    xiao = pcbnew.LoadBoard(XIAO_PCB)
    u1 = board.FindFootprintByReference("U1")
    ux, uy = MM(u1.GetPosition().x) - OX, MM(u1.GetPosition().y) - OY
    assert abs(u1.GetOrientationDegrees()) < 0.01, "U1 の向きが 0° ではない"

    def to_board(p):  # 公式の基板の点 → この基板の点（mm、layout.py の座標）
        return ux - (MM(p.x) - XC), uy - (MM(p.y) - YC)

    xpads = []   # XIAO の裏に出ている端子だけ（縁の穴の端子と、裏の端子）。表の部品の端子は数えない
    for fp in xiao.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnLayer(pcbnew.B_Cu):
                continue
            x, y = to_board(p.GetPosition())
            xpads.append((fp.GetReference(), p.GetNumber(), p.GetNetname(), x, y, fp.IsFlipped(), p))
    bad = 0
    print("1) 端子ごとの信号")
    for p in sorted(u1.Pads(), key=lambda p: int(p.GetNumber())):
        bx, by = MM(p.GetPosition().x) - OX, MM(p.GetPosition().y) - OY
        net = p.GetNetname().lstrip("/")
        # 真上にある XIAO の端子（端子の中に入っているもの）
        hits = [q for q in xpads if p.HitTest(pcbnew.VECTOR2I(int(pcbnew.FromMM(q[3] + OX)), int(pcbnew.FromMM(q[4] + OY))), 0)]
        names = sorted({q[2].split("_")[-1].split("/")[-1] for q in hits})
        want = EXPECT.get(net)
        okk = want in names and len(names) == 1
        bad += 0 if okk else 1
        print("  %2s %-10s → XIAO の %-12s %s" % (p.GetNumber(), net, ",".join(names) or "（なし）", "OK" if okk else "!! ちがう"))
    print("2) はんだ付けしない XIAO の裏の端子の真下")
    cu = []
    for t in board.GetTracks():
        if t.IsOnLayer(pcbnew.F_Cu):
            cu.append(t)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Cu) and fp.GetReference() != "U1":
                cu.append(p)
    zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.F_Cu]
    for ref, num, xnet, x, y, flipped, xp in xpads:
        if not flipped or ref in ("BAT0", "GND0"):
            continue
        # XIAO の裏の端子の形を、この基板の上の位置に置いたときの範囲（0.3mm の余裕つき）
        bb = xp.GetBoundingBox()
        hw, hh = MM(bb.GetWidth()) / 2 + 0.3, MM(bb.GetHeight()) / 2 + 0.3
        pts = [pcbnew.VECTOR2I(int(pcbnew.FromMM(x + dx + OX)), int(pcbnew.FromMM(y + dy + OY)))
               for dx in (-hw, 0, hw) for dy in (-hh, 0, hh)]
        hit = [c for c in cu if any(c.HitTest(q, 0) for q in pts)]
        zhit = any(z.GetFilledPolysList(pcbnew.F_Cu).Contains(q) for z in zones for q in pts)
        okk = not hit and not zhit
        bad += 0 if okk else 1
        print("  %-5s %-12s (%6.2f, %6.2f) %s" % (ref, xnet, x, y, "OK（真下に銅なし）" if okk else "!! 真下に銅がある"))
    print("3) USB-C の口")
    usb = [fp for fp in xiao.GetFootprints() if fp.GetReference().startswith("USB")][0]
    bb = usb.GetBoundingBox(False)
    xs = [to_board(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))[0], to_board(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))[0]]
    front = min(xs)
    okk = front >= L.OUTLINE[0][0] + 0.2
    if variant.V == "A":   # A版は XIAO を手で付けるので、はみ出してもよい
        print("  USB-C の口の先 x=%.2f、基板の端 x=%.2f → A版は手で付けるので、はみ出してもよい" % (front, L.OUTLINE[0][0]))
    else:
        bad += 0 if okk else 1
        print("  USB-C の口の先 x=%.2f、基板の端 x=%.2f → %s" % (front, L.OUTLINE[0][0], "OK（0.2mm 以上内側）" if okk else "!! はみ出す"))
    print("結果:", "すべて OK" if bad == 0 else "%d 件の問題" % bad)
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
