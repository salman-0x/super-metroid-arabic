"""Compare big-font candidates on real option-screen words, as they will look on the black menu background:
  row A = current glyphs (8x8 art stretched x2), row B = DejaVu-derived 8x16 glyphs.
Usage: python tools/preview_big.py <out.png> <scale> "text" ["text" ...]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar import arabic as AR, font_ar as F, font_big as FB, menu_ar as M

out, SC = sys.argv[1], int(sys.argv[2])
texts = sys.argv[3:]
INK, SH = (255, 255, 255), (40, 60, 150)


def draw(px16, img, ox):
    for y in range(16):
        for x in range(8):
            if px16[y][x]:
                img.putpixel((ox + x, y), INK if px16[y][x] == 2 else SH)


def shadowed(rows):
    ink = [[c == "#" for c in r] for r in rows]
    px = [[2 if ink[y][x] else 0 for x in range(8)] for y in range(16)]
    for y in range(16):
        for x in range(8):
            if ink[y][x] and x + 1 < 8 and y + 1 < 16 and px[y + 1][x + 1] == 0:
                px[y + 1][x + 1] = 1
    return px


def cur(letter, form):
    px = M.big_pixels4(F.glyph_pixels(letter, form))
    return [[2 if v == M.INK else (1 if v == M.SHADOW else 0) for v in r] for r in px]


rows = []
for text in texts:
    units = [u[1] for u in AR.shape(text, M.BIG_CS) if u[0] == "R"]
    tiles = AR.to_tiles(text, {k: i for i, k in enumerate(sorted(set(units)), start=1)}, M.BIG_CS)
    inv = {i: k for i, k in enumerate(sorted(set(units)), start=1)}
    for style in ("cur", "new"):
        img = Image.new("RGB", (len(tiles) * 8, 16), (0, 0, 0))
        for i, t in enumerate(tiles):
            if t in inv:
                if style == "cur":
                    draw(cur(*inv[t]), img, i * 8)
                else:
                    g = FB.glyph16(*inv[t])
                    if g:
                        draw(shadowed(g), img, i * 8)
        rows.append(img)
    rows.append(None)
W = max(r.width for r in rows if r) * SC
H = sum((r.height * SC + 6) if r else 16 for r in rows)
sheet = Image.new("RGB", (W + 12, H), (28, 28, 28))
y = 4
for r in rows:
    if r is None:
        y += 16
        continue
    sheet.paste(r.resize((r.width * SC, r.height * SC), Image.NEAREST), (6, y))
    y += r.height * SC + 6
sheet.save(out)
print("wrote", out, sheet.size)
