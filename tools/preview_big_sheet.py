"""Sheet of all DejaVu-derived 8x16 glyphs: one row per letter, columns I N M F, labelled by code point. Pages of 10 letters.
Usage: python tools/preview_big_sheet.py <out_prefix> [scale]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar import font_ar as F, font_big as FB

prefix = sys.argv[1]
SC = int(sys.argv[2]) if len(sys.argv) > 2 else 5
letters = [c for c in F.LETTERS if c != "ﻻ"] + ["ﻻ"]
cw, ch = 8 * SC, 16 * SC
lab = ImageFont.load_default()
PER = 10
pages = [letters[i:i + PER] for i in range(0, len(letters), PER)]
for pn, chunk in enumerate(pages):
    img = Image.new("RGB", (44 + 4 * (cw + 6), len(chunk) * (ch + 6)), (30, 30, 30))
    d = ImageDraw.Draw(img)
    for n, letter in enumerate(chunk):
        y0 = n * (ch + 6) + 3
        d.text((2, y0 + ch // 2 - 5), f"{ord(letter):04X}", fill=(160, 160, 160), font=lab)
        for i, form in enumerate("INMF"):
            x0 = 40 + i * (cw + 6)
            d.rectangle([x0 - 1, y0 - 1, x0 + cw, y0 + ch], outline=(70, 70, 70))
            if form not in F.LETTERS[letter]:
                continue
            g = FB.glyph16(letter, form)
            if g is None:
                d.text((x0 + 4, y0 + 4), "NONE", fill=(255, 80, 80), font=lab)
                continue
            for y, row in enumerate(g):
                for x, c in enumerate(row):
                    if c == "#":
                        d.rectangle([x0 + x * SC, y0 + y * SC, x0 + x * SC + SC - 1, y0 + y * SC + SC - 1], fill=(255, 255, 255))
    out = f"{prefix}_{pn + 1}.png"
    img.save(out)
    print("wrote", out, img.size, "".join(chunk))
