"""Detect phrase slots in the five option-mode tilemaps: blank = tile $0F only; a phrase is a run of non-blank words with
gaps of at most one blank word; rows r and r+1 with overlapping spans form a two-row (big) phrase, otherwise a single row.
Prints map, rows, columns, the top/bottom tile ids and the attribute byte. Usage: python tools/option_slots.py <rom> [map]"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc
from smar import sm_lz

SOURCES = [(0x97, 0x8DF4), (0x97, 0x8FCD), (0x97, 0x91C4), (0x97, 0x938D), (0x97, 0x953A)]
rom = Rom.load(sys.argv[1])
only = int(sys.argv[2]) if len(sys.argv) > 2 else None
BLANK = 0x00F


def runs(row):
    out, cur, gap = [], None, 0
    for c, w in enumerate(row):
        if (w & 0x3FF) == BLANK:
            if cur is not None:
                gap += 1
                if gap > 1:
                    out.append((cur, c - gap))
                    cur, gap = None, 0
        else:
            if cur is None:
                cur = c
            gap = 0
    if cur is not None:
        out.append((cur, len(row) - 1 - gap))
    return out


for m, (bank, addr) in enumerate(SOURCES):
    if only is not None and m != only:
        continue
    blob, _ = sm_lz.decompress(rom.data, pc(bank, addr))
    words = struct.unpack("<1024H", blob)
    rows = [words[r * 32:(r + 1) * 32] for r in range(32)]
    print(f"=== map {m}  (blank word values: {sorted({w for w in words if (w & 0x3FF) == BLANK})[:4]})")
    used = set()
    for r in range(31):
        for (a, b) in runs(rows[r]):
            if (r, a) in used:
                continue
            below = [(c0, c1) for c0, c1 in runs(rows[r + 1]) if not (c1 < a or c0 > b)]
            if below:
                c0 = min(a, min(x for x, _ in below)); c1 = max(b, max(y for _, y in below))
                top = [rows[r][c] & 0x3FF for c in range(c0, c1 + 1)]
                bot = [rows[r + 1][c] & 0x3FF for c in range(c0, c1 + 1)]
                attr = sorted({(rows[r][c] >> 8) for c in range(c0, c1 + 1) if (rows[r][c] & 0x3FF) != BLANK})
                print(f"  rows {r:2d}-{r + 1:2d} cols {c0:2d}-{c1:2d} attr={attr}  top {' '.join(f'{t:03X}' for t in top)}")
                print(f"                              bot {' '.join(f'{t:03X}' for t in bot)}")
                used.add((r + 1, a))
                for (x, y) in below:
                    used.add((r + 1, x))
            else:
                top = [rows[r][c] & 0x3FF for c in range(a, b + 1)]
                attr = sorted({(rows[r][c] >> 8) for c in range(a, b + 1) if (rows[r][c] & 0x3FF) != BLANK})
                print(f"  row  {r:2d}     cols {a:2d}-{b:2d} attr={attr}  single {' '.join(f'{t:03X}' for t in top)}")
