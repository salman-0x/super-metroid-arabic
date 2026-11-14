"""Arabic HUD labels (the ENERGY text and the reserve-tank AUTO text), edited in place in the 2bpp HUD/message tile set at $9A:B200.

Measured (analysis/pause_items16, tests/emu_hud_test.py): the HUD is BG3; its label tiles are plain tiles of the block at $9A:B200
(tile n at $9A:B200 + 16n).  ENERGY = tiles $0B,$0C,$0D,$32 (ink 2 on 1), AUTO = tiles $47,$48 (ink 1 on 3).  The text is drawn with the
condensed 6-row font in rows 1-6 of the 8-row tiles; row 0 / row 7 keep the tile's background.
"""
import hashlib

from . import pack_ar
from .rom import RomError, pc

BANK, BASE = 0x9A, 0xB200
LABELS = {
    "energy": dict(tiles=[0x0B, 0x0C, 0x0D, 0x32], ink=2, bg=1, last_row=3, sha="1d05e41c7e46"),
    "auto": dict(tiles=[0x47, 0x48], ink=1, bg=3, last_row=3, sha="9d14ac7b39f6"),
}


def _tile_at(t):
    return pc(BANK, BASE) + 16 * t


def _encode2(grid):
    out = bytearray()
    for row in grid:
        p0 = p1 = 0
        for x, v in enumerate(row):
            p0 |= (v & 1) << (7 - x)
            p1 |= (v >> 1) << (7 - x)
        out += bytes([p0, p1])
    return bytes(out)


def render(name, text, rom):
    b = LABELS[name]
    tiles = b["tiles"]
    rows = pack_ar.pack(text, micro=True)
    w, full = len(rows[0]), 8 * len(tiles)
    if w > full:
        raise RomError(f"HUD label {name!r}: {text!r} needs {w}px but there are {full}px")
    left = (full - w) // 2
    grid = [[b["bg"]] * full for _ in range(7)] + [[b["last_row"]] * full]          # rows 0-6 background, row 7 as in the original
    for y in range(6):
        for x in range(w):
            if rows[y][x] == "#":
                grid[1 + y][left + x] = b["ink"]
    return [_encode2([r[8 * i:8 * i + 8] for r in grid]) for i in range(len(tiles))]


def build(rom, spec):
    for name, b in LABELS.items():
        raw = b"".join(rom.read(_tile_at(t), 16) for t in b["tiles"])
        if b["sha"] and hashlib.sha1(raw).hexdigest()[:12] != b["sha"]:
            raise RomError(f"HUD label {name!r}: the tiles at $9A:B200 are not the original English art")
    for name, text in spec.items():
        if name not in LABELS:
            raise RomError(f"unknown HUD label {name!r}")
        for t, data in zip(LABELS[name]["tiles"], render(name, text, rom)):
            rom.write(_tile_at(t), data)
    return {"labels": dict(spec)}


def changed_regions(info):
    out = []
    for t in sorted({t for n in info["labels"] for t in LABELS[n]["tiles"]}):
        if out and out[-1][1] == _tile_at(t):
            out[-1] = (out[-1][0], _tile_at(t) + 16)
        else:
            out.append((_tile_at(t), _tile_at(t) + 16))
    return out
