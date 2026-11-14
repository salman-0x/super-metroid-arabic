"""Inventory of menu strings: lists of 16-bit tilemap words (tile = $6A + letter, $0F = space) terminated by $FFFF.
Scans the whole ROM; prints each string with its address, attribute, word count and text.
Usage: python tools/menu_strings.py <rom>"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

BASE, SPACE = 0x6A, 0x0F
rom = Rom.load(sys.argv[1])
d = rom.data
N = len(d)


def letter(w):
    t = w & 0x3FF
    if BASE <= t < BASE + 26:
        return chr(65 + t - BASE)
    if t == SPACE:
        return " "
    return None


found = []
i = 0
while i + 1 < N:
    # a string = >=3 consecutive words that decode as letters/spaces with >=3 real letters, followed by FFFF (maybe after
    # non-letter tiles such as punctuation or icon tiles)
    j, text, letters, attrs = i, "", 0, set()
    while j + 1 < N:
        w = struct.unpack_from("<H", d, j)[0]
        if w == 0xFFFF:
            break
        c = letter(w)
        if c is None:
            text += "?" if (w & 0x3FF) else "."   # keep going over odd tiles; flag them
            attrs.add(w >> 10)
        else:
            text += c
            letters += c != " "
            attrs.add(w >> 10)
        j += 2
        if j - i > 120:
            break
    if j + 1 < N and struct.unpack_from("<H", d, j)[0] == 0xFFFF and letters >= 3:
        # walk back to the true start: the first word after a previous FFFF / non-menu word is hard to know; we report
        # the maximal span of decodable words
        found.append((i, j, text, attrs))
        i = j + 2
    else:
        i += 2

# post-filter: keep strings whose text is mostly letters/spaces (avoid random data)
shown = 0
for i, j, text, attrs in found:
    n = (j - i) // 2
    odd = sum(ch in "?." for ch in text)
    if odd > max(2, n // 3):
        continue
    print(f"{snes(i)}  words={n:3d} attr={sorted(attrs)}  {text!r}")
    shown += 1
print(shown, "strings")
