"""Decompress a graphics blob from the ROM and render it as a numbered tile sheet.
Usage: python tools/gfx_sheet.py <rom> <bank_hex> <addr_hex> <bpp 2|4> <out.png> [first_tile_hex] [count] [scale]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont
from smar.rom import Rom, pc
from smar import sm_lz

rom = Rom.load(sys.argv[1])
bank, addr, bpp, out = int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4]), sys.argv[5]
first = int(sys.argv[6], 16) if len(sys.argv) > 6 else 0
count = int(sys.argv[7]) if len(sys.argv) > 7 else 128
SC = int(sys.argv[8]) if len(sys.argv) > 8 else 5
data, _ = sm_lz.decompress(rom.data, pc(bank, addr))
tsize = 8 * bpp
print(f"blob {len(data)} bytes = {len(data) // tsize} tiles at {bpp}bpp")
GRAY4 = [(14, 14, 24), (60, 70, 140), (120, 140, 200), (232, 232, 240)]


def pix(t, x, y):
    base = t * tsize
    if base + tsize > len(data):
        return 0
    v = 0
    for plane in range(bpp):
        b = data[base + (plane // 2) * 16 + 2 * y + (plane & 1)]
        v |= ((b >> (7 - x)) & 1) << plane
    return v


def color(v):
    if bpp == 2:
        return GRAY4[v]
    g = 255 - v * 16
    return (g, g, min(255, g + 30))


cols = 16
rows = (count + cols - 1) // cols
cw, ch = 8 * SC + 2, 8 * SC + 13
img = Image.new("RGB", (cols * cw, rows * ch), (255, 255, 255))
dr = ImageDraw.Draw(img)
lab = ImageFont.load_default()
for k in range(count):
    t = first + k
    x0, y0 = (k % cols) * cw, (k // cols) * ch + 12
    dr.text((x0 + 1, y0 - 11), f"{t:03X}", fill=(90, 90, 90), font=lab)
    for y in range(8):
        for x in range(8):
            c = color(pix(t, x, y))
            dr.rectangle([x0 + x * SC, y0 + y * SC, x0 + x * SC + SC - 1, y0 + y * SC + SC - 1], fill=c)
img.save(out)
print("wrote", out, img.size)
