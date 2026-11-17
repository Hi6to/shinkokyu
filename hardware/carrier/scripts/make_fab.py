# JLCPCB に送るファイルを作る（ふつうの Python で実行。KiCad の kicad-cli を使う）
#   jlcpcb/shinkokyu_carrier_gerber.zip … 基板の製造用（ガーバーと穴の位置）
#   jlcpcb/CPL_JLCPCB.csv               … 部品の位置（部品の取り付け用）
#   jlcpcb/BOM_JLCPCB.csv               … 部品表（make_bom.py が作る）
#   images/                             … 確認用の画像
import csv
import glob
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variant  # noqa: E402
ROOT = variant.ROOT
CLI = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe")
PCB = os.path.join(ROOT, variant.PROJECT + ".kicad_pcb")
OUT = os.path.join(ROOT, "jlcpcb")
IMG = os.path.join(ROOT, "images")
# JLCPCB の部品の型は、KiCad の型と 0° の向きがちがうことがある。注文の画面の絵（1番ピンの点）で確かめて直した角度
ROT_FIX = {"U2": -90, "Q1": 180, "U3": 90, "U1": 90}
LAYERS = "F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"  # 裏には部品を付けないので、裏のメタルマスク（はんだペースト）は出さない


def run(*a):
    r = subprocess.run([CLI, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit(1)


def main():
    gdir = os.path.join(OUT, "gerber")
    os.makedirs(gdir, exist_ok=True)
    for f in glob.glob(os.path.join(gdir, "*")):
        os.remove(f)
    run("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--check-zones", "-o", gdir + os.sep, PCB)
    run("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th",
        "-o", gdir + os.sep, PCB)
    z = os.path.join(OUT, variant.PROJECT + "_gerber.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(glob.glob(os.path.join(gdir, "*"))):
            zf.write(f, os.path.basename(f))
    print("ガーバー:", len(glob.glob(os.path.join(gdir, "*"))), "ファイル →", z)
    # 部品の位置
    tmp = os.path.join(OUT, "pos_kicad.csv")
    run("pcb", "export", "pos", "--side", "front", "--format", "csv", "--units", "mm", "--exclude-dnp", "-o", tmp, PCB)
    rows = list(csv.DictReader(open(tmp, encoding="utf-8")))
    os.remove(tmp)
    with open(os.path.join(OUT, "CPL_JLCPCB.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            rot = (float(r["Rot"]) + ROT_FIX.get(r["Ref"], 0)) % 360
            w.writerow([r["Ref"], r["PosX"] + "mm", r["PosY"] + "mm", "Top", "%g" % rot])
    print("部品の位置:", ", ".join(r["Ref"] for r in rows))
    # 確認用の画像
    os.makedirs(IMG, exist_ok=True)
    for side in ("top", "bottom"):
        run("pcb", "render", "--side", side, "--width", "2400", "--height", "1000", "--quality", "high",
            "--zoom", "1.0", "-o", os.path.join(IMG, "3d_%s.png" % side), PCB)
    from PIL import Image
    for side in ("top", "bottom"):
        p = os.path.join(IMG, "3d_%s.png" % side)
        im = Image.open(p).convert("RGBA")
        white = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(white, im).convert("RGB")
        box = im.convert("L").point(lambda v: 255 if v < 150 else 0).getbbox()  # 濃い色（基板）の範囲
        if box:
            im = im.crop((max(0, box[0] - 20), max(0, box[1] - 20), box[2] + 20, box[3] + 20))
        im.save(p)
    run("pcb", "export", "pdf", "--layers", "F.Cu,F.Silkscreen,F.Mask,Edge.Cuts", "--mode-single",
        "-o", os.path.join(IMG, "layer_top.pdf"), PCB)
    run("pcb", "export", "pdf", "--layers", "B.Cu,B.Silkscreen,B.Mask,Edge.Cuts", "--mode-single", "--mirror",
        "-o", os.path.join(IMG, "layer_bottom.pdf"), PCB)
    print("画像:", os.listdir(IMG))


if __name__ == "__main__":
    main()
