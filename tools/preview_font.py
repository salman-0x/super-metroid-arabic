"""Render the Arabic glyph set to PNG(s) for visual review: one row per letter, columns I N M F (left->right),
each letter labelled with its code point. Several pages when there are many letters.
Usage: python tools/preview_font.py <out_prefix> [scale]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar import font_ar as F

prefix = sys.argv[1]
SC = int(sys.argv[2]) if len(sys.argv) > 2 else 8
INKC, BGC = (25, 30, 110), (228, 228, 238)
cell = 8 * SC
pad = 3
letters = [c for c in F.LETTERS if c != "ﻻ"] + ["ﻻ"]
PER_PAGE, COLS = 12, 2
lab = ImageFont.load_default()
pages = [letters[i:i + PER_PAGE] for i in range(0, len(letters), PER_PAGE)]
for pn, chunk in enumerate(pages):
    rows = (len(chunk) + COLS - 1) // COLS
    cw = 4 * (cell + pad) + 40
    img = Image.new("RGB", (COLS * cw, rows * (cell + 14)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for n, ch in enumerate(chunk):
        bx, by = (n % COLS) * cw, (n // COLS) * (cell + 14) + 4
        d.text((bx + 2, by + cell // 2 - 5), f"{ord(ch):04X}", fill=(120, 120, 120), font=lab)
        for i, f in enumerate(F.FORMS):
            x0 = bx + 40 + i * (cell + pad)
            if f not in F.LETTERS[ch]:
                d.rectangle([x0, by, x0 + cell - 1, by + cell - 1], fill=(246, 246, 246))
                continue
            for y, r in enumerate(F.glyph_pixels(ch, f)):
                for x, c in enumerate(r):
                    d.rectangle([x0 + x * SC, by + y * SC, x0 + x * SC + SC - 2, by + y * SC + SC - 2],
                                fill=INKC if c == "#" else BGC)
    out = f"{prefix}_{pn + 1}.png"
    img.save(out)
    print("wrote", out, img.size, "letters:", "".join(chunk))
