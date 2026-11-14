"""Count all-zero 4bpp tiles in the second menu DMA block ($B6:8000, 0x2000 bytes = tile ids $300-$3FF) and in the
free zone, and list the spans. Usage: python tools/blank_tiles.py <rom>"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
blk = rom.read(pc(0xB6, 0x8000), 0x2000)
zero = [i for i in range(256) if not any(blk[i * 32:(i + 1) * 32])]


def spans(ids):
    out, s, p = [], None, None
    for i in ids:
        if s is None:
            s = p = i
        elif i == p + 1:
            p = i
        else:
            out.append((s, p)); s = p = i
    if s is not None:
        out.append((s, p))
    return out


print(f"$B6:8000 block: {len(zero)} of 256 tiles are all-zero")
print("ids (0x300+):", " ".join(f"{0x300 + a:03X}-{0x300 + b:03X}" if a != b else f"{0x300 + a:03X}" for a, b in spans(zero)))
