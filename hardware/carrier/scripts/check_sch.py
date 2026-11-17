# 回路図を作り直して、ERC と「design.py どおりにつながっているか」を確かめ、PDF を書き出す
import os
import subprocess
import tempfile
from sexpr import parse, find, find1
from design import nets

import variant
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = variant.ROOT
CLI = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe")
SCH = os.path.join(ROOT, variant.PROJECT + ".kicad_sch")


def run(*a):
    return subprocess.run([CLI, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    tmp = tempfile.mkdtemp()
    erc = os.path.join(tmp, "erc.rpt")
    run("sch", "erc", "--severity-all", "-o", erc, SCH)
    issues = [ln for ln in open(erc, encoding="utf-8") if ln.startswith("[")
              and "lib_symbol_issues" not in ln and "footprint_link_issues" not in ln]
    print("ERC:", len(issues), "件（ライブラリの設定の警告を除く）")
    for ln in issues:
        print("  ", ln.strip())
    net = os.path.join(tmp, "net.net")
    run("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, SCH)
    t = parse(open(net, encoding="utf-8").read())
    got = {}
    for n in find(find1(t, "nets"), "net"):
        name = find1(n, "name")[1]
        nodes = sorted((find1(x, "ref")[1], find1(x, "pin")[1]) for x in find(n, "node")
                       if not find1(x, "ref")[1].startswith("#"))
        if nodes and not name.startswith("unconnected"):
            got[name.lstrip("/")] = nodes
    exp = {k: sorted(v) for k, v in nets().items()}
    bad = [k for k in set(exp) | set(got) if exp.get(k) != got.get(k)]
    for k in bad:
        print("  ちがう:", k, exp.get(k), got.get(k))
    print("つながり:", "design.py と一致" if not bad else "不一致あり", len(exp), "本")
    run("sch", "export", "pdf", "-o", os.path.join(ROOT, variant.PROJECT + "_schematic.pdf"), SCH)
    return not bad


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
