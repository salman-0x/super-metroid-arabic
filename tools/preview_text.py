"""Zoomed preview of arbitrary Arabic lines using only the font module (no ROM needed), message-font look
(ink dark on the light box). Each line is drawn plain and with the thickened baseline.
Usage: python tools/preview_text.py out.png "text 1" "text 2" ...   (each argument = one line)"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar import arabic as AR, font_ar as F

SC = 8
INKC, BGC = (20, 30, 120), (232, 232, 240)
table = F.tile_table()
inv = {v: k for k, v in table.items()}
rows = []
for text in sys.argv[2:]:
    tiles = AR.to_tiles(text, table)
    for thick in (False, True):
        img = Image.new("RGB", (len(tiles) * 8 * SC, 8 * SC), BGC)
        for i, t in enumerate(tiles):
            px = F.glyph_pixels(*inv[t]) if t in inv else ["........"] * 8
            if thick:
                px = F.thicken_baseline(px)
            for y, r in enumerate(px):
                for x, c in enumerate(r):
                    if c == "#":
                        for dy in range(SC):
                            for dx in range(SC):
                                img.putpixel((i * 8 * SC + x * SC + dx, y * SC + dy), INKC)
        rows.append(img)
    rows.append(None)
W = max(i.width for i in rows if i)
sheet = Image.new("RGB", (W, sum((i.height + 8) if i else 16 for i in rows)), (255, 255, 255))
y = 0
for im in rows:
    if im is None:
        y += 16
        continue
    sheet.paste(im, (W - im.width, y))
    y += im.height + 8
sheet.save(sys.argv[1])
print("wrote", sys.argv[1], sheet.size)
