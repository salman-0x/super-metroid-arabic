"""Compare DejaVu weights for chosen letters: rows = letters, for each form two cells (bold | regular).
Usage: python tools/preview_big_weights.py <out.png> <scale> <letters>"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar import font_ar as F, font_big as FB

out, SC, letters = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cw, ch = 8 * SC, 16 * SC
lab = ImageFont.load_default()
img = Image.new("RGB", (44 + 8 * (cw + 4) + 20, len(letters) * (ch + 6)), (30, 30, 30))
d = ImageDraw.Draw(img)
for n, letter in enumerate(letters):
    y0 = n * (ch + 6) + 3
    d.text((2, y0 + ch // 2 - 5), f"{ord(letter):04X}", fill=(160, 160, 160), font=lab)
    k = 0
    for form in "INMF":
        for weight in ("bold", "regular"):
            x0 = 40 + k * (cw + 4) + (8 if weight == "bold" and k else 0)
            k += 1
            d.rectangle([x0 - 1, y0 - 1, x0 + cw, y0 + ch], outline=(70, 70, 70) if weight == "bold" else (110, 90, 40))
            if form not in F.LETTERS[letter]:
                continue
            g = FB.glyph16(letter, form, weight)
            if g is None:
                continue
            for y, row in enumerate(g):
                for x, c in enumerate(row):
                    if c == "#":
                        d.rectangle([x0 + x * SC, y0 + y * SC, x0 + x * SC + SC - 1, y0 + y * SC + SC - 1], fill=(255, 255, 255))
img.save(out)
print("wrote", out, img.size)
