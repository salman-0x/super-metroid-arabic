"""Compare menu-font styles: render Arabic words on black with the game's palette (ink white, shadow dark blue), next to
the English reference tiles. Usage: python tools/menu_style_preview.py <rom> <out.png> <scale> style1,style2 "text1" ...
(styles: any of the names accepted by menu_ar.glyph_pixels4, or 'english')"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar import arabic as AR, font_ar as F, menu_ar as M
from smar.rom import Rom, pc

rom, out, SC = Rom.load(sys.argv[1]), sys.argv[2], int(sys.argv[3])
styles = sys.argv[4].split(",")
texts = sys.argv[5:]
COL = {0: (0, 0, 0), M.SHADOW: (40, 60, 150), M.INK: (255, 255, 255)}
base = pc(0x8E, 0x8000)


def english(word):
    img = Image.new("RGB", (len(word) * 8, 8), (0, 0, 0))
    for i, ch in enumerate(word):
        t = 0x0F if ch == " " else 0x6A + ord(ch) - 65
        px = M.tile4_to_pixels(rom.data[base + t * 32: base + t * 32 + 32])
        for y in range(8):
            for x in range(8):
                img.putpixel((i * 8 + x, y), COL.get(px[y][x], (255, 0, 0)))
    return img


def arabic(text, style):
    table = M.allocate(AR.glyph_keys(text, AR.MENU))
    inv = {v: k for k, v in table.items()}
    tiles = AR.to_tiles(text, table, AR.MENU)
    img = Image.new("RGB", (len(tiles) * 8, 8), (0, 0, 0))
    for i, t in enumerate(tiles):
        px = M.glyph_pixels4(F.glyph_pixels(*inv[t]), style) if t in inv else [[0] * 8 for _ in range(8)]
        for y in range(8):
            for x in range(8):
                img.putpixel((i * 8 + x, y), COL[px[y][x]])
    return img


rows = []
for text in texts:
    for st in styles:
        rows.append(english(text) if st == "english" else arabic(text, st))
    rows.append(None)
W = max(r.width for r in rows if r) * SC
H = sum((r.height * SC + 6) if r else 14 for r in rows)
sheet = Image.new("RGB", (W + 12, H), (28, 28, 28))
y = 4
for r in rows:
    if r is None:
        y += 14
        continue
    sheet.paste(r.resize((r.width * SC, r.height * SC), Image.NEAREST), (6, y))
    y += r.height * SC + 6
sheet.save(out)
print("wrote", out, sheet.size)
