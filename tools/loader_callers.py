"""Who calls the routine that contains the menu tile-set DMA ($81:8DDB)? Search JSR/JSL/JMP to it everywhere, and show
which routine each caller sits in (nearest preceding RTS/RTL boundary is not reliable, so print the raw context).
Usage: python tools/loader_callers.py <rom>"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

d = Rom.load(sys.argv[1]).data
targets = {"JSR $8DDB (same bank)": bytes([0x20, 0xDB, 0x8D]), "JSL $818DDB": bytes([0x22, 0xDB, 0x8D, 0x81]),
           "JMP $8DDB": bytes([0x4C, 0xDB, 0x8D])}
for name, pat in targets.items():
    i, hits = d.find(pat), []
    while i != -1:
        hits.append(i)
        i = d.find(pat, i + 1)
    for h in hits:
        bank = 0x80 + h // 0x8000
        if name.startswith("JSL") or bank == 0x81:        # a bare JSR/JMP only counts inside bank $81
            print(f"{name}: {snes(h)}  " + " ".join(f"{b:02X}" for b in d[h - 10:h + 6]))
# routine start sanity: the loader begins with PHP / SEP #$30 at $81:8DDB
print("bytes at $81:8DDB:", " ".join(f"{b:02X}" for b in d[0x08000 + 0x0DDB:0x08000 + 0x0DDB + 6]))
