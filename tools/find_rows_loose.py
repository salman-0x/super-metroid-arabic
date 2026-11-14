"""Looser search for the option-mode rows: tile-id sequences (low bytes) stored (a) as 16-bit words with any constant
attribute byte, (b) as one byte per tile. Reports ROM addresses. Usage: python tools/find_rows_loose.py <rom> <dump_dir> <tag>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

rom = Rom.load(sys.argv[1])
d = rom.data
N = len(d)
dump, tag = sys.argv[2], sys.argv[3]
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st["ppu.layers[0].tilemapAddress"])


def words16(needle):
    """positions where the 16-bit words' low bytes equal needle and the high bytes are all the same (any value)."""
    n = len(needle)
    out = []
    first = bytes([needle[0]])
    i = d.find(first)
    while i != -1 and i + 2 * n <= N:
        if (i % 2 == 0 or True):
            ok = True
            hi = d[i + 1]
            for k in range(n):
                if d[i + 2 * k] != needle[k] or d[i + 2 * k + 1] != hi:
                    ok = False
                    break
            if ok:
                out.append(i)
        i = d.find(first, i + 1)
    return out


for r in range(32):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    nb = [c for c, w in enumerate(words) if (w & 0x3FF) not in (0x00F, 0x00E, 0)]
    if not nb:
        continue
    span = [w & 0xFF for w in words[nb[0]:nb[-1] + 1]]
    # use the longest prefix without a high tile bit to keep it simple
    a16 = words16(span)
    pat8 = bytes(span)
    a8, i = [], d.find(pat8)
    while i != -1:
        a8.append(snes(i)); i = d.find(pat8, i + 1)
    print(f"row {r:2d} ({len(span):2d} tiles) 16-bit:{[snes(x) for x in a16[:3]]}  8-bit:{a8[:3]}")
