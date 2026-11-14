"""Print 4bpp tiles of the menu set as pixel-index grids. Usage: python tools/show_tile4.py <rom> <hex tile> [...]"""
import os
import sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
base = pc(0x8E, 0x8000)
hist = Counter()
for a in sys.argv[2:]:
    t = int(a, 16)
    b = rom.data[base + t * 32: base + t * 32 + 32]
    print(f"tile {t:03X}")
    for y in range(8):
        row = ""
        for x in range(8):
            v = 0
            for plane in range(4):
                v |= ((b[(plane // 2) * 16 + 2 * y + (plane & 1)] >> (7 - x)) & 1) << plane
            hist[v] += 1
            row += "." if v == 0 else "0123456789ABCDEF"[v]
        print("   " + row)
print("index histogram over these tiles:", dict(sorted(hist.items())))
