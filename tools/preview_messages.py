"""Pixel-accurate preview of message tilemaps read straight from a ROM file.

Uses the ROM's own BG3 font tiles ($9A:B200, 512 tiles) and the message table, so what you see is what the
tilemap will show (ink = colour index 1, box background = 3, transparent = 0).
Usage: python tools/preview_messages.py <rom> <out.png> [msgid ...]   (ids like 01 0A 17; default: all)
"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from smar.rom import Rom, pc
from smar import messages as M

PAL = {0: (10, 10, 20), 1: (20, 30, 120), 2: (120, 140, 200), 3: (232, 232, 240)}
SC = 3


def tile_pixels(rom, tid):
    b = rom.read(pc(0x9A, 0xB200) + tid * 16, 16)
    return [[((b[2 * y] >> (7 - x)) & 1) | (((b[2 * y + 1] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]


def render_block(rom, addr, size, cache):
    words = struct.unpack(f"<{size // 2}H", rom.read(pc(0x85, addr), size))
    rows = size // M.ROW_BYTES
    img = Image.new("RGB", (32 * 8, rows * 8), PAL[0])
    for i, w in enumerate(words):
        tid, hf, vf = w & 0x3FF, bool(w & 0x4000), bool(w & 0x8000)
        if tid not in cache:
            cache[tid] = tile_pixels(rom, tid)
        px = cache[tid]
        x0, y0 = (i % 32) * 8, (i // 32) * 8
        for y in range(8):
            for x in range(8):
                sx, sy = (7 - x) if hf else x, (7 - y) if vf else y
                img.putpixel((x0 + x, y0 + y), PAL[px[sy][sx]])
    return img.resize((img.width * SC, img.height * SC), Image.NEAREST)


def main():
    rom = Rom.load(sys.argv[1])
    out = sys.argv[2]
    want = {a.upper() for a in sys.argv[3:]}
    table = M.read_table(rom)
    addrs = sorted({t for _, _, t in table})
    cache, imgs = {}, []
    for n, a in enumerate(addrs[:-1]):
        first = next(i + 1 for i, (_, _, t) in enumerate(table) if t == a)
        if want and f"{first:02X}" not in want:
            continue
        imgs.append(render_block(rom, a, addrs[n + 1] - a, cache))
    gap = 6
    sheet = Image.new("RGB", (imgs[0].width, sum(i.height + gap for i in imgs)), (255, 255, 255))
    y = 0
    for im in imgs:
        sheet.paste(im, (0, y)); y += im.height + gap
    sheet.save(out)
    print("wrote", out, sheet.size, len(imgs), "messages")


if __name__ == "__main__":
    main()
