"""Arabic for the OPTION MODE screens (five 32x32 tilemaps, stored compressed).

How the game builds them (verified in the running game by tracing writes to the WRAM staging buffer $7E:3000):
  $82:EC66-ECAA decompress five 2048-byte tilemaps with `JSL $80:B0FF` into $7F:C000/C800/D000/D800/E000, and later
  $82:ECC6 copies the selected one into the BG1 staging buffer $7E:3000.
    map 0 $97:8DF4  OPTION MODE (START GAME / ENGLISH TEXT / JAPANESE TEXT / CONTROLLER ... / SPECIAL ...)
    map 1 $97:8FCD  CONTROLLER SETTING MODE, English labels      map 2 $97:91C4  same, Japanese labels
    map 3 $97:938D  SPECIAL SETTING MODE,  English labels        map 4 $97:953A  same, Japanese labels
We decompress each map, rewrite the phrase "slots" in place (big 16-px phrases are two tile rows, small ones one), recompress
with smar.sm_lz, store the result in free space of bank $83 and repoint the call site's 24-bit source constant.

A slot is a rectangle of words with a literal guard: the expected tile ids of the English phrase.  If the ROM does not hold
exactly those ids the build refuses, so a shifted or different map can never be edited by mistake.
"""
from . import arabic as AR
from . import sm_lz
from .rom import Rom, RomError, pc

MAP_SOURCES = [(0x97, 0x8DF4), (0x97, 0x8FCD), (0x97, 0x91C4), (0x97, 0x938D), (0x97, 0x953A)]
CALL_SITES = [0xEC66, 0xEC77, 0xEC88, 0xEC99, 0xECAA]     # $82:xxxx of  A9 00 bb 85 48 A9 lo hi 85 47  (LDA/STA source pointer)
FREE_BANK, FREE_ADDR = 0x83, 0xAD66                        # trailing 0xFF run of bank $83 in the original ROM (21,146 bytes)
BLANK = 0x000F
ROWS, COLS = 32, 32


def load_map(rom: Rom, i: int):
    """-> (list of 1024 words, compressed length) of the ORIGINAL map i."""
    bank, addr = MAP_SOURCES[i]
    blob, end = sm_lz.decompress(rom.data, pc(bank, addr))
    if len(blob) != 2048:
        raise RomError(f"map {i} decompresses to {len(blob)} bytes, expected 2048")
    words = [blob[2 * k] | (blob[2 * k + 1] << 8) for k in range(1024)]
    return words, end - pc(bank, addr)


def words_to_bytes(words):
    out = bytearray()
    for w in words:
        out += bytes((w & 0xFF, w >> 8))
    return bytes(out)


def check_call_site(rom: Rom, i: int):
    base = pc(0x82, CALL_SITES[i])
    b = rom.read(base, 10)
    bank, addr = MAP_SOURCES[i]
    want = bytes([0xA9, 0x00, bank, 0x85, 0x48, 0xA9, addr & 0xFF, addr >> 8, 0x85, 0x47])
    if b != want:
        raise RomError(f"call site $82:{CALL_SITES[i]:04X} does not load the expected source ${bank:02X}:{addr:04X}")
    if rom.read(base + 10, 4) != bytes([0x22, 0xFF, 0xB0, 0x80]):
        raise RomError(f"call site $82:{CALL_SITES[i]:04X} is not followed by JSL $80:B0FF")


# ------------------------------------------------------------------ slots
def _row(words, r, c0, c1):
    return [words[r * COLS + c] & 0x3FF for c in range(c0, c1 + 1)]


def validate_slot(words, s):
    r, (e0, e1), (c0, c1) = s["row"], s["span"], s["region"]
    if not (0 <= c0 <= e0 <= e1 <= c1 < COLS):
        raise RomError(f"slot {s}: span must lie inside region inside the 32 columns")
    big = s["kind"] == "big"
    if r + (1 if big else 0) >= ROWS:
        raise RomError(f"slot {s}: row out of range")
    expects = [("expect_top", r), ("expect_bottom", r + 1)] if big else [("expect", r)]
    for key, rr in expects:
        got = _row(words, rr, e0, e1)
        want = [int(x, 16) if isinstance(x, str) else x for x in s[key]]
        if got != want:
            raise RomError(f"map {s['map']} row {rr}: expected tile ids {[hex(x) for x in want]} at columns {e0}-{e1}, "
                           f"found {[hex(x) for x in got]}")
        for c in list(range(c0, e0)) + list(range(e1 + 1, c1 + 1)):           # the free part of the region must be blank
            if (words[rr * COLS + c] & 0x3FF) != BLANK:
                raise RomError(f"map {s['map']} row {rr} col {c}: region cell is not blank")


def apply_slot(words, s, small_table, big_cs, big_table):
    """Rewrite slot s in place. big_table: glyph key -> (top, bottom) tile ids; small_table: key -> tile id."""
    validate_slot(words, s)
    r, (e0, e1), (c0, c1) = s["row"], s["span"], s["region"]
    big = s["kind"] == "big"
    non_blank = [words[r * COLS + c] for c in range(e0, e1 + 1) if (words[r * COLS + c] & 0x3FF) != BLANK]
    if not non_blank:
        raise RomError("slot has no non-blank word to take attribute bits from")
    attr = non_blank[0] & 0xFC00
    if big:
        tiles = AR.to_tiles(s["text"], {k: v[0] for k, v in big_table.items()}, big_cs)
        bottom_of = {v[0]: v[1] for v in big_table.values()}
    else:
        tiles = AR.to_tiles(s["text"], small_table, AR.MENU)
        bottom_of = {}
    width = c1 - c0 + 1
    if len(tiles) > width:
        raise RomError(f"{s['text']!r} needs {len(tiles)} columns but the region is {width} wide (map {s['map']} row {r})")
    start = {"left": c0, "right": c1 - len(tiles) + 1, "center": c0 + (width - len(tiles)) // 2}[s.get("align", "left")]
    for c in range(c0, c1 + 1):
        words[r * COLS + c] = BLANK
        if big:
            words[(r + 1) * COLS + c] = BLANK
    for k, t in enumerate(tiles):
        if t == AR.MENU.space:
            continue
        words[r * COLS + start + k] = attr | t
        if big:
            words[(r + 1) * COLS + start + k] = attr | bottom_of[t]


def build_maps(rom: Rom, slots, small_table, big_cs, big_table):
    """Edit the maps the slots belong to, recompress, store in bank $83 and repoint the call sites."""
    by_map = {}
    for s in slots:
        by_map.setdefault(s["map"], []).append(s)
    if set(rom.read(pc(FREE_BANK, FREE_ADDR), 0x10000 - FREE_ADDR)) != {0xFF}:
        raise RomError(f"${FREE_BANK:02X}:{FREE_ADDR:04X} is not free")
    cursor, info = FREE_ADDR, {}
    for m in sorted(by_map):
        check_call_site(rom, m)
        words, old_len = load_map(rom, m)
        for s in by_map[m]:
            apply_slot(words, s, small_table, big_cs, big_table)
        raw = words_to_bytes(words)
        packed = sm_lz.compress(raw)
        if sm_lz.decompress(packed, 0)[0] != raw:
            raise RomError(f"internal error: recompressed map {m} does not round-trip")
        if cursor + len(packed) > 0x10000:
            raise RomError("compressed maps do not fit in the free area of bank $83")
        rom.write(pc(FREE_BANK, cursor), packed)
        site = pc(0x82, CALL_SITES[m])
        rom.write(site + 2, bytes([FREE_BANK]))
        rom.write(site + 6, bytes([cursor & 0xFF, cursor >> 8]))
        info[m] = {"old_compressed": old_len, "new_compressed": len(packed), "at": cursor, "slots": len(by_map[m])}
        cursor += len(packed)
    return info
