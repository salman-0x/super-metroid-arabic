"""Search the ROM for each option-mode row by its tile-id *differences* (so a constant tile-base offset does not matter),
as 16-bit words (stride 2, any attribute byte) and as bytes. Usage: python tools/find_rows_delta.py <rom> <dump_dir> <tag>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

d = Rom.load(sys.argv[1]).data
N = len(d)
dump, tag = sys.argv[2], sys.argv[3]
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st["ppu.layers[0].tilemapAddress"])


def search(deltas, stride):
    out = []
    n = len(deltas) + 1
    lim = N - stride * n
    for i in range(0, lim):
        base = d[i] | ((d[i + 1] << 8) if stride == 2 else 0)
        ok = True
        for k, dl in enumerate(deltas):
            v = d[i + stride * (k + 1)] | ((d[i + stride * (k + 1) + 1] << 8) if stride == 2 else 0)
            if (v - base) & (0xFFFF if stride == 2 else 0xFF) != dl & (0xFFFF if stride == 2 else 0xFF):
                ok = False
                break
        if ok:
            out.append(i)
            if len(out) >= 3:
                break
    return out


rows = []
for r in (6, 1, 10, 17, 21):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    nb = [c for c, w in enumerate(words) if (w & 0x3FF) not in (0x00F, 0x00E, 0)]
    tiles = [w & 0x3FF for w in words[nb[0]:nb[-1] + 1]]
    rows.append((r, tiles))
for r, tiles in rows:
    deltas = [b - a for a, b in zip(tiles, tiles[1:])]
    h16 = search(deltas, 2)
    h8 = search(deltas, 1)
    print(f"row {r:2d} tiles {' '.join(f'{t:02X}' for t in tiles)}")
    print(f"        16-bit stride: {[snes(x) for x in h16]}   8-bit stride: {[snes(x) for x in h8]}")
