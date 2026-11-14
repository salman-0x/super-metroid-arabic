"""List call sites of the game's decompressor JSL $80:B0FF and show the code just before each (to find the
source-pointer setup). Usage: python tools/callers_decomp.py <rom> [context_bytes]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

rom = Rom.load(sys.argv[1])
ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 18
d = rom.data
pat = bytes([0x22, 0xFF, 0xB0, 0x80])
i, hits = d.find(pat), []
while i != -1:
    hits.append(i)
    i = d.find(pat, i + 1)
print(len(hits), "call sites of JSL $80:B0FF")
for h in hits[:60]:
    print(f"{snes(h)}  " + " ".join(f"{b:02X}" for b in d[h - ctx:h]) + " | 22 FF B0 80")
