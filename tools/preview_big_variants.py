"""Compare (weight, threshold) variants on real words, black background with the menu shadow.
Usage: python tools/preview_big_variants.py <out.png> <scale> "w:thr,w:thr,..." "text" ["text" ...]   e.g. "bold:0.55,regular:0.33" """
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar import arabic as AR, font_big as FB, menu_ar as M

out, SC, variants = sys.argv[1], int(sys.argv[2]), [v.split(":") for v in sys.argv[3].split(",")]
texts = sys.argv[4:]


def shadow(rows):
    ink = [[c == "#" for c in r] for r in rows]
    px = [[2 if ink[y][x] else 0 for x in range(8)] for y in range(16)]
    for y in range(16):
        for x in range(8):
            if ink[y][x] and x + 1 < 8 and y + 1 < 16 and px[y + 1][x + 1] == 0:
                px[y + 1][x + 1] = 1
    return px


rows = []
for text in texts:
    units = sorted({u[1] for u in AR.shape(text, M.BIG_CS) if u[0] == "R"})
    inv = {i: k for i, k in enumerate(units, start=1)}
    tiles = AR.to_tiles(text, {k: i for i, k in inv.items()}, M.BIG_CS)
    for w, thr in variants:
        img = Image.new("RGB", (len(tiles) * 8, 16), (0, 0, 0))
        for i, t in enumerate(tiles):
            if t in inv:
                g = FB.glyph16(*inv[t], weight=w, threshold=float(thr))
                if g:
                    px = shadow(g)
                    for y in range(16):
                        for x in range(8):
                            if px[y][x]:
                                img.putpixel((i * 8 + x, y), (255, 255, 255) if px[y][x] == 2 else (40, 60, 150))
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
