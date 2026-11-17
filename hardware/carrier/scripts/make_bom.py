# JLCPCB に渡す部品表（BOM）を design.py から作る
# JLCPCB の形式：Comment, Designator, Footprint, LCSC
import csv
import os
from design import PARTS

import variant
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(variant.ROOT, "jlcpcb")


def main():
    os.makedirs(OUT, exist_ok=True)
    groups = {}
    for ref, p in PARTS.items():
        if not p["lcsc"] or p["dnp"] or p["hand"]:
            continue
        key = (p.get("mpn", p["value"]), p["fp"].split(":")[1], p["lcsc"])
        groups.setdefault(key, []).append(ref)
    rows = []
    for (value, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
        refs.sort(key=lambda r: (r.rstrip("0123456789"), int(r[len(r.rstrip("0123456789")):])))
        rows.append([value, ",".join(refs), fp, lcsc])
    with open(os.path.join(OUT, "BOM_JLCPCB.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
