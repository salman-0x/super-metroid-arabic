"""Search the ROM for each *word segment* (maximal run of non-blank words) of every option-mode BG1 row, as 16-bit words
with any (constant) attribute byte. Prints the ROM address(es) per segment. Usage: python tools/find_segments.py <rom> <dump_dir> <tag>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

d = Rom.load(sys.argv[1]).data
dump, tag = sys.argv[2], sys.argv[3]
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st["ppu.layers[0].tilemapAddress"])
BLANK = {0x00F, 0x000}


def find16(tiles):
    """positions where d holds words whose low bytes are `tiles` (and high bytes constant)."""
    out = []
    first = bytes([tiles[0]])
    i = d.find(first)
    n = len(tiles)
    while i != -1:
        if i + 2 * n <= len(d):
            hi = d[i + 1]
            if all(d[i + 2 * k] == tiles[k] and d[i + 2 * k + 1] == hi for k in range(n)):
                out.append(i)
        i = d.find(first, i + 1)
    return out


for r in range(32):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    segs, cur = [], []
    for c, w in enumerate(words):
        if (w & 0x3FF) in BLANK or (w & 0x3FF) == 0x00E:
            if cur:
                segs.append(cur); cur = []
        else:
            cur.append((c, w))
    if cur:
        segs.append(cur)
    for seg in segs:
        tiles = [w & 0xFF for _, w in seg]
        if len(tiles) < 3:
            continue
        hits = find16(tiles)
        print(f"row {r:2d} col {seg[0][0]:2d} ({len(seg):2d}w attr {seg[0][1] >> 8:02X}) tiles "
              f"{' '.join(f'{(w & 0x3FF):03X}' for _, w in seg)}  -> {[snes(h) for h in hits[:4]] if hits else 'NOT FOUND'}")
