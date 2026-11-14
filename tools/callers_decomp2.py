"""List call sites of the two game decompressors ($80:B0FF to RAM, $80:B271 to VRAM) per bank; for bank $81 show code."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

d = Rom.load(sys.argv[1]).data
want = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x81
for name, pat in (("B0FF to RAM", bytes([0x22, 0xFF, 0xB0, 0x80])), ("B271 to VRAM", bytes([0x22, 0x71, 0xB2, 0x80]))):
    i, hits = d.find(pat), []
    while i != -1:
        hits.append(i)
        i = d.find(pat, i + 1)
    print(f"{name}: {len(hits)} sites; banks:", " ".join(f"${b:02X}" for b in sorted({0x80 + h // 0x8000 for h in hits})))
    for h in hits:
        if 0x80 + h // 0x8000 == want:
            print("   ", snes(h), " ".join(f"{b:02X}" for b in d[h - 14:h]), "|", " ".join(f"{b:02X}" for b in d[h:h + 8]))
