"""Reconstruct BG layers from a Mesen dump (vram_X.bin, cgram_X.bin, state_X.txt) and write one PNG per layer.
Mode 1 assumed: BG1/BG2 4bpp, BG3 2bpp. Usage: python tools/vram_view.py <dump_dir> <tag> <out_prefix> [scale]"""
import os
import re
import struct
import sys
from PIL import Image

d, tag, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
SC = int(sys.argv[4]) if len(sys.argv) > 4 else 2
vram = open(os.path.join(d, f"vram_{tag}.bin"), "rb").read()
cg = open(os.path.join(d, f"cgram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(d, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v

pal = []
for i in range(256):
    c = struct.unpack_from("<H", cg, i * 2)[0]
    r, g, b = (c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3
    pal.append((r, g, b))

BPP = {0: 4, 1: 4, 2: 2}


def tile_pixels(chr_word, t, bpp):
    base = (chr_word + t * (bpp * 4)) * 2          # words -> bytes; a tile is 8*bpp bytes = 4*bpp words
    out = []
    for y in range(8):
        row = []
        for x in range(8):
            v = 0
            for plane in range(bpp):
                off = base + (plane // 2) * 16 + 2 * y + (plane & 1)
                v |= ((vram[off % 0x10000] >> (7 - x)) & 1) << plane
            row.append(v)
        out.append(row)
    return out


for layer in (0, 1, 2):
    chr_word = int(st[f"ppu.layers[{layer}].chrAddress"])
    map_word = int(st[f"ppu.layers[{layer}].tilemapAddress"])
    wide = st[f"ppu.layers[{layer}].doubleWidth"] == "true"
    tall = st[f"ppu.layers[{layer}].doubleHeight"] == "true"
    bpp = BPP[layer]
    W, H = (64 if wide else 32), (64 if tall else 32)
    img = Image.new("RGB", (W * 8, H * 8), (0, 0, 0))
    cache = {}
    for ty in range(H):
        for tx in range(W):
            # screen blocks of 32x32 are laid out sequentially (0x400 words each)
            block = (tx // 32) + (ty // 32) * (2 if wide else 1)
            addr = (map_word + block * 0x400 + (ty % 32) * 32 + (tx % 32)) * 2
            w = struct.unpack_from("<H", vram, addr % 0x10000)[0]
            t, p, hf, vf = w & 0x3FF, (w >> 10) & 7, bool(w & 0x4000), bool(w & 0x8000)
            key = (t, p, hf, vf)
            if key not in cache:
                px = tile_pixels(chr_word, t, bpp)
                rows = []
                for y in range(8):
                    sy = 7 - y if vf else y
                    row = []
                    for x in range(8):
                        sx = 7 - x if hf else x
                        v = px[sy][sx]
                        if v == 0:
                            row.append((0, 0, 0))
                        else:
                            row.append(pal[(p * (1 << bpp) + v) % 256])
                    rows.append(row)
                cache[key] = rows
            rows = cache[key]
            for y in range(8):
                for x in range(8):
                    img.putpixel((tx * 8 + x, ty * 8 + y), rows[y][x])
    img = img.resize((img.width * SC, img.height * SC), Image.NEAREST)
    out = f"{prefix}_bg{layer + 1}.png"
    img.save(out)
    print(f"BG{layer + 1}: chr word ${chr_word:04X} map word ${map_word:04X} {W}x{H} tiles {bpp}bpp -> {out} {img.size}")
