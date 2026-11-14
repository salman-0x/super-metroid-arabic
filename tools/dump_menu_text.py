"""Decode letter-tilemap words in a bank range using a tile base: tile = base + (letter - 'A'). Words whose tile is
outside the letter range are shown as '.' (or the given space tile as ' ').  Prints one line per contiguous run
(a 'run' continues across non-letters as long as the attribute byte stays the same and the span is short).
Usage: python tools/dump_menu_text.py <rom> <bank_hex> <base_hex> [space_tile_hex] [min_letters]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc, snes

rom = Rom.load(sys.argv[1])
bank = int(sys.argv[2], 16)
base = int(sys.argv[3], 16)
space = int(sys.argv[4], 16) if len(sys.argv) > 4 else -1
minl = int(sys.argv[5]) if len(sys.argv) > 5 else 3
start = pc(bank, 0x8000)
d = rom.data[start:start + 0x8000]


def ch(lo):
    if base <= lo < base + 26:
        return chr(65 + lo - base)
    if lo == space:
        return " "
    return None


out = []
i = 0
while i + 1 < len(d):
    hi = d[i + 1]
    c = ch(d[i])
    if c and c != " ":
        j, s, letters = i, "", 0
        while j + 1 < len(d) and d[j + 1] == hi:
            cc = ch(d[j])
            if cc is None:
                break
            s += cc
            letters += cc != " "
            j += 2
        if letters >= minl:
            out.append((i, hi, s.strip(), j - i))
        i = j if j > i else i + 2
    else:
        i += 2
for i, hi, s, n in out:
    print(f"${bank:02X}:{0x8000 + i:04X} attr={hi:02X} len={n // 2:2d}  {s}")
print(len(out), "strings")
