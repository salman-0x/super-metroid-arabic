"""Arabic area names on the pause map screen ($82:9670 table of tile words, drawn with the 8x8 letter tiles $30-$49 of the pause tile set).

Measured (analysis/game_equip, analysis/pause_items16): each name is a run of words `attr, tile` (little endian: low byte attribute $28/$38,
high byte tile id) = one letter tile per word, A-Z = tiles $30-$49.  Those 26 tiles are used by nothing else on the pause screens (only the title
bar of the map screen), plus the unused zero tiles $0E, $0F, $4E.  We write the Arabic names (condensed font, 6 rows) into a pool of 29 tiles
and replace each English name's words, centred on the same position, with the Arabic tile words (blanks elsewhere).
"""
import math
import struct

from . import menu_ar as M
from . import pack_ar
from .rom import RomError, pc

BANK, TABLE, TABLE_END = 0x82, 0x9670, 0x9718
POOL = list(range(0x30, 0x4A)) + [0x0E, 0x0F, 0x4E]
ENGLISH = ["CRATERIA", "BRINSTAR", "NORFAIR", "WRECKED SHIP", "MARIDIA", "TOURIAN", "COLONY"]
ATTR, BLANK = 0x38, 0x0128
INK, BG = 13, 4
TARGET = {"MARIDIA": 3}                 # one name needs the tighter glyph width to fit the tile pool


def _words(rom):
    return [struct.unpack_from("<H", rom.data, pc(BANK, a))[0] for a in range(TABLE, TABLE_END, 2)]


def spans(rom):
    """[(first word index, last word index, text)] of the English names in the table (a single blank inside a name stays inside it)."""
    ws, out, i = _words(rom), [], 0
    letter = lambda w: 0x30 <= (w >> 8) <= 0x49                     # noqa: E731
    while i < len(ws):
        if letter(ws[i]):
            j = i
            while j + 1 < len(ws) and (letter(ws[j + 1]) or ((ws[j + 1] >> 8) == 1 and j + 2 < len(ws) and letter(ws[j + 2]))):
                j += 1
            out.append((i, j, "".join(chr(65 + (ws[k] >> 8) - 0x30) if letter(ws[k]) else " " for k in range(i, j + 1))))
            i = j + 1
        else:
            i += 1
    return out


def render(text, key):
    rows = pack_ar.pack(text, gap=0, micro=True, target=TARGET.get(key, 4))
    w = len(rows[0])
    n = math.ceil(w / 8)
    left = (8 * n - w) // 2
    grid = [[BG] * (8 * n) for _ in range(8)]
    for y in range(6):
        for x in range(w):
            if rows[y][x] == "#":
                grid[1 + y][left + x] = INK
    return [M._encode4([r[8 * i:8 * i + 8] for r in grid]) for i in range(n)]


def build(rom, spec):
    found = spans(rom)
    if [t for _, _, t in found] != ENGLISH:
        raise RomError(f"unexpected area-name table at $82:9670: {[t for _, _, t in found]}")
    for t in (0x0E, 0x0F, 0x4E):
        if any(rom.read(pc(0xB6, 0x8000) + 32 * t, 32)):
            raise RomError(f"pause tile ${t:02X} is not blank")
    arts = {k: render(spec[k], k) for k in ENGLISH}
    need = sum(len(v) for v in arts.values())
    if need > len(POOL):
        raise RomError(f"the area names need {need} tiles but only {len(POOL)} are free")
    words = _words(rom)
    pool = iter(POOL)
    used = []
    for (a, b, text), key in zip(found, ENGLISH):
        ids = []
        for data in arts[key]:
            t = next(pool)
            rom.write(pc(0xB6, 0x8000) + 32 * t, data)
            ids.append(t)
            used.append(t)
        m = len(ids)
        start = a + ((b - a + 1) - m) // 2
        if m > b - a + 1:
            raise RomError(f"{key}: Arabic name is longer than the English one")
        for k in range(a, b + 1):
            words[k] = BLANK
        for k, t in enumerate(ids):
            words[start + k] = (t << 8) | ATTR
    rom.write(pc(BANK, TABLE), struct.pack(f"<{len(words)}H", *words))
    return {"tiles": sorted(used), "names": dict(spec)}


def changed_regions(info):
    out = [(pc(BANK, TABLE), pc(BANK, TABLE_END))]
    for t in info["tiles"]:
        a = pc(0xB6, 0x8000) + 32 * t
        out.append((a, a + 32))
    return out
