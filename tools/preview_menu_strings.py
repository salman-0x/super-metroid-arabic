"""STATIC preview (not from the running game) of the translated file-select strings: the real string words from the ROM
drawn with the real 4bpp tiles the loader sends (original: $8E:8000; Arabic ROM: the relocated blob at $B8:8000).
Usage: python tools/preview_menu_strings.py <original.sfc> <arabic.sfc> <out.png>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar import menu_ar as M
from smar.rom import Rom, pc

orig, ar, out = Rom.load(sys.argv[1]), Rom.load(sys.argv[2]), sys.argv[3]
COL = {0: (0, 0, 0), M.SHADOW: (40, 60, 150), M.INK: (255, 255, 255)}
SC = 3


def tiles_of(rom):
    p = rom.read(pc(*M.LOADER), 8)
    size, bank, addr = p[6] | (p[7] << 8), p[5], p[3] | (p[4] << 8)
    return rom.read(pc(bank, addr), size)


def render(rom, blob, addr):
    words = M.read_string(rom, addr)
    img = Image.new("RGB", (len(words) * 8, 8), (0, 0, 0))
    for i, w in enumerate(words):
        t = w & 0x3FF
        if (t + 1) * 32 > len(blob):
            continue
        px = M.tile4_to_pixels(blob[t * 32:(t + 1) * 32])
        for y in range(8):
            for x in range(8):
                img.putpixel((i * 8 + x, y), COL.get(px[y][x], (255, 0, 0)))
    return img


def render_big(rom, blob, addr):
    """Two-row (16 px) string: top row words, $FFFE, bottom row words."""
    words = M.read_string(rom, addr)
    cut = words.index(0xFFFE)
    top, bottom = words[:cut], words[cut + 1:]
    img = Image.new("RGB", (len(top) * 8, 16), (0, 0, 0))
    for half, row in enumerate((top, bottom)):
        for i, w in enumerate(row):
            t = w & 0x3FF
            if (t + 1) * 32 > len(blob):
                continue
            px = M.tile4_to_pixels(blob[t * 32:(t + 1) * 32])
            for y in range(8):
                for x in range(8):
                    img.putpixel((i * 8 + x, half * 8 + y), COL.get(px[y][x], (255, 0, 0)))
    return img


bo, ba = tiles_of(orig), tiles_of(ar)
rows = []
for addr in M.ENGLISH:
    rows.append(render(orig, bo, addr))
    rows.append(render(ar, ba, addr))
for addr in M.BIG_ORIGINAL_WORDS:
    rows.append(render_big(orig, bo, addr))
    rows.append(render_big(ar, ba, addr))
W = max(r.width for r in rows) * SC
sheet = Image.new("RGB", (W + 16, sum(r.height * SC + (4 if i % 2 == 0 else 12) for i, r in enumerate(rows)) + 8), (25, 25, 25))
y = 6
for i, r in enumerate(rows):
    r = r.resize((r.width * SC, r.height * SC), Image.NEAREST)
    sheet.paste(r, (8, y))
    y += r.height + (4 if i % 2 == 0 else 12)
sheet.save(out)
print("wrote", out, sheet.size)
