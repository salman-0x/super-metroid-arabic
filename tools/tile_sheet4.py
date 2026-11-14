"""Numbered sheet of 4bpp tiles from the menu tile set in a ROM ($8E:8000 by default, or any bank/addr).
Usage: python tools/tile_sheet4.py <rom> <out.png> <first_hex> <count> [scale] [bank_hex=8E] [addr_hex=8000]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
out, first, count = sys.argv[2], int(sys.argv[3], 16), int(sys.argv[4])
SC = int(sys.argv[5]) if len(sys.argv) > 5 else 6
bank = int(sys.argv[6], 16) if len(sys.argv) > 6 else 0x8E
addr = int(sys.argv[7], 16) if len(sys.argv) > 7 else 0x8000
base = pc(bank, addr)
# CGRAM palette 0 of the file-select screen: index 13 = 44E5 (dark blue shadow), 14 = 7FFF (white ink)
PAL = {0: (0, 0, 0), 13: (40, 60, 150), 14: (255, 255, 255)}
cols = 16
rows = (count + cols - 1) // cols
cw, ch = 8 * SC + 2, 8 * SC + 13
img = Image.new("RGB", (cols * cw, rows * ch), (255, 255, 255))
d = ImageDraw.Draw(img)
lab = ImageFont.load_default()
for k in range(count):
    t = first + k
    b = rom.data[base + t * 32: base + t * 32 + 32]
    x0, y0 = (k % cols) * cw, (k // cols) * ch + 12
    d.text((x0 + 1, y0 - 11), f"{t:03X}", fill=(90, 90, 90), font=lab)
    for y in range(8):
        for x in range(8):
            v = 0
            for plane in range(4):
                v |= ((b[(plane // 2) * 16 + 2 * y + (plane & 1)] >> (7 - x)) & 1) << plane
            c = PAL.get(v, (200, 60, 60))
            d.rectangle([x0 + x * SC, y0 + y * SC, x0 + x * SC + SC - 1, y0 + y * SC + SC - 1], fill=c)
img.save(out)
print("wrote", out, img.size)
