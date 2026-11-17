# どちらの版を作るか（環境変数 VARIANT=A または B。決めないと A）
#   A版：XIAO を自分ではんだ付けする（hardware/carrier）
#   B版：XIAO も JLCPCB が付ける（hardware/carrier_b）
import os

V = os.environ.get("VARIANT", "A").strip().upper()
assert V in ("A", "B"), "VARIANT は A か B"
HERE = os.path.dirname(os.path.abspath(__file__))
LIBDIR = os.path.normpath(os.path.join(HERE, "..", "lib"))   # 自作の記号と型（A版・B版で共通）
if V == "A":
    ROOT = os.path.normpath(os.path.join(HERE, ".."))
    PROJECT = "shinkokyu_carrier"
else:
    ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "carrier_b"))
    PROJECT = "shinkokyu_carrier_b"
