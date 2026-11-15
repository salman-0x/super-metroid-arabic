"""Arabic "PLANET ZEBES" title of the save-load map screen (shown after a file is picked, before the game starts).

Measured (analysis/game_full, Mesen 2): the title is 22 sprites (11 letters, each = a top and a bottom 8x8 tile, 8x16 in all), a spritemap
at $82:CBFB = count word + 5-byte entries `x lo, x hi (bit 0 = x bit 8), y, tile, attr`.  This screen loads its sprite tiles from the second
half of the pause tile set ($B6:C000, tile n at +32n, 4bpp), not from the menu set at $8E:8000.  The 18 English letter tiles of the title sit
there; the pause screens draw no letters from this half, so the Arabic glyph art replaces them in place and the spritemap is rewritten to
the new glyphs, centred where the English title was.
"""
import hashlib
import struct

from . import arabic as A
from . import font_big as FB
from . import menu_ar as M
from .rom import RomError, pc

MAP_AT = (0x82, 0xCBFB)
MAP_ENTRIES = 22
MAP_SHA = "4019e1af5152"                      # first 12 hex digits of sha1 of the original 2 + 22*5 bytes
TILES_AT = (0xB6, 0xC000)
SLOTS = [0x0A, 0x0B, 0x0D, 0x0E, 0x11, 0x1A, 0x1B, 0x1E, 0x25, 0x27, 0x2B, 0x2C, 0x35, 0x37, 0x38, 0x3B, 0x42, 0x52]   # the English title's own tiles
SLOTS_SHA = "82e9ec84169b"      # first 12 hex digits of sha1 of those 18 original tiles, in this order
INK, SHADOW = 14, 13                          # colours the English letters use
ATTR = 0x30                                   # priority 3, palette 0 (as the original entries)
CS = A.Charset(space=0, latin={})
CENTRE_X = 0                                  # the English title spans x -48..+48 around the sprite origin


def _hash(b):
    return hashlib.sha1(b).hexdigest()[:12]


def glyph_tiles(letter, form):
    """-> (top, bottom) 32-byte 4bpp tiles of one 8x16 big-font glyph: ink plus a 1 px shadow on the right/below."""
    rows = FB.glyph16(letter, form)
    ink = {(x, y) for y in range(16) for x in range(8) if rows[y][x] == "#"}
    px = [[INK if (x, y) in ink else (SHADOW if ((x - 1, y) in ink or (x, y - 1) in ink) else 0) for x in range(8)] for y in range(16)]
    return M._encode4(px[:8]), M._encode4(px[8:])


def layout(text):
    """-> list of units, visual left to right: a glyph key or None (space)."""
    units = A.shape(text, CS)
    seq = [u[1] if u[0] == "R" else None for u in units]
    return seq[::-1]


def entries(units, tile_of):
    """Spritemap entries (bottom then top per glyph, as the original); x centred on CENTRE_X."""
    n = len(units)
    left = CENTRE_X - 4 * n
    out = []
    for i, key in enumerate(units):
        if key is None:
            continue
        top, bottom = tile_of[key]
        x = left + 8 * i
        for tile, y in ((bottom, 0x00), (top, 0xF8)):
            if tile is None:                          # empty half (e.g. the top of a letter with dots only below): no sprite
                continue
            out.append(bytes([x & 0xFF, (x >> 8) & 1, y, tile & 0xFF, ATTR | (tile >> 8)]))
    return out


def build(rom, spec):
    """spec: {"title": "..."}; rewrites the title spritemap and replaces the English title letter tiles with Arabic glyphs."""
    at = pc(*MAP_AT)
    orig = rom.read(at, 2 + 5 * MAP_ENTRIES)
    if struct.unpack_from("<H", orig)[0] != MAP_ENTRIES or _hash(orig) != MAP_SHA:
        raise RomError("unexpected PLANET ZEBES spritemap at $82:CBFB")
    text = spec["title"]
    units = layout(text)
    keys = sorted({k for k in units if k is not None}, key=lambda k: (k[0], A.F.FORMS.index(k[1])))
    halves, tile_of, slot_of_half = [], {}, {}
    for k in keys:
        top, bottom = glyph_tiles(*k)
        pair = []
        for half in (top, bottom):
            if not any(half):
                pair.append(None)
                continue
            if half not in slot_of_half:
                if len(slot_of_half) >= len(SLOTS):
                    raise RomError(f"{text!r} needs more than the {len(SLOTS)} title tiles")
                slot_of_half[half] = SLOTS[len(slot_of_half)]
            pair.append(slot_of_half[half])
        tile_of[k] = tuple(pair)
    ents = entries(units, tile_of)
    if len(ents) > MAP_ENTRIES:
        raise RomError(f"{text!r} needs {len(ents)} sprites, the spritemap has room for {MAP_ENTRIES}")
    if _hash(b"".join(rom.read(pc(*TILES_AT) + 32 * t, 32) for t in SLOTS)) != SLOTS_SHA:
        raise RomError("the title letter tiles at $8E:8000 are not the original English art")
    for half, slot in slot_of_half.items():
        rom.write(pc(*TILES_AT) + 32 * slot, half)
    rom.write(at, struct.pack("<H", len(ents)) + b"".join(ents))
    return {"title": text, "sprites": len(ents), "tiles": sorted(slot_of_half.values())}


def changed_regions(info):
    out = [(pc(*MAP_AT), pc(*MAP_AT) + 2 + 5 * info["sprites"])]
    for t in sorted(info["tiles"]):                               # adjacent tiles merge into one range
        a = pc(*TILES_AT) + 32 * t
        if len(out) > 1 and out[-1][1] == a:
            out[-1] = (out[-1][0], a + 32)
        else:
            out.append((a, a + 32))
    return out

