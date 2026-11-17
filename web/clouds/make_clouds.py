"""煙の画面（retro.html）の雲のドット絵をつくる

もとの絵：フリー素材の雲（22×15マス）を写し取ったもの。出どころは README.md を参照
使い方：py make_clouds.py preview.png clouds.json

文字の意味：. 外  # 黒い外枠  o 白  s 影（薄い青灰）
差分の作り方：左右反転／平らな所の列・行を足す・抜く／2つを重ねる
"""
import json
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

# いただいた絵から1マスずつ読み取ったもの（右下の2×3マスは、スクリーンショットのボタンが重なっていたので、左下と同じ作りに直した）
RAW = [
    "wwwwwww######wwwwwwwww",
    "wwwwww#wwwwss#wwwwwwww",
    "wwwww#swwwwwss####wwww",
    "wwww#swwwwwwssswww#www",
    "wwww#swwwwsswwwwwws#ww",
    "wwww#wwwwswwwwwwwww#ww",
    "ww##wwwwwwwwwwwwwww#ww",
    "w#swwwwwwwwwwwwwwwww#w",
    "#sswwwwwwwwwwwwwwwwww#",
    "#sswwwwwwwwwwwwwwwwww#",
    "#sswwwwwwwwwwwwwwwwww#",
    "#ssswwwwwwwssswwwwwws#",
    "w#ssssswwsssssswwwws#w",
    "ww##ssssss####sssss#ww",
    "wwww######wwww#####www",
]


def to_grid(raw):
    """外側の w を . に、中の w を o にする（外から塗りつぶして見分ける）"""
    h, w = len(raw), len(raw[0])
    g = [list(r) for r in raw]
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h) or g[y][x] != "w":
            continue
        seen.add((x, y))
        g[y][x] = "."
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return ["".join("o" if c == "w" else c for c in row) for row in g]


def mirror(g):
    return [row[::-1] for row in g]


def ins_cols(g, col, n):
    return [row[:col] + row[col] * n + row[col:] for row in g]


def del_cols(g, cols):
    return ["".join(c for i, c in enumerate(row) if i not in cols) for row in g]


def ins_rows(g, row, n):
    return g[:row] + [g[row]] * n + g[row:]


def del_rows(g, rows):
    return [r for i, r in enumerate(g) if i not in rows]


def overlay(back, front, dx, dy):
    """back の上に front を (dx, dy) ずらして重ねる（front が手前）"""
    w = max(len(back[0]), dx + len(front[0]))
    h = max(len(back), dy + len(front))
    out = [["."] * w for _ in range(h)]
    for y, row in enumerate(back):
        for x, c in enumerate(row):
            if c != ".":
                out[y][x] = c
    for y, row in enumerate(front):
        for x, c in enumerate(row):
            if c != ".":
                out[y + dy][x + dx] = c
    return ["".join(r) for r in out]


def scale(g, k):
    """大きい版：中身と影を k 倍にし、黒い外枠は1マスのまま描き直す（ドット絵の大きい版の作り方）"""
    h, w = len(g), len(g[0])
    H, W = round(h * k) + 2, round(w * k) + 2
    out = [["."] * W for _ in range(H)]
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            sx, sy = int((x - 1) / k), int((y - 1) / k)
            if sy < h and sx < w and g[sy][sx] in "os":
                out[y][x] = g[sy][sx]
    inside = lambda x, y: 0 <= x < W and 0 <= y < H and out[y][x] in "os"
    for y in range(H):
        for x in range(W):
            if out[y][x] == "." and any(inside(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = "#"
    # 余った外の行・列を切る
    rows = [r for r in out if any(c != "." for c in r)]
    cols = [i for i in range(W) if any(r[i] != "." for r in rows)]
    return ["".join(r[i] for i in range(cols[0], cols[-1] + 1)) for r in rows]


base = to_grid(RAW)
CLOUDS = {
    "もと": base,
    "左右反転": mirror(base),
    "横長": ins_cols(ins_cols(base, 16, 3), 8, 4),
    "小さい": del_rows(del_cols(base, {9, 10, 15}), {8, 9}),
    "小さい2": mirror(del_rows(del_cols(base, {8, 9, 16}), {8, 9})),
    "低い横長": ins_cols(del_rows(base, {8, 9, 10}), 9, 6),
    "大きい（2つ重ね）": overlay(ins_cols(mirror(base), 9, 3), ins_rows(base, 8, 1), 9, 3),
    "大（1.5倍）": scale(base, 1.5),
    "大（1.5倍・反転・横長）": scale(ins_cols(mirror(base), 9, 3), 1.5),
    "特大（2倍）": scale(mirror(base), 2),
    "特大（2倍・横長）": scale(ins_cols(base, 16, 3), 2),
    "巨大（2倍と1.5倍の重ね）": overlay(scale(base, 2), scale(mirror(base), 1.5), 30, 9),
}
LABEL = scale(ins_cols(ins_cols(base, 16, 8), 8, 10), 2)  # 言葉を書く雲（2倍の文字で4文字まで）
LABEL_WIDE = scale(ins_cols(ins_cols(base, 16, 14), 8, 16), 2)  # 長い言葉（5〜6文字）用

COLORS = {".": None, "o": (255, 255, 255), "s": (223, 230, 247), "#": (27, 28, 34)}
allg = list(CLOUDS.values()) + [LABEL, LABEL_WIDE]
cell = 8
W = sum(len(g[0]) for g in allg) * cell + (len(allg) + 1) * 16
H = max(len(g) for g in allg) * cell + 32
img = Image.new("RGB", (W, H), (120, 128, 140))
ox = 16
for g in allg:
    for y, row in enumerate(g):
        for x, c in enumerate(row):
            col = COLORS[c]
            if col:
                for dy in range(cell):
                    for dx in range(cell):
                        img.putpixel((ox + x * cell + dx, 16 + y * cell + dy), col)
    ox += len(g[0]) * cell + 16
img.save(sys.argv[1])
json.dump({"clouds": list(CLOUDS.values()), "label": LABEL, "labelWide": LABEL_WIDE}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print({k: (len(v[0]), len(v)) for k, v in CLOUDS.items()}, "label", (len(LABEL[0]), len(LABEL)), "wide", (len(LABEL_WIDE[0]), len(LABEL_WIDE)))
