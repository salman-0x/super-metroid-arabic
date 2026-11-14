"""Locate known English words in the ROM regardless of the tile base, by their letter-distance signature.
A string is matched if consecutive characters differ by the same amounts as the word's letters do (A=0..Z=25), either
as 8-bit values (1 byte/char) or as 16-bit words with a constant high byte (1 word/char).
Usage: python tools/find_words.py <rom> WORD [WORD ...]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

rom = Rom.load(sys.argv[1])
d = rom.data
N = len(d)


def sig(word):
    v = [ord(c) - 65 for c in word]
    return [b - a for a, b in zip(v, v[1:])], v[0]


def find8(word):
    s, first = sig(word)
    out = []
    for i in range(N - len(word)):
        ok = True
        for k, dl in enumerate(s):
            if d[i + k + 1] - d[i + k] != dl:
                ok = False
                break
        if ok:
            out.append((i, d[i] - first))
    return out


def find16(word):
    s, first = sig(word)
    out = []
    for i in range(0, N - 2 * len(word)):
        hi = d[i + 1]
        ok = True
        for k, dl in enumerate(s):
            j = i + 2 * k
            if d[j + 3] != hi or d[j + 2] - d[j] != dl:
                ok = False
                break
        if ok:
            out.append((i, d[i] - first, hi))
    return out


for word in sys.argv[2:]:
    w8, w16 = find8(word), find16(word)
    print(f"== {word}: {len(w8)} byte-hits, {len(w16)} word-hits")
    for off, base in w8[:12]:
        ctx = d[max(0, off - 4): off + len(word) + 12]
        print(f"   8bit  {snes(off)} base={base:#04x}  " + " ".join(f"{b:02X}" for b in ctx))
    for off, base, hi in w16[:12]:
        print(f"   16bit {snes(off)} base={base:#04x} attr={hi:02X}")
