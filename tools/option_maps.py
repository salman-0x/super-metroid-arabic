"""Decompress the five menu tilemaps loaded at $82:EC70-ECB4 and print their non-empty rows (tile ids; attr in brackets).
Usage: python tools/option_maps.py <rom> [index 0-4 | all]"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc
from smar import sm_lz

SOURCES = [(0x97, 0x8DF4, 0x7FC000), (0x97, 0x8FCD, 0x7FC800), (0x97, 0x91C4, 0x7FD000), (0x97, 0x938D, 0x7FD800),
           (0x97, 0x953A, 0x7FE000)]
rom = Rom.load(sys.argv[1])
which = sys.argv[2] if len(sys.argv) > 2 else "all"
for i, (bank, addr, dest) in enumerate(SOURCES):
    if which not in ("all", str(i)):
        continue
    blob, end = sm_lz.decompress(rom.data, pc(bank, addr))
    words = struct.unpack("<%dH" % (len(blob) // 2), blob)
    print(f"=== map {i}: ${bank:02X}:{addr:04X} -> ${dest:06X}  compressed {end - pc(bank, addr)} B, decompressed {len(blob)} B")
    for r in range(len(words) // 32):
        row = words[r * 32:(r + 1) * 32]
        if all((w & 0x3FF) in (0x00F, 0x000) for w in row):
            continue
        attrs = sorted({w >> 8 for w in row if (w & 0x3FF) not in (0x00F, 0)})
        print(f"  row {r:2d} attr={[f'{a:02X}' for a in attrs]}  " + " ".join("..." if (w & 0x3FF) in (0x00F, 0) else f"{w & 0x3FF:03X}" for w in row))
