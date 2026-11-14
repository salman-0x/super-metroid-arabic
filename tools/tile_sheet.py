"""Zoomed, numbered sheet of ROM font tiles (original English font block at $9A:B200).
Usage: python tools/tile_sheet.py <rom> <out.png> <first_hex> <count_dec> [scale]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
out, first, count = sys.argv[2], int(sys.argv[3], 16), int(sys.argv[4])
SC = int(sys.argv[5]) if len(sys.argv) > 5 else 6
PAL = {0: (10, 10, 20), 1: (20, 30, 120), 2: (120, 140, 200), 3: (232, 232, 240)}
cols = 16
rows = (count + cols - 1) // cols
cw, ch = 8 * SC + 2, 8 * SC + 14
img = Image.new("RGB", (cols * cw, rows * ch), (255, 255, 255))
d = ImageDraw.Draw(img)
lab = ImageFont.load_default()
for i in range(count):
    tid = first + i
    b = rom.read(pc(0x9A, 0xB200) + tid * 16, 16)
    x0, y0 = (i % cols) * cw, (i // cols) * ch + 12
    d.text((x0 + 2, y0 - 11), f"{tid:03X}", fill=(90, 90, 90), font=lab)
    for y in range(8):
        for x in range(8):
            v = ((b[2 * y] >> (7 - x)) & 1) | (((b[2 * y + 1] >> (7 - x)) & 1) << 1)
            d.rectangle([x0 + x * SC, y0 + y * SC, x0 + x * SC + SC - 1, y0 + y * SC + SC - 1], fill=PAL[v])
img.save(out)
print("wrote", out, img.size)
