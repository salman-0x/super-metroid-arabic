"""Find where the words of each BG1 row of a Mesen dump are stored in the ROM (as a contiguous word run).
For every non-empty row it takes the longest run of non-blank words and searches the ROM for that exact word sequence.
Usage: python tools/find_screen_rows.py <rom> <dump_dir> <tag>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

rom = Rom.load(sys.argv[1])
d = rom.data
dump, tag = sys.argv[2], sys.argv[3]
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st["ppu.layers[0].tilemapAddress"])
BLANK = {0x000, 0x00F, 0x00E}
for r in range(32):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    idx = [c for c, w in enumerate(words) if (w & 0x3FF) not in BLANK or (w & 0x3FF) == 0]
    # contiguous span from first to last non-blank word
    nb = [c for c, w in enumerate(words) if (w & 0x3FF) not in (0x00F, 0x00E)]
    if not nb:
        continue
    span = words[nb[0]:nb[-1] + 1]
    pat = struct.pack(f"<{len(span)}H", *span)
    hits, i = [], d.find(pat)
    while i != -1:
        hits.append(snes(i))
        i = d.find(pat, i + 1)
    print(f"row {r:2d} cols {nb[0]:2d}-{nb[-1]:2d} ({len(span):2d} words): {hits[:4] if hits else 'NOT FOUND as a contiguous run'}")
