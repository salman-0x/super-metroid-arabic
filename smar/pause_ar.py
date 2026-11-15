"""Arabic labels of the pause screens (equipment screen: SAMUS title, SUPPLY, BEAM, SUIT, MISC., BOOTS).

Measured (analysis/game_equip, tests/emu_pause_test.py): the pause screens draw from the raw 4bpp tile set at $B6:8000 (tile n at
$B6:8000 + 32n, DMA'd to VRAM word 0), and each label is a short run of tiles that only its own tilemap cells use (SUPPLY = tiles
$107-$10A, BEAM $F9-$FB, SUIT $F6-$F8, MISC. $1B0-$1B2, BOOTS $A0-$A2, SAMUS title $13A-$13F).  The art is 1 px strokes, ink colour 13
on background colour 4.  So the translation just overwrites the pixels of those tiles in place: no tilemap, pointer or size changes.
"""
import hashlib

from . import menu_ar as M
from . import pack_ar
from .rom import RomError, pc

BANK, BASE = 0xB6, 0x8000
INK, BG = 13, 4
INK_BOX = 4                      # the button labels are drawn in colour 4
# name -> (tiles, sha1 prefix of the original 4bpp bytes of those tiles)
LABELS = {
    "title": ([0x13A, 0x13B, 0x13C, 0x13D, 0x13E, 0x13F], "72024c745a76"),
    "supply": ([0x107, 0x108, 0x109, 0x10A], "b6e500668dfe"),
    "beam": ([0xF9, 0xFA, 0xFB], "dfde9ab7971a"),
    "suit": ([0xF6, 0xF7, 0xF8], "3bfc71e27ca6"),
    "misc": ([0x1B0, 0x1B1, 0x1B2], "e76f7ec5312c"),
    "boots": ([0xA0, 0xA1, 0xA2], "017d21814c65"),
}
BOLD = set()                     # doubling the width smeared the title; 1 px strokes read better


def _tile_at(t):
    return pc(BANK, BASE) + 32 * t


def _bold(rows):
    return ["".join("#" if r[x] == "#" or (x and r[x - 1] == "#") else "." for x in range(len(r))) for r in rows]


def render(name, text):
    """-> list of tile byte strings (one per tile of the label)."""
    tiles = LABELS[name][0]
    rows = pack_ar.pack(text)
    if name in BOLD:
        rows = _bold(rows)
    w, full = len(rows[0]), 8 * len(tiles)
    if w > full:
        raise RomError(f"label {name!r}: {text!r} needs {w}px but the box has {full}px")
    left = (full - w) // 2
    grid = [[INK if (left <= x < left + w and rows[y][x - left] == "#") else BG for x in range(full)] for y in range(8)]
    return [M._encode4([row[8 * i:8 * i + 8] for row in grid]) for i in range(len(tiles))]


# Map-screen buttons: text drawn inside a coloured box of two tile rows.  tiles = row-major grid (cols); rect = interior x0,y0,x1,y1
# (pixels, inclusive) that holds the text; bg = fill colour; the frame and shadow pixels outside the rect stay untouched.
BOXES = {
    "map": dict(tiles=[0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD], cols=5, rect=(1, 4, 37, 11), bg=11,
                sha="34551d4ba9c7"),
    "samus_btn": dict(tiles=[0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x89, 0x8A, 0x8B, 0x8C, 0x8D], cols=5, rect=(1, 4, 37, 11), bg=11,
                      sha="924c9b8584b0"),
    "start": dict(tiles=[0xA5, 0xA6, 0xA7, 0xA8], cols=4, rect=(1, 1, 30, 6), bg=14, sha="e0d018f27b03", micro=True),
    "exit": dict(tiles=[0xB8, 0xB9, 0xBA, 0xBB, 0xC8, 0xC9, 0xCA, 0xCB], cols=4, rect=(4, 5, 28, 11), bg=7, sha="89562d362781", gap=0),
}


def _decode4(b):
    return [[sum((((b[(p // 2) * 16 + 2 * y + (p & 1)]) >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)] for y in range(8)]


def render_box(name, text, rom):
    """-> {tile id: 32 bytes}: the box's tiles with the English letters replaced by the packed Arabic word."""
    b = BOXES[name]
    cols, ids = b["cols"], b["tiles"]
    rows = len(ids) // cols
    grid = [[0] * (8 * cols) for _ in range(8 * rows)]
    for k, t in enumerate(ids):
        px = _decode4(rom.read(_tile_at(t), 32))
        for y in range(8):
            for x in range(8):
                grid[8 * (k // cols) + y][8 * (k % cols) + x] = px[y][x]
    x0, y0, x1, y1 = b["rect"]
    word = pack_ar.pack(text, gap=b.get("gap", 1), micro=b.get("micro", False))
    ys = [y for y in range(len(word)) if "#" in word[y]]
    word = word[min(ys):max(ys) + 1]
    w, h = len(word[0]), len(word)
    if w > x1 - x0 + 1 or h > y1 - y0 + 1:
        raise RomError(f"box {name!r}: {text!r} needs {w}x{h}px but the text area is {x1 - x0 + 1}x{y1 - y0 + 1}px")
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = b["bg"]
    left, top = x0 + (x1 - x0 + 1 - w) // 2, y0 + (y1 - y0 + 1 - h) // 2
    for y in range(h):
        for x in range(w):
            if word[y][x] == "#":
                grid[top + y][left + x] = INK_BOX
    return {t: M._encode4([row[8 * (k % cols):8 * (k % cols) + 8] for row in grid[8 * (k // cols):8 * (k // cols) + 8]])
            for k, t in enumerate(ids)}


# Equipment-screen item names: each name is a strip of tiles (8 px tall, orange background colour 11, ink 10).  "suit" is shared by the
# VARIA and GRAVITY names, so those two are split: the Arabic name is [specific word][درع].  Text is the condensed 6-row font.
STRIPS = {
    "varia": ([0x100, 0x101, 0x102], "770111065ae6"),
    "suit": ([0x103, 0x104, 0x105], "ecdeaa540c34"),
    "gravity": ([0xD0, 0xD1, 0xD2, 0xD3], "53c9d1b54f33"),
    "morph": ([0x120, 0x121, 0x122, 0x123, 0x117, 0x118, 0x10F, 0x11F], "0e8df2e8132f"),
    "bomb": ([0xD5, 0xD6, 0xD7], "b5c3f6d78dd1"),
    "spring": ([0x110, 0x111, 0x112, 0x113, 0x114, 0x115, 0x116], "c7ab0ffc8117"),
    "screw": ([0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6], "ed3d612c1e3f"),
    "charge": ([0xD8, 0xD9, 0xDA, 0xE7], "41aba2312689"),
    "ice": ([0xDB, 0xDC], "c8d6b2f0c704"),
    "wave": ([0xDD, 0xDE, 0xDF], "e8edc57caa82"),
    "spazer": ([0xE8, 0xE9, 0xEA, 0xEB], "36fc2f5ac959"),
    "plasma": ([0xEC, 0xED, 0xEE, 0xEF], "4bbcde51e323"),
    "hijump": ([0x130, 0x131, 0x132, 0x133, 0x134, 0x135, 0x136], "d7c37b42c040"),
    "space": ([0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5], "7871d67e4508"),
    "speed": ([0x124, 0x125, 0x126, 0x127, 0x128, 0x129, 0x12A, 0x12B], "9bbde06687e2"),
}
STRIP_GAP = {"varia": 0, "bomb": 0}          # these two words only fit without the 1 px gap between unconnected letters
STRIP_BG, STRIP_INK = 11, 10


def render_strip(name, text):
    tiles = STRIPS[name][0]
    rows = pack_ar.pack(text, gap=STRIP_GAP.get(name, 1), micro=True)
    w, full = len(rows[0]), 8 * len(tiles)
    if w > full:
        raise RomError(f"item {name!r}: {text!r} needs {w}px but the strip has {full}px")
    left = full - w - min(1, full - w)                  # right-aligned (the script starts on the right), 1 px margin when possible
    grid = [[STRIP_BG] * full for _ in range(8)]
    for y in range(6):                                  # rows 1-6: one blank row above and below
        for x in range(w):
            if rows[y][x] == "#":
                grid[1 + y][left + x] = STRIP_INK
    return [M._encode4([row[8 * i:8 * i + 8] for row in grid]) for i in range(len(tiles))]


# Reserve-tank box of the equipment screen ("MODE [AUTO]" / "RESERVE TANK", BG1 rows 10-11, tiles used nowhere else).  The mode value
# swaps between the AUTO tiles ($156-$159) and the MANUAL tiles ($146-$149), so both are translated.  Each entry: the tiles, the pixel
# columns the text may use (the bracket pixels outside stay), ink/background colours, and how the word sits in that area.
TEXTS = {
    "reserve_label": dict(tiles=[0x119, 0x11A, 0x11B], x=(0, 23), ink=14, align="right", sha="8e38e2ecc7bf"),
    "reserve_auto": dict(tiles=[0x156, 0x157, 0x158, 0x159], x=(2, 29), ink=1, align="center", sha="4847ca78c108"),
    "reserve_manual": dict(tiles=[0x146, 0x147, 0x148, 0x149], x=(2, 29), ink=1, align="center", sha="c1765d5c8a5b"),
    "reserve_tank": dict(tiles=list(range(0x80, 0x87)), x=(0, 55), ink=13, align="right", sha="4fc4eeeb49b7"),
}


def render_text(name, text, rom):
    """-> {tile id: 32 bytes}: the tiles with the text area cleared and the Arabic word (condensed font, 6 rows) drawn in it."""
    b = TEXTS[name]
    ids = b["tiles"]
    grid = [[0] * (8 * len(ids)) for _ in range(8)]
    for k, t in enumerate(ids):
        px = _decode4(rom.read(_tile_at(t), 32))
        for y in range(8):
            for x in range(8):
                grid[y][8 * k + x] = px[y][x]
    x0, x1 = b["x"]
    word = pack_ar.pack(text, gap=1, micro=True)[:6]
    w = len(word[0])
    if w > x1 - x0 + 1:
        raise RomError(f"reserve text {name!r}: {text!r} needs {w}px but the area has {x1 - x0 + 1}px")
    for y in range(8):
        for x in range(x0, x1 + 1):
            grid[y][x] = BG
    left = x1 - w if b["align"] == "right" else x0 + (x1 - x0 + 1 - w) // 2
    left = max(left, x0)                                        # right-aligned with a 1 px margin when it fits
    for y in range(6):
        for x in range(w):
            if word[y][x] == "#":
                grid[1 + y][left + x] = b["ink"]
    return {t: M._encode4([row[8 * k:8 * k + 8] for row in grid]) for k, t in enumerate(ids)}


def build(rom, spec):
    """spec: {"title": "...", "supply": "...", ...}; overwrites the tile pixels in place."""
    for name, (tiles, sha) in LABELS.items():
        raw = b"".join(rom.read(_tile_at(t), 32) for t in tiles)
        if hashlib.sha1(raw).hexdigest()[:12] != sha:
            raise RomError(f"pause label {name!r}: the tiles at $B6:8000 are not the original English art")
    for name, b in BOXES.items():
        raw = b"".join(rom.read(_tile_at(t), 32) for t in b["tiles"])
        if hashlib.sha1(raw).hexdigest()[:12] != b["sha"]:
            raise RomError(f"pause button {name!r}: the tiles at $B6:8000 are not the original English art")
    for name, (tiles, sha) in STRIPS.items():
        raw = b"".join(rom.read(_tile_at(t), 32) for t in tiles)
        if hashlib.sha1(raw).hexdigest()[:12] != sha:
            raise RomError(f"pause item name {name!r}: the tiles at $B6:8000 are not the original English art")
    for name, b in TEXTS.items():
        raw = b"".join(rom.read(_tile_at(t), 32) for t in b["tiles"])
        if hashlib.sha1(raw).hexdigest()[:12] != b["sha"]:
            raise RomError(f"reserve box {name!r}: the tiles at $B6:8000 are not the original English art")
    out = {}
    for name, text in spec.items():
        if name in TEXTS:
            for t, data in render_text(name, text, rom).items():
                rom.write(_tile_at(t), data)
        elif name.startswith("item_"):
            key = name[5:]
            if key not in STRIPS:
                raise RomError(f"unknown pause item {name!r}")
            for t, data in zip(STRIPS[key][0], render_strip(key, text)):
                rom.write(_tile_at(t), data)
        elif name in BOXES:
            for t, data in render_box(name, text, rom).items():
                rom.write(_tile_at(t), data)
        elif name in LABELS:
            for t, data in zip(LABELS[name][0], render(name, text)):
                rom.write(_tile_at(t), data)
        else:
            raise RomError(f"unknown pause label {name!r}")
        out[name] = text
    return {"labels": out}


def changed_regions(info):
    """(start, end) file ranges build() may write, adjacent tiles merged (a diff of two neighbouring tiles is one range)."""
    out = []
    for t in sorted({t for n in info["labels"] for t in (TEXTS[n]["tiles"] if n in TEXTS else STRIPS[n[5:]][0] if n.startswith("item_") else BOXES[n]["tiles"] if n in BOXES else LABELS[n][0])}):
        if out and out[-1][1] == _tile_at(t):
            out[-1] = (out[-1][0], _tile_at(t) + 32)
        else:
            out.append((_tile_at(t), _tile_at(t) + 32))
    return out
