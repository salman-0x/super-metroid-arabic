"""Dump the $FFFF-terminated word lists in a bank-$81 address range, showing each word's tile and attribute and a decode of
the big (16-px) font where possible. Usage: python tools/big_strings.py <rom> <lo_hex> <hi_hex>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
# big font (16 px): top tile ids; the bottom half is top + 0x10.  Known from the rendered sheet + the SAMUS/DATA words
BIG = {0x0A: "A", 0x0B: "B", 0x0C: "C", 0x0D: "D", 0x0E: "E", 0x0F: "F", 0x21: "H", 0x22: "I", 0x23: "J", 0x24: "K",
       0x25: "L", 0x26: "M", 0x27: "N", 0x2B: "S", 0x2C: "T", 0x2D: "U", 0x2E: "V", 0x2F: "W", 0x40: "X", 0x41: "Y",
       0x42: "Z", 0x00: "O", 0x01: "1", 0x02: "2", 0x03: "3", 0x04: "4", 0x05: "5", 0x06: "6", 0x07: "7", 0x08: "8",
       0x09: "9", 0x4E: "-"}
BIG_BOTTOM = {k + 0x10: v for k, v in BIG.items()}
a = lo
while a < hi:
    start = a
    words = []
    while a < hi:
        w = struct.unpack_from("<H", rom.data, pc(0x81, a))[0]
        a += 2
        if w == 0xFFFF:
            break
        words.append(w)
    dec = "".join(BIG.get(w & 0x3FF, "?") if (w & 0x3FF) != 0x0F else " " for w in words)
    decb = "".join(BIG_BOTTOM.get(w & 0x3FF, "?") if (w & 0x3FF) != 0x1F else " " for w in words)
    print(f"$81:{start:04X}-{a - 1:04X} ({len(words):2d}w)  top:|{dec}|  bottom:|{decb}|")
    print("      " + " ".join(f"{w:04X}" for w in words))
