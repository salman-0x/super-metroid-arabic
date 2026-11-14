"""Show the raw words of every file-select string (bank $81 $B4A0-$B730 and $9300-$93FF) so non-letter tiles
(icons, button letters) inside the dialogs are visible. Usage: python tools/raw_strings.py <rom>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])


def show(lo, hi):
    a = lo
    while a < hi:
        words = []
        start = a
        while True:
            w = struct.unpack_from("<H", rom.data, pc(0x81, a))[0]
            a += 2
            if w == 0xFFFF:
                break
            words.append(w)
            if a >= hi:
                break
        dec = "".join(chr(65 + (w & 0x3FF) - 0x6A) if 0x6A <= (w & 0x3FF) < 0x84 else (" " if (w & 0x3FF) == 0x0F else "#")
                      for w in words)
        print(f"$81:{start:04X}-{a - 1:04X} ({len(words):2d} words, +FFFF)  |{dec}|")
        print("      " + " ".join(f"{w:04X}" for w in words))


print("== file select dialogs"); show(0xB4A0, 0xB720)
print("== game over menu"); show(0x92F0, 0x93F0)
