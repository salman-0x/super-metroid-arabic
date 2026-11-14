"""Arabic "(SAMUS _)" dialogs of the file-select screen: COPY (SAMUS _) TO WHERE?, COPY (SAMUS _) TO (SAMUS _), CLEAR (SAMUS _).

How the original draws them (measured, see tests/emu_slot_test.py):
  * the code draws the string with `LDY #string / LDX #offset / JSR $B3E2` into the BG1 tilemap buffer $7E:3600, then writes the file letter
    on top of a placeholder cell:  LDA $19B7 (source file 0-2) / CLC / ADC #$206A / STA $7E:375C   (and $19B9 -> $7E:3776, $3760, $376A
    in the other two dialogs).  $206A is the menu font's letter A (palette bits $2000), so the letter is A, B or C.
  * for Arabic we write new strings to free space in bank $81, repoint the LDY/LDX operands, move each placeholder (the STA long operand)
    to the cell we left blank for it, and change the ADC operand to the first of three consecutive Arabic letter tiles (أ ب ج) that
    menu_ar appends to the tile set.
"""
import struct

from . import arabic as AR
from . import font_ar as F
from .rom import RomError, pc

BANK = 0x81
FREE_AT, FREE_LEN = 0xF31A, 0x0BE6                  # second half of the free run $81:EF1A-$FF00 (game over uses the first part)
SPACE = 0x00F
ATTR = 0x2000
BUFFER = 0x3600
PLACEHOLDER = 0x3FE                                  # tile id that never reaches the ROM: marks the cell of the file letter
SLOT_CS = AR.Charset(space=SPACE, latin=AR.MENU.latin,
                     punct={**AR.MENU.punct, "(": AR.MENU.punct[")"], ")": AR.MENU.punct["("], "#": PLACEHOLDER})
LETTER_KEYS = [("أ", "I"), ("ب", "I"), ("ج", "I")]   # files A, B, C
ORIG_ADC = 0x206A

# name -> LDY opcode address, LDX opcode address, original string address, original X, original words, [(ADC opcode, STA opcode, old offset)]
ENTRIES = {
    "copy_from": (0x97A8, 0x97AB, 0xB596, 0x0148,
                  "206C 2078 2079 2082 200F 208A 207C 206A 2076 207E 207C 200F 200F 208B 200F 207D 2078 200F 2080 2071 206E 207B 206E 2085",
                  [(0x97B8, 0x97BB, 0x3760)]),
    "copy_both": (0x98BB, 0x98BE, 0xB5C8, 0x0144,
                  "206C 2078 2079 2082 200F 208A 207C 206A 2076 207E 207C 200F 200F 208B 200F 207D 2078 200F 208A 207C 206A 2076 "
                  "207E 207C 200F 200F 208B 2088",
                  [(0x98CB, 0x98CE, 0x375C), (0x98D6, 0x98D9, 0x3776)]),
    "clear": (0x9C0F, 0x9C12, 0xB69A, 0x0140,
              "000F 000F 000F 000F 000F 000F 000F 000F 006C 0075 006E 006A 007B 000F 008A 007C 006A 0076 007E 007C 000F 006A 008B "
              "0088 000F 000F 000F 000F 000F 000F 000F",
              [(0x9C1F, 0x9C22, 0x376A)]),
}


def small_keys(spec):
    keys = set()
    for name in ENTRIES:
        keys |= AR.glyph_keys(spec[name], SLOT_CS)
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


def compose(name, text, table):
    """-> (words incl. terminator, first column, [placeholder cell column per file letter]).
    The string covers at least the cells of the original (padded with blanks) so nothing of an earlier screen shows through."""
    _, _, _, x, hexwords, _ = ENTRIES[name]
    orig_col, orig_n = (x % 0x40) // 2, len(hexwords.split())
    tiles = AR.to_tiles(text, table, SLOT_CS)
    n = len(tiles)
    col = (32 - n) // 2
    if col < 0:
        raise RomError(f"dialog {name!r} needs {n} columns")
    start, end = min(col, orig_col), max(col + n, orig_col + orig_n)
    cells = [SPACE] * (end - start)
    holes = []
    for k, t in enumerate(tiles):
        if t == PLACEHOLDER:
            holes.append(col + k)
        else:
            cells[col - start + k] = t
    words = [ATTR | t for t in cells]
    return words + [0xFFFF], start, holes


def build(rom, spec, table, slot_base):
    """Write the three Arabic dialogs and patch the code. `slot_base`: tile id of the Arabic letter for file A (B, C follow)."""
    for name, (ldy, ldx, addr, x, hexwords, sites) in ENTRIES.items():
        if _read_words(rom, addr) != [int(w, 16) for w in hexwords.split()]:
            raise RomError(f"$81:{addr:04X} does not hold the expected original dialog {name!r}")
        if rom.read(pc(BANK, ldy), 6) != bytes([0xA0, addr & 255, addr >> 8, 0xA2, x & 255, x >> 8]):
            raise RomError(f"unexpected LDY/LDX operands for {name!r} at $81:{ldy:04X}")
        for adc, sta, off in sites:
            if rom.read(pc(BANK, adc), 7) != bytes([0x69, 0x6A, 0x20, 0x8F, off & 255, off >> 8, 0x7E]):
                raise RomError(f"unexpected ADC/STA at $81:{adc:04X} for {name!r}")
    if rom.read(pc(BANK, FREE_AT), FREE_LEN) != b"\xFF" * FREE_LEN:
        raise RomError("the free run at $81:F31A is not free")
    blob, placed = bytearray(), {}
    for name, (ldy, ldx, addr, x, hexwords, sites) in ENTRIES.items():
        words, start, holes = compose(name, spec[name], table)
        if len(holes) != len(sites):
            raise RomError(f"dialog {name!r} needs {len(sites)} '#' placeholders, has {len(holes)}")
        at = FREE_AT + len(blob)
        blob += struct.pack(f"<{len(words)}H", *words)
        row = x // 0x40
        placed[name] = {"ptr": at, "x": row * 0x40 + 2 * start, "holes": [BUFFER + 2 * (row * 32 + c) for c in holes]}
    if len(blob) > FREE_LEN:
        raise RomError("the dialogs do not fit the free run")
    rom.write(pc(BANK, FREE_AT), bytes(blob))
    for name, (ldy, ldx, addr, x, hexwords, sites) in ENTRIES.items():
        p = placed[name]
        rom.write(pc(BANK, ldy + 1), struct.pack("<H", p["ptr"]))
        rom.write(pc(BANK, ldx + 1), struct.pack("<H", p["x"]))
        for (adc, sta, off), hole in zip(sites, p["holes"]):
            rom.write(pc(BANK, adc + 1), struct.pack("<H", ATTR | slot_base))
            rom.write(pc(BANK, sta + 1), struct.pack("<H", hole))
    return {"bytes": len(blob), "placed": placed, "slot_base": slot_base}


def letter_tiles():
    """The three letter glyph rows (small menu style) in the order of the files A, B, C."""
    return [F.glyph_pixels(*k) for k in LETTER_KEYS]


def changed_regions(info):
    out = [(pc(BANK, FREE_AT), pc(BANK, FREE_AT) + info["bytes"])]
    for name, (ldy, ldx, _a, _x, _h, sites) in ENTRIES.items():
        out += [(pc(BANK, ldy + 1), pc(BANK, ldy + 1) + 2), (pc(BANK, ldx + 1), pc(BANK, ldx + 1) + 2)]
        for adc, sta, _off in sites:
            out += [(pc(BANK, adc + 1), pc(BANK, adc + 1) + 2), (pc(BANK, sta + 1), pc(BANK, sta + 1) + 2)]
    return out
