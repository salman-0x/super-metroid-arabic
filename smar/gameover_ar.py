"""Arabic GAME OVER screen (game state $1A).

How the screen is built (measured in the running game, see tests/emu_gameover_test.py):
  * $81:91B7-$9233 fills the BG1 tilemap buffer $7E:3600 with blanks, then draws five strings with `LDY #string / LDX #offset /
    JSR $B3E2`.  $B3E2 copies words ($FFFE = next tile row at the same start column, $FFFF = end) to $7E:3600 + X, X = 2*(32*row+col).
  * The strings are the menu font's words ($81:92DC GAME OVER (big, two rows), $9304 FIND THE METROID LARVA!, $9334 TRY AGAIN ?,
    $934C YES + (RETURN TO GAME), $93A0 NO + (GO TO TITLE)).  Their lengths are fixed in ROM, so we write the Arabic strings to
    free space in bank $81 and change only the five LDY/LDX operands.
  * The tile art is the one the file-select menu already uses (menu_ar allocates the Arabic menu tiles in the relocated tile set).
"""
import struct

from . import arabic as AR
from .rom import RomError, pc

BANK = 0x81
FREE_AT, FREE_LEN = 0xEF1A, 0x0400                  # first part of the free run $81:EF1A-$FF00 (slot_ar uses the rest)
SPACE = 0x00F
SMALL_CS = AR.Charset(space=SPACE, latin=AR.MENU.latin,
                      punct={**AR.MENU.punct, "(": AR.MENU.punct[")"], ")": AR.MENU.punct["("]})   # RTL: brackets mirror
BIG_CS = AR.Charset(space=SPACE, latin={}, punct={})
RIGHT_LIMIT = 31                                    # last usable tile column

# name -> (LDY operand address, LDX operand address, original string address, original X, kind, original words)
ENTRIES = {
    "title": (0x9206, 0x9209, 0x92DC, 0x0156, "big",
              "000C 000A 0026 000E 000F 0000 002D 000E 000D FFFE 0030 001A 0036 001E 000F 0010 003E 001E 003A"),
    "find": (0x920F, 0x9212, 0x9304, 0x038A, "small",
             "006F 0072 0077 006D 000F 007D 0071 006E 000F 0076 006E 007D 007B 0078 0072 006D 000F 0075 006A 007B 007F 006A 0084"),
    "again": (0x9218, 0x921B, 0x9334, 0x0414, "small", "007D 007B 0082 000F 006A 0070 006A 0072 0077 000F 0085"),
    "yes": (0x9221, 0x9224, 0x934C, 0x04CE, "combo",
            "0041 000E 002B " + "000F " * 17 + "FFFE 0017 001E 003B 000F 008A 007B 006E 007D 007E 007B 0077 000F 007D 0078 000F "
            "0070 006A 0076 006E 008B"),
    "no": (0x922A, 0x922D, 0x93A0, 0x05CE, "combo",
           "0027 000F 0000 " + "000F " * 14 + "FFFE 0037 000F 0010 000F 008A 0070 0078 000F 007D 0078 000F 007D 0072 007D 0075 "
           "006E 008B"),
}
TEXT_KEYS = {"title": "title", "find": "find", "again": "again", "yes": ("yes_big", "yes_small"), "no": ("no_big", "no_small")}


def small_keys(spec):
    keys = set()
    for t in (spec["find"], spec["again"], spec["yes_small"], spec["no_small"]):
        keys |= AR.glyph_keys(t, SMALL_CS)
    return keys


def big_keys(spec):
    keys = set()
    for t in (spec["title"], spec["yes_big"], spec["no_big"]):
        keys |= AR.glyph_keys(t, BIG_CS)
    return keys


def _read_words(rom, addr):
    out = []
    while True:
        w = struct.unpack_from("<H", rom.data, pc(BANK, addr))[0]
        if w == 0xFFFF:
            return out
        out.append(w)
        addr += 2
        if len(out) > 100:
            raise RomError(f"string at $81:{addr:04X} has no terminator")


def _big_word(text, big_table):
    """-> (top words, bottom words) of a big word, visual left-to-right."""
    tiles = AR.to_tiles(text, {k: v[0] for k, v in big_table.items()}, BIG_CS)
    bottom_of = {v[0]: v[1] for v in big_table.values()}
    return [t for t in tiles], [bottom_of.get(t, SPACE) if t != SPACE else SPACE for t in tiles]


def compose(name, spec, table, big_table):
    """-> (words incl. terminator, tile row width, kind). The words are placed by `place`."""
    kind = ENTRIES[name][4]
    if kind == "small":
        words = AR.to_tiles(spec[name], table, SMALL_CS)
        return words + [0xFFFF], len(words)
    if kind == "big":
        top, bottom = _big_word(spec[name], big_table)
        return top + [0xFFFE] + bottom + [0xFFFF], len(top)
    big_text, small_text = spec[name + "_big"], spec[name + "_small"]
    top, bottom = _big_word(big_text, big_table)
    small = AR.to_tiles(small_text, table, SMALL_CS)
    gap = [SPACE]
    top_row = top + gap + [SPACE] * len(small)
    bottom_row = bottom + gap + small
    return top_row + [0xFFFE] + bottom_row + [0xFFFF], len(top_row)


def column(name, width):
    """First tile column: the big words of YES/NO keep the original column (the selection cursor sprite sits left of it);
    the other strings are centred on the 32-column screen."""
    kind, orig_x = ENTRIES[name][4], ENTRIES[name][3]
    orig_col = (orig_x % 0x40) // 2
    if kind == "combo":
        col = orig_col
    else:
        col = (32 - width) // 2
    if col < 0 or col + width - 1 > RIGHT_LIMIT:
        raise RomError(f"game-over string {name!r} ({width} columns) does not fit the screen")
    return col


def build(rom, spec, table, big_table):
    """Write the Arabic strings to free space and repoint the five LDY/LDX pairs. Returns a report."""
    for name, (ldy, ldx, addr, x, kind, hexwords) in ENTRIES.items():
        if _read_words(rom, addr) != [int(w, 16) for w in hexwords.split()]:
            raise RomError(f"$81:{addr:04X} does not hold the expected original game-over string {name!r}")
        want = bytes([0xA0, addr & 255, addr >> 8, 0xA2, x & 255, x >> 8])
        if rom.read(pc(BANK, ldy), 6) != want:
            raise RomError(f"unexpected LDY/LDX operands for {name!r} at $81:{ldy:04X}")
    area = rom.read(pc(BANK, FREE_AT), FREE_LEN)
    if area != b"\xFF" * FREE_LEN:
        raise RomError("the free run at $81:EF1A is not free")
    blob, at, placed = bytearray(), FREE_AT, {}
    for name, (ldy, ldx, addr, x, kind, _) in ENTRIES.items():
        words, width = compose(name, spec, table, big_table)
        col = column(name, width)
        row = x // 0x40
        new_x = row * 0x40 + 2 * col
        placed[name] = (at + len(blob), new_x, width)
        blob += struct.pack(f"<{len(words)}H", *words)
    if len(blob) > FREE_LEN:
        raise RomError("the game-over strings do not fit the free run")
    rom.write(pc(BANK, FREE_AT), bytes(blob))
    for name, (ldy, ldx, *_rest) in ENTRIES.items():
        ptr, new_x, _ = placed[name]
        rom.write(pc(BANK, ldy + 1), struct.pack("<H", ptr))
        rom.write(pc(BANK, ldx + 1), struct.pack("<H", new_x))
    return {"bytes": len(blob), "placed": placed}


def changed_regions(info):
    out = [(pc(BANK, FREE_AT), pc(BANK, FREE_AT) + info["bytes"])]
    for ldy, ldx, *_ in ENTRIES.values():
        out += [(pc(BANK, ldy + 1), pc(BANK, ldy + 1) + 2), (pc(BANK, ldx + 1), pc(BANK, ldx + 1) + 2)]
    return out
